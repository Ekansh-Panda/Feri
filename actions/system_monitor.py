"""
system_monitor.py — /proc, /sys, psutil and ps telemetry for JARVIS NEXUS.

Class API:  `SystemMonitor` — exposes get_cpu_usage, get_memory_usage,
get_disk_usage, get_network_stats, get_thermal, get_battery,
get_process_list, get_system_status, and a daemon mode.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import psutil


_IS_LINUX = platform.system() == "Linux"


# ── /proc helpers ───────────────────────────────────────────────────────────

def _read_proc(path: str) -> Optional[str]:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def _read_proc_int(path: str, default: int = 0) -> int:
    val = _read_proc(path)
    if val is None:
        return default
    try:
        return int(val.strip().split()[0])
    except Exception:
        return default


@dataclass
class CpuSnapshot:
    percent: float
    cores: list[float] = field(default_factory=list)
    load1: float = 0.0
    load5: float = 0.0
    load15: float = 0.0
    freq_mhz: float = 0.0
    logical_cores: int = 0
    physical_cores: int = 0


@dataclass
class MemSnapshot:
    total: int
    used: int
    free: int
    available: int
    percent: float
    swap_total: int
    swap_used: int
    swap_percent: float


@dataclass
class DiskSnapshot:
    mount: str
    device: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float


@dataclass
class NetSnapshot:
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int
    per_interface: dict[str, dict[str, int]] = field(default_factory=dict)


@dataclass
class ThermalSnapshot:
    cpu_temp_c: Optional[float] = None
    gpu_temp_c: Optional[float] = None
    fan_rpm: Optional[int] = None
    zones: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BatterySnapshot:
    available: bool
    batteries: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ProcessInfo:
    pid: int
    name: str
    username: str
    cpu_percent: float
    mem_percent: float
    status: str
    create_time: float


class SystemMonitor:
    """Linux-first telemetry source built on /proc, /sys, psutil and ps."""

    DEFAULT_THRESHOLDS = {
        "cpu":  90.0,
        "ram":  90.0,
        "temp": 85.0,
        "gpu":  95.0,
        "disk": 90.0,
    }

    def __init__(self, thresholds: Optional[dict[str, float]] = None):
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._last_alert: dict[str, float] = {}
        self._cpu_streak = 0
        self._cooldown = 300.0
        self._daemon_thread: Optional[threading.Thread] = None
        self._daemon_stop = threading.Event()
        self._daemon_cb: Optional[Callable[[dict], None]] = None

    # ── CPU ────────────────────────────────────────────────────────────────

    def get_cpu_usage(self) -> CpuSnapshot:
        per = psutil.cpu_percent(interval=0.0, percpu=True)
        overall = sum(per) / len(per) if per else psutil.cpu_percent(interval=0.0)
        load1, load5, load15 = 0.0, 0.0, 0.0
        if _IS_LINUX:
            try:
                with open("/proc/loadavg") as f:
                    parts = f.read().split()
                load1, load5, load15 = float(parts[0]), float(parts[1]), float(parts[2])
            except Exception:
                pass
        freq = 0.0
        try:
            f = psutil.cpu_freq()
            if f:
                freq = f.current
        except Exception:
            pass
        return CpuSnapshot(
            percent=round(float(overall), 1),
            cores=[round(float(c), 1) for c in per],
            load1=load1, load5=load5, load15=load15,
            freq_mhz=round(freq, 1),
            logical_cores=psutil.cpu_count(logical=True) or 0,
            physical_cores=psutil.cpu_count(logical=False) or 0,
        )

    # ── Memory ─────────────────────────────────────────────────────────────

    def get_memory_usage(self) -> MemSnapshot:
        vm = psutil.virtual_memory()
        sw = psutil.swap_memory()
        return MemSnapshot(
            total=vm.total, used=vm.used, free=vm.free,
            available=vm.available, percent=round(vm.percent, 1),
            swap_total=sw.total, swap_used=sw.used,
            swap_percent=round(sw.percent, 1),
        )

    # ── Disk ───────────────────────────────────────────────────────────────

    def get_disk_usage(self, path: str = "/") -> DiskSnapshot:
        du = psutil.disk_usage(path)
        # Best-effort device/fstype detection
        device, fstype = "", ""
        try:
            for part in psutil.disk_partitions(all=False):
                if path.startswith(part.mountpoint):
                    device, fstype = part.device, part.fstype
                    break
        except Exception:
            pass
        return DiskSnapshot(
            mount=path, device=device, fstype=fstype,
            total=du.total, used=du.used, free=du.free,
            percent=round(du.percent, 1),
        )

    # ── Network ────────────────────────────────────────────────────────────

    def get_network_stats(self) -> NetSnapshot:
        nio = psutil.net_io_counters(pernic=True)
        per_iface = {
            name: {
                "bytes_sent": s.bytes_sent, "bytes_recv": s.bytes_recv,
                "packets_sent": s.packets_sent, "packets_recv": s.packets_recv,
                "errin": s.errin, "errout": s.errout,
                "dropin": s.dropin, "dropout": s.dropout,
            }
            for name, s in nio.items()
        }
        tot = psutil.net_io_counters(pernic=False)
        return NetSnapshot(
            bytes_sent=tot.bytes_sent, bytes_recv=tot.bytes_recv,
            packets_sent=tot.packets_sent, packets_recv=tot.packets_recv,
            errin=tot.errin, errout=tot.errout,
            dropin=tot.dropin, dropout=tot.dropout,
            per_interface=per_iface,
        )

    # ── Thermal ────────────────────────────────────────────────────────────

    def get_thermal(self) -> ThermalSnapshot:
        snap = ThermalSnapshot()
        try:
            sensors = psutil.sensors_temperatures(fahrenheit=False)
            for name, entries in sensors.items():
                if not entries:
                    continue
                entry = entries[0]
                snap.zones.append({
                    "name": name, "label": entry.label or name,
                    "current_c": entry.current, "high_c": entry.high,
                    "critical_c": entry.critical,
                })
            cpu_keys = ("coretemp", "k10temp", "cpu_thermal", "acpitz",
                        "cpu-thermal", "zenpower", "it8688", "cpu")
            for k in cpu_keys:
                if k in sensors and sensors[k]:
                    snap.cpu_temp_c = sensors[k][0].current
                    break
            if snap.cpu_temp_c is None and snap.zones:
                snap.cpu_temp_c = snap.zones[0]["current_c"]
        except Exception:
            pass

        # GPU temp via nvidia-smi
        if shutil.which("nvidia-smi"):
            try:
                r = subprocess.run(
                    ["nvidia-smi", "--query-gpu=temperature.gpu",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=4,
                )
                if r.returncode == 0 and r.stdout.strip():
                    snap.gpu_temp_c = float(r.stdout.strip().splitlines()[0])
            except Exception:
                pass

        # Fan rpm
        try:
            fans = psutil.sensors_fans()
            for entries in fans.values():
                if entries:
                    snap.fan_rpm = int(entries[0].current)
                    break
        except Exception:
            pass
        return snap

    # ── Battery ────────────────────────────────────────────────────────────

    def get_battery(self) -> BatterySnapshot:
        snap = BatterySnapshot(available=False)
        if not _IS_LINUX:
            try:
                batt = psutil.sensors_battery()
                if batt is not None:
                    snap.available = True
                    snap.batteries.append({
                        "name": "psutil",
                        "status": "Discharging" if batt.power_plugged is False else "Charging",
                        "capacity": int(batt.percent),
                        "secs_left": batt.secsleft,
                    })
            except Exception:
                pass
            return snap

        base = Path("/sys/class/power_supply")
        if not base.exists():
            return snap
        snap.available = True
        for entry in base.iterdir():
            try:
                typ = (entry / "type").read_text().strip()
            except Exception:
                continue
            if typ != "Battery":
                continue
            def _r(name: str) -> str:
                try:
                    return (entry / name).read_text().strip()
                except Exception:
                    return ""
            try:
                capacity = int(_r("capacity"))
            except Exception:
                capacity = -1
            try:
                energy_now = int(_r("energy_now"))
            except Exception:
                energy_now = -1
            try:
                power_now = int(_r("power_now"))
            except Exception:
                power_now = -1
            snap.batteries.append({
                "name": entry.name,
                "status": _r("status"),
                "capacity": capacity,
                "energy_now": energy_now,
                "power_now": power_now,
            })
        return snap

    # ── Process list ───────────────────────────────────────────────────────

    def get_process_list(self, sort_by: str = "cpu", limit: int = 50) -> list[ProcessInfo]:
        sort_key = {
            "cpu": lambda p: p.cpu_percent,
            "mem": lambda p: p.mem_percent,
            "pid": lambda p: p.pid,
            "name": lambda p: p.name.lower(),
        }.get(sort_by, lambda p: p.cpu_percent)

        procs: list[ProcessInfo] = []
        attrs = ["pid", "name", "username", "cpu_percent",
                 "memory_percent", "status", "create_time"]
        for p in psutil.process_iter(attrs, ad_value=None):
            try:
                info = p.info
                procs.append(ProcessInfo(
                    pid=int(info.get("pid") or 0),
                    name=(info.get("name") or "")[:80],
                    username=info.get("username") or "",
                    cpu_percent=float(info.get("cpu_percent") or 0.0),
                    mem_percent=float(info.get("memory_percent") or 0.0),
                    status=info.get("status") or "",
                    create_time=float(info.get("create_time") or 0.0),
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=sort_key, reverse=(sort_by in ("cpu", "mem", "pid")))
        return procs[:limit]

    # ── Combined status ────────────────────────────────────────────────────

    def get_system_status(self) -> dict:
        cpu = self.get_cpu_usage()
        mem = self.get_memory_usage()
        try:
            disk = self.get_disk_usage("/")
        except Exception:
            disk = None
        net = self.get_network_stats()
        therm = self.get_thermal()
        batt = self.get_battery()

        return {
            "cpu": asdict(cpu),
            "memory": asdict(mem),
            "disk": asdict(disk) if disk else None,
            "network": asdict(net),
            "thermal": asdict(therm),
            "battery": asdict(batt),
            "ts": time.time(),
        }

    # ── Daemon mode ────────────────────────────────────────────────────────

    def start_daemon(
        self,
        callback: Callable[[dict], None],
        interval: int = 30,
    ) -> None:
        """Continuously call callback(system_status) every `interval` seconds."""
        if self._daemon_thread and self._daemon_thread.is_alive():
            return
        self._daemon_cb = callback
        self._daemon_stop.clear()

        def _loop():
            while not self._daemon_stop.is_set():
                try:
                    if self._daemon_cb:
                        self._daemon_cb(self.get_system_status())
                except Exception as e:
                    print(f"[SystemMonitor] daemon tick error: {e}")
                self._daemon_stop.wait(interval)

        self._daemon_thread = threading.Thread(
            target=_loop, name="SystemMonitor-Daemon", daemon=True
        )
        self._daemon_thread.start()

    def stop_daemon(self) -> None:
        self._daemon_stop.set()

    # ── Alert gate (legacy) ────────────────────────────────────────────────

    def check(self) -> Optional[str]:
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            temp_obj = self.get_thermal()
            temp = temp_obj.cpu_temp_c or 0.0
        except Exception:
            return None

        alerts: list[str] = []
        if cpu >= self.thresholds["cpu"]:
            self._cpu_streak += 1
            if self._cpu_streak >= 3 and self._can_alert("cpu"):
                alerts.append(f"[SYSTEM_ALERT] CPU usage is critically high ({cpu:.0f}%).")
                self._record("cpu")
                self._cpu_streak = 0
        else:
            self._cpu_streak = 0
        if ram >= self.thresholds["ram"] and self._can_alert("ram"):
            alerts.append(f"[SYSTEM_ALERT] RAM is at {ram:.0f}%.")
            self._record("ram")
        if temp and temp >= self.thresholds["temp"] and self._can_alert("temp"):
            alerts.append(f"[SYSTEM_ALERT] CPU temperature is {temp:.0f}°C.")
            self._record("temp")
        return " ".join(alerts) if alerts else None

    def _can_alert(self, key: str) -> bool:
        return (time.monotonic() - self._last_alert.get(key, 0)) > self._cooldown

    def _record(self, key: str) -> None:
        self._last_alert[key] = time.monotonic()


# ── Module-level convenience (legacy callers) ───────────────────────────────

_instance: Optional[SystemMonitor] = None


def _get_instance() -> SystemMonitor:
    global _instance
    if _instance is None:
        _instance = SystemMonitor()
    return _instance


def get_system_status() -> dict:
    return _get_instance().get_system_status()


def get_cpu_usage() -> dict:
    return asdict(_get_instance().get_cpu_usage())


def get_memory_usage() -> dict:
    return asdict(_get_instance().get_memory_usage())


def get_disk_usage(path: str = "/") -> dict:
    return asdict(_get_instance().get_disk_usage(path))


def get_network_stats() -> dict:
    return asdict(_get_instance().get_network_stats())


def get_thermal() -> dict:
    return asdict(_get_instance().get_thermal())


def get_battery() -> dict:
    return asdict(_get_instance().get_battery())


def get_process_list(sort_by: str = "cpu", limit: int = 50) -> list[dict]:
    return [asdict(p) for p in _get_instance().get_process_list(sort_by, limit)]