"""JanitorAgent — cleanup, temp purge, and cache management for Arch Linux."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.janitor")


class JanitorAgent:
    """Performs system cleanup tasks on Arch Linux."""

    def clean_temp(self) -> dict[str, Any]:
        """Purge /tmp and user temp directories.

        Returns:
            Dict with bytes freed and files removed.
        """
        paths = [Path("/tmp"), Path.home() / ".tmp", Path.home() / ".cache" / "tmp"]
        total_freed = 0
        files_removed = 0
        for p in paths:
            if not p.exists():
                continue
            for entry in p.rglob("*"):
                try:
                    size = entry.stat().st_size if entry.is_file() else 0
                    if entry.is_file() or entry.is_symlink():
                        entry.unlink()
                        total_freed += size
                        files_removed += 1
                    elif entry.is_dir():
                        try:
                            entry.rmdir()
                        except OSError:
                            pass
                except OSError:
                    continue
        return {"bytes_freed": total_freed, "files_removed": files_removed, "paths": [str(p) for p in paths]}

    def clean_journal(self) -> dict[str, Any]:
        """Vacuum systemd journal logs.

        Returns:
            Dict with bytes freed and status.
        """
        try:
            proc = subprocess.run(
                ["journalctl", "--vacuum-size=100M", "--vacuum-time=7d"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = proc.stdout
            freed = 0
            for line in output.splitlines():
                if "freed" in line.lower():
                    m = re_search = None  # noqa: F841
                    import re
                    m = re.search(r"(\d+(?:\.\d+)?)\s*([KMG]?B)", line, re.IGNORECASE)
                    if m:
                        num = float(m.group(1))
                        unit = m.group(2).upper()
                        if unit == "KB":
                            freed = int(num * 1024)
                        elif unit == "MB":
                            freed = int(num * 1024 * 1024)
                        elif unit == "GB":
                            freed = int(num * 1024 * 1024 * 1024)
            return {"bytes_freed": freed, "status": "ok", "output": output}
        except FileNotFoundError:
            return {"status": "skipped", "reason": "journalctl not available"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def clean_pacman_cache(self) -> dict[str, Any]:
        """Clean pacman package cache using paccache.

        Returns:
            Dict with bytes freed and packages removed.
        """
        try:
            proc = subprocess.run(
                ["paccache", "-r", "-k", "2", "--verbose"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {"status": "ok" if proc.returncode == 0 else "error", "stdout": proc.stdout, "stderr": proc.stderr}
        except FileNotFoundError:
            return {"status": "skipped", "reason": "paccache not found. Install pacman-contrib."}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def clean_aur_cache(self) -> dict[str, Any]:
        """Clean AUR helper cache (yay).

        Returns:
            Dict with bytes freed and status.
        """
        if not shutil.which("yay"):
            return {"status": "skipped", "reason": "yay not installed"}
        try:
            proc = subprocess.run(
                ["yay", "-Scc", "--noconfirm"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {"status": "ok" if proc.returncode == 0 else "error", "stdout": proc.stdout, "stderr": proc.stderr}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def clean_docker(self) -> dict[str, Any]:
        """Prune Docker system.

        Returns:
            Dict with bytes freed and status.
        """
        if not shutil.which("docker"):
            return {"status": "skipped", "reason": "docker not installed"}
        try:
            proc = subprocess.run(
                ["docker", "system", "prune", "-f", "--filter", "until=168h"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {"status": "ok" if proc.returncode == 0 else "error", "stdout": proc.stdout, "stderr": proc.stderr}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def clean_thumbnails(self) -> dict[str, Any]:
        """Remove stale thumbnail caches.

        Returns:
            Dict with bytes freed and files removed.
        """
        paths = [
            Path.home() / ".cache" / "thumbnails",
            Path.home() / ".local" / "share" / "gnome-shell" / "thumbnail_cache",
        ]
        total_freed = 0
        files_removed = 0
        for p in paths:
            if not p.exists():
                continue
            for entry in p.rglob("*"):
                try:
                    if entry.is_file():
                        size = entry.stat().st_size
                        entry.unlink()
                        total_freed += size
                        files_removed += 1
                except OSError:
                    continue
        return {"bytes_freed": total_freed, "files_removed": files_removed, "paths": [str(p) for p in paths]}

    def full_cleanup(self) -> dict[str, Any]:
        """Run all cleanup tasks.

        Returns:
            Dict with aggregated results and total bytes freed.
        """
        tasks = [
            ("temp", self.clean_temp),
            ("journal", self.clean_journal),
            ("pacman", self.clean_pacman_cache),
            ("aur", self.clean_aur_cache),
            ("docker", self.clean_docker),
            ("thumbnails", self.clean_thumbnails),
        ]

        results: dict[str, Any] = {}
        total_freed = 0
        for name, fn in tasks:
            try:
                res = fn()
                results[name] = res
                total_freed += res.get("bytes_freed", 0)
            except Exception as exc:
                results[name] = {"status": "error", "error": str(exc)}

        return {"total_bytes_freed": total_freed, "tasks": results}
