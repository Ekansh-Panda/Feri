"""
Agent Runtime — process lifecycle manager for JARVIS sub-agents.

Spawns, monitors, and terminates agent processes defined in `agents/`.
Enforces CPU/memory limits via `resource` (POSIX) and tracks PIDs.
"""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:
    import resource as posix_resource
except ImportError:
    posix_resource = None  # type: ignore[assignment]

try:
    import psutil  # type: ignore[import-untyped]
except ImportError:
    psutil = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"


@dataclass
class AgentRecord:
    """Track a single spawned agent process."""

    agent_id: str
    agent_type: str
    task: str
    pid: int
    started_at: float
    cmd: List[str]
    process: subprocess.Popen
    cpu_limit: Optional[int] = None
    mem_limit_mb: Optional[int] = None
    metadata: Dict[str, str] = field(default_factory=dict)


class AgentRuntime:
    """Manage subprocess lifecycle for JARVIS agents."""

    def __init__(
        self,
        agents_dir: Optional[Path] = None,
        default_cpu_pct: int = 50,
        default_mem_mb: int = 512,
    ) -> None:
        self.agents_dir: Path = Path(agents_dir) if agents_dir else AGENTS_DIR
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self._agents: Dict[str, AgentRecord] = {}
        self._lock = threading.RLock()
        self.default_cpu_pct = default_cpu_pct
        self.default_mem_mb = default_mem_mb

    def _agent_script_path(self, agent_type: str) -> Path:
        """Resolve script for an agent type, accepting several naming conventions."""
        candidates = [
            self.agents_dir / f"{agent_type}.py",
            self.agents_dir / agent_type / "__main__.py",
            self.agents_dir / f"{agent_type}.sh",
        ]
        for c in candidates:
            if c.exists():
                return c
        raise FileNotFoundError(
            f"No agent script found for type={agent_type!r} in {self.agents_dir}"
        )

    def _preexec_limits(self, cpu_pct: Optional[int], mem_mb: Optional[int]):
        """Return a preexec_fn that applies POSIX resource limits to the child."""
        if posix_resource is None:
            return None

        cpu = cpu_pct or self.default_cpu_pct
        mem = mem_mb or self.default_mem_mb

        def _apply() -> None:
            try:
                # CPU seconds; falls back to RLIMIT_CPU; 50% of one CPU-second per wall-sec
                posix_resource.setrlimit(
                    posix_resource.RLIMIT_CPU,
                    (cpu, cpu * 2),
                )
                # Address-space limit in bytes
                posix_resource.setrlimit(
                    posix_resource.RLIMIT_AS,
                    (mem * 1024 * 1024, mem * 1024 * 1024),
                )
                # Make the child its own process group so we can signal the tree
                os.setsid()
            except Exception:
                pass

        return _apply

    def spawn_agent(
        self,
        agent_type: str,
        task: str,
        *,
        extra_args: Optional[List[str]] = None,
        cwd: Optional[Path] = None,
        cpu_limit: Optional[int] = None,
        mem_limit_mb: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> str:
        """Spawn an agent subprocess. Returns the agent_id."""
        script = self._agent_script_path(agent_type)
        agent_id = f"{agent_type}-{uuid.uuid4().hex[:8]}"

        cmd = ["python3", str(script), "--task", task]
        if extra_args:
            cmd.extend(extra_args)

        work_dir = str(cwd) if cwd else str(REPO_ROOT)

        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        process_env["JARVIS_AGENT_ID"] = agent_id

        proc = subprocess.Popen(
            cmd,
            cwd=work_dir,
            env=process_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            preexec_fn=self._preexec_limits(cpu_limit, mem_limit_mb),
        )

        record = AgentRecord(
            agent_id=agent_id,
            agent_type=agent_type,
            task=task,
            pid=proc.pid,
            started_at=time.time(),
            cmd=cmd,
            process=proc,
            cpu_limit=cpu_limit or self.default_cpu_pct,
            mem_limit_mb=mem_limit_mb or self.default_mem_mb,
        )
        with self._lock:
            self._agents[agent_id] = record
        return agent_id

    def kill_agent(self, agent_id: str, timeout: float = 5.0) -> bool:
        """Terminate an agent gracefully, then forcefully."""
        with self._lock:
            rec = self._agents.get(agent_id)
            if not rec:
                return False
            proc = rec.process
        try:
            # Try to kill the whole process group first
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    proc.kill()
                try:
                    proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            with self._lock:
                self._agents.pop(agent_id, None)
        return True

    def list_active_agents(self) -> List[Dict[str, object]]:
        """Return a snapshot of running agents, with PIDs and uptime."""
        snapshot: List[Dict[str, object]] = []
        now = time.time()
        with self._lock:
            dead: List[str] = []
            for aid, rec in self._agents.items():
                alive = rec.process.poll() is None
                if not alive:
                    dead.append(aid)
                    continue
                snapshot.append(
                    {
                        "agent_id": aid,
                        "agent_type": rec.agent_type,
                        "pid": rec.pid,
                        "uptime_s": round(now - rec.started_at, 2),
                        "task": rec.task[:120],
                        "cpu_limit": rec.cpu_limit,
                        "mem_limit_mb": rec.mem_limit_mb,
                    }
                )
            for aid in dead:
                self._agents.pop(aid, None)
        return snapshot

    def health_check(self, agent_id: str) -> Dict[str, object]:
        """Return health status for a given agent_id."""
        with self._lock:
            rec = self._agents.get(agent_id)
        if not rec:
            return {"alive": False, "reason": "unknown_agent"}
        exit_code = rec.process.poll()
        if exit_code is not None:
            return {"alive": False, "reason": "exited", "exit_code": exit_code}
        info: Dict[str, object] = {
            "alive": True,
            "pid": rec.pid,
            "uptime_s": round(time.time() - rec.started_at, 2),
            "agent_type": rec.agent_type,
        }
        if psutil is not None:
            try:
                p = psutil.Process(rec.pid)
                with p.oneshot():
                    info["cpu_pct"] = p.cpu_percent(interval=0.05)
                    info["rss_mb"] = round(p.memory_info().rss / (1024 * 1024), 2)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                info["alive"] = False
                info["reason"] = "no_such_process"
        return info

    def kill_all(self) -> int:
        """Kill every tracked agent. Returns count terminated."""
        ids = list(self._agents.keys())
        for aid in ids:
            self.kill_agent(aid)
        return len(ids)


__all__ = ["AgentRuntime", "AgentRecord"]