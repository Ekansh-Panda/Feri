"""pacman/yay AUR management plugin."""

import subprocess
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class PackageManager:
    """pacman/yay AUR management."""

    def install(self, package: str) -> dict[str, Any]:
        """Install package via pacman -S."""
        try:
            result = subprocess.run(
                ["sudo", "pacman", "-S", "--noconfirm", "--needed", package],
                capture_output=True, text=True, timeout=120, check=False,
            )
            return {"status": "success" if result.returncode == 0 else "error", "code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        except FileNotFoundError:
            return {"status": "error", "message": "pacman not found"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Installation timed out"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def install_aur(self, package: str) -> dict[str, Any]:
        """Install AUR package via yay -S."""
        try:
            result = subprocess.run(
                ["yay", "-S", "--noconfirm", "--needed", package],
                capture_output=True, text=True, timeout=300, check=False,
            )
            return {"status": "success" if result.returncode == 0 else "error", "code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        except FileNotFoundError:
            return {"status": "error", "message": "yay not installed"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "AUR build timed out"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def remove(self, package: str) -> dict[str, Any]:
        """Remove package via pacman -Rns."""
        try:
            result = subprocess.run(
                ["sudo", "pacman", "-Rns", "--noconfirm", package],
                capture_output=True, text=True, timeout=120, check=False,
            )
            return {"status": "success" if result.returncode == 0 else "error", "code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def update_system(self) -> dict[str, Any]:
        """Update system via pacman -Syu."""
        try:
            result = subprocess.run(
                ["sudo", "pacman", "-Syu", "--noconfirm"],
                capture_output=True, text=True, timeout=600, check=False,
            )
            return {"status": "success" if result.returncode == 0 else "error", "code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def search(self, query: str) -> dict[str, Any]:
        """Search packages via pacman -Ss."""
        try:
            result = subprocess.run(
                ["pacman", "-Ss", query],
                capture_output=True, text=True, timeout=30, check=False,
            )
            return {"status": "success" if result.returncode == 0 else "error", "results": result.stdout}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_installed(self) -> dict[str, Any]:
        """List explicitly installed packages."""
        try:
            result = subprocess.run(
                ["pacman", "-Qe"],
                capture_output=True, text=True, timeout=30, check=True,
            )
            packages = [line.split()[0] for line in result.stdout.strip().splitlines() if line.strip()]
            return {"status": "success", "count": len(packages), "packages": packages}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def clean_cache(self) -> dict[str, Any]:
        """Clean pacman cache with paccache -r."""
        try:
            result = subprocess.run(
                ["sudo", "paccache", "-r", "-k", "3"],
                capture_output=True, text=True, timeout=60, check=False,
            )
            return {"status": "success" if result.returncode == 0 else "error", "stdout": result.stdout}
        except FileNotFoundError:
            return {"status": "error", "message": "paccache not found"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def check_updates(self) -> dict[str, Any]:
        """Check AUR updates via yay -Qu."""
        try:
            result = subprocess.run(
                ["yay", "-Qu"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            updates = result.stdout.strip().splitlines()
            return {"status": "success", "updates_available": len(updates), "updates": updates}
        except FileNotFoundError:
            return {"status": "error", "message": "yay not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def get_tools() -> list[dict]:
    return [
        {"name": "install", "description": "Install package via pacman.", "parameters": {"type": "object", "properties": {"package": {"type": "string"}}, "required": ["package"]}},
        {"name": "install_aur", "description": "Install AUR package via yay.", "parameters": {"type": "object", "properties": {"package": {"type": "string"}}, "required": ["package"]}},
        {"name": "remove", "description": "Remove package.", "parameters": {"type": "object", "properties": {"package": {"type": "string"}}, "required": ["package"]}},
        {"name": "update_system", "description": "Full system update."},
        {"name": "search", "description": "Search packages.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
        {"name": "list_installed", "description": "List explicitly installed packages."},
        {"name": "clean_cache", "description": "Clean pacman cache."},
        {"name": "check_updates", "description": "Check AUR updates."},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = PackageManager()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(json.dumps(execute("check_updates", {}), indent=2))
