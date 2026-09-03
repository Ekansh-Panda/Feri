"""NetworkAgent — network scanning, firewall, DNS, and bandwidth monitoring."""

from __future__ import annotations

import ipaddress
import logging
import platform
import shutil
import socket
import subprocess
import time
from typing import Any

logger = logging.getLogger("jarvis.network")


class NetworkAgent:
    """Network scanning, firewall control, DNS operations."""

    def scan_network(self, subnet: str) -> dict[str, Any]:
        """Ping sweep a subnet using nmap.

        Args:
            subnet: CIDR notation (e.g. 192.168.1.0/24).

        Returns:
            Dict with discovered hosts.
        """
        hosts = []
        try:
            proc = subprocess.run(
                ["nmap", "-sn", "-T4", subnet],
                capture_output=True,
                text=True,
                timeout=120,
            )
            for line in proc.stdout.splitlines():
                if "Nmap scan report for" in line:
                    ip = line.split()[-1].strip("()")
                    hosts.append(ip)
            return {"subnet": subnet, "hosts": hosts, "status": "ok"}
        except FileNotFoundError:
            return {"subnet": subnet, "hosts": hosts, "status": "skipped", "error": "nmap not found"}
        except subprocess.TimeoutExpired:
            return {"subnet": subnet, "hosts": hosts, "status": "timeout"}
        except Exception as exc:
            return {"subnet": subnet, "hosts": hosts, "status": "error", "error": str(exc)}

    def port_scan(self, target: str, ports: str) -> dict[str, Any]:
        """Scan specific ports on a target.

        Args:
            target: IP or hostname.
            ports: Port specification (e.g. 22,80,443 or 1-1024).

        Returns:
            Dict with open ports.
        """
        results: dict[str, Any] = {"target": target, "ports": []}
        try:
            proc = subprocess.run(
                ["nmap", "-p", ports, target],
                capture_output=True,
                text=True,
                timeout=120,
            )
            for line in proc.stdout.splitlines():
                if "/tcp" in line and "open" in line:
                    port = line.split("/")[0].strip()
                    results["ports"].append(port)
            results["status"] = "ok"
            return results
        except FileNotFoundError:
            return {**results, "status": "skipped", "error": "nmap not found"}
        except Exception as exc:
            return {**results, "status": "error", "error": str(exc)}

    def get_open_ports(self) -> dict[str, Any]:
        """List listening sockets using ss.

        Returns:
            Dict with listening sockets.
        """
        try:
            if shutil.which("ss"):
                proc = subprocess.run(["ss", "-tulnp"], capture_output=True, text=True, timeout=10)
                return {"output": proc.stdout, "status": "ok" if proc.returncode == 0 else "error", "tool": "ss"}
            if shutil.which("netstat"):
                proc = subprocess.run(["netstat", "-tulnp"], capture_output=True, text=True, timeout=10)
                return {"output": proc.stdout, "status": "ok" if proc.returncode == 0 else "error", "tool": "netstat"}
            return {"status": "skipped", "error": "Neither ss nor netstat found"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def block_ip(self, ip: str) -> dict[str, Any]:
        """Block an IP using ufw or iptables.

        Args:
            ip: IP address to block.

        Returns:
            Dict with status.
        """
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return {"status": "error", "error": f"Invalid IP: {ip}"}

        if shutil.which("ufw"):
            try:
                proc = subprocess.run(["ufw", "deny", "from", ip, "to", "any"], capture_output=True, text=True, timeout=10)
                return {"status": "ok" if proc.returncode == 0 else "error", "output": proc.stdout, "tool": "ufw"}
            except Exception as exc:
                return {"status": "error", "error": str(exc)}

        if shutil.which("iptables"):
            try:
                proc = subprocess.run(["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"], capture_output=True, text=True, timeout=10)
                return {"status": "ok" if proc.returncode == 0 else "error", "output": proc.stdout, "tool": "iptables"}
            except Exception as exc:
                return {"status": "error", "error": str(exc)}

        return {"status": "error", "error": "No firewall tool (ufw/iptables) found"}

    def unblock_ip(self, ip: str) -> dict[str, Any]:
        """Unblock an IP.

        Args:
            ip: IP address to unblock.

        Returns:
            Dict with status.
        """
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return {"status": "error", "error": f"Invalid IP: {ip}"}

        if shutil.which("ufw"):
            try:
                proc = subprocess.run(["ufw", "delete", "deny", "from", ip, "to", "any"], capture_output=True, text=True, timeout=10)
                return {"status": "ok" if proc.returncode == 0 else "error", "output": proc.stdout, "tool": "ufw"}
            except Exception as exc:
                return {"status": "error", "error": str(exc)}

        if shutil.which("iptables"):
            try:
                subprocess.run(["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"], capture_output=True, text=True, timeout=10)
                return {"status": "ok", "tool": "iptables"}
            except Exception as exc:
                return {"status": "error", "error": str(exc)}

        return {"status": "error", "error": "No firewall tool (ufw/iptables) found"}

    def dns_lookup(self, domain: str) -> dict[str, Any]:
        """DNS lookup for a domain.

        Args:
            domain: Domain name.

        Returns:
            Dict with resolved addresses.
        """
        try:
            infos = socket.getaddrinfo(domain, None)
            addresses = list({info[4][0] for info in infos})
            return {"domain": domain, "addresses": addresses, "status": "ok"}
        except Exception as exc:
            return {"domain": domain, "addresses": [], "status": "error", "error": str(exc)}

    def reverse_dns(self, ip: str) -> dict[str, Any]:
        """Reverse DNS lookup.

        Args:
            ip: IP address.

        Returns:
            Dict with hostname.
        """
        try:
            hostname, _, _ = socket.gethostbyaddr(ip)
            return {"ip": ip, "hostname": hostname, "status": "ok"}
        except Exception as exc:
            return {"ip": ip, "hostname": "", "status": "error", "error": str(exc)}

    def trace_route(self, host: str) -> dict[str, Any]:
        """Run traceroute to a host.

        Args:
            host: Hostname or IP.

        Returns:
            Dict with hops.
        """
        tool = "traceroute"
        if platform.system() == "Windows":
            tool = "tracert"
        if not shutil.which(tool):
            tool = "tracepath" if shutil.which("tracepath") else None
        if not tool:
            return {"host": host, "status": "skipped", "error": "No traceroute tool available"}

        try:
            proc = subprocess.run([tool, host], capture_output=True, text=True, timeout=60)
            return {"host": host, "hops": proc.stdout.splitlines(), "status": "ok" if proc.returncode == 0 else "error"}
        except Exception as exc:
            return {"host": host, "status": "error", "error": str(exc)}

    def get_bandwidth(self) -> dict[str, Any]:
        """Estimate bandwidth using iftop-style parsing.

        Returns:
            Dict with interfaces and traffic.
        """
        try:
            with open("/proc/net/dev", "r", encoding="utf-8") as f:
                lines = f.readlines()[2:]
            interfaces: dict[str, Any] = {}
            for line in lines:
                parts = line.split()
                if len(parts) < 10:
                    continue
                iface = parts[0].strip(":")
                rx = int(parts[1])
                tx = int(parts[9])
                interfaces[iface] = {"rx_bytes": rx, "tx_bytes": tx}
            return {"interfaces": interfaces, "status": "ok"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
