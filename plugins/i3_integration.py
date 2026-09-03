"""i3 window/workspace integration plugin."""

import json
import os
import subprocess
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class I3Integration:
    """i3-msg window/workspace control."""

    def _i3_msg(self, command: str) -> Any:
        """Execute i3-msg command and return parsed JSON or text."""
        try:
            result = subprocess.run(
                ["i3-msg", command],
                capture_output=True, text=True, check=True, timeout=10,
            )
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return result.stdout.strip()
        except FileNotFoundError:
            return {"status": "error", "message": "i3-msg not installed"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": e.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_workspace_tree(self) -> dict[str, Any]:
        """Get full i3 tree JSON."""
        tree = self._i3_msg("--tree")
        if isinstance(tree, dict) and tree.get("status") == "error":
            return tree
        return {"status": "success", "tree": tree}

    def switch_workspace(self, number: int) -> dict[str, Any]:
        """Switch to workspace by number."""
        result = self._i3_msg(f"workspace {number}")
        return {"status": "success", "result": result}

    def launch_on_workspace(self, app: str, workspace: int) -> dict[str, Any]:
        """Launch application on specific workspace."""
        self.switch_workspace(workspace)
        try:
            subprocess.Popen([app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"status": "success", "app": app, "workspace": workspace}
        except FileNotFoundError:
            return {"status": "error", "message": f"{app} not found"}

    def tile_layout(self, layout: str) -> dict[str, Any]:
        """Set tiling layout: splith, splitv, stack, tab."""
        valid = {"splith", "splitv", "stack", "tab"}
        layout = layout.lower()
        if layout not in valid:
            return {"status": "error", "message": f"Invalid layout. Must be one of {valid}"}
        result = self._i3_msg(f"layout {layout}")
        return {"status": "success", "layout": layout, "result": result}

    def get_all_windows(self) -> list[dict[str, Any]]:
        """Get all open windows with titles, PIDs, workspaces."""
        tree = self.get_workspace_tree()
        if tree.get("status") == "error":
            return []
        root = tree.get("tree", {})
        windows = []
        for ws in root.get("nodes", root.get("workspaces", [])):
            if isinstance(ws, dict):
                self._extract_windows(ws, windows)
        return windows

    def _extract_windows(self, node: dict, windows: list) -> None:
        """Recursively extract windows from tree node."""
        if node.get("type") == "con":
            windows.append({
                "id": node.get("id"),
                "title": node.get("name"),
                "pid": node.get("pid"),
                "workspace": node.get("workspace"),
                "focused": node.get("focused", False),
                "window_properties": node.get("window_properties", {}),
            })
        for child in node.get("nodes", []):
            self._extract_windows(child, windows)

    def kill_window(self, pid: int) -> dict[str, Any]:
        """Kill window by PID."""
        try:
            os.kill(pid, 9)
            return {"status": "success", "pid": pid}
        except ProcessLookupError:
            return {"status": "error", "message": f"Process {pid} not found"}
        except PermissionError:
            return {"status": "error", "message": f"Permission denied for PID {pid}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def scratchpad_show(self) -> dict[str, Any]:
        """Show scratchpad window."""
        result = self._i3_msg("scratchpad show")
        return {"status": "success", "result": result}

    def fullscreen_toggle(self) -> dict[str, Any]:
        """Toggle fullscreen for focused window."""
        result = self._i3_msg("fullscreen toggle")
        return {"status": "success", "result": result}

    def resize_window(self, direction: str, amount: int = 10) -> dict[str, Any]:
        """Resize window in direction (left, right, up, down)."""
        valid = {"left", "right", "up", "down"}
        direction = direction.lower()
        if direction not in valid:
            return {"status": "error", "message": f"Invalid direction. Must be one of {valid}"}
        result = self._i3_msg(f"resize {direction} {amount} px")
        return {"status": "success", "direction": direction, "amount": amount, "result": result}

    def move_to_workspace(self, direction: str) -> dict[str, Any]:
        """Move focused container to workspace (prev/next or number)."""
        result = self._i3_msg(f"move container to workspace {direction}")
        return {"status": "success", "direction": direction, "result": result}


def get_tools() -> list[dict]:
    return [
        {"name": "get_workspace_tree", "description": "Get full i3 tree JSON."},
        {"name": "switch_workspace", "description": "Switch to workspace by number.", "parameters": {"type": "object", "properties": {"number": {"type": "integer"}}, "required": ["number"]}},
        {"name": "launch_on_workspace", "description": "Launch app on workspace.", "parameters": {"type": "object", "properties": {"app": {"type": "string"}, "workspace": {"type": "integer"}}, "required": ["app", "workspace"]}},
        {"name": "tile_layout", "description": "Set tiling layout.", "parameters": {"type": "object", "properties": {"layout": {"type": "string"}}, "required": ["layout"]}},
        {"name": "get_all_windows", "description": "Get all open windows."},
        {"name": "kill_window", "description": "Kill window by PID.", "parameters": {"type": "object", "properties": {"pid": {"type": "integer"}}, "required": ["pid"]}},
        {"name": "scratchpad_show", "description": "Show scratchpad."},
        {"name": "fullscreen_toggle", "description": "Toggle fullscreen."},
        {"name": "resize_window", "description": "Resize window.", "parameters": {"type": "object", "properties": {"direction": {"type": "string"}, "amount": {"type": "integer"}}, "required": ["direction"]}},
        {"name": "move_to_workspace", "description": "Move to workspace.", "parameters": {"type": "object", "properties": {"direction": {"type": "string"}}, "required": ["direction"]}},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = I3Integration()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    i3 = I3Integration()
    print(json.dumps(i3.get_all_windows(), indent=2))
