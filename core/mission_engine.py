import json
import os
import subprocess
import time
import uuid
from typing import List, Dict, Optional, Callable
from enum import Enum

from pydantic import BaseModel


class Status(str, Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SubTask(BaseModel):
    id: str
    name: str
    status: Status = Status.PLANNED
    result: Optional[str] = None
    retries: int = 0
    max_retries: int = 3
    error: Optional[str] = None


class Mission(BaseModel):
    id: str
    title: str
    goal: str
    status: Status = Status.PLANNED
    subtasks: List[SubTask] = []
    artifacts: List[str] = []
    logs: List[str] = []
    created_at: float = time.time()
    updated_at: float = time.time()

    def log(self, msg: str):
        self.logs.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        self.updated_at = time.time()


class MissionEngine:
    def __init__(self, base="missions"):
        self.active_dir = Path(base) / "active"
        self.completed_dir = Path(base) / "completed"
        self.failed_dir = Path(base) / "failed"
        for d in [self.active_dir, self.completed_dir, self.failed_dir]:
            d.mkdir(parents=True, exist_ok=True)
        self.missions: Dict[str, Mission] = {}
        self._callbacks: List[Callable] = []
        self._restore()

    def _restore(self):
        for f in self.active_dir.glob("*.json"):
            try:
                with open(f) as fh:
                    m = Mission(**json.load(fh))
                if m.status == Status.RUNNING:
                    m.status = Status.PAUSED
                    m.log("System reboot detected. Paused.")
                self.missions[m.id] = m
            except Exception:
                pass

    def on_update(self, callback: Callable):
        self._callbacks.append(callback)

    def _notify(self, mission: Mission):
        for cb in self._callbacks:
            try:
                cb(mission)
            except Exception:
                pass

    def create(self, title: str, goal: str, subtask_names: List[str]) -> Mission:
        mid = uuid.uuid4().hex[:8]
        subtasks = [
            SubTask(id=uuid.uuid4().hex[:8], name=n)
            for n in subtask_names
        ]
        m = Mission(id=mid, title=title, goal=goal, subtasks=subtasks)
        m.log(f"Mission created: {len(subtasks)} subtasks")
        self.missions[mid] = m
        self._save(m)
        self._notify(m)
        return m

    def update_subtask(self, mid: str, sid_or_idx, status: Status,
                       result: str = None, error: str = None):
        m = self.missions.get(mid)
        if not m:
            return

        st = None
        if isinstance(sid_or_idx, int):
            if 0 <= sid_or_idx < len(m.subtasks):
                st = m.subtasks[sid_or_idx]
        else:
            st = next((s for s in m.subtasks if s.id == sid_or_idx), None)

        if st:
            st.status = status
            if result:
                st.result = result
            if error:
                st.error = error
                st.retries += 1
            m.log(f"Subtask '{st.name}' -> {status.value}")

        if all(s.status == Status.COMPLETED for s in m.subtasks):
            m.status = Status.COMPLETED
            self._archive(m, self.completed_dir)
        elif any(s.status == Status.FAILED and s.retries >= s.max_retries
                 for s in m.subtasks):
            m.status = Status.FAILED
            self._archive(m, self.failed_dir)
        else:
            m.status = Status.RUNNING
            self._save(m)

        self._notify(m)

    def log(self, mid: str, msg: str):
        m = self.missions.get(mid)
        if m:
            m.log(msg)
            self._save(m)

    def add_artifact(self, mid: str, path: str):
        m = self.missions.get(mid)
        if m:
            m.artifacts.append(path)
            self._save(m)

    def get_active(self) -> List[Mission]:
        return [
            m for m in self.missions.values()
            if m.status in (Status.RUNNING, Status.PAUSED, Status.AWAITING_APPROVAL)
        ]

    def _save(self, m: Mission):
        path = self.active_dir / f"{m.id}.json"
        with open(path, "w") as f:
            json.dump(m.model_dump(), f, indent=2, default=str)

    def _archive(self, m: Mission, dest: Path):
        old = self.active_dir / f"{m.id}.json"
        new = dest / f"{m.id}.json"
        self._save(m)
        if old.exists():
            old.rename(new)
        if m.id in self.missions:
            del self.missions[m.id]
