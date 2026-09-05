import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from core.mission_engine import MissionEngine


class ArchI3Adapter:
    def install_package(self, package: str) -> str:
        result = subprocess.run(
            ["sudo", "pacman", "-S", "--noconfirm", package],
            capture_output=True, text=True
        )
        return result.stdout + result.stderr

    def install_aur(self, package: str) -> str:
        result = subprocess.run(
            ["yay", "-S", "--noconfirm", package],
            capture_output=True, text=True
        )
        return result.stdout + result.stderr

    def set_volume(self, pct: int) -> str:
        subprocess.run(
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"]
        )
        return f"Volume set to {pct}%"

    def set_brightness(self, pct: str) -> str:
        subprocess.run(["brightnessctl", "set", f"{pct}%"])
        return f"Brightness set to {pct}%"

    def firewall_lockdown(self) -> str:
        cmds = [
            ["sudo", "iptables", "-F"],
            ["sudo", "iptables", "-P", "INPUT", "DROP"],
            ["sudo", "iptables", "-P", "FORWARD", "DROP"],
            ["sudo", "iptables", "-P", "OUTPUT", "DROP"],
            ["sudo", "iptables", "-A", "INPUT", "-i", "lo", "-j", "ACCEPT"],
            ["sudo", "iptables", "-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"],
            ["sudo", "iptables", "-A", "INPUT", "-m", "state", "--state", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
            ["sudo", "iptables", "-A", "OUTPUT", "-m", "state", "--state", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
        ]
        for cmd in cmds:
            subprocess.run(cmd, check=False)
        return "Firewall locked down. Only loopback permitted."

    def screenshot(self) -> str:
        path = "/tmp/jarvis_screenshot.png"
        subprocess.run(["scrot", path], check=False)
        return path

    def window_control(self, action: str, params: Dict[str, Any]) -> str:
        cmd_map = {
            "focus": lambda p: f"focus {p.get('direction', 'right')}",
            "move": lambda p: f"move {p.get('direction', 'right')}",
            "workspace": lambda p: f"workspace {p.get('number', 1)}",
            "layout": lambda p: f"layout {p.get('layout', 'splith')}",
            "kill": lambda p: "kill",
            "fullscreen": lambda p: "fullscreen toggle",
            "scratchpad": lambda p: "move scratchpad",
        }
        if action not in cmd_map:
            return f"Unknown window action: {action}"
        i3_cmd = cmd_map[action](params)
        subprocess.run(["i3-msg", i3_cmd], check=False)
        return f"Executed i3-msg {i3_cmd}"

    def auto_start(self, name: str, command: str) -> str:
        svc_path = Path.home() / ".config" / "systemd" / "user" / f"jarvis-{name}.service"
        svc_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"""[Unit]
Description=JARVIS Auto-Start: {name}

[Service]
Type=simple
ExecStart={command}
Restart=always

[Install]
WantedBy=default.target
"""
        svc_path.write_text(content)
        subprocess.run(["systemctl", "--user", "enable", f"jarvis-{name}.service"], check=False)
        subprocess.run(["systemctl", "--user", "start", f"jarvis-{name}.service"], check=False)
        return f"Autostart '{name}' configured via systemd user service."

    def open_app(self, app: str, workspace: Optional[int] = None) -> str:
        if workspace:
            subprocess.run(["i3-msg", f"workspace {workspace}; exec {app}"], check=False)
        else:
            subprocess.run(["i3-msg", f"exec {app}"], check=False)
        return f"Launched {app}" + (f" on workspace {workspace}" if workspace else "")

    def notify(self, title: str, body: str, urgency: str = "normal") -> str:
        subprocess.run(
            ["notify-send", "-u", urgency, title, body],
            check=False
        )
        return f"Notification sent: {title}"


class LinuxGenericAdapter:
    def install_package(self, package: str) -> str:
        if os.path.exists("/etc/debian_version"):
            result = subprocess.run(
                ["sudo", "apt", "install", "-y", package],
                capture_output=True, text=True
            )
        elif os.path.exists("/etc/fedora-release"):
            result = subprocess.run(
                ["sudo", "dnf", "install", "-y", package],
                capture_output=True, text=True
            )
        else:
            return "Unsupported Linux distribution."
        return result.stdout + result.stderr

    def set_volume(self, pct: int) -> str:
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"], check=False)
        return f"Volume set to {pct}%"

    def set_brightness(self, pct: str) -> str:
        subprocess.run(["brightnessctl", "set", f"{pct}%"], check=False)
        return f"Brightness set to {pct}%"

    def firewall_lockdown(self) -> str:
        subprocess.run(["sudo", "iptables", "-F"], check=False)
        subprocess.run(["sudo", "iptables", "-P", "INPUT", "DROP"], check=False)
        subprocess.run(["sudo", "iptables", "-P", "OUTPUT", "DROP"], check=False)
        subprocess.run(["sudo", "iptables", "-A", "INPUT", "-i", "lo", "-j", "ACCEPT"], check=False)
        subprocess.run(["sudo", "iptables", "-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"], check=False)
        return "Firewall locked down."

    def screenshot(self) -> str:
        path = "/tmp/jarvis_screenshot.png"
        subprocess.run(["scrot", path], check=False)
        return path

    def window_control(self, action: str, params: Dict[str, Any]) -> str:
        return f"Window control '{action}' not available on this WM."

    def auto_start(self, name: str, command: str) -> str:
        return "Autostart not configured for this platform."

    def open_app(self, app: str, workspace: Optional[int] = None) -> str:
        subprocess.Popen([app], shell=True)
        return f"Launched {app}"

    def notify(self, title: str, body: str, urgency: str = "normal") -> str:
        subprocess.run(["notify-send", "-u", urgency, title, body], check=False)
        return f"Notification sent: {title}"


class MacOSAdapter:
    def install_package(self, package: str) -> str:
        result = subprocess.run(
            ["brew", "install", package],
            capture_output=True, text=True
        )
        return result.stdout + result.stderr

    def set_volume(self, pct: int) -> str:
        subprocess.run(["osascript", "-e", f"set volume output volume {pct}"], check=False)
        return f"Volume set to {pct}%"

    def set_brightness(self, pct: str) -> str:
        subprocess.run(["brightness", str(int(pct) / 100)], check=False)
        return f"Brightness set to {pct}%"

    def firewall_lockdown(self) -> str:
        return "Firewall lockdown not implemented for macOS."

    def screenshot(self) -> str:
        path = "/tmp/jarvis_screenshot.png"
        subprocess.run(["screencapture", "-x", path], check=False)
        return path

    def window_control(self, action: str, params: Dict[str, Any]) -> str:
        return f"Window control '{action}' not implemented for macOS."

    def auto_start(self, name: str, command: str) -> str:
        return "Autostart not configured for macOS."

    def open_app(self, app: str, workspace: Optional[int] = None) -> str:
        subprocess.run(["open", "-a", app], check=False)
        return f"Launched {app}"

    def notify(self, title: str, body: str, urgency: str = "normal") -> str:
        subprocess.run(
            ["osascript", "-e", f'display notification "{body}" with title "{title}"'],
            check=False
        )
        return f"Notification sent: {title}"


class WindowsAdapter:
    def install_package(self, package: str) -> str:
        result = subprocess.run(
            ["winget", "install", package],
            capture_output=True, text=True
        )
        return result.stdout + result.stderr

    def set_volume(self, pct: int) -> str:
        return f"Volume set to {pct}% (Windows placeholder)"

    def set_brightness(self, pct: str) -> str:
        return f"Brightness set to {pct}% (Windows placeholder)"

    def firewall_lockdown(self) -> str:
        return "Firewall lockdown not implemented for Windows."

    def screenshot(self) -> str:
        path = "/tmp/jarvis_screenshot.png"
        subprocess.run(["nircmd.exe", "savescreenshot", path], check=False)
        return path

    def window_control(self, action: str, params: Dict[str, Any]) -> str:
        return f"Window control '{action}' not implemented for Windows."

    def auto_start(self, name: str, command: str) -> str:
        return "Autostart not configured for Windows."

    def open_app(self, app: str, workspace: Optional[int] = None) -> str:
        subprocess.Popen([app], shell=True)
        return f"Launched {app}"

    def notify(self, title: str, body: str, urgency: str = "normal") -> str:
        return f"Notification sent: {title}"


class Orchestrator:
    def __init__(self, api_keys: Dict[str, str], gemini_key: str, mission_engine: MissionEngine):
        self.api_keys = api_keys
        self.gemini_key = gemini_key
        self.mission_engine = mission_engine
        self.adapter = self.get_os_adapter()
        self.running = False

    def get_os_adapter(self):
        system = platform.system()
        if system == "Linux" and os.path.exists("/etc/arch-release"):
            return ArchI3Adapter()
        elif system == "Linux":
            return LinuxGenericAdapter()
        elif system == "Darwin":
            return MacOSAdapter()
        elif system == "Windows":
            return WindowsAdapter()
        return LinuxGenericAdapter()

    def route_intent(self, intent: str, params: Dict[str, Any]) -> str:
        intent = intent.lower().strip()
        if intent in ("open_app", "launch"):
            return self.adapter.open_app(
                params.get("app", ""),
                params.get("workspace")
            )
        elif intent == "volume":
            return self.adapter.set_volume(int(params.get("level", 50)))
        elif intent == "brightness":
            return self.adapter.set_brightness(str(params.get("level", 50)))
        elif intent == "screenshot":
            return self.adapter.screenshot()
        elif intent == "firewall_lockdown":
            return self.adapter.firewall_lockdown()
        elif intent == "notify":
            return self.adapter.notify(
                params.get("title", "JARVIS"),
                params.get("body", "")
            )
        elif intent == "window_control":
            return self.adapter.window_control(
                params.get("action", "focus"),
                params.get("params", {})
            )
        elif intent == "auto_start":
            return self.adapter.auto_start(
                params.get("name", ""),
                params.get("command", "")
            )
        else:
            return f"Intent '{intent}' not recognized."

    def start(self):
        self.running = True
        print("JARVIS Orchestrator online.")

    def stop(self):
        self.running = False
        print("JARVIS Orchestrator shutting down.")
