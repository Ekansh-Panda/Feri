
"""Dangerous action confirmation banner."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ApprovalBanner(QWidget):
    """Red/warning styled confirmation banner for dangerous actions."""

    approved = pyqtSignal(str)  # type: ignore[name-defined]
    denied = pyqtSignal(str)    # type: ignore[name-defined]

    def __init__(self, parent=None, timeout_ms: int = 30000) -> None:
        super().__init__(parent)
        self._action = ""
        self._token = ""
        self._timeout_ms = timeout_ms
        self._remaining = timeout_ms
        self.setVisible(False)
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)
        self._title = QLabel("⚠  ACTION REQUIRES APPROVAL")
        self._title.setStyleSheet("color: #ff3355; font-weight: bold; font-size: 14px;")
        lay.addWidget(self._title)
        self._desc = QLabel("")
        self._desc.setWordWrap(True)
        self._desc.setStyleSheet("color: #ffccaa;")
        lay.addWidget(self._desc)
        self._token_label = QLabel("")
        self._token_label.setStyleSheet("color: #ff8844; font-family: monospace;")
        lay.addWidget(self._token_label)
        row = QHBoxLayout()
        row.addStretch()
        self._approve_btn = QPushButton("APPROVE")
        self._approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._approve_btn.setStyleSheet("""
            QPushButton { background: #ff0000; color: #fff; border: none; padding: 8px 18px; font-weight: bold; }
            QPushButton:hover { background: #cc0000; }
        """)
        self._approve_btn.clicked.connect(self._on_approve)
        row.addWidget(self._approve_btn)
        self._deny_btn = QPushButton("DENY")
        self._deny_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._deny_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #aaa; border: 1px solid #555; padding: 8px 18px; }
            QPushButton:hover { border-color: #fff; color: #fff; }
        """)
        self._deny_btn.clicked.connect(self._on_deny)
        row.addWidget(self._deny_btn)
        lay.addLayout(row)
        self.setStyleSheet("""
            ApprovalBanner {
                background: rgba(30, 5, 5, 240);
                border: 1px solid #ff3355;
                border-radius: 8px;
            }
        """)

    def show_action(self, action: str, token: str) -> None:
        self._action = action
        self._token = token
        self._remaining = self._timeout_ms
        self._desc.setText(action)
        self._token_label.setText(f"Token: {token}")
        self.setVisible(True)
        self._tmr.start(1000)

    def _tick(self) -> None:
        self._remaining -= 1000
        if self._remaining <= 0:
            self._tmr.stop()
            self._on_deny()
        self.update()

    def _on_approve(self) -> None:
        self._tmr.stop()
        self.setVisible(False)
        self.approved.emit(self._token)

    def _on_deny(self) -> None:
        self._tmr.stop()
        self.setVisible(False)
        self.denied.emit(self._token)
