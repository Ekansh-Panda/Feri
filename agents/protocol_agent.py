"""ProtocolAgent — named protocol execution with registry."""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger("jarvis.protocol")


class ProtocolAgent:
    """Dispatches named protocol executions."""

    def __init__(self) -> None:
        self._protocols: dict[str, Callable[..., Any]] = {}
        self._descriptions: dict[str, str] = {}
        self._register_builtins()

    def execute(self, protocol_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a named protocol.

        Args:
            protocol_name: Name of the protocol.
            params: Protocol parameters.

        Returns:
            Result dict from the protocol.
        """
        params = params or {}
        fn = self._protocols.get(protocol_name)
        if fn is None:
            return {"status": "error", "error": f"Unknown protocol: {protocol_name}"}
        try:
            result = fn(params)
            if isinstance(result, dict):
                result.setdefault("protocol", protocol_name)
                return result
            return {"status": "ok", "protocol": protocol_name, "result": result}
        except Exception as exc:
            logger.error("Protocol %s failed: %s", protocol_name, exc)
            return {"status": "error", "protocol": protocol_name, "error": str(exc)}

    def list_protocols(self) -> list[str]:
        """List available protocol names.

        Returns:
            Sorted list of protocol names.
        """
        return sorted(self._protocols.keys())

    def register_protocol(self, name: str, func: Callable[..., Any], description: str = "") -> None:
        """Register a custom protocol.

        Args:
            name: Protocol name.
            func: Callable accepting a params dict.
            description: Human-readable description.
        """
        if not callable(func):
            raise ValueError("func must be callable")
        self._protocols[name] = func
        self._descriptions[name] = description or ""

    # -- built-in protocols --

    def _register_builtins(self) -> None:
        self.register_protocol("house_party", self._house_party, "Prepare home for guests: lights, music, temp, doors.")
        self.register_protocol("clean_slate", self._clean_slate, "Reset workspace: close apps, clear clutter, fresh session.")
        self.register_protocol("lockdown", self._lockdown, "Harden security: firewall, lock screen, mute, block ports.")
        self.register_protocol("shadow", self._shadow, "Enter stealth mode: minimize noise, hide traces, quiet mode.")
        self.register_protocol("rescue", self._rescue, "Emergency recovery: backup, logs, diagnostics.")
        self.register_protocol("forge", self._forge, "Build environment: install deps, create venv, configure.")
        self.register_protocol("exam", self._exam, "Exam mode: block distractions, lockdown, focus mode.")
        self.register_protocol("archive", self._archive, "Archive project: compress, timestamp, checksum, offload.")

    def _house_party(self, params: dict[str, Any]) -> dict[str, Any]:
        actions: list[str] = []
        if params.get("lights_on"):
            actions.append("Lights set to party mode")
        if params.get("music_play"):
            actions.append("Music queued")
        if params.get("temp_adjust"):
            actions.append(f"Temperature adjusted to {params.get('temperature', 21)}C")
        if params.get("unlock_doors"):
            actions.append("Doors unlocked")
        return {"status": "ok", "actions": actions, "message": "House Party protocol activated."}

    def _clean_slate(self, params: dict[str, Any]) -> dict[str, Any]:
        actions: list[str] = []
        if params.get("close_apps"):
            actions.append("Non-essential apps closed")
        if params.get("clear_clutter"):
            actions.append("Desktop organized")
        if params.get("restart_services"):
            actions.append("Services restarted")
        return {"status": "ok", "actions": actions, "message": "Clean Slate protocol activated."}

    def _lockdown(self, params: dict[str, Any]) -> dict[str, Any]:
        actions: list[str] = []
        if params.get("enable_firewall"):
            actions.append("Firewall enabled (ufw deny incoming)")
        if params.get("lock_screen"):
            actions.append("Screen locked")
        if params.get("mute"):
            actions.append("Audio muted")
        if params.get("block_ports"):
            ports = params.get("ports", [])
            actions.append(f"Ports blocked: {ports}")
        return {"status": "ok", "actions": actions, "message": "Lockdown protocol activated."}

    def _shadow(self, params: dict[str, Any]) -> dict[str, Any]:
        actions: list[str] = []
        if params.get("minimize_notifications"):
            actions.append("Notifications disabled")
        if params.get("hide_tray"):
            actions.append("Tray icons hidden")
        if params.get("clear_logs"):
            actions.append("Recent logs cleared")
        return {"status": "ok", "actions": actions, "message": "Shadow protocol activated."}

    def _rescue(self, params: dict[str, Any]) -> dict[str, Any]:
        actions: list[str] = []
        if params.get("backup"):
            actions.append("Critical files backed up")
        if params.get("capture_logs"):
            actions.append("System logs captured")
        if params.get("diagnostics"):
            actions.append("Diagnostics collected")
        return {"status": "ok", "actions": actions, "message": "Rescue protocol activated."}

    def _forge(self, params: dict[str, Any]) -> dict[str, Any]:
        actions: list[str] = []
        if params.get("install_deps"):
            actions.append("Dependencies installed")
        if params.get("create_venv"):
            actions.append("Virtual environment created")
        if params.get("configure"):
            actions.append("Environment configured")
        return {"status": "ok", "actions": actions, "message": "Forge protocol activated."}

    def _exam(self, params: dict[str, Any]) -> dict[str, Any]:
        actions: list[str] = []
        if params.get("block_distractions"):
            actions.append("Distractions blocked")
        if params.get("enable_focus"):
            actions.append("Focus mode enabled")
        if params.get("lock_browser"):
            actions.append("Browser locked to exam tabs")
        return {"status": "ok", "actions": actions, "message": "Exam protocol activated."}

    def _archive(self, params: dict[str, Any]) -> dict[str, Any]:
        actions: list[str] = []
        if params.get("compress"):
            actions.append("Project compressed")
        if params.get("timestamp"):
            actions.append("Timestamp added")
        if params.get("checksum"):
            actions.append("Checksum generated")
        return {"status": "ok", "actions": actions, "message": "Archive protocol activated."}
