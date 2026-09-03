"""
open_app.py — i3-msg exec launcher with fuzzy matching and desktop-file index.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional


_SYSTEM = platform.system()

_DESKTOP_DIRS: list[Path] = [
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
    Path.home() / ".local" / "share" / "applications",
    Path("/var/lib/flatpak/exports/share/applications"),
    Path.home() / ".local" / "share" / "flatpak" / "exports" / "share" / "applications",
]


_APP_ALIASES: dict[str, str] = {
    "chrome":          "google-chrome",
    "google chrome":   "google-chrome",
    "firefox":         "firefox",
    "brave":           "brave-browser",
    "telegram":        "telegram-desktop",
    "discord":         "discord",
    "spotify":         "spotify",
    "code":            "code",
    "vscode":          "code",
    "visual studio":   "code",
    "terminal":        "x-terminal-emulator",
    "explorer":        "nautilus",
    "file manager":    "nautilus",
    "calculator":      "gnome-calculator",
    "settings":        "gnome-control-center",
    "task manager":    "gnome-system-monitor",
    "steam":           "steam",
    "obs":             "obs",
    "obs studio":      "obs",
    "gimp":            "gimp",
    "inkscape":        "inkscape",
    "libreoffice":     "libreoffice",
    "word":            "libreoffice --writer",
    "excel":           "libreoffice --calc",
    "powerpoint":      "libreoffice --impress",
    "vlc":             "vlc",
    "mpv":             "mpv",
    "thunderbird":     "thunderbird",
    "signal":          "signal-desktop",
    "slack":           "slack",
    "zoom":            "zoom",
    "postman":         "postman",
    "dbeaver":         "dbeaver",
    "obsidian":        "obsidian",
    "notion":          "notion-app",
    "steam":           "steam",
    "lutris":          "lutris",
    "heroic":          "heroic",
}


def _i3_msg(payload: str, timeout: int = 10) -> tuple[bool, str]:
    if not shutil.which("i3-msg"):
        return False, "i3-msg not installed"
    try:
        r = subprocess.run(
            ["i3-msg", f"exec {payload}"],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode == 0, (r.stderr or r.stdout or "").strip()
    except Exception as e:
        return False, str(e)


def _launch(command: str) -> tuple[bool, str]:
    binary = (
        shutil.which(command.split()[0]) or
        shutil.which(command.split()[0].lower())
    )
    if binary:
        try:
            subprocess.Popen(
                command.split() if binary == command.split()[0] else [binary, *command.split()[1:]],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.6)
            return True, ""
        except Exception as e:
            return False, str(e)
    return False, f"{command} not found in PATH"


class OpenApp:
    """i3-msg exec launcher with fuzzy match against desktop files."""

    def __init__(self) -> None:
        self.desktop_files: list[dict] = self._index_desktop_files()
        self._names: list[str] = [d["name"] for d in self.desktop_files]

    # ── Public API ─────────────────────────────────────────────────────────

    def open(self, app_name: str) -> bool:
        """Resolve `app_name` to a command and exec it via i3-msg."""
        if not app_name:
            return False

        cmd = self._resolve(app_name)
        if not cmd:
            return False
        ok, err = _i3_msg(cmd)
        if ok:
            return True
        # i3-msg missing — try direct exec as a fallback
        return _launch(cmd)[0]

    def open_on_workspace(self, app: str, workspace: int | str) -> bool:
        if not shutil.which("i3-msg"):
            return self.open(app)
        try:
            subprocess.run(
                ["i3-msg", f"workspace {workspace}; exec {self._resolve(app)}"],
                capture_output=True, timeout=10,
            )
            return True
        except Exception:
            return False

    def list_available(self) -> list[dict]:
        return list(self.desktop_files)

    def search(self, query: str, limit: int = 12) -> list[dict]:
        """Fuzzy match against indexed desktop files."""
        if not query:
            return self.desktop_files[:limit]
        q = query.lower().strip()
        scored: list[tuple[float, dict]] = []
        for entry in self.desktop_files:
            name = entry["name"].lower()
            ratio = SequenceMatcher(None, q, name).ratio()
            if q in name or q in entry["exec"].lower():
                ratio += 0.25
            if ratio > 0.35:
                scored.append((ratio, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    # ── Internals ──────────────────────────────────────────────────────────

    def _resolve(self, app_name: str) -> Optional[str]:
        key = app_name.lower().strip()
        if key in _APP_ALIASES:
            return _APP_ALIASES[key]

        for alias, cmd in _APP_ALIASES.items():
            if alias in key or key in alias:
                return cmd

        # Fuzzy match against desktop files
        results = self.search(app_name, limit=1)
        if results and results[0].get("exec"):
            return results[0]["exec"]
        return app_name if shutil.which(app_name) else None

    def _index_desktop_files(self) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        for d in _DESKTOP_DIRS:
            if not d.exists():
                continue
            for f in d.iterdir():
                if f.suffix != ".desktop":
                    continue
                if f.name in seen:
                    continue
                seen.add(f.name)
                try:
                    entry = self._parse_desktop(f)
                    if entry:
                        out.append(entry)
                except Exception:
                    continue
        out.sort(key=lambda e: e["name"].lower())
        return out

    @staticmethod
    def _parse_desktop(path: Path) -> Optional[dict]:
        name, exec_cmd, icon, comment = "", "", "", ""
        in_desktop_entry = False
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line.startswith("[Desktop Entry]"):
                in_desktop_entry = True
                continue
            if line.startswith("[") and line.endswith("]"):
                in_desktop_entry = False
                continue
            if not in_desktop_entry or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k == "Name" and not name:
                name = v.strip()
            elif k == "Exec":
                exec_cmd = v.split("%")[0].strip()
            elif k == "Icon":
                icon = v.strip()
            elif k == "Comment":
                comment = v.strip()
        if not name or not exec_cmd:
            return None
        if "NoDisplay=true" in (name + exec_cmd + comment):
            pass
        return {
            "path": str(path), "name": name, "exec": exec_cmd,
            "icon": icon, "comment": comment,
        }