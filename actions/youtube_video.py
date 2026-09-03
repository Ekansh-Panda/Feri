"""
youtube_video.py — yt-dlp based YouTube search, play, download and metadata.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _ytdlp() -> Optional[str]:
    return shutil.which("yt-dlp") or shutil.which("youtube-dl")


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return subprocess.CompletedProcess(cmd, -1, "", str(e))


class YouTubeVideo:
    """Search, play, download and inspect YouTube videos via yt-dlp."""

    DEFAULT_OUTPUT_DIR = Path.home() / ".jarvis" / "downloads"

    def __init__(self, output_dir: Optional[Path | str] = None):
        self.output_dir = Path(output_dir) if output_dir else self.DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Search ─────────────────────────────────────────────────────────────

    def search(self, query: str, max_results: int = 8) -> list[dict]:
        """Plain yt-dlp search — title/url/duration/id."""
        ytdlp = _ytdlp()
        if not ytdlp:
            return []
        cmd = [
            ytdlp,
            f"ytsearch{max_results}:{query}",
            "--dump-json",
            "--skip-download",
            "--no-warnings",
        ]
        r = _run(cmd, timeout=45)
        if r.returncode != 0:
            return []
        out: list[dict] = []
        for line in r.stdout.splitlines():
            try:
                d = json.loads(line)
            except Exception:
                continue
            out.append({
                "id":        d.get("id", ""),
                "title":     d.get("title", ""),
                "url":       d.get("webpage_url", ""),
                "duration":  d.get("duration", 0),
                "channel":   d.get("channel") or d.get("uploader", ""),
                "view_count": d.get("view_count", 0),
                "thumbnail": d.get("thumbnail", ""),
            })
        return out

    # ── Playback ───────────────────────────────────────────────────────────

    def play(self, query: str, audio_only: bool = False) -> bool:
        """Stream the top match through mpv."""
        results = self.search(query, max_results=1)
        if not results:
            return False
        url = results[0]["url"]
        mpv = shutil.which("mpv")
        if not mpv:
            return False
        cmd = [mpv, "--no-terminal"]
        if audio_only:
            cmd += ["--no-video"]
        cmd.append(url)
        try:
            subprocess.Popen(cmd,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def play_url(self, url: str, audio_only: bool = False) -> bool:
        mpv = shutil.which("mpv")
        if not mpv or not url:
            return False
        cmd = [mpv, "--no-terminal"]
        if audio_only:
            cmd += ["--no-video"]
        cmd.append(url)
        try:
            subprocess.Popen(cmd,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    # ── Download ───────────────────────────────────────────────────────────

    def download(self, url: str, output_dir: Optional[Path | str] = None,
                 audio_only: bool = False) -> Optional[Path]:
        ytdlp = _ytdlp()
        if not ytdlp or not url:
            return None
        out_dir = Path(output_dir) if output_dir else self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        out_template = str(out_dir / "%(title).150B [%(id)s].%(ext)s")
        cmd = [ytdlp, "-o", out_template, "--no-mtime", "--no-warnings"]
        if audio_only:
            cmd += ["-x", "--audio-format", "mp3"]
        cmd.append(url)
        r = _run(cmd, timeout=600)
        if r.returncode != 0:
            print(f"[YouTube] download failed: {r.stderr.strip()}")
            return None
        # Return newest file in out_dir
        files = sorted(out_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        return files[0] if files else None

    # ── Metadata ───────────────────────────────────────────────────────────

    def get_info(self, url: str) -> dict:
        ytdlp = _ytdlp()
        if not ytdlp or not url:
            return {"error": "yt-dlp missing or no url"}
        r = _run([ytdlp, "--dump-json", "--skip-download", url], timeout=30)
        if r.returncode != 0 or not r.stdout.strip():
            return {"error": f"could not fetch info: {r.stderr.strip()}"}
        try:
            d = json.loads(r.stdout.splitlines()[0])
            return {
                "id":           d.get("id", ""),
                "title":        d.get("title", ""),
                "channel":      d.get("channel") or d.get("uploader", ""),
                "duration":     d.get("duration", 0),
                "view_count":   d.get("view_count", 0),
                "like_count":   d.get("like_count", 0),
                "upload_date":  d.get("upload_date", ""),
                "description":  d.get("description", "")[:1000],
                "thumbnail":    d.get("thumbnail", ""),
                "tags":         d.get("tags", [])[:20],
                "url":          d.get("webpage_url", url),
            }
        except Exception as e:
            return {"error": f"parse error: {e}"}