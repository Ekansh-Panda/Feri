"""SentinelAgent — system health monitor with alerting."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.sentinel")


@dataclass
class HealthStatus:
    component: str = ""
    healthy: bool = True
    message: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "healthy": self.healthy,
            "message": self.message,
            "metrics": self.metrics,
        }


class SentinelAgent:
    """Monitors system health and alerts on anomalies."""

    def __init__(self, alert_command: str | None = None) -> None:
        self._alert_cmd = alert_command or self._default_alert_command()
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._history: list[dict[str, Any]] = []

    def check_system_health(self) -> dict[str, Any]:
        """Check CPU, RAM, disk, temperature, and battery.

        Returns:
            Dict with status per component.
        """
        results: dict[str, Any] = {"timestamp": time.time(), "components": {}}

        cpu = self._cpu_info()
        results["components"]["cpu"] = cpu.to_dict()

        mem = self._memory_info()
        results["components"]["memory"] = mem.to_dict()

        disk = self._disk_info()
        results["components"]["disk"] = disk.to_dict()

        thermal = self._thermal_info()
        results["components"]["thermal"] = thermal.to_dict()

        battery = self._battery_info()
        results["components"]["battery"] = battery.to_dict()

        overall = all(c.healthy for c in [cpu, mem, disk, thermal, battery] if c.component)
        results["overall_healthy"] = overall
        return results

    def check_service_health(self, service: str) -> dict[str, Any]:
        """Check systemd service status.

        Args:
            service: systemd unit name.

        Returns:
            Dict with service status.
        """
        if not self._systemd_available():
            return {"component": service, "healthy": False, "message": "systemd not available"}
        try:
            proc = subprocess.run(
                ["systemctl", "is-active", "--quiet", service],
                capture_output=True,
                text=True,
                timeout=10,
            )
            healthy = proc.returncode == 0
            status = HealthStatus(component=service, healthy=healthy, message="active" if healthy else "inactive")
            return status.to_dict()
        except Exception as exc:
            return {"component": service, "healthy": False, "message": str(exc)}

    def check_network_health(self) -> dict[str, Any]:
        """Check connectivity, DNS, and latency.

        Returns:
            Dict with network status.
        """
        components: dict[str, Any] = {}
        hosts = [("dns", "8.8.8.8"), ("internet", "1.1.1.1"), ("http", "https://www.google.com")]
        for name, target in hosts:
            try:
                if name == "http":
                    import urllib.request
                    req = urllib.request.Request(target, method="HEAD")
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        components[name] = {"healthy": resp.status == 200, "latency_ms": 0, "detail": f"HTTP {resp.status}"}
                else:
                    start = time.time()
                    if platform.system() == "Windows":
                        proc = subprocess.run(["ping", "-n", "1", "-w", "3000", target], capture_output=True, text=True, timeout=5)
                    else:
                        proc = subprocess.run(["ping", "-c", "1", "-W", "3", target], capture_output=True, text=True, timeout=5)
                    latency = (time.time() - start) * 1000
                    components[name] = {"healthy": proc.returncode == 0, "latency_ms": round(latency, 1), "detail": "reachable" if proc.returncode == 0 else "unreachable"}
            except Exception as exc:
                components[name] = {"healthy": False, "detail": str(exc)}

        healthy = all(c.get("healthy") for c in components.values()) if components else False
        return {"components": components, "overall_healthy": healthy}

    def detect_anomalies(self) -> list[dict[str, Any]]:
        """Detect unusual patterns in system metrics.

        Returns:
            List of anomaly dicts.
        """
        anomalies: list[dict[str, Any]] = []
        cpu = self._cpu_info()
        if cpu.metrics.get("usage_percent", 0) > 95:
            anomalies.append({"type": "cpu", "severity": "high", "message": "CPU usage > 95%"})

        mem = self._memory_info()
        if mem.metrics.get("percent", 0) > 95:
            anomalies.append({"type": "memory", "severity": "high", "message": "Memory usage > 95%"})

        thermal = self._thermal_info()
        for sensor, data in thermal.metrics.items():
            if isinstance(data, dict) and data.get("temp_c", 0) > 90:
                anomalies.append({"type": "thermal", "severity": "high", "message": f"{sensor} temp > 90C"})

        disk = self._disk_info()
        for mount, data in disk.metrics.items():
            if isinstance(data, dict) and data.get("percent", 0) > 95:
                anomalies.append({"type": "disk", "severity": "medium", "message": f"{mount} disk > 95%"})

        return anomalies

    def alert(self, level: str, message: str) -> None:
        """Send a desktop notification and log the alert.

        Args:
            level: Alert level (info|warning|critical).
            message: Alert message.
        """
        record = {"level": level, "message": message, "timestamp": time.time()}
        self._history.append(record)
        if len(self._history) > 1000:
            self._history = self._history[-1000:]

        log_fn = {"info": logger.info, "warning": logger.warning, "critical": logger.critical}.get(level, logger.info)
        log_fn("ALERT [%s]: %s", level, message)

        try:
            subprocess.run(
                ["notify-send", "-u", level, "JARVIS Sentinel", message],
                capture_output=True,
                timeout=5,
            )
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.warning("notify-send failed: %s", exc)

    def daemon_mode(self, interval: int = 60) -> None:
        """Run periodic health checks.

        Args:
            interval: Seconds between checks.
        """
        self._running = True
        self._stop_event.clear()
        while not self._stop_event.is_set():
            try:
                health = self.check_system_health()
                anomalies = self.detect_anomalies()
                for a in anomalies:
                    self.alert(a["severity"], a["message"])
            except Exception as exc:
                logger.error("Sentinel daemon error: %s", exc)
            self._stop_event.wait(interval)

    def stop_daemon(self) -> str:
        """Stop the daemon loop.

        Returns:
            Status string.
        """
        self._stop_event.set()
        self._running = False
        return "Sentinel daemon stopped."

    # -- helpers --

    def _default_alert_command(self) -> str:
        return "notify-send -u {level} 'JARVIS Sentinel' '{message}'"

    def _cpu_info(self) -> HealthStatus:
        try:
            if platform.system() == "Windows":
                return self._cpu_info_windows()
            if platform.system() == "Darwin":
                return self._cpu_info_darwin()
            return self._cpu_info_linux()
        except Exception as exc:
            return HealthStatus(component="cpu", healthy=False, message=str(exc))

    def _cpu_info_linux(self) -> HealthStatus:
        usage = 0.0
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                parts = f.readline().split()
            idle = int(parts[4])
            total = sum(int(p) for p in parts[1:])
            usage = round((1 - idle / total) * 100, 1) if total else 0.0
        except Exception:
            pass
        try:
            count = os.cpu_count() or 1
            freq = 0.0
            freq_file = Path("/proc/cpuinfo")
            if freq_file.exists():
                text = freq_file.read_text(encoding="utf-8", errors="replace")
                m = re_search = None  # noqa: F841
                for line in text.splitlines():
                    if "cpu MHz" in line:
                        try:
                            freq = float(line.split(":")[1].strip())
                        except Exception:
                            pass
                        break
            return HealthStatus(component="cpu", healthy=usage < 95, message=f"{usage}% used, {count} cores", metrics={"usage_percent": usage, "cores": count, "mhz": freq})
        except Exception as exc:
            return HealthStatus(component="cpu", healthy=True, message=str(exc), metrics={"usage_percent": usage})

    def _cpu_info_darwin(self) -> HealthStatus:
        try:
            proc = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=5)
            brand = proc.stdout.strip()
            proc = subprocess.run(["sysctl", "-n", "hw.ncpu"], capture_output=True, text=True, timeout=5)
            cores = int(proc.stdout.strip() or 1)
            return HealthStatus(component="cpu", healthy=True, message=brand, metrics={"brand": brand, "cores": cores})
        except Exception as exc:
            return HealthStatus(component="cpu", healthy=False, message=str(exc))

    def _cpu_info_windows(self) -> HealthStatus:
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "(Get-WmiObject Win32_Processor).LoadPercentage"],
                capture_output=True, text=True, timeout=5
            )
            usage = float(proc.stdout.strip() or 0)
            return HealthStatus(component="cpu", healthy=usage < 95, message=f"{usage}% used", metrics={"usage_percent": usage})
        except Exception as exc:
            return HealthStatus(component="cpu", healthy=False, message=str(exc))

    def _memory_info(self) -> HealthStatus:
        try:
            import psutil
            mem = psutil.virtual_memory()
            healthy = mem.percent < 95
            return HealthStatus(component="memory", healthy=healthy, message=f"{mem.percent}% used", metrics={
                "total_bytes": mem.total, "available_bytes": mem.available, "percent": mem.percent,
            })
        except Exception as exc:
            return HealthStatus(component="memory", healthy=False, message=str(exc))

    def _disk_info(self) -> HealthStatus:
        try:
            import psutil
            parts = psutil.disk_partitions(all=False)
            mounts: dict[str, Any] = {}
            healthy = True
            for part in parts:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    if usage.percent > 95:
                        healthy = False
                    mounts[part.mountpoint] = {"total_bytes": usage.total, "used_bytes": usage.used, "percent": usage.percent}
                except Exception:
                    continue
            return HealthStatus(component="disk", healthy=healthy, message=f"{len(mounts)} partitions", metrics=mounts)
        except Exception as exc:
            return HealthStatus(component="disk", healthy=False, message=str(exc))

    def _thermal_info(self) -> HealthStatus:
        try:
            import psutil
            sensors = psutil.sensors_temperatures()
            metrics: dict[str, Any] = {}
            healthy = True
            for name, entries in sensors.items():
                for entry in entries:
                    val = entry.current
                    if val > 90:
                        healthy = False
                    metrics[f"{name}_{entry.label or 'unknown'}"] = {"temp_c": val, "high": entry.high, "critical": entry.critical}
            return HealthStatus(component="thermal", healthy=healthy, message=f"{len(metrics)} sensors", metrics=metrics)
        except Exception as exc:
            return HealthStatus(component="thermal", healthy=True, message=str(exc))

    def _battery_info(self) -> HealthStatus:
        try:
            import psutil
            batt = psutil.sensors_battery()
            if batt is None:
                return HealthStatus(component="battery", healthy=True, message="No battery (desktop)")
            healthy = batt.percent > 10 or batt.power_plugged
            return HealthStatus(component="battery", healthy=healthy, message=f"{batt.percent}% {'plugged' if batt.power_plugged else 'battery'}", metrics={"percent": batt.percent, "power_plugged": batt.power_plugged, "secs_left": batt.secsleft})
        except Exception as exc:
            return HealthStatus(component="battery", healthy=True, message=str(exc))

    def _systemd_available(self) -> bool:
        return Path("/run/systemd/system").exists() or shutil.which("systemctl") is not None
