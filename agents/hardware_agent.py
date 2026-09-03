"""HardwareAgent — /sys, /proc, sensors, GPU, undervolt control."""

from __future__ import annotations

import logging
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.hardware")


class HardwareAgent:
    """Reads and controls hardware via sysfs, /proc, and native utilities."""

    def full_telemetry(self) -> dict[str, Any]:
        """Collect all hardware telemetry.

        Returns:
            Dict with cpu, memory, gpu, thermal, disk, battery, usb info.
        """
        return {
            "cpu": self.cpu_info(),
            "memory": self.memory_info(),
            "gpu": self.gpu_info(),
            "thermal": self.thermal_info(),
            "disk": self.disk_info(),
            "battery": self.battery_info(),
            "usb": self.usb_info(),
        }

    def cpu_info(self) -> dict[str, Any]:
        """CPU info from /proc/cpuinfo and usage.

        Returns:
            Dict with CPU details.
        """
        info: dict[str, Any] = {"model": "unknown", "cores": 0, "usage_percent": 0.0}
        try:
            cpuinfo = Path("/proc/cpuinfo")
            if cpuinfo.exists():
                text = cpuinfo.read_text(encoding="utf-8", errors="replace")
                for line in text.splitlines():
                    if line.startswith("model name"):
                        info["model"] = line.split(":", 1)[1].strip()
                        break
                info["cores"] = len([l for l in text.splitlines() if l.startswith("processor")])
        except Exception as exc:
            logger.warning("cpu_info failed: %s", exc)
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                parts = f.readline().split()
            idle = int(parts[4])
            total = sum(int(p) for p in parts[1:])
            info["usage_percent"] = round((1 - idle / total) * 100, 1) if total else 0.0
        except Exception:
            pass
        return info

    def memory_info(self) -> dict[str, Any]:
        """Memory info from /proc/meminfo.

        Returns:
            Dict with RAM details.
        """
        info: dict[str, Any] = {"total_bytes": 0, "available_bytes": 0, "percent": 0.0}
        try:
            meminfo = Path("/proc/meminfo")
            if meminfo.exists():
                text = meminfo.read_text(encoding="utf-8")
                vals = {}
                for line in text.splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        vals[key] = int(parts[1]) * 1024
                total = vals.get("MemTotal", 0)
                avail = vals.get("MemAvailable", vals.get("MemFree", 0))
                info["total_bytes"] = total
                info["available_bytes"] = avail
                info["percent"] = round((1 - avail / total) * 100, 1) if total else 0.0
        except Exception as exc:
            logger.warning("memory_info failed: %s", exc)
        return info

    def gpu_info(self) -> dict[str, Any]:
        """GPU info from nvidia-smi or /sys.

        Returns:
            Dict with GPU details.
        """
        info: dict[str, Any] = {"vendor": "unknown", "model": "unknown", "memory_used_mb": 0, "memory_total_mb": 0, "temperature_c": 0}
        if shutil.which("nvidia-smi"):
            try:
                proc = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,temperature.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=10
                )
                parts = [p.strip() for p in proc.stdout.split(",")]
                if len(parts) >= 4:
                    info["vendor"] = "nvidia"
                    info["model"] = parts[0]
                    info["memory_used_mb"] = int(parts[1])
                    info["memory_total_mb"] = int(parts[2])
                    info["temperature_c"] = int(parts[3])
                    return info
            except Exception as exc:
                logger.warning("nvidia-smi failed: %s", exc)

        amdgpu = Path("/sys/class/drm/card0/device/vendor")
        if amdgpu.exists():
            try:
                vendor = amdgpu.read_text(encoding="utf-8", errors="replace").strip()
                info["vendor"] = vendor
            except Exception:
                pass
        return info

    def thermal_info(self) -> dict[str, Any]:
        """Thermal sensors from /sys/class/thermal or lm-sensors.

        Returns:
            Dict with thermal readings.
        """
        zones: dict[str, Any] = {}
        thermal_dir = Path("/sys/class/thermal")
        if thermal_dir.exists():
            for zone in thermal_dir.glob("thermal_zone*"):
                try:
                    temp_raw = (zone / "temp").read_text(encoding="utf-8", errors="replace").strip()
                    temp_c = round(int(temp_raw) / 1000.0, 1) if temp_raw.isdigit() else 0.0
                    type_name = (zone / "type").read_text(encoding="utf-8", errors="replace").strip() if (zone / "type").exists() else zone.name
                    zones[type_name] = {"temp_c": temp_c}
                except Exception:
                    continue
        if not zones and shutil.which("sensors"):
            try:
                proc = subprocess.run(["sensors"], capture_output=True, text=True, timeout=10)
                for line in proc.stdout.splitlines():
                    if "°C" in line:
                        m = re.search(r"([A-Za-z0-9_]+):\s*\+?([\d.]+)°C", line)
                        if m:
                            zones[m.group(1)] = {"temp_c": float(m.group(2))}
            except Exception as exc:
                logger.warning("sensors failed: %s", exc)
        return zones

    def disk_info(self) -> dict[str, Any]:
        """Disk info from lsblk and /sys.

        Returns:
            Dict with disk details.
        """
        disks: dict[str, Any] = {}
        try:
            proc = subprocess.run(["lsblk", "-d", "-o", "NAME,SIZE,TYPE,MODEL", "-n"], capture_output=True, text=True, timeout=10)
            for line in proc.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[2] == "disk":
                    disks[parts[0]] = {"size": parts[1], "model": parts[3] if len(parts) > 3 else ""}
        except Exception as exc:
            logger.warning("lsblk failed: %s", exc)
        return disks

    def battery_info(self) -> dict[str, Any]:
        """Battery info from /sys/class/power_supply.

        Returns:
            Dict with battery details.
        """
        info: dict[str, Any] = {"present": False}
        ps_dir = Path("/sys/class/power_supply")
        if not ps_dir.exists():
            return info
        for entry in ps_dir.iterdir():
            if "BAT" not in entry.name.upper():
                continue
            try:
                cap = (entry / "capacity").read_text(encoding="utf-8", errors="replace").strip()
                status = (entry / "status").read_text(encoding="utf-8", errors="replace").strip()
                info = {
                    "present": True,
                    "name": entry.name,
                    "capacity_percent": int(cap) if cap.isdigit() else 0,
                    "status": status,
                }
                return info
            except Exception:
                continue
        return info

    def usb_info(self) -> dict[str, Any]:
        """USB device list from lsusb.

        Returns:
            Dict with USB devices.
        """
        devices: list[str] = []
        try:
            proc = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=10)
            devices = [line for line in proc.stdout.splitlines() if line.strip()]
        except Exception as exc:
            logger.warning("lsusb failed: %s", exc)
        return {"count": len(devices), "devices": devices}

    def set_gpu_fan(self, speed_pct: int) -> dict[str, Any]:
        """Set NVIDIA GPU fan speed.

        Args:
            speed_pct: Fan speed percentage (0-100).

        Returns:
            Dict with status.
        """
        if not shutil.which("nvidia-smi"):
            return {"status": "error", "error": "nvidia-smi not found"}
        speed = max(0, min(100, speed_pct))
        try:
            proc = subprocess.run(
                ["nvidia-smi", "-pm", "1", "-pl", "250", f"-fan", str(speed)],
                capture_output=True, text=True, timeout=10
            )
            return {"status": "ok" if proc.returncode == 0 else "error", "speed_pct": speed, "stderr": proc.stderr}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def undervolt_cpu(self, offset_mv: int) -> dict[str, Any]:
        """Apply Intel CPU undervolt offset.

        Args:
            offset_mv: Millivolt offset (negative values reduce voltage).

        Returns:
            Dict with status.
        """
        if not shutil.which("intel-undervolt"):
            return {"status": "error", "error": "intel-undervolt not found"}
        try:
            subprocess.run(["intel-undervolt", "apply"], capture_output=True, text=True, timeout=10)
            return {"status": "ok", "offset_mv": offset_mv}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def get_kernel_logs(self, lines: int = 50) -> dict[str, Any]:
        """Read kernel logs from dmesg.

        Args:
            lines: Number of lines to read.

        Returns:
            Dict with log lines.
        """
        try:
            proc = subprocess.run(["dmesg", "-T", "-l", str(lines)], capture_output=True, text=True, timeout=10)
            log_lines = [l for l in proc.stdout.splitlines() if l.strip()]
            return {"lines": log_lines, "count": len(log_lines), "status": "ok"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def flush_ram_cache(self) -> dict[str, Any]:
        """Flush filesystem caches from RAM (requires root).

        Returns:
            Dict with status.
        """
        try:
            with open("/proc/sys/vm/drop_caches", "w", encoding="utf-8") as f:
                f.write("3\n")
            return {"status": "ok", "message": "Pagecache, dentries, and inodes flushed"}
        except PermissionError:
            return {"status": "error", "error": "Permission denied. Run with sudo."}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def load_kernel_module(self, mod: str) -> dict[str, Any]:
        """Load a kernel module via modprobe.

        Args:
            mod: Module name.

        Returns:
            Dict with status.
        """
        try:
            proc = subprocess.run(["modprobe", mod], capture_output=True, text=True, timeout=10)
            return {"status": "ok" if proc.returncode == 0 else "error", "module": mod, "stderr": proc.stderr}
        except FileNotFoundError:
            return {"status": "error", "error": "modprobe not found"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
