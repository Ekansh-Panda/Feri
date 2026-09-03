"""Btrfs snapshot and rollback manager plugin."""

import json
import os
import subprocess
from datetime import datetime
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class BtrfsManager:
    """Btrfs snapshot, rollback, and filesystem management."""

    def create_snapshot(self, name: str) -> dict[str, Any]:
        """Create a new btrfs snapshot using snapper."""
        try:
            result = subprocess.run(
                ["sudo", "snapper", "create", "--type", "single", "--print-number", "--description", name],
                capture_output=True, text=True, timeout=30, check=True,
            )
            number = result.stdout.strip()
            return {"status": "success", "snapshot_number": number, "name": name}
        except FileNotFoundError:
            return {"status": "error", "message": "snapper not installed"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": e.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_snapshots(self) -> dict[str, Any]:
        """List all btrfs snapshots via snapper."""
        try:
            result = subprocess.run(
                ["sudo", "snapper", "list"],
                capture_output=True, text=True, timeout=15, check=False,
            )
            return {"status": "success", "output": result.stdout, "stderr": result.stderr}
        except FileNotFoundError:
            return {"status": "error", "message": "snapper not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def rollback_snapshot(self, number: int) -> dict[str, Any]:
        """Rollback to a specific snapshot number via snapper."""
        try:
            result = subprocess.run(
                ["sudo", "snapper", "rollback", str(number)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            return {"status": "success" if result.returncode == 0 else "error", "stdout": result.stdout, "stderr": result.stderr}
        except FileNotFoundError:
            return {"status": "error", "message": "snapper not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_default_snapshot(self) -> dict[str, Any]:
        """Get current boot snapshot (default snapshot)."""
        try:
            result = subprocess.run(
                ["sudo", "snapper", "list"],
                capture_output=True, text=True, timeout=15, check=False,
            )
            lines = result.stdout.strip().splitlines()
            for line in lines:
                parts = line.split()
                if len(parts) >= 2 and parts[-1].lower() in ("yes", "boot"):
                    return {"status": "success", "default_snapshot": parts[0], "line": line}
            return {"status": "success", "default_snapshot": None, "note": "No default snapshot found"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def delete_snapshot(self, number: int) -> dict[str, Any]:
        """Delete a snapshot by number."""
        try:
            result = subprocess.run(
                ["sudo", "snapper", "delete", str(number)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            return {"status": "success" if result.returncode == 0 else "error", "number": number}
        except FileNotFoundError:
            return {"status": "error", "message": "snapper not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_filesystem_usage(self) -> dict[str, Any]:
        """Get btrfs filesystem disk usage."""
        try:
            result = subprocess.run(
                ["sudo", "btrfs", "filesystem", "df", "/"],
                capture_output=True, text=True, timeout=15, check=False,
            )
            return {"status": "success", "output": result.stdout}
        except FileNotFoundError:
            return {"status": "error", "message": "btrfs not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def get_tools() -> list[dict]:
    return [
        {"name": "create_snapshot", "description": "Create a btrfs snapshot.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
        {"name": "list_snapshots", "description": "List all snapshots."},
        {"name": "rollback_snapshot", "description": "Rollback to snapshot.", "parameters": {"type": "object", "properties": {"number": {"type": "integer"}}, "required": ["number"]}},
        {"name": "get_default_snapshot", "description": "Get default snapshot."},
        {"name": "delete_snapshot", "description": "Delete snapshot.", "parameters": {"type": "object", "properties": {"number": {"type": "integer"}}, "required": ["number"]}},
        {"name": "get_filesystem_usage", "description": "Get btrfs filesystem usage."},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = BtrfsManager()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(json.dumps(execute("list_snapshots", {}), indent=2))
