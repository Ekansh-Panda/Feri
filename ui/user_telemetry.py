
"""Fatigue, vitals, sleep debt telemetry."""

from __future__ import annotations

import random
from datetime import datetime
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class UserTelemetry(QWidget):
    """Fatigue index gauge, hours awake, battery, sleep debt, suggestions."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._fatigue = 0.0
        self._hours_awake = 0.0
        self._battery = 100
        self._sleep_debt = 0.0
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(5000)
        self._tick()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)
        self._fatigue_lbl = QLabel()
        self._fatigue_lbl.setStyleSheet("color: #00dcff; font-weight: bold;")
        lay.addWidget(self._fatigue_lbl)
        self._suggestion_lbl = QLabel()
        self._suggestion_lbl.setWordWrap(True)
        self._suggestion_lbl.setStyleSheet("color: #5ab8cc;")
        lay.addWidget(self._suggestion_lbl)
        self._stats = QLabel()
        self._stats.setStyleSheet("color: #8ffcff;")
        lay.addWidget(self._stats)
        lay.addStretch()

    def _tick(self) -> None:
        self._hours_awake = min(24.0, self._hours_awake + (random.random() * 0.1))
        self._fatigue = min(1.0, self._hours_awake / 18.0 + random.uniform(-0.05, 0.05))
        self._battery = max(0, self._battery - random.randint(0, 1))
        self._sleep_debt = max(0.0, self._sleep_debt - 0.1 + random.uniform(-0.2, 0.2))
        self._update_ui()

    def _update_ui(self) -> None:
        self._fatigue_lbl.setText(f"Fatigue Index: {self._fatigue:.2%}")
        suggestions = []
        if self._fatigue > 0.8:
            suggestions.append("Rest recommended immediately.")
        if self._battery < 20:
            suggestions.append("Connect charger.")
        if self._sleep_debt > 8:
            suggestions.append("Sleep debt high. Consider nap.")
        self._suggestion_lbl.setText("Intervention: " + (" | ".join(suggestions) if suggestions else "All nominal."))
        self._stats.setText(
            f"Hours Awake: {self._hours_awake:.1f}  |  Battery: {self._battery}%  |  Sleep Debt: {self._sleep_debt:.1f}h"
        )
        color = "#00ff88" if self._fatigue < 0.5 else ("#ffcc00" if self._fatigue < 0.8 else "#ff0000")
        self._fatigue_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
