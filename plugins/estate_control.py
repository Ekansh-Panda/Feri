"""Home Assistant / MQTT smart home control plugin."""

import json
import subprocess
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class EstateControl:
    """Home Assistant / MQTT smart home control."""

    def __init__(self, ha_url: str, ha_token: str) -> None:
        self.ha_url = ha_url.rstrip("/")
        self.ha_token = ha_token
        self.headers = {
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
        }

    def _ha_request(self, method: str, endpoint: str, data: dict | None = None) -> dict:
        import urllib.request

        url = f"{self.ha_url}/api/{endpoint.lstrip('/')}"
        if data:
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(url, data=payload, method=method)
        else:
            req = urllib.request.Request(url, method=method)
        for k, v in self.headers.items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            return {"status": "error", "code": e.code, "message": error_body}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_all_states(self) -> dict:
        """Return all HA entity states."""
        return self._ha_request("GET", "states")

    def execute_scene(self, scene: str) -> dict:
        """Activate a Home Assistant scene."""
        return self._ha_request("POST", "services/scene/turn_on", {"entity_id": scene})

    def secure_perimeter(self) -> dict:
        """Lock all doors, turn on perimeter lights, and lock screen."""
        results = {}
        results["locks"] = self._ha_request(
            "POST", "services/lock/lock", {"entity_id": "all"}
        )
        results["lights"] = self._ha_request(
            "POST", "services/light/turn_on",
            {"entity_id": "group.perimeter_lights", "brightness_pct": 100},
        )
        results["screen_lock"] = self.lock_screen()
        return results

    def set_climate(self, temp: float) -> dict:
        """Set thermostat temperature."""
        return self._ha_request(
            "POST", "services/climate/set_temperature",
            {"entity_id": "climate.thermostat", "temperature": temp},
        )

    def set_screen_brightness(self, pct: int) -> dict:
        """Set screen brightness using brightnessctl."""
        pct = max(0, min(100, pct))
        try:
            result = subprocess.run(
                ["brightnessctl", "set", f"{pct}%"],
                capture_output=True, text=True, check=True,
            )
            return {"status": "success", "stdout": result.stdout}
        except FileNotFoundError:
            return {"status": "error", "message": "brightnessctl not installed"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": e.stderr}

    def set_volume(self, pct: int) -> dict:
        """Set system volume using pactl."""
        pct = max(0, min(150, pct))
        try:
            result = subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{pct}%"],
                capture_output=True, text=True, check=True,
            )
            return {"status": "success", "stdout": result.stdout}
        except FileNotFoundError:
            return {"status": "error", "message": "pactl not installed"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": e.stderr}

    def mute_all(self) -> dict:
        """Mute all audio sinks."""
        try:
            result = subprocess.run(
                ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"],
                capture_output=True, text=True, check=True,
            )
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def unmute_all(self) -> dict:
        """Unmute all audio sinks."""
        try:
            result = subprocess.run(
                ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"],
                capture_output=True, text=True, check=True,
            )
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def play_ambiance(self, genre: str) -> dict:
        """Play ambiance music via mpv with yt-dlp."""
        genre_map = {
            "lofi": "lofi hip hop radio",
            "jazz": "jazz relax",
            "ambient": "ambient music",
            "synthwave": "synthwave radio",
            "classical": "classical music",
        }
        query = genre_map.get(genre.lower(), genre)
        try:
            subprocess.Popen(
                ["mpv", f"ytdl://ytsearch:{query}", "--no-video", "--loop"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"status": "success", "genre": genre, "query": query}
        except FileNotFoundError:
            return {"status": "error", "message": "mpv not installed"}

    def stop_music(self) -> dict:
        """Stop music playback using playerctl."""
        try:
            result = subprocess.run(
                ["playerctl", "stop"],
                capture_output=True, text=True, check=True,
            )
            return {"status": "success"}
        except FileNotFoundError:
            return {"status": "error", "message": "playerctl not installed"}
        except subprocess.CalledProcessError:
            return {"status": "success"}

    def lock_screen(self) -> dict:
        """Lock screen with i3lock."""
        try:
            result = subprocess.run(
                ["i3lock", "-c", "000000"],
                capture_output=True, text=True, check=False,
            )
            return {"status": "success", "code": result.returncode}
        except FileNotFoundError:
            return {"status": "error", "message": "i3lock not installed"}

    def get_hardware_inventory(self) -> dict:
        """Get hardware inventory via lshw, lspci, lsusb."""
        def run(cmd: list[str]) -> str:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
                return r.stdout
            except Exception as e:
                return f"Error: {e}"

        return {
            "lshw": run(["lshw", "-short"]),
            "lspci": run(["lspci", "-vvv"]),
            "lsusb": run(["lsusb", "-v"]),
        }


def get_tools() -> list[dict]:
    return [
        {"name": "get_all_states", "description": "Get all Home Assistant entity states."},
        {"name": "execute_scene", "description": "Activate a HA scene.", "parameters": {"type": "object", "properties": {"scene": {"type": "string"}}, "required": ["scene"]}},
        {"name": "secure_perimeter", "description": "Lock all, lights on, screen lock."},
        {"name": "set_climate", "description": "Set thermostat temperature.", "parameters": {"type": "object", "properties": {"temp": {"type": "number"}}, "required": ["temp"]}},
        {"name": "set_screen_brightness", "description": "Set screen brightness (0-100).", "parameters": {"type": "object", "properties": {"pct": {"type": "integer"}}, "required": ["pct"]}},
        {"name": "set_volume", "description": "Set system volume (0-150).", "parameters": {"type": "object", "properties": {"pct": {"type": "integer"}}, "required": ["pct"]}},
        {"name": "mute_all", "description": "Mute all audio sinks."},
        {"name": "unmute_all", "description": "Unmute all audio sinks."},
        {"name": "play_ambiance", "description": "Play ambiance music by genre.", "parameters": {"type": "object", "properties": {"genre": {"type": "string"}}, "required": ["genre"]}},
        {"name": "stop_music", "description": "Stop music playback."},
        {"name": "lock_screen", "description": "Lock screen with i3lock."},
        {"name": "get_hardware_inventory", "description": "Get hardware inventory."},
    ]


def execute(tool_name: str, params: dict) -> dict:
    """Execute a tool by name."""
    instance = EstateControl("http://localhost:8123", "")
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(json.dumps(get_tools(), indent=2))
    print(json.dumps(execute("get_hardware_inventory", {}), indent=2))
