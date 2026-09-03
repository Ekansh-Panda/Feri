"""TerminalAgent — root shell execution with safety checks and session management."""

from __future__ import annotations

import logging
import os
import pwd
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.terminal")

_DESTRUCTIVE_RE = (
    "rm -rf /",
    "rm -rf ~/",
    "mkfs",
    ":(){ :|:& };:",
    "dd if=/dev/zero",
    "dd if=/dev/random of=/dev/",
    "chmod -R 777 /",
    "chown -R",
    "kill -9 -1",
    "pkill -9",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    "init 0",
    "init 6",
    "systemctl poweroff",
    "systemctl reboot",
)


class TerminalAgent:
    """Executes shell commands with safety checks, sudo handling, and session management."""

    def __init__(self, default_timeout: int = 30) -> None:
        self.default_timeout = default_timeout
        self._sessions: dict[str, dict[str, Any]] = {}
        self._next_id = 1

    def run(self, command: str, sudo: bool = False, timeout: int | None = None) -> dict[str, Any]:
        """Execute a shell command.

        Args:
            command: Shell command to run.
            sudo: Whether to run with sudo.
            timeout: Timeout in seconds (defaults to instance default).

        Returns:
            Dict with stdout, stderr, returncode, and status.
        """
        timeout = timeout if timeout is not None else self.default_timeout
        command = command.strip()
        if not command:
            return {"stdout": "", "stderr": "Empty command.", "returncode": -1, "status": "error"}

        if self._is_destructive(command):
            return {
                "stdout": "",
                "stderr": "Destructive command blocked by safety policy.",
                "returncode": -2,
                "status": "blocked",
            }

        effective_cmd = command
        if sudo:
            effective_cmd = f"sudo -n {command}"

        try:
            proc = subprocess.run(
                effective_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._safe_env(),
            )
            return {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
                "status": "ok" if proc.returncode == 0 else "error",
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s.",
                "returncode": -1,
                "status": "timeout",
            }
        except Exception as exc:
            logger.error("run() failed: %s", exc)
            return {
                "stdout": "",
                "stderr": str(exc),
                "returncode": -1,
                "status": "error",
            }

    def run_background(self, command: str, sudo: bool = False) -> dict[str, Any]:
        """Start a nohup background process.

        Args:
            command: Shell command.
            sudo: Whether to use sudo.

        Returns:
            Dict with pid and status.
        """
        command = command.strip()
        if not command:
            return {"pid": 0, "status": "error", "error": "Empty command."}

        if self._is_destructive(command):
            return {"pid": 0, "status": "blocked", "error": "Destructive command blocked."}

        effective_cmd = command
        if sudo:
            effective_cmd = f"sudo -n {command}"

        log_path = Path("/tmp") / f"jarvis_bg_{self._next_id}.log"
        try:
            proc = subprocess.Popen(
                f"nohup {effective_cmd} > {log_path} 2>&1 & echo $!",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self._safe_env(),
            )
            stdout, _ = proc.communicate(timeout=5)
            pid_str = stdout.strip().splitlines()[-1] if stdout.strip() else "0"
            pid = int(pid_str) if pid_str.isdigit() else 0

            sid = f"bg_{self._next_id}"
            self._next_id += 1
            self._sessions[sid] = {
                "pid": pid,
                "command": command,
                "log_path": str(log_path),
                "started_at": time.time(),
                "status": "running",
            }
            return {"sid": sid, "pid": pid, "status": "running", "log_path": str(log_path)}
        except Exception as exc:
            logger.error("run_background() failed: %s", exc)
            return {"pid": 0, "status": "error", "error": str(exc)}

    def get_output(self, pid: int) -> dict[str, Any]:
        """Retrieve output for a background process.

        Args:
            pid: Process ID.

        Returns:
            Dict with stdout, stderr, and status.
        """
        for sid, session in self._sessions.items():
            if session.get("pid") == pid:
                log_path = session.get("log_path", "")
                if log_path and Path(log_path).exists():
                    try:
                        content = Path(log_path).read_text(encoding="utf-8", errors="replace")
                        session["status"] = "completed"
                        return {"sid": sid, "output": content, "status": "completed"}
                    except Exception as exc:
                        return {"sid": sid, "output": "", "status": "error", "error": str(exc)}
                return {"sid": sid, "output": "", "status": "no_log"}
        return {"output": "", "status": "not_found", "error": f"PID {pid} not tracked."}

    def get_session_output(self, sid: str) -> dict[str, Any]:
        """Retrieve output for a background session by session ID.

        Args:
            sid: Session ID (e.g. bg_1).

        Returns:
            Dict with session info and output.
        """
        session = self._sessions.get(sid)
        if not session:
            return {"status": "not_found", "error": f"Session {sid} not found."}
        log_path = session.get("log_path", "")
        output = ""
        if log_path and Path(log_path).exists():
            try:
                output = Path(log_path).read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                return {"status": "error", "error": str(exc)}
        return {
            "sid": sid,
            "pid": session.get("pid"),
            "command": session.get("command"),
            "status": session.get("status", "unknown"),
            "output": output,
        }

    def kill(self, pid: int) -> dict[str, Any]:
        """Terminate a background process.

        Args:
            pid: Process ID.

        Returns:
            Dict with status.
        """
        for sid, session in list(self._sessions.items()):
            if session.get("pid") == pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.2)
                    try:
                        os.kill(pid, 0)
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    session["status"] = "killed"
                    return {"sid": sid, "pid": pid, "status": "killed"}
                except ProcessLookupError:
                    session["status"] = "already_exited"
                    return {"sid": sid, "pid": pid, "status": "already_exited"}
                except Exception as exc:
                    return {"sid": sid, "pid": pid, "status": "error", "error": str(exc)}
        return {"pid": pid, "status": "not_found", "error": f"PID {pid} not tracked."}

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active background sessions.

        Returns:
            List of session summaries.
        """
        result = []
        for sid, session in self._sessions.items():
            pid = session.get("pid")
            alive = False
            if pid:
                try:
                    os.kill(pid, 0)
                    alive = True
                except ProcessLookupError:
                    session["status"] = "exited"
            result.append({
                "sid": sid,
                "pid": pid,
                "command": session.get("command"),
                "status": session.get("status", "unknown") if alive else "exited",
                "started_at": session.get("started_at"),
            })
        return result

    # -- helpers --

    def _is_destructive(self, command: str) -> bool:
        lower = command.lower()
        for pattern in _DESTRUCTIVE_RE:
            if pattern in lower:
                logger.warning("Blocked destructive command pattern: %s", pattern)
                return True
        return False

    def _safe_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["LANG"] = env.get("LANG", "C.UTF-8")
        return env
