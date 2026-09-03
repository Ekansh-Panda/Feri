"""
screen_processor.py — screenshot, webcam, OCR and vision descriptions for
JARVIS NEXUS on Arch Linux + i3wm.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _run(cmd: list[str], timeout: int = 15, check: bool = False) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
    except Exception as e:
        return subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr=str(e))


def _run_bytes(cmd: list[str], timeout: int = 15) -> bytes:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.stdout or b""
    except Exception:
        return b""


class ScreenProcessor:
    """Screenshot, webcam, OCR and Gemini-Vision description."""

    SCREENSHOT_DIR = Path.home() / ".jarvis" / "screenshots"
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Screenshots ─────────────────────────────────────────────────────────

    def capture_screen(self, region: str = "full") -> Optional[Path]:
        """scrot screenshot. `region` may be 'full' or 'WxH+X+Y'."""
        out = self.SCREENSHOT_DIR / f"screen_{int(time.time())}.png"
        if region == "full":
            r = _run(["scrot", str(out)])
        else:
            r = _run(["scrot", "-a", region, str(out)])
        if r.returncode == 0 and out.exists():
            return out
        # Fallback to import (ImageMagick)
        if _which("import"):
            r = _run(["import", "-window", "root", str(out)])
            if r.returncode == 0 and out.exists():
                return out
        # mss python fallback
        try:
            import mss
            with mss.mss() as sct:
                img = sct.grab(sct.monitors[0])
                from PIL import Image
                Image.frombytes("RGB", img.size, img.rgb).save(out)
                return out
        except Exception:
            return None

    def capture_window(self, window_id: Optional[str] = None) -> Optional[Path]:
        """Capture the focused window or a specific x11 window id."""
        out = self.SCREENSHOT_DIR / f"window_{int(time.time())}.png"
        if window_id:
            r = _run(["scrot", "-u", str(window_id), str(out)])
        else:
            # Focus window then screenshot root — close approximation
            r = _run(["scrot", "-u", str(out)])
        if r.returncode == 0 and out.exists():
            return out
        if _which("import"):
            wid = window_id or "root"
            r = _run(["import", "-window", wid, str(out)])
            if r.returncode == 0 and out.exists():
                return out
        return None

    def capture_webcam(self, device: str = "/dev/video0") -> Optional[Path]:
        """fswebcam/ffmpeg capture."""
        out = self.SCREENSHOT_DIR / f"webcam_{int(time.time())}.jpg"
        if _which("fswebcam"):
            r = _run([
                "fswebcam", "-d", device, "-r", "1280x720",
                "--no-banner", "--jpeg", "95", str(out),
            ])
            if r.returncode == 0 and out.exists():
                return out
        if _which("ffmpeg"):
            r = _run([
                "ffmpeg", "-y", "-f", "v4l2", "-i", device,
                "-frames:v", "1", "-q:v", "2", str(out),
            ])
            if r.returncode == 0 and out.exists():
                return out
        return None

    # ── OCR ─────────────────────────────────────────────────────────────────

    def ocr(self, image_path: str | Path) -> str:
        """Tesseract OCR over an image. Returns extracted text."""
        image_path = Path(image_path)
        if not image_path.exists():
            return ""
        out_base = tempfile.NamedTemporaryFile(suffix="", delete=False).name
        try:
            r = _run(["tesseract", str(image_path), out_base, "-l", "eng+osd"])
            if r.returncode != 0:
                return ""
            txt = Path(out_base + ".txt").read_text(encoding="utf-8", errors="ignore")
            return txt.strip()
        finally:
            for p in (Path(out_base), Path(out_base + ".txt")):
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass

    def find_text_on_screen(self, text: str) -> list[dict]:
        """OCR the screen, then look for `text`. Returns bounding boxes."""
        shot = self.capture_screen()
        if not shot:
            return []
        ocr_text = self.ocr(shot)
        if text.lower() not in ocr_text.lower():
            return []

        # Use tesseract tsv to get bbox data
        out_base = tempfile.NamedTemporaryFile(suffix="", delete=False).name
        try:
            _run([
                "tesseract", str(shot), out_base,
                "-l", "eng+osd", "tsv",
            ])
            tsv_path = Path(out_base + ".tsv")
            if not tsv_path.exists():
                return [{"text": text, "found": True, "shot": str(shot)}]
            matches: list[dict] = []
            target = text.lower().split()
            words_buffer: list[dict] = []
            for line in tsv_path.read_text(encoding="utf-8", errors="ignore").splitlines()[1:]:
                parts = line.split("\t")
                if len(parts) < 12:
                    words_buffer.clear()
                    continue
                w = parts[11].strip()
                if not w:
                    words_buffer.clear()
                    continue
                if w.lower() == target[0]:
                    words_buffer = [{
                        "text": w, "left": int(parts[6]), "top": int(parts[7]),
                        "w": int(parts[8]), "h": int(parts[9]),
                    }]
                elif words_buffer and w.lower() == target[len(words_buffer)]:
                    words_buffer.append({
                        "text": w, "left": int(parts[6]), "top": int(parts[7]),
                        "w": int(parts[8]), "h": int(parts[9]),
                    })
                else:
                    words_buffer = []
                if len(words_buffer) == len(target):
                    left = min(b["left"] for b in words_buffer)
                    top = min(b["top"] for b in words_buffer)
                    right = max(b["left"] + b["w"] for b in words_buffer)
                    bot = max(b["top"] + b["h"] for b in words_buffer)
                    matches.append({
                        "text": text, "left": left, "top": top,
                        "right": right, "bottom": bot,
                    })
                    words_buffer = []
            return matches or [{"text": text, "found": True, "shot": str(shot)}]
        finally:
            for p in (Path(out_base), Path(out_base + ".tsv")):
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass

    # ── Vision description ──────────────────────────────────────────────────

    def describe_screen(self, prompt: str = "Describe what is visible on this screen.") -> str:
        """Capture screen + send to Gemini Vision."""
        shot = self.capture_screen()
        if not shot:
            return "Failed to capture screen."
        return self._describe_image(shot, prompt)

    def describe_image(self, image_path: str | Path, prompt: str = "Describe this image.") -> str:
        return self._describe_image(Path(image_path), prompt)

    def _describe_image(self, image_path: Path, prompt: str) -> str:
        if not image_path.exists():
            return f"Image not found: {image_path}"
        try:
            from google import genai
            from config import get_config

            api_key = get_config().get("gemini_api_key", "") or os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                return "Gemini API key not configured."

            client = genai.Client(api_key=api_key)
            uploaded = client.files.upload(file=str(image_path))
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=[uploaded, prompt],
            )
            text = ""
            for part in response.candidates[0].content.parts:
                if getattr(part, "text", None):
                    text += part.text
            return text.strip() or "(no description)"
        except Exception as e:
            return f"Vision error: {e}"

    # ── Convenience ────────────────────────────────────────────────────────

    def describe_webcam(self, prompt: str = "Describe what the webcam sees.") -> str:
        shot = self.capture_webcam()
        if not shot:
            return "Failed to capture webcam."
        return self._describe_image(shot, prompt)