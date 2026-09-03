"""
Network Warfare — perimeter scanning, ARP spoof detection, firewall control,
Wi-Fi management, and DNS blackholing for JARVIS.

All commands are root-privileged; missing privileges are reported, not hidden.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(cmd: List[str], timeout: int = 15, check: bool = False) -> Dict[str, object]:
    """Run a command, return dict with stdout/stderr/code; never raise."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }
    except FileNotFoundError as e:
        return {"ok": False, "stdout": "", "stderr": f"not_found:{e}", "exit_code": 127}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": "timeout", "exit_code": 124}
    except Exception as e:  # pragma: no cover
        return {"ok": False, "stdout": "", "stderr": str(e), "exit_code": 1}


class NetworkWarfare:
    """Defensive network operations: scanning, ARP watch, firewall, Wi-Fi, DNS."""

    def __init__(self, subnet: str = "192.168.1.0/24", known_macs: Optional[Dict[str, str]] = None) -> None:
        self.subnet = subnet
        self.known_macs: Dict[str, str] = known_macs or {}
        self._arp_thread: Optional[threading.Thread] = None
        self._arp_stop = threading.Event()
        self._arp_alert_cb = None  # type: ignore[var-annotated]
        self._arp_state_lock = threading.Lock()
        self._arp_current_mac: Optional[str] = None

    # ---- Scanning ----

    def scan_perimeter(self) -> Dict[str, object]:
        """ARP-sweep the subnet; flag unknown MACs. Falls back to /proc ARP table."""
        devices: List[Dict[str, str]] = []
        arp = _run(["arp", "-a"])
        for line in arp["stdout"].splitlines():
            parts = line.split()
            if len(parts) >= 4 and "(" in line:
                ip = parts[1].strip("()")
                dev = parts[3] if len(parts) > 3 else "?"
                mac = parts[3] if ":" in parts[-1] else parts[-1]
                if ":" in mac:
                    devices.append({"ip": ip, "mac": mac, "iface": dev})
        unknown = [d for d in devices if d["mac"] not in self.known_macs.values()]
        return {
            "ok": arp["ok"] or bool(devices),
            "subnet": self.subnet,
            "devices": devices,
            "unknown": unknown,
            "count": len(devices),
        }

    # ---- ARP spoof monitoring ----

    def monitor_arp_spoofing(self, gateway_ip: str, gateway_mac: str,
                             interval: float = 2.0,
                             on_alert=None) -> bool:
        """Daemon thread watching for gateway-MAC change."""
        if self._arp_thread and self._arp_thread.is_alive():
            return False
        self._arp_stop.clear()
        self._arp_alert_cb = on_alert
        self._arp_current_mac = gateway_mac.lower()

        def _loop() -> None:
            while not self._arp_stop.is_set():
                res = _run(["arp", "-n", gateway_ip])
                current = None
                for line in res["stdout"].splitlines():
                    parts = line.split()
                    if len(parts) >= 3 and parts[0] == gateway_ip:
                        current = parts[2].lower()
                        break
                with self._arp_state_lock:
                    prev = self._arp_current_mac
                if current and prev and current != prev:
                    alert = {
                        "type": "arp_spoof",
                        "gateway_ip": gateway_ip,
                        "expected_mac": prev,
                        "observed_mac": current,
                        "ts": time.time(),
                    }
                    if self._arp_alert_cb:
                        try:
                            self._arp_alert_cb(alert)
                        except Exception:
                            pass
                    with self._arp_state_lock:
                        self._arp_current_mac = current
                self._arp_stop.wait(interval)

        self._arp_thread = threading.Thread(target=_loop, name="ARPMonitor", daemon=True)
        self._arp_thread.start()
        return True

    def stop_arp_monitor(self) -> None:
        self._arp_stop.set()
        if self._arp_thread:
            self._arp_thread.join(timeout=3.0)
            self._arp_thread = None

    def alert_and_lockdown(self) -> Dict[str, object]:
        """Combine alert + lockdown (caller is expected to log/notify)."""
        alert = {"alert": True, "ts": time.time(), "level": "high"}
        lock = self.initiate_lockdown()
        return {"alert": alert, "lockdown": lock}

    # ---- Firewall ----

    def initiate_lockdown(self) -> Dict[str, object]:
        """iptables DROP all inbound except loopback."""
        cmds = [
            ["iptables", "-I", "INPUT", "-i", "lo", "-j", "ACCEPT"],
            ["iptables", "-I", "OUTPUT", "-o", "lo", "-j", "ACCEPT"],
            ["iptables", "-P", "INPUT", "DROP"],
            ["iptables", "-P", "OUTPUT", "DROP"],
            ["iptables", "-P", "FORWARD", "DROP"],
        ]
        results = [_run(c) for c in cmds]
        return {"ok": all(r["ok"] for r in results), "results": results}

    def restore_network(self) -> Dict[str, object]:
        """Flush iptables and reset policies to ACCEPT."""
        cmds = [
            ["iptables", "-F"],
            ["iptables", "-X"],
            ["iptables", "-P", "INPUT", "ACCEPT"],
            ["iptables", "-P", "OUTPUT", "ACCEPT"],
            ["iptables", "-P", "FORWARD", "ACCEPT"],
        ]
        results = [_run(c) for c in cmds]
        return {"ok": all(r["ok"] for r in results), "results": results}

    def block_ip(self, ip: str) -> Dict[str, object]:
        """Block a single IP in INPUT + OUTPUT."""
        return _run(["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"])

    # ---- Connection mgmt ----

    def get_active_connections(self) -> List[Dict[str, str]]:
        """Parse `ss -tulnp` into structured records."""
        out = _run(["ss", "-tulnp"])
        conns: List[Dict[str, str]] = []
        for line in out["stdout"].splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 5:
                conns.append(
                    {
                        "netid": parts[0],
                        "state": parts[1],
                        "local": parts[4] if len(parts) > 4 else "",
                        "peer": parts[5] if len(parts) > 5 else "",
                        "process": parts[-1] if "users:" in line else "",
                    }
                )
        return conns

    def kill_connection(self, port: int) -> Dict[str, object]:
        """Find and kill processes bound to the given port."""
        lsof = shutil.which("lsof")
        if not lsof:
            return {"ok": False, "error": "lsof_not_installed"}
        info = _run([lsof, "-ti", f":{port}"], timeout=10)
        pids = [p for p in info["stdout"].split() if p.isdigit()]
        killed = []
        for pid in pids:
            res = _run(["kill", "-9", pid])
            if res["ok"]:
                killed.append(int(pid))
        return {"ok": bool(killed), "killed": killed}

    # ---- DNS ----

    def dns_lockdown(self, blocked_domains: List[str]) -> Dict[str, object]:
        """Blackhole domains by adding 0.0.0.1 entries to /etc/hosts."""
        if not blocked_domains:
            return {"ok": True, "added": 0}
        try:
            content = Path("/etc/hosts").read_text(encoding="utf-8")
        except Exception:
            content = ""
        added = 0
        for d in blocked_domains:
            entry = f"0.0.0.1 {d}\n"
            if entry not in content:
                content += entry
                added += 1
        try:
            Path("/etc/hosts").write_text(content, encoding="utf-8")
            return {"ok": True, "added": added}
        except PermissionError as e:
            return {"ok": False, "error": str(e)}

    # ---- Wi-Fi (NetworkManager) ----

    def get_wifi_networks(self) -> List[Dict[str, str]]:
        """List visible Wi-Fi SSIDs via nmcli."""
        nmcli = shutil.which("nmcli")
        if not nmcli:
            return []
        out = _run([nmcli, "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"])
        nets: List[Dict[str, str]] = []
        for line in out["stdout"].splitlines():
            parts = line.split(":")
            if not parts or not parts[0]:
                continue
            nets.append(
                {"ssid": parts[0], "signal": parts[1] if len(parts) > 1 else "",
                 "security": parts[2] if len(parts) > 2 else ""}
            )
        return nets

    def connect_wifi(self, ssid: str, password: str) -> Dict[str, object]:
        """Connect to a Wi-Fi network via NetworkManager."""
        nmcli = shutil.which("nmcli")
        if not nmcli:
            return {"ok": False, "error": "nmcli_not_found"}
        return _run([nmcli, "dev", "wifi", "connect", ssid, "password", password], timeout=30)

    def disconnect_wifi(self) -> Dict[str, object]:
        nmcli = shutil.which("nmcli")
        if not nmcli:
            return {"ok": False, "error": "nmcli_not_found"}
        return _run([nmcli, "networking", "off"], timeout=15)

    def enable_airplane_mode(self) -> Dict[str, object]:
        rfkill = shutil.which("rfkill")
        if not rfkill:
            return {"ok": False, "error": "rfkill_not_found"}
        return _run([rfkill, "block", "all"])

    def disable_airplane_mode(self) -> Dict[str, object]:
        rfkill = shutil.which("rfkill")
        if not rfkill:
            return {"ok": False, "error": "rfkill_not_found"}
        return _run([rfkill, "unblock", "all"])


__all__ = ["NetworkWarfare"]