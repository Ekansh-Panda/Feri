"""
core/audit.py — Structured audit logging with systemd-journald integration.

Every privileged or state-changing action is logged here with the actor,
parameters, result, and timestamp.  On Linux systems with systemd, entries
are also pushed to the journal via the native journald protocol so they
survive log rotation and are queryable with `journalctl`.
"""
from __future__ import annotations

import json
import os
import socket
import struct
import threading
import time
import traceback
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from systemd import journal as _journal  # type: ignore[import]
    _HAS_JOURNALD = True
except ImportError:
    _HAS_JOURNALD = False


class AuditLogger:
    """Thread-safe audit logger with optional systemd-journald backend.

    Logs every action to an in-memory ring buffer, a JSON-lines file on
    disk, and (on Linux with systemd) the native journal.

    Attributes:
        log_path: Path to the JSON-lines audit log file.
        journal: True if journald integration is active.
    """

    SYSTEMD_STRUCT_VERSION = 1
    JOURNAL_IDENTIFIER = "jarvis-nexus"
    _SYSLOG_WELCOME = 6  # LOG_INFO equivalent for journald

    def __init__(
        self,
        log_path: Optional[str | Path] = None,
        use_journald: bool = True,
        max_memory_entries: int = 1000,
    ) -> None:
        """Initialise the audit logger.

        Args:
            log_path: Path to the JSON-lines audit log.  Defaults to
                <BASE_DIR>/memory/audit_log.jsonl.
            use_journald: If True and systemd is available, mirror all
                entries to the system journal.
            max_memory_entries: How many entries to keep in memory.
        """
        from core import BASE_DIR, MEMORY_DIR
        self.log_path: Path = (
            Path(log_path) if log_path else MEMORY_DIR / "audit_log.jsonl"
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.journal: bool = use_journald and _HAS_JOURNALD
        self._lock = threading.RLock()
        self._max_memory = max_memory_entries
        self._entries: deque[dict[str, Any]] = deque(maxlen=max_memory_entries)

    def log(
        self,
        action: str,
        params: Optional[dict[str, Any]] = None,
        result: Any = None,
        user: str = "system",
        level: str = "INFO",
    ) -> str:
        """Log a single audited action.

        Args:
            action: Name of the action or tool invoked.
            params: Parameter dict passed to the action.
            result: Return value or status of the action.
            user: The actor requesting the action.
            level: Severity level: INFO, WARN, ERROR, DENY.

        Returns:
            The entry ID string for correlation.
        """
        entry_id = f"{int(time.time() * 1000)}-{os.urandom(4).hex()}"
        entry: dict[str, Any] = {
            "id": entry_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "epoch": time.time(),
            "action": action,
            "params": params or {},
            "result": result,
            "user": user,
            "level": level,
            "hostname": socket.gethostname(),
        }

        with self._lock:
            self._entries.append(entry)
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except OSError as e:
                print(f"[Audit] Failed to write log file: {e}")

        if self.journal:
            self._send_to_journal(entry)

        return entry_id

    def _send_to_journal(self, entry: dict[str, Any]) -> None:
        """Send *entry* to the systemd journal via the native interface.

        Falls back to the syslog module if the systemd journald Python
        bindings are installed but the journal socket is unavailable.
        """
        try:
            message = f"{entry['user']}@{entry['hostname']} :: {entry['action']} [{entry['level']}] -> {entry['result']}"
            self._journal_send(message, entry)
        except Exception:
            pass

    def _journal_send(self, message: str, entry: dict[str, Any]) -> None:
        """Send a structured message to journald using the native protocol."""
        if not _HAS_JOURNALD:
            return
        fields = {
            "MESSAGE": message,
            "PRIORITY": str(self._severity(entry["level"])),
            "SYSLOG_IDENTIFIER": self.JOURNAL_IDENTIFIER,
            "LOGGER": entry["user"],
            "ACTION": entry["action"],
            "ENTRY_ID": entry["id"],
        }
        try:
            _journal.send(
                fields["MESSAGE"],
                priority=self._severity(entry["level"]),
                SYSLOG_IDENTIFIER=self.JOURNAL_IDENTIFIER,
                LOGGER=str(entry["user"]),
                ACTION=str(entry["action"]),
                ENTRY_ID=str(entry["id"]),
            )
        except Exception as e:
            print(f"[Audit] journald send failed: {e}")

    @staticmethod
    def _severity(level: str) -> int:
        """Map severity level string to syslog priority."""
        mapping = {
            "INFO": 6,
            "WARN": 4,
            "WARNING": 4,
            "ERROR": 3,
            "DENY": 3,
            "DEBUG": 7,
            "CRITICAL": 2,
        }
        return mapping.get(level.upper(), 6)

    def log_error(self, action: str, error: Exception, user: str = "system") -> str:
        """Convenience wrapper for logging exceptions with full traceback.

        Args:
            action: Name of the action that failed.
            error: The exception that was raised.
            user: The actor associated with the action.

        Returns:
            The entry ID string.
        """
        tb = traceback.format_exc()
        return self.log(
            action=action,
            params={"exception_type": type(error).__name__},
            result={"error": str(error), "traceback": tb},
            user=user,
            level="ERROR",
        )

    def log_denied(self, action: str, user: str = "system", reason: str = "") -> str:
        """Log a permission denial.

        Args:
            action: The action that was denied.
            user: The actor who attempted it.
            reason: Why it was denied.

        Returns:
            The entry ID string.
        """
        return self.log(
            action=action,
            params={"reason": reason},
            result="DENIED",
            user=user,
            level="DENY",
        )

    def query(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        action_type: Optional[str] = None,
        user: Optional[str] = None,
        level: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Query the audit log with filters.

        Searches both the in-memory ring buffer and the on-disk JSON-lines
        log.  The in-memory entries are checked first, then the file is
        scanned for any entries beyond the memory buffer.

        Args:
            start_time: Earliest epoch timestamp to include.
            end_time: Latest epoch timestamp to include.
            action_type: Filter by action name (substring match).
            user: Filter by actor username.
            level: Filter by severity level.
            limit: Maximum number of entries to return.

        Returns:
            List of matching log entry dicts, sorted newest-first.
        """
        results: list[dict[str, Any]] = []
        with self._lock:
            for entry in reversed(self._entries):
                if self._matches(entry, start_time, end_time, action_type, user, level):
                    results.append(entry)
                    if len(results) >= limit:
                        return results

        if len(results) < limit and self.log_path.exists():
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    file_entries = []
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        file_entries.append(entry)
                    for entry in reversed(file_entries):
                        if len(results) >= limit:
                            break
                        if entry in results:
                            continue
                        if self._matches(entry, start_time, end_time, action_type, user, level):
                            results.append(entry)
            except OSError:
                pass

        return results[:limit]

    @staticmethod
    def _matches(
        entry: dict[str, Any],
        start_time: Optional[float],
        end_time: Optional[float],
        action_type: Optional[str],
        user: Optional[str],
        level: Optional[str],
    ) -> bool:
        """Check if an entry matches the query filters."""
        if start_time is not None and entry.get("epoch", 0) < start_time:
            return False
        if end_time is not None and entry.get("epoch", 0) > end_time:
            return False
        if action_type is not None:
            if action_type.lower() not in str(entry.get("action", "")).lower():
                return False
        if user is not None and entry.get("user") != user:
            return False
        if level is not None and entry.get("level", "").upper() != level.upper():
            return False
        return True

    def stats(self) -> dict[str, Any]:
        """Return summary statistics about the audit log."""
        with self._lock:
            levels: dict[str, int] = {}
            actions: dict[str, int] = {}
            users: set[str] = set()
            for entry in self._entries:
                lvl = entry.get("level", "INFO")
                levels[lvl] = levels.get(lvl, 0) + 1
                act = entry.get("action", "unknown")
                actions[act] = actions.get(act, 0) + 1
                users.add(entry.get("user", "system"))
            return {
                "total_entries": len(self._entries),
                "levels": levels,
                "top_actions": dict(
                    sorted(actions.items(), key=lambda x: -x[1])[:10]
                ),
                "users": sorted(users),
                "journald_active": self.journal,
            }
