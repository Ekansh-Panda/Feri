"""
Watchdog — keeps JARVIS alive.

Spawns and supervises a target command. If the process exits, restarts it
after `restart_delay`. Provides a stop switch and status flag.
"""

from __future__ import annotations

import shlex
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


class Watchdog:
    """Monitor loop that restarts a child process on exit."""

    def __init__(self, target_cmd: str, restart_delay: int = 5,
                 max_restarts: int = 0, log_dir: Optional[Path] = None) -> None:
        self.target_cmd = target_cmd
        self.restart_delay = max(0, int(restart_delay))
        self.max_restarts = max(0, int(max_restarts))
        self.log_dir = Path(log_dir) if log_dir else REPO_ROOT / "memory" / "watchdog"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self.restart_count = 0
        self.started_at: Optional[float] = None
        self.last_exit_code: Optional[int] = None

    def start(self) -> bool:
        """Begin supervision. Returns True if a thread was started."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._monitor_loop, name="Watchdog", daemon=True
            )
            self._thread.start()
            return True

    def stop(self, timeout: float = 10.0) -> None:
        """Signal monitor to exit and terminate the child."""
        self._stop.set()
        with self._lock:
            proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=timeout / 2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None

    def is_running(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def _spawn(self) -> Optional[subprocess.Popen]:
        args = shlex.split(self.target_cmd) if isinstance(self.target_cmd, str) else list(self.target_cmd)
        if not args:
            return None
        stdout = open(self.log_dir / "stdout.log", "ab", buffering=0)
        stderr = open(self.log_dir / "stderr.log", "ab", buffering=0)
        return subprocess.Popen(
            args,
            stdout=stdout,
            stderr=stderr,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(REPO_ROOT),
        )

    def _monitor_loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                if self._proc is None or self._proc.poll() is not None:
                    proc = self._spawn()
                    self._proc = proc
                    if proc is not None and self.started_at is None:
                        self.started_at = time.time()
            proc = self._proc
            if proc is None:
                self._stop.wait(self.restart_delay)
                continue

            # Wait for either exit or stop signal
            while not self._stop.is_set() and proc.poll() is None:
                self._stop.wait(0.5)

            if self._stop.is_set():
                break

            self.last_exit_code = proc.poll()
            self.restart_count += 1
            if self.max_restarts and self.restart_count > self.max_restarts:
                # Cap reached; bail out and surface status
                self._stop.set()
                break
            self._stop.wait(self.restart_delay)
            with self._lock:
                self._proc = None

    def status(self) -> Dict[str, object]:
        """Return a snapshot of watchdog status."""
        with self._lock:
            proc = self._proc
        return {
            "running": proc is not None and proc.poll() is None,
            "pid": proc.pid if proc else None,
            "restart_count": self.restart_count,
            "last_exit_code": self.last_exit_code,
            "target_cmd": self.target_cmd,
            "uptime_s": round(time.time() - self.started_at, 2) if self.started_at else 0,
        }


__all__ = ["Watchdog"]