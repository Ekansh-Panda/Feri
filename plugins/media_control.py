"""Media control plugin: playerctl, mpv, spotify, ffmpeg."""

import subprocess
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class MediaControl:
    """Media control via playerctl, mpv, spotify."""

    def play_pause(self) -> dict:
        """Toggle play/pause."""
        try:
            subprocess.run(["playerctl", "play-pause"], check=True, timeout=5)
            return {"status": "success"}
        except FileNotFoundError:
            return {"status": "error", "message": "playerctl not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def next_track(self) -> dict:
        """Next track."""
        try:
            subprocess.run(["playerctl", "next"], check=True, timeout=5)
            return {"status": "success"}
        except FileNotFoundError:
            return {"status": "error", "message": "playerctl not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def prev_track(self) -> dict:
        """Previous track."""
        try:
            subprocess.run(["playerctl", "previous"], check=True, timeout=5)
            return {"status": "success"}
        except FileNotFoundError:
            return {"status": "error", "message": "playerctl not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def stop(self) -> dict:
        """Stop playback."""
        try:
            subprocess.run(["playerctl", "stop"], check=True, timeout=5)
            return {"status": "success"}
        except FileNotFoundError:
            return {"status": "error", "message": "playerctl not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def set_volume(self, pct: int) -> dict:
        """Set volume (0-100)."""
        pct = max(0, min(100, pct))
        try:
            subprocess.run(["playerctl", "volume", str(pct / 100.0)], check=True, timeout=5)
            return {"status": "success"}
        except FileNotFoundError:
            return {"status": "error", "message": "playerctl not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_volume(self) -> dict:
        """Get current volume."""
        try:
            r = subprocess.run(["playerctl", "volume"], capture_output=True, text=True, check=True, timeout=5)
            return {"status": "success", "volume": float(r.stdout.strip())}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_status(self) -> dict:
        """Get current playback status: title, artist, status."""
        try:
            r_title = subprocess.run(["playerctl", "metadata", "title"], capture_output=True, text=True, timeout=5, check=False)
            r_artist = subprocess.run(["playerctl", "metadata", "artist"], capture_output=True, text=True, timeout=5, check=False)
            r_status = subprocess.run(["playerctl", "status"], capture_output=True, text=True, timeout=5, check=False)
            return {
                "status": "success",
                "title": r_title.stdout.strip(),
                "artist": r_artist.stdout.strip(),
                "playback_status": r_status.stdout.strip(),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def play_youtube(self, query: str) -> dict:
        """Play YouTube audio via mpv + ytdl."""
        try:
            subprocess.Popen(
                ["mpv", f"ytdl://ytsearch:{query}", "--no-video", "--loop"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return {"status": "success", "query": query}
        except FileNotFoundError:
            return {"status": "error", "message": "mpv not installed"}

    def play_youtube_video(self, url: str) -> dict:
        """Play YouTube video via mpv."""
        try:
            subprocess.Popen(
                ["mpv", f"ytdl://{url}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return {"status": "success", "url": url}
        except FileNotFoundError:
            return {"status": "error", "message": "mpv not installed"}

    def download_youtube(self, url: str, output_dir: str = "/tmp") -> dict:
        """Download YouTube video via yt-dlp."""
        try:
            os.makedirs(output_dir, exist_ok=True)
            result = subprocess.run(
                ["yt-dlp", "-P", output_dir, url],
                capture_output=True, text=True, timeout=120,
            )
            return {"status": "success" if result.returncode == 0 else "error", "stdout": result.stdout, "stderr": result.stderr}
        except FileNotFoundError:
            return {"status": "error", "message": "yt-dlp not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def record_screen(self, duration: int, output: str) -> dict:
        """Record screen via ffmpeg x11grab."""
        try:
            cmd = [
                "ffmpeg", "-y", "-f", "x11grab", "-r", "30", "-s", "1920x1080",
                "-i", ":0.0", "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                output,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 30)
            return {"status": "success" if result.returncode == 0 else "error", "file": output}
        except FileNotFoundError:
            return {"status": "error", "message": "ffmpeg not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def get_tools() -> list[dict]:
    return [
        {"name": "play_pause", "description": "Toggle play/pause."},
        {"name": "next_track", "description": "Next track."},
        {"name": "prev_track", "description": "Previous track."},
        {"name": "stop", "description": "Stop playback."},
        {"name": "set_volume", "description": "Set volume (0-100).", "parameters": {"type": "object", "properties": {"pct": {"type": "integer"}}, "required": ["pct"]}},
        {"name": "get_volume", "description": "Get current volume."},
        {"name": "get_status", "description": "Get playback status."},
        {"name": "play_youtube", "description": "Play YouTube audio.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
        {"name": "play_youtube_video", "description": "Play YouTube video.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
        {"name": "download_youtube", "description": "Download YouTube video.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}, "output_dir": {"type": "string"}}, "required": ["url"]}},
        {"name": "record_screen", "description": "Record screen.", "parameters": {"type": "object", "properties": {"duration": {"type": "integer"}, "output": {"type": "string"}}, "required": ["duration", "output"]}},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = MediaControl()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(json.dumps(execute("get_status", {}), indent=2))
