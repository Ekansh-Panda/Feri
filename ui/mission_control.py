
"""Mission dashboard widget."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class MissionControl(QWidget):
    """Mission dashboard with progress bars and subtask status."""

    expanded = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._missions: list[dict] = []
        self._expanded: dict[str, bool] = {}
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def load_missions(self, missions: list[dict]) -> None:
        self._missions = missions
        self._render()

    def _render(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for m in self._missions:
            card = self._build_card(m)
            self._layout.addWidget(card)
        self._layout.addStretch()

    def _build_card(self, m: dict) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame { background: rgba(0,6,10,180); border: 1px solid #0d3347; border-radius: 8px; }
            QFrame:hover { border-color: #1a5c7a; }
        """)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        name = m.get("name", m.get("id", "Mission"))
        status = m.get("status", "pending")
        progress = float(m.get("progress", 0.0))
        header = QHBoxLayout()
        title = QLabel(name)
        title.setStyleSheet("color: #00dcff; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        st_lbl = QLabel(status.upper())
        st_lbl.setStyleSheet(f"color: {_status_color(status)}; font-size: 11px;")
        header.addWidget(st_lbl)
        lay.addLayout(header)
        pb = QProgressBar()
        pb.setRange(0, 100)
        pb.setValue(int(progress))
        pb.setTextVisible(True)
        pb.setFormat(f"{int(progress)}%")
        pb.setStyleSheet("""
            QProgressBar { background: #010d14; border: 1px solid #0d3347; border-radius: 4px; height: 10px; }
            QProgressBar::chunk { background: #00dcff; border-radius: 4px; }
        """)
        lay.addWidget(pb)
        subtasks = m.get("subtasks", [])
        if subtasks:
            toggle = QPushButton("Expand ▼")
            toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle.setStyleSheet("""
                QPushButton { background: transparent; color: #5ab8cc; border: none; text-align: left; padding: 2px; }
                QPushButton:hover { color: #00dcff; }
            """)
            toggle.clicked.connect(lambda _, n=name, b=toggle: self._toggle_subtasks(n, b, subtasks, lay))
            lay.addWidget(toggle)
            if self._expanded.get(name):
                self._add_subtasks(lay, subtasks)
        return frame

    def _add_subtasks(self, lay: QVBoxLayout, subtasks: list[dict]) -> None:
        for st in subtasks:
            row = QHBoxLayout()
            icon = "✔" if st.get("done") else "◌"
            color = "#00ff88" if st.get("done") else "#ff3355"
            lbl = QLabel(f"{icon} {st.get('name', st.get('title', 'subtask'))}")
            lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
            row.addWidget(lbl)
            row.addStretch()
            lay.addLayout(row)

    def _toggle_subtasks(self, name: str, btn: QPushButton, subtasks: list[dict], lay: QVBoxLayout) -> None:
        expanded = self._expanded.get(name, False)
        self._expanded[name] = not expanded
        btn.setText("Collapse ▲" if not expanded else "Expand ▼")
        if not expanded:
            self._add_subtasks(lay, subtasks)
        else:
            self._render()

    def update_mission(self, mission_id: str, data: dict) -> None:
        for m in self._missions:
            if m.get("id") == mission_id:
                m.update(data)
                self._render()
                break


def _status_color(status: str) -> str:
    s = status.lower()
    if s in ("completed", "done", "success"):
        return "#00ff88"
    if s in ("running", "active"):
        return "#ffcc00"
    if s in ("failed", "error"):
        return "#ff3355"
    return "#5ab8cc"
