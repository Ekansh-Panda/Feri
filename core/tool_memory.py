"""
Tool Memory — track tool success/failure and suggest tools from history.

Uses SQLite for atomic counters plus a ChromaDB-backed semantic index
to recommend tools based on similar past tasks.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


class ToolMemory:
    """Persistent record of tool calls and their outcomes."""

    def __init__(self, base: str = "memory/tool_memory") -> None:
        self.base = Path(base)
        if not self.base.is_absolute():
            self.base = REPO_ROOT / base
        self.base.mkdir(parents=True, exist_ok=True)
        self._db_path = self.base / "tool_history.db"
        self._lock = threading.RLock()
        self._init_db()
        self._vector = None  # type: ignore[var-annotated]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    params TEXT,
                    result TEXT,
                    error TEXT,
                    task TEXT,
                    ts REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tool_name ON tool_history(tool_name)"
            )

    def _vector_memory(self):
        if self._vector is None:
            try:
                from .vector_memory import VectorMemory

                self._vector = VectorMemory(
                    db_path=str(self.base / "chroma_db"), collection="tool_memory"
                )
            except Exception:
                self._vector = False
        return self._vector if self._vector else None

    def record_success(self, tool_name: str, params: Dict[str, Any], result: str,
                       task: Optional[str] = None) -> None:
        """Log a successful tool invocation."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO tool_history(tool_name, success, params, result, error, task, ts)"
                " VALUES (?, ?, ?, ?, NULL, ?, ?)",
                (tool_name, 1, json.dumps(params, default=str)[:2000],
                 result[:4000], task, time.time()),
            )
        vec = self._vector_memory()
        if vec and task:
            try:
                vec.add_document(
                    f"{task} -> {tool_name} (ok)",
                    metadata={"tool": tool_name, "success": True},
                )
            except Exception:
                pass

    def record_failure(self, tool_name: str, params: Dict[str, Any], error: str,
                       task: Optional[str] = None) -> None:
        """Log a failed tool invocation."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO tool_history(tool_name, success, params, result, error, task, ts)"
                " VALUES (?, ?, ?, NULL, ?, ?, ?)",
                (tool_name, 0, json.dumps(params, default=str)[:2000],
                 error[:4000], task, time.time()),
            )
        vec = self._vector_memory()
        if vec and task:
            try:
                vec.add_document(
                    f"{task} -> {tool_name} (fail: {error[:120]})",
                    metadata={"tool": tool_name, "success": False},
                )
            except Exception:
                pass

    def get_success_rate(self, tool_name: str) -> float:
        """Return success ratio 0.0–1.0 for a tool. 0.5 default if no data."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS total, SUM(success) AS wins "
                "FROM tool_history WHERE tool_name = ?",
                (tool_name,),
            ).fetchone()
        total = row["total"] or 0
        if total == 0:
            return 0.5
        return float(row["wins"] or 0) / float(total)

    def history(self, tool_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent history rows (most recent first)."""
        with self._lock, self._connect() as conn:
            if tool_name:
                rows = conn.execute(
                    "SELECT * FROM tool_history WHERE tool_name = ? ORDER BY id DESC LIMIT ?",
                    (tool_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tool_history ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def suggest_tool(self, task_description: str) -> Optional[Dict[str, Any]]:
        """Recommend best tool based on past similar tasks + success rates."""
        vec = self._vector_memory()
        candidates: List[Tuple[str, float]] = []
        if vec:
            try:
                hits = vec.query(task_description, n_results=5)
                for h in hits:
                    tool = h.get("metadata", {}).get("tool")
                    if tool:
                        candidates.append((tool, float(h.get("score", 0.0))))
            except Exception:
                pass

        # Aggregate by tool
        scores: Dict[str, float] = {}
        for tool, sc in candidates:
            scores[tool] = scores.get(tool, 0.0) + sc

        # Blend with global success rate
        with self._lock, self._connect() as conn:
            tools = [r["tool_name"] for r in conn.execute(
                "SELECT DISTINCT tool_name FROM tool_history"
            ).fetchall()]

        if not scores:
            if not tools:
                return None
            best = max(tools, key=lambda t: self.get_success_rate(t))
            return {"tool": best, "score": 0.5, "reason": "highest_historical_success_rate"}

        # Penalize tools with poor success rates
        for t in list(scores):
            rate = self.get_success_rate(t)
            scores[t] = scores[t] * (0.5 + 0.5 * rate)

        best_tool = max(scores, key=lambda t: scores[t])
        return {
            "tool": best_tool,
            "score": round(scores[best_tool], 4),
            "reason": "semantic_match_weighted_by_success",
        }


__all__ = ["ToolMemory"]