
"""Reactive audio waveform widget."""

from __future__ import annotations

import math
import random
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class WaveformWidget(QWidget):
    """Real-time reactive audio waveform visualization."""

    def __init__(self, parent=None, bars: int = 48) -> None:
        super().__init__(parent)
        self._bars = bars
        self._levels: list[float] = [0.0] * bars
        self._targets: list[float] = [0.0] * bars
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._update_targets)
        self._tmr.start(80)
        self.setMinimumHeight(80)

    def set_level(self, level: float) -> None:
        """Set overall audio level 0.0–1.0."""
        for i in range(self._bars):
            self._targets[i] = max(self._targets[i], level * (0.4 + 0.6 * random.random()))

    def _update_targets(self) -> None:
        for i in range(self._bars):
            if self._targets[i] > 0.01:
                self._targets[i] *= 0.85
            else:
                self._targets[i] = 0.0
        self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        for i in range(self._bars):
            self._levels[i] += (self._targets[i] - self._levels[i]) * 0.3
            lvl = self._levels[i]
            bar_h = max(4, int(lvl * (H - 20)))
            x = (W / self._bars) * i + 2
            w = (W / self._bars) - 4
            alpha = int(80 + 175 * lvl)
            color = QColor(0, 220, 255, alpha)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(int(x), H - bar_h - 6, int(w), bar_h, 3, 3)
        p.end()
