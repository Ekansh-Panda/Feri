
"""Main PyQt6 HUD application for JARVIS NEXUS — Stark OS."""

from __future__ import annotations

import platform
import subprocess
import threading
from pathlib import Path

import psutil

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .arc_reactor import ArcReactor
from .glass_panel import GlassPanel
from .hologram_view import HologramView
from .mission_control import MissionControl
from .waveform import WaveformWidget
from .approval_banner import ApprovalBanner
from .protocol_buttons import ProtocolButtons
from .telemetry_gauges import TelemetryGauges
from .neural_transcript import NeuralTranscript
from .global_surveillance import GlobalSurveillance
from .user_telemetry import UserTelemetry


class StarkHUD(QMainWindow):
    """Main HUD window for JARVIS NEXUS."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JARVIS NEXUS — Stark OS")
        self._visible = True
        self._setup_window()
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_telemetry_poll()
        self.showFullScreen()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        pal = QPalette()
        pal.setColor(QPalette.ColorRole.Window, QColor(0, 6, 10, 0))
        self.setPalette(pal)

    def _setup_ui(self) -> None:
        central = QWidget()
        central.setStyleSheet("background: rgba(0,6,10,30);")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("J.A.R.V.I.S   NEXUS")
        title.setStyleSheet("color: #00dcff; font-weight: bold; font-size: 18px; letter-spacing: 2px;")
        header.addWidget(title)
        header.addStretch()
        self._status = QLabel("ONLINE")
        self._status.setStyleSheet("color: #00ff88; font-weight: bold;")
        header.addWidget(self._status)
        root.addLayout(header)
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #0d3347; background: rgba(0,6,10,40); }
            QTabBar::tab { background: rgba(0,6,10,120); color: #5ab8cc; padding: 8px 18px; margin-right: 4px; border: 1px solid #0d3347; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: rgba(0,20,30,180); color: #00dcff; border-color: #1a5c7a; }
            QTabBar::tab:hover { color: #d8f8ff; }
        """)
        self._tabs = tabs
        self._build_tabs(tabs)
        root.addWidget(tabs)
        self._approval = ApprovalBanner(timeout_ms=30000)
        self._approval.approved.connect(lambda t: print(f"Approved: {t}"))
        self._approval.denied.connect(lambda t: print(f"Denied: {t}"))
        root.addWidget(self._approval)

    def _build_tabs(self, tabs: QTabWidget) -> None:
        arc_tab = QWidget()
        alay = QVBoxLayout(arc_tab)
        alay.addWidget(ArcReactor())
        alay.addWidget(WaveformWidget())
        tabs.addTab(arc_tab, "Arc Reactor")

        holo_tab = QWidget()
        hlay = QVBoxLayout(holo_tab)
        hlay.addWidget(HologramView())
        tabs.addTab(holo_tab, "Holo Workbench")

        mission_tab = QWidget()
        mlay = QVBoxLayout(mission_tab)
        self._mission_ctrl = MissionControl()
        self._mission_ctrl.load_missions([
            {"id": "m1", "name": "System Bootstrap", "status": "active", "progress": 72.0, "subtasks": [
                {"name": "Load drivers", "done": True}, {"name": "Init networks", "done": True},
                {"name": "Start daemons", "done": False}, {"name": "Verify integrity", "done": False},
            ]},
            {"id": "m2", "name": "Security Audit", "status": "pending", "progress": 15.0, "subtasks": [
                {"name": "Scan ports", "done": True}, {"name": "Check signatures", "done": False},
            ]},
        ])
        mlay.addWidget(self._mission_ctrl)
        tabs.addTab(mission_tab, "Mission Control")

        neural_tab = QWidget()
        nlay = QVBoxLayout(neural_tab)
        self._neural = NeuralTranscript()
        self._neural.message_sent.connect(lambda t: self._neural.stream_text(f"Processing: {t}"))
        nlay.addWidget(self._neural)
        tabs.addTab(neural_tab, "Neural Transcript")

        surveillance_tab = QWidget()
        slay = QVBoxLayout(surveillance_tab)
        slay.addWidget(GlobalSurveillance())
        tabs.addTab(surveillance_tab, "Global Surveillance")

        telemetry_tab = QWidget()
        tlay = QVBoxLayout(telemetry_tab)
        tlay.addWidget(TelemetryGauges())
        tlay.addWidget(UserTelemetry())
        tabs.addTab(telemetry_tab, "Telemetry")

        protocol_tab = QWidget()
        play = QVBoxLayout(protocol_tab)
        pb = ProtocolButtons()
        pb.status_update.connect(lambda n, s: print(f"Protocol {n}: {s}"))
        play.addWidget(pb)
        tabs.addTab(protocol_tab, "Protocols")

    def _setup_shortcuts(self) -> None:
        from PyQt6.QtGui import QShortcut
        from PyQt6.QtCore import Qt
        toggle = QShortcut(Qt.Key.Key_Super | Qt.Key.Key_J, self)
        toggle.activated.connect(self._toggle_visibility)

    def _toggle_visibility(self) -> None:
        if self._visible:
            self.hide()
            self._i3_scratchpad("show")
        else:
            self.showFullScreen()
            self._i3_scratchpad("hide")
        self._visible = not self._visible

    def _i3_scratchpad(self, action: str) -> None:
        def _run() -> None:
            try:
                subprocess.run(["i3-msg", f"scratchpad {action}"], capture_output=True, timeout=5)
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()

    def _setup_telemetry_poll(self) -> None:
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._update_telemetry)
        self._tmr.start(2000)

    def _update_telemetry(self) -> None:
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            self._status.setText(f"CPU {cpu:.0f}% | RAM {mem:.0f}%")
            color = "#00ff88"
            if cpu > 80 or mem > 80:
                color = "#ff3355"
            elif cpu > 60 or mem > 60:
                color = "#ffcc00"
            self._status.setStyleSheet(f"color: {color}; font-weight: bold;")
        except Exception:
            pass
