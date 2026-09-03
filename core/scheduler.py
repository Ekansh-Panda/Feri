"""
JARVIS Scheduler — APScheduler wrapper with SQLite job store.

Provides persistent, restart-safe timed tasks.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


class JARVISScheduler:
    """Persistent APScheduler with SQLite job store."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = Path(db_path) if db_path else REPO_ROOT / "memory" / "scheduler.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._scheduler = None  # type: ignore[var-annotated]
        self._lock = threading.RLock()
        self._init_error: Optional[str] = None

        try:
            from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
            from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore  # type: ignore[import-untyped]

            jobstores = {"default": SQLAlchemyJobStore(url=f"sqlite:///{self.db_path}")}
            self._scheduler = BackgroundScheduler(jobstores=jobstores)
            self._scheduler.start()
        except Exception as e:  # pragma: no cover - import-time safety
            self._init_error = str(e)
            self._scheduler = None

    @property
    def available(self) -> bool:
        return self._scheduler is not None

    def add_job(
        self,
        func: Callable[..., Any],
        trigger: str = "interval",
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        **trigger_kwargs: Any,
    ) -> Optional[str]:
        """Schedule a job. Trigger e.g. 'interval', 'cron', 'date'."""
        if not self.available:
            return None
        with self._lock:
            job = self._scheduler.add_job(
                func,
                trigger=trigger,
                args=args or [],
                kwargs=kwargs or {},
                id=job_id,
                replace_existing=True,
                **trigger_kwargs,
            )
            return job.id

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job by id."""
        if not self.available:
            return False
        with self._lock:
            try:
                self._scheduler.remove_job(job_id)
                return True
            except Exception:
                return False

    def list_jobs(self) -> List[Dict[str, Any]]:
        """Return a JSON-serialisable list of scheduled jobs."""
        if not self.available:
            return []
        out: List[Dict[str, Any]] = []
        for job in self._scheduler.get_jobs():
            out.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "trigger": str(job.trigger),
                    "func": f"{job.func.__module__}.{job.func.__name__}" if hasattr(job, "func") else "?",
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                }
            )
        return out

    def shutdown(self, wait: bool = False) -> None:
        """Stop the scheduler."""
        if self.available:
            try:
                self._scheduler.shutdown(wait=wait)
            except Exception:
                pass
            self._scheduler = None


__all__ = ["JARVISScheduler"]