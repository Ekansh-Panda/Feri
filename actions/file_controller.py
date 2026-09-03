"""
file_controller.py — file system operations for JARVIS NEXUS.
"""
from __future__ import annotations

import mimetypes
import os
import platform
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Union


_SYSTEM = platform.system()
_TRASH_DIR = Path.home() / ".jarvis" / "trash"
_TRASH_DIR.mkdir(parents=True, exist_ok=True)


def _resolve(path: Union[str, Path]) -> Path:
    p = Path(os.path.expanduser(str(path))).resolve()
    return p


def _human_size(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024.0:
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


def _human_time(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


class FileController:
    """Cross-platform file-system operations with a soft-trash fallback."""

    TRASH_DIR = _TRASH_DIR

    def list(self, path: Union[str, Path] = "~") -> list[dict]:
        p = _resolve(path)
        if not p.exists():
            return []
        if p.is_file():
            return [self.get_info(p)]
        items: list[dict] = []
        try:
            for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                items.append(self.get_info(entry))
        except PermissionError:
            pass
        return items

    def create_dir(self, path: Union[str, Path]) -> bool:
        p = _resolve(path)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False

    def delete(self, path: Union[str, Path], permanent: bool = False) -> bool:
        p = _resolve(path)
        if not p.exists():
            return False
        try:
            if permanent:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                return True
            # Try send2trash first, otherwise move to local trash
            try:
                from send2trash import send2trash
                send2trash(str(p))
                return True
            except Exception:
                pass
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            target = self.TRASH_DIR / f"{p.name}_{stamp}"
            shutil.move(str(p), str(target))
            return True
        except Exception:
            return False

    def copy(self, src: Union[str, Path], dst: Union[str, Path]) -> bool:
        s, d = _resolve(src), _resolve(dst)
        try:
            if s.is_dir():
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s, d)
            return True
        except Exception:
            return False

    def move(self, src: Union[str, Path], dst: Union[str, Path]) -> bool:
        s, d = _resolve(src), _resolve(dst)
        try:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(s), str(d))
            return True
        except Exception:
            return False

    def search(
        self,
        pattern: str,
        path: Union[str, Path] = "~",
        max_results: int = 200,
    ) -> list[Path]:
        """Glob/regex-style filename search."""
        p = _resolve(path)
        results: list[Path] = []
        if not p.exists():
            return results

        # Glob pattern (containing *, ?, [])
        if any(ch in pattern for ch in "*?[]"):
            try:
                for hit in p.rglob(pattern):
                    results.append(hit)
                    if len(results) >= max_results:
                        break
            except Exception:
                pass
            return results

        # Substring / case-insensitive name match
        needle = pattern.lower()
        try:
            for entry in p.rglob("*"):
                if needle in entry.name.lower():
                    results.append(entry)
                    if len(results) >= max_results:
                        break
        except Exception:
            pass
        return results

    def get_info(self, path: Union[str, Path]) -> dict:
        p = _resolve(path)
        try:
            st = p.stat()
        except Exception:
            return {"path": str(p), "exists": False}

        mime, _ = mimetypes.guess_type(str(p))
        return {
            "path":        str(p),
            "name":        p.name,
            "exists":      True,
            "is_dir":      p.is_dir(),
            "is_file":     p.is_file(),
            "is_symlink":  p.is_symlink(),
            "size_bytes":  st.st_size,
            "size_human":  _human_size(st.st_size),
            "mime":        mime or "",
            "created":     _human_time(st.st_ctime),
            "modified":    _human_time(st.st_mtime),
            "accessed":    _human_time(st.st_atime),
            "mode":        oct(st.st_mode),
            "owner":       p.owner() if hasattr(p, "owner") else "",
        }

    def open(self, path: Union[str, Path]) -> bool:
        p = _resolve(path)
        if not p.exists():
            return False
        if _SYSTEM == "Linux":
            opener = shutil.which("xdg-open") or shutil.which("gio")
        elif _SYSTEM == "Darwin":
            opener = shutil.which("open")
        else:
            opener = shutil.which("start")
        if not opener:
            return False
        try:
            if _SYSTEM == "Linux" and opener.endswith("gio"):
                subprocess.Popen([opener, "open", str(p)],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            elif _SYSTEM == "Windows":
                subprocess.Popen([opener, str(p)], shell=True,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen([opener, str(p)],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False