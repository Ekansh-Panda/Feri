import os
import subprocess
import importlib
import time


class PluginAuthor:
    def __init__(self, plugin_dir="plugins"):
        self.plugin_dir = plugin_dir

    def generate_plugin(self, name: str, description: str, code: str) -> str:
        path = os.path.join(self.plugin_dir, f"{name}.py")

        with open(path, "w") as f:
            f.write(code)

        result = subprocess.run(
            ["python", "-m", "py_compile", path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            os.remove(path)
            return f"Plugin '{name}' failed syntax check:\n{result.stderr}"

        try:
            mod = importlib.import_module(f"plugins.{name}")
            importlib.reload(mod)
        except Exception as e:
            return f"Plugin written but hot-reload failed: {e}"

        return f"FORGE COMPLETE: Plugin '{name}' created, tested, and loaded. {description}"

    def list_plugins(self) -> list:
        plugins = []
        for f in os.listdir(self.plugin_dir):
            if f.endswith(".py") and not f.startswith("_"):
                plugins.append(f.replace(".py", ""))
        return plugins

    def disable_plugin(self, name: str):
        path = os.path.join(self.plugin_dir, f"{name}.py")
        disabled = path + ".disabled"
        if os.path.exists(path):
            os.rename(path, disabled)
            return f"Plugin '{name}' disabled."
        return f"Plugin '{name}' not found."

    def enable_plugin(self, name: str):
        disabled = os.path.join(self.plugin_dir, f"{name}.py.disabled")
        path = os.path.join(self.plugin_dir, f"{name}.py")
        if os.path.exists(disabled):
            os.rename(disabled, path)
            return f"Plugin '{name}' re-enabled."
        return f"Disabled plugin '{name}' not found."
