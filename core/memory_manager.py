"""
Memory Manager — SQLite-backed memory + JSON structured storage.

Provides long-term facts (JSON), episodic session logs, and FTS search.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


class MemoryManager:
    """Structured memory: long-term JSON, episodic sessions, FTS search."""

    def __init__(self, base: str = "memory") -> None:
        self.base = Path(base)
        if not self.base.is_absolute():
            self.base = REPO_ROOT / base
        self.base.mkdir(parents=True, exist_ok=True)

        self.long_term_path = self.base / "long_term.json"
        self.identity_path = self.base / "identity.json"
        self.episodic_dir = self.base / "episodic"
        self.episodic_dir.mkdir(parents=True, exist_ok=True)

        self._db_path = self.base / "memory.db"
        self._lock = threading.RLock()

        self.long_term: Dict[str, Any] = self._read_json(
            self.long_term_path, default={"facts": {}, "preferences": {}, "relationships": {}}
        )
        self.identity: Dict[str, Any] = self._read_json(
            self.identity_path, default={"name": "JARVIS", "language": "en", "owner": "cobalt"}
        )

        self._init_db()

    @staticmethod
    def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return default
        path.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return default

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    key UNINDEXED,
                    kind UNINDEXED,
                    content,
                    tokenize = 'porter unicode61'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_meta (
                    key TEXT PRIMARY KEY,
                    kind TEXT,
                    updated_at REAL
                )
                """
            )

    # ---- Persistence helpers ----

    def save_memory(self, data: Dict[str, Any]) -> None:
        """Overwrite long_term.json with the given dict."""
        with self._lock:
            self.long_term = data
            self.long_term_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_memory(self) -> Dict[str, Any]:
        """Return a deep copy of long_term memory."""
        with self._lock:
            return json.loads(json.dumps(self.long_term))

    # ---- FTS ----

    def _index(self, key: str, kind: str, content: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM memory_fts WHERE key = ?", (key,))
            conn.execute(
                "INSERT INTO memory_fts(key, kind, content) VALUES (?, ?, ?)",
                (key, kind, content),
            )
            conn.execute(
                "INSERT OR REPLACE INTO memory_meta(key, kind, updated_at) VALUES (?, ?, ?)",
                (key, kind, time.time()),
            )

    def search_memory(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Full-text search over indexed memory entries."""
        if not query.strip():
            return []
        with self._lock, self._connect() as conn:
            try:
                rows = conn.execute(
                    "SELECT key, kind, content FROM memory_fts WHERE memory_fts MATCH ? LIMIT ?",
                    (query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                # Fall back to LIKE if FTS query syntax is malformed
                like = f"%{query}%"
                rows = conn.execute(
                    "SELECT key, kind, content FROM memory_fts WHERE content LIKE ? LIMIT ?",
                    (like, limit),
                ).fetchall()
        return [dict(r) for r in rows]

    def add_entry(self, key: str, kind: str, content: str) -> None:
        """Public hook to index a memory entry."""
        self._index(key, kind, content)

    # ---- Prompt packing ----

    def format_memory_for_prompt(self, max_chars: int = 4000) -> str:
        """Compact relevant memory into a prompt-safe block."""
        lines: List[str] = []
        identity = self.identity
        lines.append(f"IDENTITY: {identity.get('name', 'JARVIS')} | owner={identity.get('owner')}")
        prefs = self.long_term.get("preferences", {})
        if prefs:
            top = ", ".join(f"{k}={v}" for k, v in list(prefs.items())[:6])
            lines.append(f"PREFS: {top}")
        facts = self.long_term.get("facts", {})
        for k, v in list(facts.items())[:8]:
            lines.append(f"FACT[{k}]={v}")
        rels = self.long_term.get("relationships", {})
        for k, v in list(rels.items())[:6]:
            lines.append(f"REL[{k}]={v}")
        out = "\n".join(lines)
        if len(out) > max_chars:
            out = out[: max_chars - 3] + "..."
        return out

    # ---- Episodic sessions ----

    def save_session_summary(self, session_id: str, summary: str) -> Path:
        """Persist an episodic summary to disk and FTS index."""
        safe_id = session_id.replace("/", "_").replace("..", "_")
        path = self.episodic_dir / f"{safe_id}.json"
        payload = {
            "session_id": session_id,
            "summary": summary,
            "saved_at": time.time(),
            "saved_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._index(f"session:{session_id}", "session", summary)
        return path

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List episodic sessions, most recent first."""
        items: List[Dict[str, Any]] = []
        for p in sorted(self.episodic_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                items.append(json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return items

    def pop_last_session(self) -> Optional[Dict[str, Any]]:
        """Retrieve and delete the most recent session summary."""
        files = sorted(self.episodic_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not files:
            return None
        last = files[0]
        try:
            data = json.loads(last.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"raw": last.read_text(encoding="utf-8", errors="ignore")}
        last.unlink(missing_ok=True)
        # Remove from FTS too
        sid = data.get("session_id", last.stem)
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM memory_fts WHERE key = ?", (f"session:{sid}",))
            conn.execute("DELETE FROM memory_meta WHERE key = ?", (f"session:{sid}",))
        return data

    # ---- Key-value facts ----

    def get_fact(self, key: str, default: Any = None) -> Any:
        """Fetch a fact; checks FTS first, then long_term JSON."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT content FROM memory_fts WHERE key = ? LIMIT 1", (f"fact:{key}",)
            ).fetchone()
        if row:
            try:
                return json.loads(row["content"])
            except json.JSONDecodeError:
                return row["content"]
        return self.long_term.get("facts", {}).get(key, default)

    def set_fact(self, key: str, value: Any) -> None:
        """Persist a fact to both FTS and long-term JSON."""
        payload = json.dumps(value, ensure_ascii=False)
        self._index(f"fact:{key}", "fact", payload)
        self.long_term.setdefault("facts", {})[key] = value
        self.save_memory(self.long_term)


__all__ = ["MemoryManager"]