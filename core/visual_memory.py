"""
Visual Memory — periodic screen capture + OCR → ChromaDB.

Uses `scrot` (or `grim` on Wayland) for screenshots, `tesseract` for OCR,
and the VectorMemory backend for indexing. All tools are optional; missing
binaries degrade gracefully.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .vector_memory import VectorMemory

REPO_ROOT = Path(__file__).resolve().parent.parent


class VisualMemory:
    """Capture screenshots, OCR them, index in VectorMemory."""

    def __init__(self, interval: int = 30, db_path: str = "memory/chroma_db") -> None:
        self.interval = max(5, int(interval))
        self._vector = VectorMemory(db_path=db_path, collection="visual_memory")
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._capture_tool = self._detect_capture_tool()
        self._ocr_tool = shutil.which("tesseract")
        self._tmpdir = Path(tempfile.gettempdir()) / "jarvis_visual"
        self._tmpdir.mkdir(parents=True, exist_ok=True)
        self._capture_count = 0

    @staticmethod
    def _detect_capture_tool() -> Optional[str]:
        for tool in ("scrot", "grim", "gnome-screenshot", "import"):
            if shutil.which(tool):
                return tool
        return None

    def start(self) -> bool:
        """Begin the capture loop in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return False
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._capture_loop, name="VisualMemory", daemon=True
        )
        self._thread.start()
        return True

    def stop(self, join_timeout: float = 5.0) -> None:
        """Signal the loop to stop and wait for it."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=join_timeout)
            self._thread = None

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _capture_screenshot(self, out_path: Path) -> bool:
        if not self._capture_tool:
            return False
        try:
            if self._capture_tool == "grim":
                cmd = ["grim", str(out_path)]
            elif self._capture_tool == "scrot":
                cmd = ["scrot", "-o", str(out_path)]
            elif self._capture_tool == "gnome-screenshot":
                cmd = ["gnome-screenshot", "-f", str(out_path)]
            else:
                cmd = ["import", "-window", "root", str(out_path)]
            subprocess.run(cmd, check=True, timeout=15,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return out_path.exists() and out_path.stat().st_size > 0
        except Exception:
            return False

    def _ocr(self, image_path: Path) -> str:
        if not self._ocr_tool:
            return ""
        try:
            out = subprocess.run(
                ["tesseract", str(image_path), "-", "-l", "eng"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return out.stdout.strip()
        except Exception:
            return ""

    def _capture_loop(self) -> None:
        while not self._stop.is_set():
            stamp = time.strftime("%Y%m%d_%H%M%S")
            img = self._tmpdir / f"shot_{stamp}.png"
            if self._capture_screenshot(img):
                text = self._ocr(img)
                if text:
                    meta = {"ts": time.time(), "image": img.name, "iso": stamp}
                    self._vector.add_document(text, metadata=meta)
                    self._capture_count += 1
                # Try to clean up immediately to avoid disk pressure
                try:
                    img.unlink(missing_ok=True)
                except Exception:
                    pass
            self._stop.wait(self.interval)

    def recall(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Semantic search over captured screen OCR text."""
        return self._vector.query(query, n_results=n_results)

    def status(self) -> Dict[str, Any]:
        """Return current status of the visual memory engine."""
        return {
            "running": self.is_running(),
            "interval_s": self.interval,
            "capture_tool": self._capture_tool,
            "ocr_tool": self._ocr_tool,
            "captures_indexed": self._capture_count,
            "collection": self._vector.get_collection_stats(),
        }


__all__ = ["VisualMemory"]