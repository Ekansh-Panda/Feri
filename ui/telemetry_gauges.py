
"""CPU/RAM/GPU/Temp telemetry gauges."""

from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class _Gauge(QWidget):
    """Circular gauge widget."""

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        self._label = label
        self._value = 0.0
        self.setMinimumSize(100, 100)

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(100.0, value))
        self.update()

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        r = min(W, H) / 2 - 10
        color = _color_for(self._value)
        pen = QPen(color, 8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(int(cx - r), int(cy - r), int(r * 2), int(r * 2), 0, int(360 * 16 * (self._value / 100.0)))
        bg_pen = QPen(QColor(13, 51, 71, 80), 8)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(bg_pen)
        p.drawArc(int(cx - r), int(cy - r), int(r * 2), int(r * 2), 0, int(360 * 16))
        p.setPen(QColor(143, 252, 255))
        p.setFont(_mono(10, True))
        p.drawText(int(cx - 30), int(cy + 4), f"{int(self._value)}%")
        p.setFont(_mono(8))
        p.setPen(QColor(90, 184, 204))
        p.drawText(int(cx - 25), int(cy + 18), self._label)
        p.end()


def _color_for(value: float) -> QColor:
    if value > 80:
        return QColor(255, 51, 85)
    if value > 60:
        return QColor(255, 204, 0)
    return QColor(0, 255, 136)


def _mono(size: int, bold: bool = False):
    from PyQt6.QtGui import QFont
    return QFont("Courier New", size, QFont.Weight.Bold if bold else QFont.Weight.Normal)


class TelemetryGauges(QWidget):
    """CPU/RAM/GPU/Temp circular gauge widgets."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._gauges: dict[str, _Gauge] = {}
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(16)
        for label in ["CPU", "RAM", "GPU", "TEMP"]:
            g = _Gauge(label)
            self._gauges[label] = g
            lay.addWidget(g)
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._poll)
        self._tmr.start(2000)
        self._poll()

    def _poll(self) -> None:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            self._gauges["CPU"].set_value(cpu)
            self._gauges["RAM"].set_value(mem)
        except Exception:
            pass
        try:
            import pynvml
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            self._gauges["GPU"].set_value(float(util.gpu))
        except Exception:
            self._gauges["GPU"].set_value(-1.0)
        try:
            temps = psutil.sensors_temperatures()
            for entries in temps.values():
                if entries:
                    self._gauges["TEMP"].set_value(min(100.0, entries[0].current))
                    break
            else:
                self._gauges["TEMP"].set_value(0.0)
        except Exception:
            self._gauges["TEMP"].set_value(0.0)
