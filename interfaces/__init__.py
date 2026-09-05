"""
interfaces/ — Multi-interface selection layer for JARVIS NEXUS.

Three interfaces are available:
  - jn   (current): New PyQt6 Stark HUD (ui.stark_hud.StarkHUD)
  - og   (original): The original JarvisUI (ui.py) — full feature set
  - nice (new Tkinter): A clean, lightweight Tkinter interface

All three accept the same orchestrator/mission_engine/bridge context and
expose the same minimal surface (start/stop + signal handlers). The
interface selector picks one and instantiates it.

Voice profile/persona is unified — the original JARVIS personality is
restored via core/persona.py so all three interfaces speak with the
same British-witted voice.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# All three interfaces must be on sys.path
PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


INTERFACES = {
    "jn": {
        "name": "JN (PyQt6 Stark HUD)",
        "description": "New glassmorphic HUD with Arc Reactor, holograms, telemetry",
        "module": "ui.stark_hud",
        "class": "StarkHUD",
        "deps": ["PyQt6", "PyQt6-WebEngine"],
    },
    "og": {
        "name": "OG (Original JarvisUI)",
        "description": "The full Mark LII JarvisUI — file drop, camera, plugins, dashboard",
        "module": "ui",
        "class": "JarvisUI",
        "deps": ["PyQt6", "PyQt6-WebEngine"],
    },
    "nice": {
        "name": "Nice (Tkinter)",
        "description": "Clean, lightweight Tkinter — no WebEngine required",
        "module": "interfaces.nice_ui",
        "class": "NiceUI",
        "deps": ["tkinter"],
    },
}


def list_interfaces() -> dict:
    """Return the dict of available interfaces with availability check."""
    result = {}
    for key, meta in INTERFACES.items():
        available = True
        reason = ""
        try:
            if meta["module"] == "interfaces.nice_ui":
                import tkinter  # noqa: F401
            elif meta["module"] == "ui.stark_hud":
                from PyQt6.QtWidgets import QApplication  # noqa: F401
            elif meta["module"] == "ui":
                # Original ui.py is at the repo root
                ui_py = PROJECT_DIR / "ui.py"
                if not ui_py.exists():
                    raise ImportError(f"{ui_py} not found")
        except ImportError as e:
            available = False
            reason = str(e)
        result[key] = {**meta, "available": available, "reason": reason}
    return result


def select_interface(prefer: Optional[str] = None) -> str:
    """Ask the user which interface to launch. Returns the chosen key.

    If `prefer` is set and the interface is available, returns it without
    asking. If not, falls back to a terminal menu.
    """
    available = list_interfaces()
    if prefer and prefer in available and available[prefer]["available"]:
        return prefer
    # Default to og if present, else jn, else nice
    if not prefer:
        for fallback in ("og", "jn", "nice"):
            if fallback in available and available[fallback]["available"]:
                prefer = fallback
                break

    print("=" * 60)
    print("  JARVIS NEXUS — Interface Selection")
    print("=" * 60)
    keys = list(available.keys())
    for i, key in enumerate(keys, 1):
        meta = available[key]
        status = "[OK]" if meta["available"] else "[--]"
        print(f"  {i}. {key:5s}  {status}  {meta['name']}")
        print(f"           {meta['description']}")
        if not meta["available"]:
            print(f"           (unavailable: {meta['reason']})")
    print()
    if prefer and prefer in available and available[prefer]["available"]:
        print(f"  Default: {prefer} ({available[prefer]['name']})")
    print()
    while True:
        try:
            choice = input("Select interface [1-3] or q to quit: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(0)
        if choice in ("q", "quit", "exit"):
            sys.exit(0)
        if not choice and prefer:
            return prefer
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(keys):
                key = keys[idx]
                if available[key]["available"]:
                    return key
                print(f"  {key} is not available: {available[key]['reason']}")
                continue
        if choice in available:
            if available[choice]["available"]:
                return choice
            print(f"  {choice} is not available: {available[choice]['reason']}")
            continue
        print("  Invalid choice.")


def build_interface(
    key: str,
    *,
    orchestrator=None,
    mission_engine=None,
    bridge=None,
    config: Optional[dict] = None,
):
    """Instantiate the chosen interface. Returns the interface object.

    The object exposes a uniform surface:
      - .run() -> int (exit code, blocks until window closes)
      - .stop() (optional, for async shutdown)
    """
    if key not in INTERFACES:
        raise ValueError(f"Unknown interface: {key}")
    meta = INTERFACES[key]
    if key == "jn":
        from ui.stark_hud import StarkHUD
        return StarkHUD(orchestrator=orchestrator,
                        mission_engine=mission_engine,
                        bridge=bridge)
    if key == "og":
        # Original JarvisUI — takes face_path, optional size
        # The original lives at the repo root as `ui.py`, not in the `ui/` package
        import importlib.util
        ui_py = PROJECT_DIR / "ui.py"
        spec = importlib.util.spec_from_file_location("_original_ui", ui_py)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load {ui_py}")
        module = importlib.util.module_from_spec(spec)
        sys.modules["_original_ui"] = module
        spec.loader.exec_module(module)
        JarvisUI = module.JarvisUI
        face_path = str(PROJECT_DIR / "config" / "jarvis.ico")
        return JarvisUI(face_path=face_path)
    if key == "nice":
        from interfaces.nice_ui import NiceUI
        return NiceUI(orchestrator=orchestrator,
                      mission_engine=mission_engine,
                      bridge=bridge,
                      config=config or {})
    raise ValueError(f"Interface {key} not implemented")


__all__ = ["INTERFACES", "list_interfaces", "select_interface", "build_interface"]
