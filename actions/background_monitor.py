"""
background_monitor.py — class-based topic watching daemon.

Persists monitor definitions to disk and runs periodic DDG news checks.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from actions.web_search import _ddg_news


_BLOCKED = {
    "bitcoin", "ethereum", "dogecoin", "solana", "binance",
    "nft", "blockchain", "defi", "altcoin", "memecoin", "coin", "token",
    "crypto", "kripto", "cripto", "krypto", "крипто", "仮想通貨", "暗号資産",
    "cryptocurrency",
}


def _is_blocked(topic: str) -> bool:
    t = topic.lower()
    return any(w in t for w in _BLOCKED)


def _slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", topic.lower().strip())[:40].strip("_")


def _title_hash(title: str) -> str:
    return hashlib.md5(title.encode("utf-8", errors="ignore")).hexdigest()[:12]


@dataclass
class Monitor:
    monitor_id: str
    topic: str
    callback: Optional[Callable[[dict], None]] = None
    interval: int = 300
    last_run: float = 0.0
    last_hash: str = ""
    added: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    enabled: bool = True

    def should_run(self, now: float | None = None) -> bool:
        if not self.enabled:
            return False
        now = now if now is not None else time.time()
        return (now - self.last_run) >= self.interval


class BackgroundMonitor:
    """Topic-watching daemon with persistence and a tick loop."""

    STATE_PATH = Path.home() / ".jarvis" / "monitors.json"

    def __init__(self, state_path: Optional[Path | str] = None):
        self.state_path = Path(state_path) if state_path else self.STATE_PATH
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._monitors: dict[str, Monitor] = {}
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._load()

    # ── Public API ──────────────────────────────────────────────────────────

    def add_monitor(
        self,
        topic: str,
        callback: Optional[Callable[[dict], None]] = None,
        interval: int = 300,
    ) -> str:
        """Register a topic. Returns the monitor_id."""
        topic = (topic or "").strip()
        if not topic:
            raise ValueError("topic must not be empty")
        if _is_blocked(topic):
            raise ValueError("crypto / financial topics are not monitored")

        with self._lock:
            for m in self._monitors.values():
                if m.topic.lower() == topic.lower():
                    return m.monitor_id

            mid = uuid.uuid4().hex[:12]
            monitor = Monitor(
                monitor_id=mid,
                topic=topic,
                callback=callback,
                interval=max(60, int(interval)),
            )
            self._monitors[mid] = monitor
            self._save()
            return mid

    def remove_monitor(self, monitor_id: str) -> bool:
        with self._lock:
            m = self._monitors.pop(monitor_id, None)
            if m:
                self._save()
                return True
            return False

    def list_monitors(self) -> list[dict]:
        with self._lock:
            return [
                {**asdict(m), "callback": None}
                for m in self._monitors.values()
            ]

    def get_monitor(self, monitor_id: str) -> Optional[Monitor]:
        with self._lock:
            return self._monitors.get(monitor_id)

    def check_all(self) -> list[dict]:
        """Run every monitor whose interval has elapsed. Returns alerts."""
        alerts: list[dict] = []
        now = time.time()
        for m in list(self._monitors.values()):
            if not m.should_run(now):
                continue
            alert = self._check_one(m)
            m.last_run = now
            if alert:
                alerts.append(alert)
        if alerts:
            self._save()
        return alerts

    def check_one(self, monitor_id: str) -> Optional[dict]:
        with self._lock:
            m = self._monitors.get(monitor_id)
            if not m:
                return None
        alert = self._check_one(m)
        m.last_run = time.time()
        self._save()
        return alert

    def start(self, tick_seconds: int = 60) -> None:
        """Run a background thread that ticks periodically."""
        if self._running:
            return
        self._running = True

        def _loop():
            while self._running:
                try:
                    self.check_all()
                except Exception as e:
                    print(f"[BackgroundMonitor] tick error: {e}")
                time.sleep(max(10, tick_seconds))

        self._thread = threading.Thread(target=_loop, name="BackgroundMonitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    # ── Internals ───────────────────────────────────────────────────────────

    def _check_one(self, monitor: Monitor) -> Optional[dict]:
        try:
            results = _ddg_news(monitor.topic, max_results=5)
        except Exception as e:
            print(f"[BackgroundMonitor] DDG failed for '{monitor.topic}': {e}")
            return None
        if not results:
            return None

        top = results[0]
        title = (top.get("title") or "").strip()
        if not title:
            return None

        h = _title_hash(title)
        if h == monitor.last_hash:
            return None
        monitor.last_hash = h

        alert = {
            "monitor_id": monitor.monitor_id,
            "topic": monitor.topic,
            "title": title,
            "snippet": top.get("snippet", ""),
            "url": top.get("url", ""),
            "source": top.get("source", ""),
            "ts": datetime.now().isoformat(timespec="seconds"),
        }

        if monitor.callback:
            try:
                monitor.callback(alert)
            except Exception as e:
                print(f"[BackgroundMonitor] callback error for '{monitor.topic}': {e}")
        return alert

    def _save(self) -> None:
        with self._lock:
            data = {
                mid: {
                    "monitor_id": m.monitor_id,
                    "topic": m.topic,
                    "interval": m.interval,
                    "last_run": m.last_run,
                    "last_hash": m.last_hash,
                    "added": m.added,
                    "enabled": m.enabled,
                }
                for mid, m in self._monitors.items()
            }
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self.state_path)

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return
        for mid, payload in data.items():
            try:
                self._monitors[mid] = Monitor(
                    monitor_id=payload["monitor_id"],
                    topic=payload["topic"],
                    callback=None,
                    interval=int(payload.get("interval", 300)),
                    last_run=float(payload.get("last_run", 0.0)),
                    last_hash=payload.get("last_hash", ""),
                    added=payload.get("added", datetime.now().isoformat(timespec="seconds")),
                    enabled=bool(payload.get("enabled", True)),
                )
            except Exception:
                continue


# ── Module-level helper for legacy callers ─────────────────────────────────

def add_monitor(topic: str) -> str:
    """Legacy facade — used by old jarvis tooling."""
    bm = BackgroundMonitor()
    return bm.add_monitor(topic=topic)


def remove_monitor(topic: str) -> str:
    bm = BackgroundMonitor()
    for m in bm.list_monitors():
        if topic.lower() in m["topic"].lower():
            if bm.remove_monitor(m["monitor_id"]):
                return f"Stopped monitoring: {m['topic']}"
    return f"Not found: {topic}"


def list_monitors() -> list[str]:
    return [m["topic"] for m in BackgroundMonitor().list_monitors()]


def check_all() -> list[str]:
    alerts = BackgroundMonitor().check_all()
    return [
        f"[MONITOR_ALERT] {a['topic']}\nHeadline: {a['title']}\n{a.get('snippet','')[:150]}\nSource: {a.get('source','')}"
        for a in alerts
    ]