
"""Custom painted Arc Reactor widget."""

from __future__ import annotations

import math
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QWidget


class ArcReactor(QWidget):
    """Animated Arc Reactor with glowing cyan and Stark red concentric rings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self._angle = 0.0
        self._pulse = 0.0
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(16)

    def _tick(self) -> None:
        self._angle = (self._angle + 0.8) % 360
        self._pulse = (self._pulse + 0.06) % (math.pi * 2)
        self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        base_r = min(W, H) / 2
        cyan = QColor(0, 220, 255)
        red = QColor(255, 0, 0)
        glow = QColor(0, 220, 255, int(40 + 20 * math.sin(self._pulse)))

        # outer rotating ring
        for i in range(8):
            r = base_r - i * 6
            if r < 10:
                break
            pen = QPen(QColor(0, 220, 255, int(180 - i * 20)), 2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            rect = _RectF(cx - r, cy - r, r * 2, r * 2)
            p.drawArc(rect, int(self._angle * 16) + i * 8, int(300 * 16))

        # inner solid ring
        pen = QPen(QColor(255, 0, 0, 200), 3)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(_RectF(cx - base_r * 0.55, cy - base_r * 0.55, base_r * 1.1, base_r * 1.1))

        # center glow
        grad = QRadialGradient(cx, cy, base_r * 0.3)
        grad.setColorAt(0.0, QColor(0, 220, 255, 180))
        grad.setColorAt(0.5, QColor(0, 220, 255, 60))
        grad.setColorAt(1.0, QColor(0, 220, 255, 0))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(_RectF(cx - base_r * 0.3, cy - base_r * 0.3, base_r * 0.6, base_r * 0.6))

        # core
        p.setBrush(QColor(255, 0, 0, int(120 + 60 * math.sin(self._pulse))))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(_RectF(cx - base_r * 0.12, cy - base_r * 0.12, base_r * 0.24, base_r * 0.24))
        p.end()


def _RectF(x: float, y: float, w: float, h: float):
    from PyQt6.QtCore import QRectF
    return QRectF(x, y, w, h)
