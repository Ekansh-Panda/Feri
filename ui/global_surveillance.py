
"""Global surveillance panel: airspace, weather, seismic, network."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from PyQt6.QtCore import QMetaObject, QTimer, Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class GlobalSurveillance(QWidget):
    """Airspace, weather, seismic, network panel with auto-refresh."""

    def __init__(self, parent=None, refresh_sec: int = 30) -> None:
        super().__init__(parent)
        self._refresh_sec = refresh_sec
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self.refresh_all)
        self._tmr.start(refresh_sec * 1000)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        top = QHBoxLayout()
        top.addWidget(QLabel("🌐  GLOBAL SURVEILLANCE"))
        top.addStretch()
        refresh = QPushButton("Refresh")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.clicked.connect(self.refresh_all)
        top.addWidget(refresh)
        lay.addLayout(top)
        self._airspace = QTextEdit()
        self._weather = QTextEdit()
        self._seismic = QTextEdit()
        self._network = QTextEdit()
        for title, widget in [
            ("✈  Airspace (OpenSky)", self._airspace),
            ("☁  Weather (wttr.in)", self._weather),
            ("🌍  Seismic (USGS)", self._seismic),
            ("🌐  Network", self._network),
        ]:
            card = QWidget()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(8, 6, 8, 6)
            hdr = QLabel(title)
            hdr.setStyleSheet("color: #00dcff; font-weight: bold; font-size: 12px;")
            cl.addWidget(hdr)
            widget.setReadOnly(True)
            widget.setStyleSheet("""
                QTextEdit { background: rgba(0,6,10,180); color: #8ffcff; border: 1px solid #0d3347; border-radius: 4px; padding: 6px; font-size: 11px; }
            """)
            cl.addWidget(widget)
            lay.addWidget(card)
        threading.Thread(target=self.refresh_all, daemon=True).start()

    def refresh_all(self) -> None:
        threading.Thread(target=self._update_airspace, daemon=True).start()
        threading.Thread(target=self._update_weather, daemon=True).start()
        threading.Thread(target=self._update_seismic, daemon=True).start()
        threading.Thread(target=self._update_network, daemon=True).start()

    def _update_airspace(self) -> None:
        try:
            import requests
            r = requests.get("https://opensky-network.org/api/states/all", timeout=10)
            data = r.json()
            states = data.get("states", [])[:20]
            lines = [f"{s[1]}  {s[2]}  alt:{s[7]}  spd:{s[9]}  hdg:{s[10]}" for s in states]
            self._set_text(self._airspace, "\n".join(lines) if lines else "No data")
        except Exception as e:
            self._set_text(self._airspace, f"Error: {e}")

    def _update_weather(self) -> None:
        try:
            import requests
            r = requests.get("https://wttr.in/?format=3", timeout=10)
            self._set_text(self._weather, r.text.strip())
        except Exception as e:
            self._set_text(self._weather, f"Error: {e}")

    def _update_seismic(self) -> None:
        try:
            import requests
            r = requests.get(
                "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
                timeout=10,
            )
            data = r.json()
            quakes = data.get("features", [])[:10]
            lines = [
                f"Mag {q['properties']['mag']:.1f} — {q['properties']['place']} ({datetime.fromtimestamp(q['properties']['time']/1000, tz=timezone.utc).strftime('%H:%M UTC')})"
                for q in quakes
            ]
            self._set_text(self._seismic, "\n".join(lines) if lines else "No quakes")
        except Exception as e:
            self._set_text(self._seismic, f"Error: {e}")

    def _update_network(self) -> None:
        try:
            import socket
            host = socket.gethostname()
            ip = socket.gethostbyname(host)
            lines = [f"Host: {host}", f"IP: {ip}", f"Updated: {datetime.now().strftime('%H:%M:%S')}"]
            self._set_text(self._network, "\n".join(lines))
        except Exception as e:
            self._set_text(self._network, f"Error: {e}")

    def _set_text(self, widget: QTextEdit, text: str) -> None:
        widget.setText(text)
