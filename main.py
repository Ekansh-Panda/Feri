"""
JARVIS NEXUS — Entry point.

Architecture:
  - Main thread: Interface event loop (jn=PyQt6, og=PyQt6, nice=Tkinter)
  - Worker thread (via core.bridge.JarvisBridge): Gemini Live asyncio session
  - Signals cross the thread boundary safely

Interface selection:
  Run `feri` (no args) to pick from jn/og/nice.
  Run `feri start jn` / `feri start og` / `feri start nice` to pick directly.
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

# Set Qt attribute BEFORE any QApplication creation. Required by
# PyQt6 6.11+ for QWebEngineWidgets to import.
from PyQt6.QtCore import Qt
try:
    from PyQt6.QtWidgets import QApplication as _QApplication_pre
    _QApplication_pre.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
except Exception:
    pass

from core.bridge import JarvisBridge
from core.mission_engine import MissionEngine
from core.orchestrator import Orchestrator
from core.persona import get_greeting, get_persona
from core.plugin_loader import discover_plugins
from interfaces import build_interface, select_interface

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


def main(argv: list = None) -> int:
    argv = argv or sys.argv[1:]
    preferred = None
    if argv and argv[0] in ("jn", "og", "nice"):
        preferred = argv[0]

    persona = get_persona()
    print("=" * 60)
    print(f"  {persona['title']} — {persona['version']}")
    if is_arch():
        print("  Platform: ARCH LINUX + i3wm [PRIMARY]")
    else:
        print(f"  Platform: {platform.system()} [FALLBACK]")
    print(f"  Voice: {persona['voice']['voice_name']}")
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

    # ── Interface selection ─────────────────────────────────────────
    if not preferred:
        try:
            preferred = select_interface()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return 0
    print(f"[OK] Selected interface: {preferred}")

    # ── Qt application (must exist BEFORE building the interface, because
    #     hologram_view.py imports QWebEngineWidgets which needs AA_ShareOpenGLContexts
    #     set before QCoreApplication is created) ──────────────────
    if preferred in ("jn", "og"):
        from PyQt6.QtWidgets import QApplication as _QApp
        app = _QApp.instance() or _QApp(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        app.setApplicationName("JARVIS NEXUS")
        app.setApplicationVersion("7.0")
    else:
        # Tkinter path — no QApplication needed
        app = None

    # ── Build the chosen interface ──────────────────────────────────
    bridge = JarvisBridge()
    interface = build_interface(
        preferred,
        orchestrator=orchestrator,
        mission_engine=mission_engine,
        bridge=bridge,
        config=api_keys,
    )

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
        try:
            bridge.stop()
        except Exception:
            pass
        try:
            if hasattr(interface, "stop"):
                interface.stop()
        except Exception:
            pass
        try:
            orchestrator.stop()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # ── Run ─────────────────────────────────────────────────────────
    if hasattr(interface, "run"):
        return interface.run()
    # Fallback: just keep the process alive
    try:
        while True:
            signal.pause()
    except KeyboardInterrupt:
        _shutdown(None, None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
