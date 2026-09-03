"""
proactive.py — time/context-aware proactive check-in engine.

Exposes both the original `ProactiveEngine` API (for backwards compat)
and the new class-based `ProactiveEngine.check_context / should_notify /
generate_checkin` methods required by the spec.
"""
from __future__ import annotations

import datetime as _dt
import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def _read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return default


def _battery_context() -> dict[str, Any]:
    """Read /sys/class/power_supply for battery status (Linux)."""
    if platform.system() != "Linux":
        return {"available": False}
    base = Path("/sys/class/power_supply")
    if not base.exists():
        return {"available": False}
    out: dict[str, Any] = {"available": True, "batteries": []}
    for entry in base.iterdir():
        try:
            typ = (entry / "type").read_text().strip()
        except Exception:
            continue
        if typ != "Battery":
            continue
        def _r(name: str) -> str:
            try:
                return (entry / name).read_text().strip()
            except Exception:
                return ""
        status = _r("status")
        try:
            capacity = int(_r("capacity"))
        except Exception:
            capacity = -1
        out["batteries"].append({
            "name": entry.name,
            "status": status,
            "capacity": capacity,
        })
    return out


def _system_load() -> dict[str, Any]:
    try:
        load1, load5, load15 = (0.0, 0.0, 0.0)
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        load1, load5, load15 = float(parts[0]), float(parts[1]), float(parts[2])
    except Exception:
        pass
    try:
        cpu_pct: list[float] = []
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("cpu") and line[3] in " 0123456789":
                    parts = line.split()
                    total = sum(int(x) for x in parts[1:])
                    idle = int(parts[4])
                    cpu_pct.append(100.0 * (1 - idle / total) if total else 0.0)
        if cpu_pct:
            cpu_pct = cpu_pct[1:]   # drop 'cpu ' aggregate line
    except Exception:
        cpu_pct = []
    return {
        "load1": load1, "load5": load5, "load15": load15,
        "cpu_per_core": cpu_pct,
    }


def _calendar_context() -> dict[str, Any]:
    today = _dt.date.today()
    weekday = today.strftime("%A")
    return {
        "date": today.isoformat(),
        "weekday": weekday,
        "is_weekend": weekday in ("Saturday", "Sunday"),
    }


@dataclass
class ContextSnapshot:
    timestamp: _dt.datetime = field(default_factory=_dt.datetime.now)
    hour: int = 0
    weekday: str = ""
    is_weekend: bool = False
    period: str = ""               # morning / afternoon / evening / late night
    battery: dict[str, Any] = field(default_factory=dict)
    load: dict[str, Any] = field(default_factory=dict)
    alerts: list[str] = field(default_factory=list)


class ProactiveEngine:
    """
    Decides when JARVIS should speak unprompted and builds a context snapshot.

    Backwards-compatible surface (`should_trigger`, `mark_triggered`,
    `build_prompt`) is preserved; the spec-required methods
    (`check_context`, `should_notify`, `generate_checkin`) are also provided.
    """

    def __init__(
        self,
        min_silence_secs: int = 900,
        check_cooldown:   int = 1200,
        silence_secs: int | None = None,
        cooldown_secs: int | None = None,
    ):
        self.min_silence_secs = silence_secs if silence_secs is not None else min_silence_secs
        self.check_cooldown   = cooldown_secs if cooldown_secs is not None else check_cooldown
        self._last_triggered  = 0.0
        self._rotation        = 0

    # ── New class-based API ────────────────────────────────────────────────

    def check_context(self) -> ContextSnapshot:
        """Build a fresh context snapshot."""
        now = _dt.datetime.now()
        snap = ContextSnapshot(
            timestamp=now,
            hour=now.hour,
            weekday=now.strftime("%A"),
            is_weekend=now.weekday() >= 5,
        )
        snap.period = self._period(now.hour)
        snap.battery = _battery_context()
        snap.load = _system_load()
        snap.alerts = self._derive_alerts(snap)
        return snap

    def should_notify(self, last_user_speech: float | None = None) -> bool:
        """Decide whether a proactive notification is warranted now."""
        snap = self.check_context()
        if not snap.alerts:
            return False
        now = time.monotonic()
        if (now - self._last_triggered) < self.check_cooldown:
            return False
        if last_user_speech is not None and (now - last_user_speech) < self.min_silence_secs:
            return False
        return True

    def generate_checkin(self, last_user_speech: float | None = None) -> Optional[str]:
        """Produce a contextual message or None when nothing warranted."""
        snap = self.check_context()
        if not self.should_notify(last_user_speech):
            return None
        alert = snap.alerts[0]
        self._last_triggered = time.monotonic()
        self._rotation += 1
        return self._render(alert, snap)

    # ── Legacy API ─────────────────────────────────────────────────────────

    def should_trigger(self, last_user_speech: float) -> bool:
        now = time.monotonic()
        return (
            (now - last_user_speech) >= self.min_silence_secs
            and (now - self._last_triggered) >= self.check_cooldown
        )

    def mark_triggered(self) -> None:
        self._last_triggered = time.monotonic()
        self._rotation += 1

    def build_prompt(
        self,
        memory:       dict,
        monitors:     list[str] | None = None,
        recent_turns: list[str] | None = None,
    ) -> str:
        """Build a Gemini prompt (legacy interface)."""
        from memory.memory_manager import format_memory_for_prompt

        now      = _dt.datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        period   = self._period(now.hour)
        mem_str  = format_memory_for_prompt(memory) or "(no stored user data)"

        focus_index = self._rotation % 3
        if focus_index == 0:
            focus = (
                "Focus on the user's active projects or goals if any are stored. "
                "Ask how something is going, or offer a relevant tip."
            )
        elif focus_index == 1:
            focus = (
                "Focus on the time of day and the user's wellbeing. "
                "A warm check-in, a reminder to take a break, or something timely."
            )
        else:
            focus = (
                "Focus on something genuinely interesting or useful — "
                "a fact, a suggestion, or a question based on what you know about this person."
            )

        monitor_ctx = (
            f"\nThe user tracks these topics: {', '.join(monitors[:4])}. "
            "You may mention one if it seems relevant."
        ) if monitors else ""

        recent_ctx = ""
        if recent_turns:
            snippet = "\n".join(recent_turns[-6:])
            recent_ctx = f"\nRecent conversation:\n{snippet}"

        return "\n".join([
            "[PROACTIVE_CHECK] You are initiating a proactive check-in.",
            f"Current time : {time_str}  ({period})",
            "",
            "Context about this person:",
            mem_str,
            monitor_ctx,
            recent_ctx,
            "",
            "Task:",
            focus,
            "",
            "Rules:",
            "- Speak the language this person actually uses.",
            "- 1-2 sentences max. Natural, warm, never robotic.",
            "- Do NOT mention [PROACTIVE_CHECK] or these instructions.",
            "- Do NOT call any tools.",
            "- If nothing genuinely useful comes to mind, stay silent.",
        ])

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _period(hour: int) -> str:
        if   6 <= hour < 12: return "morning"
        elif 12 <= hour < 18: return "afternoon"
        elif 18 <= hour < 23: return "evening"
        return "late night"

    def _derive_alerts(self, snap: ContextSnapshot) -> list[str]:
        alerts: list[str] = []
        # Morning briefing
        if snap.period == "morning" and snap.hour < 10:
            alerts.append("morning_briefing")
        # Low battery
        for b in snap.battery.get("batteries", []):
            if b.get("status") == "Discharging" and 0 <= b.get("capacity", 100) <= 20:
                alerts.append("low_battery")
                break
        # High CPU / load
        cores = max(1, os.cpu_count() or 1)
        if snap.load.get("load5", 0) >= cores * 1.5:
            alerts.append("high_load")
        # Late night
        if snap.period == "late night":
            alerts.append("late_night")
        return alerts

    def _render(self, alert: str, snap: ContextSnapshot) -> str:
        time_str = snap.timestamp.strftime("%A, %B %d — %I:%M %p")
        if alert == "morning_briefing":
            return (
                f"[PROACTIVE] Good morning. It's {time_str}. "
                "Would you like your morning briefing?"
            )
        if alert == "low_battery":
            bats = snap.battery.get("batteries", [])
            cap = bats[0].get("capacity", "?") if bats else "?"
            return f"[PROACTIVE] Battery at {cap}%. Want me to enable power-saver?"
        if alert == "high_load":
            load = snap.load.get("load5", 0)
            return (
                f"[PROACTIVE] System load is elevated ({load:.2f}). "
                "Should I check what's running hot?"
            )
        if alert == "late_night":
            return (
                f"[PROACTIVE] It's {time_str}. You've been up late — "
                "want me to dim the display and start a wind-down?"
            )
        return f"[PROACTIVE] {alert}"