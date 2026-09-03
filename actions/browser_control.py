"""
browser_control.py — Chromium / browser control via xdotool + DevTools Protocol.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional


_SYSTEM = platform.system()
_HISTORY: list[str] = []


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _xdg_open(url: str) -> bool:
    if _which("xdg-open"):
        try:
            subprocess.Popen(["xdg-open", url],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False
    return False


def _run_xdotool(args: list[str], timeout: int = 5) -> bool:
    if not _which("xdotool"):
        return False
    try:
        r = subprocess.run(["xdotool", *args], capture_output=True, timeout=timeout)
        return r.returncode == 0
    except Exception:
        return False


def _chromium_executable() -> Optional[str]:
    for c in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        if _which(c):
            return c
    return None


class BrowserControl:
    """Browser launcher + xdotool-driven page actions."""

    DEVTOOLS_PORT = 9222

    def __init__(self) -> None:
        self._chromium = _chromium_executable()

    # ── Navigation ─────────────────────────────────────────────────────────

    def open_url(self, url: str, new_window: bool = False) -> bool:
        if not url:
            return False
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url
        if self._chromium:
            cmd = [self._chromium]
            if new_window:
                cmd.append("--new-window")
            cmd.append(url)
            try:
                subprocess.Popen(cmd,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                _HISTORY.append(url)
                return True
            except Exception:
                pass
        return _xdg_open(url)

    def new_tab(self, url: str = "") -> bool:
        if url:
            url = ("https://" + url) if not url.startswith("http") else url
            # Focus browser first
            _run_xdotool(["key", "ctrl+l"])
            time.sleep(0.1)
            _run_xdotool(["type", "--clearmodifiers", url])
            _run_xdotool(["key", "Return"])
            _HISTORY.append(url)
            return True
        return _run_xdotool(["key", "ctrl+t"])

    def close_tab(self) -> bool:
        return _run_xdotool(["key", "ctrl+w"])

    def go_back(self) -> bool:
        return _run_xdotool(["key", "alt+Left"])

    def go_forward(self) -> bool:
        return _run_xdotool(["key", "alt+Right"])

    def reload(self) -> bool:
        return _run_xdotool(["key", "F5"])

    # ── Scrolling / focus ──────────────────────────────────────────────────

    def scroll(self, direction: str = "down", amount: int = 5) -> bool:
        if direction not in ("up", "down", "left", "right"):
            return False
        keymap = {"up": "Up", "down": "Down", "left": "Left", "right": "Right"}
        key = keymap[direction]
        return _run_xdotool(["key", "--repeat", str(max(1, amount)), key])

    # ── DevTools Protocol (when launched with --remote-debugging-port) ────

    def devtools_command(self, method: str, params: Optional[dict] = None) -> Optional[dict]:
        try:
            payload = {"id": int(time.time() * 1000) % 1_000_000,
                       "method": method, "params": params or {}}
            req = urllib.request.Request(
                f"http://127.0.0.1:{self.DEVTOOLS_PORT}/json",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    def get_tabs(self) -> list[dict]:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{self.DEVTOOLS_PORT}/json", timeout=3
            ) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def navigate_active_tab(self, url: str) -> bool:
        tabs = self.get_tabs()
        if not tabs:
            return False
        page = tabs[0].get("webSocketDebuggerUrl")
        if not page:
            return False
        # Real-time CDP requires websocket-client; fall back to xdotool typing.
        return self.new_tab(url)

    # ── Agent bridge ───────────────────────────────────────────────────────

    def interact(self, description: str) -> str:
        """
        Hook for BrowserAgent — translates natural-language intent into
        xdotool actions. The full Playwright automation lives in
        agents/browser_agent.py.
        """
        try:
            from agents.browser_agent import BrowserAgent
            return BrowserAgent().run(description)
        except Exception as e:
            return f"browser agent unavailable: {e}"

    @property
    def history(self) -> list[str]:
        return list(_HISTORY)