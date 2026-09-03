
"""Protocol quick-launch buttons."""

from __future__ import annotations

import threading
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QGridLayout, QPushButton, QWidget

from ..plugins.protocols import StarkProtocols


_PROTOCOLS = [
    ("House Party", "#00dcff"),
    ("Clean Slate", "#00ff88"),
    ("Lockdown", "#ff0000"),
    ("Shadow", "#aa00ff"),
    ("Rescue", "#ffaa00"),
    ("Forge", "#ffcc00"),
    ("Exam", "#00aaff"),
    ("Archive", "#88aaff"),
]


class ProtocolButtons(QWidget):
    """Grid of protocol quick-launch buttons."""

    status_update = pyqtSignal(str, str)  # protocol name, status

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._protocols = StarkProtocols()
        self._active: dict[str, bool] = {name: False for name, _ in _PROTOCOLS}
        self._overlay_timer = QTimer(self)
        self._overlay_timer.timeout.connect(self._hide_overlays)
        self._overlay_visible: dict[str, QWidget] = {}
        grid = QGridLayout(self)
        grid.setSpacing(10)
        for idx, (name, color) in enumerate(_PROTOCOLS):
            btn = QPushButton(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(44)
            btn.setStyleSheet(self._btn_style(color, False))
            btn.clicked.connect(lambda _, n=name, c=color, b=btn: self._run(n, c, b))
            grid.addWidget(btn, idx // 2, idx % 2)
        self.setStyleSheet("background: transparent;")

    def _btn_style(self, color: str, active: bool) -> str:
        bg = color if active else "transparent"
        fg = "#000" if active else color
        return f"""
            QPushButton {{
                background: {bg}; color: {fg};
                border: 2px solid {color}; border-radius: 6px;
                font-weight: bold; font-size: 13px;
            }}
            QPushButton:hover {{ background: {color}22; }}
        """

    def _run(self, name: str, color: str, btn: QPushButton) -> None:
        if self._active.get(name):
            return
        self._active[name] = True
        btn.setStyleSheet(self._btn_style(color, True))
        self.status_update.emit(name, "running")
        t = threading.Thread(target=self._execute, args=(name,), daemon=True)
        t.start()

    def _execute(self, name: str) -> None:
        method = getattr(self._protocols, name.lower().replace(" ", "_") + "_protocol", None)
        if method:
            try:
                result = method() if name != "House Party" else method("auto", 3)
            except TypeError:
                result = {"status": "error", "message": "invalid args"}
        else:
            result = {"status": "error", "message": "unknown protocol"}
        status = result.get("status", "error") if isinstance(result, dict) else "error"
        self._active[name] = False
        self.status_update.emit(name, status)

    def _hide_overlays(self) -> None:
        for w in self._overlay_visible.values():
            w.hide()
        self._overlay_visible.clear()
