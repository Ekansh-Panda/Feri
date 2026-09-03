"""Systemd manager plugin: service, timer, journal control."""

import subprocess
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class SystemdManager:
    """Service/timer/journal control."""

    def start_service(self, svc: str) -> dict[str, Any]:
        """Start a systemd service."""
        try:
            r = subprocess.run(["sudo", "systemctl", "start", svc], capture_output=True, text=True, timeout=30)
            return {"status": "success" if r.returncode == 0 else "error", "service": svc, "stdout": r.stdout, "stderr": r.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def stop_service(self, svc: str) -> dict[str, Any]:
        """Stop a systemd service."""
        try:
            r = subprocess.run(["sudo", "systemctl", "stop", svc], capture_output=True, text=True, timeout=30)
            return {"status": "success" if r.returncode == 0 else "error", "service": svc, "stdout": r.stdout, "stderr": r.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def restart_service(self, svc: str) -> dict[str, Any]:
        """Restart a systemd service."""
        try:
            r = subprocess.run(["sudo", "systemctl", "restart", svc], capture_output=True, text=True, timeout=30)
            return {"status": "success" if r.returncode == 0 else "error", "service": svc, "stdout": r.stdout, "stderr": r.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def service_status(self, svc: str) -> dict[str, Any]:
        """Get systemctl status."""
        try:
            r = subprocess.run(["systemctl", "status", svc], capture_output=True, text=True, timeout=10)
            return {"status": "success", "service": svc, "output": r.stdout, "stderr": r.stderr, "code": r.returncode}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_services(self, filter_state: str = "running") -> dict[str, Any]:
        """List systemd units filtered by state."""
        try:
            state_map = {"running": "active", "failed": "failed", "stopped": "inactive"}
            state = state_map.get(filter_state.lower(), filter_state)
            r = subprocess.run(
                ["systemctl", "list-units", f"--type=service", f"--state={state}"],
                capture_output=True, text=True, timeout=15, check=False,
            )
            lines = [line for line in r.stdout.strip().splitlines() if line and not line.startswith("UNIT")]
            return {"status": "success", "filter": filter_state, "services": lines}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def journal_logs(self, unit: str, lines: int = 50) -> dict[str, Any]:
        """Get journalctl logs for a unit."""
        try:
            r = subprocess.run(
                ["journalctl", "-u", unit, "-n", str(lines), "--no-pager"],
                capture_output=True, text=True, timeout=10,
            )
            return {"status": "success", "unit": unit, "logs": r.stdout, "stderr": r.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def create_timer(self, name: str, command: str, schedule: str) -> dict[str, Any]:
        """Create a systemd service and timer."""
        timer_content = f"""[Unit]
Description=JARVIS Timer {name}

[Timer]
OnCalendar={schedule}
Persistent=true

[Install]
WantedBy=timers.target
"""
        service_content = f"""[Unit]
Description=JARVIS Service {name}

[Service]
Type=oneshot
ExecStart={command}
"""
        timer_path = f"/etc/systemd/system/{name}.timer"
        service_path = f"/etc/systemd/system/{name}.service"
        try:
            with open(service_path, "w") as f:
                f.write(service_content)
            with open(timer_path, "w") as f:
                f.write(timer_content)
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True, timeout=10)
            subprocess.run(["sudo", "systemctl", "enable", "--now", timer_path], check=False, timeout=10)
            return {"status": "success", "timer": timer_path, "service": service_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def enable_service(self, svc: str) -> dict[str, Any]:
        """Enable a systemd service."""
        try:
            r = subprocess.run(["sudo", "systemctl", "enable", svc], capture_output=True, text=True, timeout=30)
            return {"status": "success" if r.returncode == 0 else "error", "service": svc}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def disable_service(self, svc: str) -> dict[str, Any]:
        """Disable a systemd service."""
        try:
            r = subprocess.run(["sudo", "systemctl", "disable", svc], capture_output=True, text=True, timeout=30)
            return {"status": "success" if r.returncode == 0 else "error", "service": svc}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def is_enabled(self, svc: str) -> dict[str, Any]:
        """Check if a service is enabled."""
        try:
            r = subprocess.run(["systemctl", "is-enabled", svc], capture_output=True, text=True, timeout=10)
            enabled = r.stdout.strip() == "enabled"
            return {"status": "success", "service": svc, "enabled": enabled}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def is_active(self, svc: str) -> dict[str, Any]:
        """Check if a service is active."""
        try:
            r = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=10)
            active = r.stdout.strip() == "active"
            return {"status": "success", "service": svc, "active": active}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def get_tools() -> list[dict]:
    return [
        {"name": "start_service", "description": "Start systemd service.", "parameters": {"type": "object", "properties": {"svc": {"type": "string"}}, "required": ["svc"]}},
        {"name": "stop_service", "description": "Stop systemd service.", "parameters": {"type": "object", "properties": {"svc": {"type": "string"}}, "required": ["svc"]}},
        {"name": "restart_service", "description": "Restart systemd service.", "parameters": {"type": "object", "properties": {"svc": {"type": "string"}}, "required": ["svc"]}},
        {"name": "service_status", "description": "Service status.", "parameters": {"type": "object", "properties": {"svc": {"type": "string"}}, "required": ["svc"]}},
        {"name": "list_services", "description": "List services by state.", "parameters": {"type": "object", "properties": {"filter_state": {"type": "string"}}, "required": []}},
        {"name": "journal_logs", "description": "Get journal logs.", "parameters": {"type": "object", "properties": {"unit": {"type": "string"}, "lines": {"type": "integer"}}, "required": ["unit"]}},
        {"name": "create_timer", "description": "Create systemd timer.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "command": {"type": "string"}, "schedule": {"type": "string"}}, "required": ["name", "command", "schedule"]}},
        {"name": "enable_service", "description": "Enable service.", "parameters": {"type": "object", "properties": {"svc": {"type": "string"}}, "required": ["svc"]}},
        {"name": "disable_service", "description": "Disable service.", "parameters": {"type": "object", "properties": {"svc": {"type": "string"}}, "required": ["svc"]}},
        {"name": "is_enabled", "description": "Check if enabled.", "parameters": {"type": "object", "properties": {"svc": {"type": "string"}}, "required": ["svc"]}},
        {"name": "is_active", "description": "Check if active.", "parameters": {"type": "object", "properties": {"svc": {"type": "string"}}, "required": ["svc"]}},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = SystemdManager()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(json.dumps(execute("list_services", {"filter_state": "running"}), indent=2))
