"""
hardware_control.py — sensors, GPU telemetry, fan/undervolt/power/governor.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Union


_SYSTEM = platform.system()
_IS_LINUX = _SYSTEM == "Linux"


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _read_int(path: Path, default: int = 0) -> int:
    try:
        return int(path.read_text().strip())
    except Exception:
        return default


def _read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text().strip()
    except Exception:
        return default


def _run(cmd: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return subprocess.CompletedProcess(cmd, -1, "", str(e))


_VALID_GOVERNORS = {
    "performance", "powersave", "userspace", "ondemand",
    "conservative", "schedutil",
}


class HardwareControl:
    """Sensors, GPU, fans, undervolt, power and CPU governor on Arch Linux."""

    def __init__(self) -> None:
        self._thermal_base = Path("/sys/class/thermal") if _IS_LINUX else None
        self._hwmon_base   = Path("/sys/class/hwmon") if _IS_LINUX else None
        self._powercap_base = Path("/sys/class/powercap") if _IS_LINUX else None

    # ── Temperatures / fans ────────────────────────────────────────────────

    def get_cpu_temp(self) -> Optional[float]:
        """Try psutil first, then /sys/class/thermal."""
        try:
            import psutil
            temps = psutil.sensors_temperatures(fahrenheit=False)
            for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz",
                        "cpu-thermal", "zenpower", "it8688", "cpu"):
                if key in temps and temps[key]:
                    return float(temps[key][0].current)
            for entries in temps.values():
                if entries:
                    return float(entries[0].current)
        except Exception:
            pass

        if self._thermal_base and self._thermal_base.exists():
            for zone in sorted(self._thermal_base.glob("thermal_zone*")):
                typ = _read_text(zone / "type", "")
                if typ.startswith(("x86_pkg_temp", "cpu", "acpi", "coretemp")):
                    val = _read_int(zone / "temp", 0)
                    if val:
                        # millidegrees → celsius
                        if val > 1000:
                            return val / 1000.0
                        return float(val)
        return None

    def get_gpu_temp(self) -> Optional[float]:
        if _which("nvidia-smi"):
            r = _run(["nvidia-smi", "--query-gpu=temperature.gpu",
                      "--format=csv,noheader,nounits"], timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                try:
                    return float(r.stdout.strip().splitlines()[0])
                except ValueError:
                    pass
        # AMD via hwmon
        if self._hwmon_base and self._hwmon_base.exists():
            for chip in self._hwmon_base.iterdir():
                name = _read_text(chip / "name", "")
                if any(k in name.lower() for k in ("amdgpu", "radeon", "nvidia")):
                    for f in chip.glob("temp*_input"):
                        v = _read_int(f, 0)
                        if v:
                            return v / 1000.0
        return None

    def get_fan_speed(self) -> Optional[int]:
        if self._hwmon_base and self._hwmon_base.exists():
            for chip in self._hwmon_base.iterdir():
                for f in chip.glob("fan*_input"):
                    val = _read_int(f, 0)
                    if val:
                        return val
        try:
            import psutil
            fans = psutil.sensors_fans()
            for entries in fans.values():
                if entries:
                    return int(entries[0].current)
        except Exception:
            pass
        return None

    def set_fan_speed(self, speed: Union[int, str]) -> bool:
        """Manual fan PWM (0-255 or 'auto')."""
        if not (self._hwmon_base and self._hwmon_base.exists()):
            return False
        if isinstance(speed, str) and speed.lower() == "auto":
            target_val = 0
            target_str = "0"
        else:
            try:
                pwm = max(0, min(255, int(speed)))
            except (TypeError, ValueError):
                return False
            target_val = pwm
            target_str = str(pwm)

        enabled = False
        for chip in self._hwmon_base.iterdir():
            pwm_enable = chip / "pwm1_enable"
            pwm_file = chip / "pwm1"
            if not pwm_file.exists():
                continue
            try:
                if target_val == 0:
                    pwm_enable.write_text("2")
                else:
                    pwm_enable.write_text("1")
                pwm_file.write_text(target_str)
                enabled = True
            except Exception:
                continue
        return enabled

    # ── Undervolt ──────────────────────────────────────────────────────────

    def undervolt_cpu(self, offset: int) -> bool:
        """Intel undervolt using intel-undervolt.
        `offset` in millivolts (e.g. -80 for -80 mV)."""
        if not _which("intel-undervolt"):
            return False
        try:
            r = _run(["intel-undervolt", "apply",
                      f"--voltage", f"{offset}", "--debug"], timeout=30)
            return r.returncode == 0
        except Exception:
            return False

    # ── Power ──────────────────────────────────────────────────────────────

    def get_power_consumption(self) -> Optional[float]:
        """RAPL via /sys/class/powercap, in watts."""
        if not (self._powercap_base and self._powercap_base.exists()):
            return None
        # Look at the package (RAPL) energy counter; convert to instantaneous W
        rapl = None
        for entry in self._powercap_base.iterdir():
            name = _read_text(entry / "name", "")
            if "package" in name.lower() or "intel-rapl" in name.lower():
                rapl = entry
                break
        if not rapl:
            return None
        try:
            max_uj = int(_read_text(rapl / "max_energy_range_uj", "0"))
            e_uj   = int(_read_text(rapl / "energy_uj", "0"))
            if not max_uj or not e_uj:
                return None
            # Two samples 250ms apart
            import time
            time.sleep(0.25)
            e_uj2 = int(_read_text(rapl / "energy_uj", "0"))
            delta = max(0, e_uj - e_uj2)
            return round(delta / 250_000.0, 2)   # µJ / 250 ms → W
        except Exception:
            return None

    # ── Governor ───────────────────────────────────────────────────────────

    def set_cpu_governor(self, governor: str) -> bool:
        governor = (governor or "").lower().strip()
        if governor not in _VALID_GOVERNORS:
            raise ValueError(f"invalid governor: {governor}")

        cpufreq = Path("/sys/devices/system/cpu/cpufreq")
        if not cpufreq.exists():
            # Fallback to cpupower
            if _which("cpupower"):
                r = _run(["cpupower", "frequency-set", "-g", governor], timeout=10)
                return r.returncode == 0
            return False
        ok = False
        for cpu in sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*")):
            gov_file = cpu / "cpufreq/scaling_governor"
            if gov_file.exists():
                try:
                    gov_file.write_text(governor)
                    ok = True
                except Exception:
                    continue
        return ok

    def get_cpu_governor(self) -> str:
        gov = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
        return _read_text(gov, "unknown")

    # ── Combined ───────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        return {
            "cpu_temp_c":    self.get_cpu_temp(),
            "gpu_temp_c":    self.get_gpu_temp(),
            "fan_rpm":       self.get_fan_speed(),
            "power_w":       self.get_power_consumption(),
            "governor":      self.get_cpu_governor() if _IS_LINUX else "n/a",
            "ts":            __import__("time").time(),
        }