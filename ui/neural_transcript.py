
"""Live voice conversation panel."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QTextCursor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class NeuralTranscript(QWidget):
    """Live voice conversation panel with user/JARVIS message bubbles."""

    message_sent = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._stream_timer = QTimer(self)
        self._stream_timer.timeout.connect(self._stream_step)
        self._stream_queue: list[tuple[str, str]] = []
        self._streaming = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self._history = QTextEdit()
        self._history.setReadOnly(True)
        self._history.setStyleSheet("""
            QTextEdit {
                background: rgba(0,6,10,180); color: #8ffcff;
                border: 1px solid #0d3347; border-radius: 6px; padding: 8px;
            }
        """)
        self._history.setFont(_mono(10))
        lay.addWidget(self._history)
        row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Speak or type...")
        self._input.setStyleSheet("""
            QLineEdit { background: #010d14; color: #d8f8ff; border: 1px solid #0d3347; border-radius: 4px; padding: 8px; }
            QLineEdit:focus { border-color: #00dcff; }
        """)
        self._input.setFont(_mono(10))
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)
        send = QPushButton("SEND")
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet("""
            QPushButton { background: #00dcff; color: #000; border: none; padding: 8px 14px; font-weight: bold; }
            QPushButton:hover { background: #00aacc; }
        """)
        send.clicked.connect(self._send)
        row.addWidget(send)
        lay.addLayout(row)

    def append_user(self, text: str) -> None:
        self._append_message("USER", text, "#d8f8ff", Qt.AlignmentFlag.AlignRight)

    def append_jarvis(self, text: str) -> None:
        self._append_message("JARVIS", text, "#ff0000", Qt.AlignmentFlag.AlignLeft)

    def stream_text(self, text: str) -> None:
        self._stream_queue.append(("JARVIS", text))
        if not self._streaming:
            self._streaming = True
            self._stream_timer.start(12)

    def _stream_step(self) -> None:
        if not self._stream_queue:
            self._stream_timer.stop()
            self._streaming = False
            return
        role, text = self._stream_queue[0]
        if not hasattr(self, "_stream_pos") or not hasattr(self, "_stream_role") or self._stream_role != role:
            self._stream_role = role
            self._stream_text = text
            self._stream_pos = 0
            self._history.moveCursor(QTextCursor.MoveOperation.End)
            self._history.setTextColor(QColor("#888888"))
            self._history.insertPlainText(f"\n{role}: ")
            self._history.moveCursor(QTextCursor.MoveOperation.End)
        if self._stream_pos < len(self._stream_text):
            ch = self._stream_text[self._stream_pos]
            color = "#ff0000" if role == "JARVIS" else "#d8f8ff"
            self._history.setTextColor(QColor(color))
            self._history.insertPlainText(ch)
            self._stream_pos += 1
            self._history.moveCursor(QTextCursor.MoveOperation.End)
        else:
            self._stream_queue.pop(0)
            delattr(self, "_stream_pos")
            delattr(self, "_stream_role")

    def _append_message(self, role: str, text: str, color: str, align: Qt.AlignmentFlag) -> None:
        self._history.moveCursor(QTextCursor.MoveOperation.End)
        self._history.setTextColor(QColor("#888888"))
        self._history.insertPlainText(f"\n{role}: ")
        self._history.setTextColor(QColor(color))
        self._history.insertPlainText(text)
        self._history.moveCursor(QTextCursor.MoveOperation.End)

    def _send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self.append_user(text)
        self.message_sent.emit(text)
        self._input.clear()


def _mono(size: int):
    from PyQt6.QtGui import QFont
    return QFont("Courier New", size)
