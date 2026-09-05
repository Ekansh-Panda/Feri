"""
JARVIS NEXUS — Entry point.

Architecture:
  - Main thread: PyQt6 event loop + StarkHUD
  - Worker thread (via core.bridge.JarvisBridge): Gemini Live asyncio session
  - Signals cross the thread boundary safely

This file owns the QApplication, the HUD, the bridge, and the
worker thread. It does NOT contain any Gemini SDK calls directly —
those live in core/gemini_session.py and are wired in only if the
user has configured an API key.
"""

from __future__ import annotations

import json
import os
import platform
import signal
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from core.bridge import JarvisBridge
from core.mission_engine import MissionEngine
from core.orchestrator import Orchestrator
from core.plugin_loader import discover_plugins
from ui.stark_hud import StarkHUD

CONFIG_DIR = PROJECT_DIR / "config"
API_KEYS_PATH = CONFIG_DIR / "api_keys.json"


def load_api_keys() -> dict:
    if API_KEYS_PATH.exists():
        try:
            return json.loads(API_KEYS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def is_arch() -> bool:
    return os.path.exists("/etc/arch-release")


def main() -> int:
    print("=" * 60)
    print("  J.A.R.V.I.S. NEXUS — STARK OS")
    if is_arch():
        print("  Platform: ARCH LINUX + i3wm [PRIMARY]")
    else:
        print(f"  Platform: {platform.system()} [FALLBACK]")
    print("=" * 60)

    api_keys = load_api_keys()
    gemini_key = api_keys.get("gemini_api_key", "").strip()
    if not gemini_key or gemini_key == "YOUR_GEMINI_KEY":
        print("[WARN] No Gemini API key in config/api_keys.json.")
        print("[WARN] JARVIS will run in OFFLINE MODE. Run 'feri setup' to configure.")
    else:
        print(f"[OK] Gemini API key loaded (ends ...{gemini_key[-6:]}).")

    # ── Core subsystems ─────────────────────────────────────────────
    mission_engine = MissionEngine(base=str(PROJECT_DIR / "missions"))
    orchestrator = Orchestrator(api_keys, gemini_key, mission_engine)
    discover_plugins(
        plugins_dir=PROJECT_DIR / "plugins",
        core_tool_names=set(),
    )

    # ── Qt application ──────────────────────────────────────────────
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("JARVIS NEXUS")
    app.setApplicationVersion("7.0")

    # ── Thread-safe bridge (initially idle — Gemini only starts if
    #     a real key is configured) ────────────────────────────────
    bridge = JarvisBridge()

    # ── HUD ─────────────────────────────────────────────────────────
    hud = StarkHUD(orchestrator=orchestrator, mission_engine=mission_engine, bridge=bridge)
    hud.show()

    # ── Optional: start Gemini session in background thread ────────
    if gemini_key and gemini_key != "YOUR_GEMINI_KEY":
        try:
            from core.gemini_session import build_session_factory
            bridge.set_session_factory(build_session_factory(gemini_key, bridge))
            bridge.start()
            print("[OK] Gemini Live session started in background.")
        except Exception as e:
            print(f"[WARN] Could not start Gemini Live session: {e}")
    else:
        print("[INFO] HUD-only mode. Type 'feri setup' to enable voice.")

    # ── Signal handling ────────────────────────────────────────────
    def _shutdown(sig, frame):
        print("\nJARVIS: Shutting down gracefully, sir.")
        bridge.stop()
        orchestrator.stop()
        app.quit()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
