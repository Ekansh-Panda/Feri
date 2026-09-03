"""
game_updater.py — Steam (steamcmd) and Epic (heroic / legendary) CLI helpers.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return subprocess.CompletedProcess(cmd, -1, "", str(e))


_STEAM_PATHS = [
    Path.home() / ".local/share/Steam/steamapps",
    Path.home() / ".steam/steam/steamapps",
    Path.home() / ".steam/root/steamapps",
]


def _read_acf(path: Path) -> dict:
    """Read a Steam appmanifest .acf file as a flat dict."""
    try:
        import vdf  # type: ignore
        return vdf.load(open(path, encoding="utf-8"))
    except Exception:
        pass
    # Minimal fallback parser for the few fields we need
    out: dict = {}
    cur = out
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("}"):
            if "parent" in cur:
                cur = out
            continue
        if line.startswith("{"):
            continue
        if '"' in line:
            parts = line.split('"')
            if len(parts) >= 4:
                key, val = parts[1], parts[3]
                if key == "appid" and "appid" not in out:
                    out["appid"] = val
                elif key == "name":
                    out["name"] = val
                elif key == "installdir":
                    out["installdir"] = val
                elif key == "buildid":
                    out["buildid"] = val
                elif key == "LastPlayed":
                    out["last_played"] = val
                elif key == "StateFlags":
                    out["state_flags"] = val
    return out


class GameUpdater:
    """Steam and Epic Games launcher CLI wrapper."""

    # ── Steam ──────────────────────────────────────────────────────────────

    def update_steam(self) -> bool:
        steamcmd = _which("steamcmd") or _which("steam")
        if not steamcmd:
            print("[GameUpdater] steamcmd not found.")
            return False
        if steamcmd.endswith("steamcmd"):
            cmd = [steamcmd, "+login", "anonymous", "+quit"]
        else:
            cmd = [steamcmd, "-silent"]
        r = _run(cmd, timeout=300)
        return r.returncode == 0

    def list_installed_steam(self) -> list[dict]:
        games: list[dict] = []
        seen: set[str] = set()
        for base in _STEAM_PATHS:
            if not base.exists():
                continue
            for f in base.glob("appmanifest_*.acf"):
                appid = f.stem.replace("appmanifest_", "")
                if appid in seen:
                    continue
                seen.add(appid)
                data = _read_acf(f)
                games.append({
                    "platform":    "steam",
                    "appid":       data.get("appid", appid),
                    "name":        data.get("name", f"App {appid}"),
                    "install_dir": data.get("installdir", ""),
                    "build_id":    data.get("buildid", ""),
                    "last_played": data.get("last_played", ""),
                    "state_flags": data.get("state_flags", ""),
                })
        return games

    # ── Epic / Heroic ──────────────────────────────────────────────────────

    def update_epic(self) -> bool:
        for tool in ("heroic", "legendary"):
            if _which(tool):
                r = _run([tool, "list"], timeout=120)
                # Some heroic versions require no args; skip second invocation
                return r.returncode == 0
        print("[GameUpdater] neither heroic nor legendary CLI found.")
        return False

    def list_installed_epic(self) -> list[dict]:
        """Read Legendary's installed.json."""
        candidates = [
            Path.home() / ".config/legendary/installed.json",
            Path.home() / ".var/app/com.heroicgameslauncher.hgl/config/legendary/installed.json",
        ]
        out: list[dict] = []
        for path in candidates:
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for app_name, meta in data.items():
                out.append({
                    "platform":   "epic",
                    "app_name":   app_name,
                    "title":      meta.get("title", app_name),
                    "version":    meta.get("version", ""),
                    "install_path": meta.get("install_path", ""),
                    "executable": meta.get("executable", ""),
                })
        return out

    def list_installed_games(self, platform: str = "all") -> list[dict]:
        out: list[dict] = []
        if platform in ("all", "steam"):
            out += self.list_installed_steam()
        if platform in ("all", "epic"):
            out += self.list_installed_epic()
        return out

    # ── Launch ─────────────────────────────────────────────────────────────

    def launch_game(self, platform: str, game_id: str) -> bool:
        if platform == "steam":
            steam = _which("steam")
            if not steam:
                return False
            try:
                subprocess.Popen([steam, f"steam://rungameid/{game_id}"],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return True
            except Exception:
                return False
        if platform == "epic":
            heroic = _which("heroic")
            legendary = _which("legendary")
            if heroic:
                try:
                    subprocess.Popen([heroic, "launch", game_id, "--no-wine-debug"],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return True
                except Exception:
                    pass
            if legendary:
                try:
                    subprocess.Popen([legendary, "launch", game_id],
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return True
                except Exception:
                    return False
        return False