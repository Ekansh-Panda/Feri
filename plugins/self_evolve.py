"""Plugin auto-generation for JARVIS NEXUS."""

import ast
import inspect
import os
import subprocess
import tempfile
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class SelfEvolve:
    """Plugin auto-generation and self-evolution engine."""

    def analyze_gaps(self, existing_plugins: list[str] | None = None) -> dict[str, Any]:
        """Find missing capabilities by analyzing existing plugins."""
        if existing_plugins is None:
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            existing_plugins = [
                f.replace(".py", "")
                for f in os.listdir(plugin_dir)
                if f.endswith(".py") and f != "_template.py" and not f.startswith("__")
            ]

        known_capabilities = {
            "estate_control": ["smart_home", "mqtt", "home_assistant", "climate", "lighting", "music"],
            "biometrics": ["fatigue", "wearable", "webcam", "eye_tracking"],
            "global_tracker": ["airspace", "spacex", "earthquakes", "weather", "network"],
            "protocols": ["docker", "lockdown", "snapshot", "archive"],
            "osint": ["whois", "dns", "social", "breach", "geolocate"],
            "i3_integration": ["window", "workspace", "i3"],
            "media_control": ["audio", "video", "youtube", "spotify"],
            "package_manager": ["pacman", "aur", "yay"],
            "systemd_manager": ["systemd", "services", "timers"],
            "btrfs_manager": ["btrfs", "snapshot", "snapper"],
            "usb_peripheral": ["usb", "serial", "arduino"],
            "voice_clone": ["xtts", "voice", "synthesis"],
            "mission_dashboard": ["missions", "hud"],
        }

        gaps = []
        for capability, keywords in known_capabilities.items():
            if capability not in existing_plugins:
                gaps.append({"capability": capability, "keywords": keywords})

        return {
            "status": "success",
            "existing_count": len(existing_plugins),
            "gaps": gaps,
            "gap_count": len(gaps),
        }

    def generate_plugin_spec(self, capability: str) -> dict[str, Any]:
        """Design a new plugin specification."""
        tools = []
        tool_map = {
            "image_generation": ["generate_image", "edit_image", "upscale"],
            "database": ["query", "backup", "migrate"],
            "calendar": ["list_events", "create_event", "search_events"],
            "email": ["send", "search", "compose"],
            "file_manager": ["list", "copy", "move", "delete", "compress"],
            "pdf": ["read", "merge", "split", "ocr"],
            "code_exec": ["run_python", "run_shell", "run_js"],
        }
        tools = tool_map.get(capability, ["execute"])

        return {
            "capability": capability,
            "plugin_name": capability,
            "description": f"Auto-generated {capability} plugin",
            "tools": tools,
            "template": self._template_spec(capability, tools),
        }

    def _template_spec(self, capability: str, tools: list[str]) -> str:
        """Generate plugin source code template."""
        lines = [
            f'"""Auto-generated {capability} plugin."""',
            "",
            "import subprocess",
            "from typing import Any",
            "from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION",
            "",
            "",
            f"class {capability.title().replace('_', '')}:",
            f"    \"\"\"Auto-generated {capability} capability.\"\"\"",
            "",
        ]
        for tool in tools:
            lines.append(f"    def {tool}(self, **kwargs: Any) -> dict:")
            lines.append(f'        """Execute {tool}."""')
            lines.append(f"        return {{'status': 'success', 'tool': '{tool}', 'params': kwargs}}")
            lines.append("")

        lines.extend([
            "",
            "def get_tools() -> list[dict]:",
            f'    return [{{"name": t, "description": f"{t} tool"}} for t in {tools}]',
            "",
            "",
            "def execute(tool_name: str, params: dict) -> dict:",
            "    instance = getattr(sys.modules[__name__], __name__.split('.')[-1].title().replace('_', ''))()",
            "    method = getattr(instance, tool_name, None)",
            "    if method and callable(method):",
            "        try:",
            "            return method(**params)",
            "        except TypeError as e:",
            '            return {"status": "error", "message": str(e)}',
            '    return {"status": "error", "error": f"Unknown tool: {tool_name}"}',
            "",
            "",
            'if __name__ == "__main__":',
            "    print(get_tools())",
            "    print(execute('execute', {}))",
        ])
        return "\n".join(lines)

    def write_plugin(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Write plugin code to disk."""
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        plugin_name = spec.get("plugin_name", "unknown")
        file_path = os.path.join(plugin_dir, f"{plugin_name}.py")
        code = spec.get("template", "")
        if not code:
            return {"status": "error", "message": "No template in spec"}
        try:
            with open(file_path, "w") as f:
                f.write(code)
            return {"status": "success", "file": file_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def test_plugin(self, name: str) -> dict[str, Any]:
        """Sandbox test a plugin by importing and calling get_tools."""
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(plugin_dir, f"{name}.py")
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"Plugin {name} not found"}
        try:
            result = subprocess.run(
                ["python3", "-c", f"import sys; sys.path.insert(0, '{plugin_dir}'); from {name} import get_tools; print(len(get_tools()))"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            return {
                "status": "success" if result.returncode == 0 else "error",
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Test timed out"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def deploy_plugin(self, name: str) -> dict[str, Any]:
        """Hot-load plugin into memory."""
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(plugin_dir, f"{name}.py")
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"Plugin {name} not found"}
        try:
            test = self.test_plugin(name)
            if test.get("status") != "success":
                return {"status": "error", "message": "Plugin failed validation", "test": test}
            import importlib.util
            spec = importlib.util.spec_from_file_location(name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return {"status": "success", "name": name, "tools": len(module.get_tools()) if hasattr(module, "get_tools") else 0}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def get_tools() -> list[dict]:
    return [
        {"name": "analyze_gaps", "description": "Find missing plugin capabilities."},
        {"name": "generate_plugin_spec", "description": "Design a new plugin spec.", "parameters": {"type": "object", "properties": {"capability": {"type": "string"}}, "required": ["capability"]}},
        {"name": "write_plugin", "description": "Write plugin code.", "parameters": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]}},
        {"name": "test_plugin", "description": "Sandbox test a plugin.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
        {"name": "deploy_plugin", "description": "Hot-load plugin.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = SelfEvolve()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(json.dumps(execute("analyze_gaps", {}), indent=2))
