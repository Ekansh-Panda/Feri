
"""Glassmorphic panel component for JARVIS NEXUS HUD."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QFrame, QVBoxLayout


class GlassPanel(QFrame):
    """Semi-transparent rounded panel with subtle border."""

    def __init__(
        self,
        parent=None,
        radius: int = 12,
        bg_alpha: int = 30,
        border_alpha: int = 80,
    ) -> None:
        super().__init__(parent)
        self._radius = radius
        self._bg_alpha = bg_alpha
        self._border_alpha = border_alpha
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self._radius, self._radius)
        bg = QColor(0, 6, 10, self._bg_alpha)
        border = QColor(13, 51, 71, self._border_alpha)
        p.fillPath(path, bg)
        pen = QPen(border, 1)
        pen.setStyle(Qt.PenStyle.SolidLine)
        p.strokePath(path, pen)
        p.end()
