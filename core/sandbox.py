"""
Sandbox — isolated command execution.

Prefers Docker (always available on modern Arch), falls back to nsjail if
present. Enforces timeouts and resource limits via Docker flags; nsjail
relies on its own seccomp/cgroup config.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class SandboxResult:
    """Outcome of a sandboxed execution."""

    ok: bool
    stdout: str
    stderr: str
    exit_code: int
    duration_s: float
    backend: str
    timed_out: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class Sandbox:
    """Run shell commands inside Docker or nsjail with hard limits."""

    def __init__(self) -> None:
        self._docker = shutil.which("docker")
        self._nsjail = shutil.which("nsjail")
        self._default_network = "none"  # we always disable network by default

    # ---- Docker backend ----

    def execute(
        self,
        command: str,
        image: str = "python:3.12-slim",
        timeout: int = 30,
        *,
        cpu_quota_pct: int = 50,
        memory_mb: int = 256,
        mounts: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> SandboxResult:
        """Run `command` inside `image` via Docker with resource limits."""
        if not self._docker:
            return SandboxResult(
                ok=False,
                stdout="",
                stderr="docker binary not found on PATH",
                exit_code=127,
                duration_s=0.0,
                backend="docker",
            )

        cpu_quota = max(10000, int(cpu_quota_pct * 1000))  # microseconds per 100ms period
        mem_bytes = max(64, int(memory_mb)) * 1024 * 1024

        cmd: List[str] = [
            self._docker,
            "run",
            "--rm",
            "-i",
            "--network",
            self._default_network,
            "--cpus",
            f"{max(0.05, cpu_quota_pct / 100):.2f}",
            "--memory",
            f"{mem_bytes}",
            "--pids-limit",
            "128",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,size=64m",
        ]

        for m in mounts or []:
            cmd += ["-v", m]

        if env:
            for k, v in env.items():
                cmd += ["-e", f"{k}={v}"]

        cmd += [image, "bash", "-lc", command]

        return self._run(cmd, timeout=timeout, backend="docker")

    # ---- nsjail backend ----

    def execute_nsjail(self, command: str, timeout: int = 30) -> SandboxResult:
        """Run `command` inside nsjail if available, else error result."""
        if not self._nsjail:
            return SandboxResult(
                ok=False,
                stdout="",
                stderr="nsjail binary not found on PATH",
                exit_code=127,
                duration_s=0.0,
                backend="nsjail",
            )

        cmd = [
            self._nsjail,
            "--mode",
            "o",
            "--time_limit",
            str(max(1, timeout)),
            "--disable_rl",
            "--disable_rl_pow",
            "--disable_proc",
            "--disable_sbrk",
            "--quiet",
            "--",
            "/bin/sh",
            "-c",
            command,
        ]
        return self._run(cmd, timeout=timeout + 2, backend="nsjail")

    # ---- Shared ----

    @staticmethod
    def _run(cmd: List[str], timeout: int, backend: str) -> SandboxResult:
        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            dur = time.time() - start
            return SandboxResult(
                ok=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
                duration_s=round(dur, 3),
                backend=backend,
            )
        except subprocess.TimeoutExpired as e:
            dur = time.time() - start
            return SandboxResult(
                ok=False,
                stdout=e.stdout.decode(errors="ignore") if isinstance(e.stdout, bytes) else (e.stdout or ""),
                stderr=(e.stderr.decode(errors="ignore") if isinstance(e.stderr, bytes) else (e.stderr or "")) + f"\n[timeout after {timeout}s]",
                exit_code=124,
                duration_s=round(dur, 3),
                backend=backend,
                timed_out=True,
            )
        except FileNotFoundError as e:
            return SandboxResult(
                ok=False, stdout="", stderr=f"executable not found: {e}",
                exit_code=127, duration_s=0.0, backend=backend,
            )

    def capabilities(self) -> Dict[str, bool]:
        """Report which sandbox backends are available."""
        return {"docker": bool(self._docker), "nsjail": bool(self._nsjail)}


__all__ = ["Sandbox", "SandboxResult"]