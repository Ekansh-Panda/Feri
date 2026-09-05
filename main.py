import asyncio
import json
import os
import platform
import signal
import sys
import time
from pathlib import Path

from core.orchestrator import Orchestrator
from core.mission_engine import MissionEngine
from core.plugin_loader import discover_plugins
from core.llm_client import LLMClient
from ui.stark_hud import StarkHUD
from PyQt6.QtWidgets import QApplication

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

def load_api_keys() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}

def check_arch() -> bool:
    return os.path.exists("/etc/arch-release")

def main():
    print("=" * 60)
    print("  J.A.R.V.I.S. NEXUS — STARK OS")
    if check_arch():
        print("  Platform: ARCH LINUX + i3wm [PRIMARY]")
    else:
        print(f"  Platform: {platform.system()} [FALLBACK]")
    print("=" * 60)

    api_keys = load_api_keys()
    llm = LLMClient(api_keys.get("gemini_api_key", ""))
    mission_engine = MissionEngine()
    orchestrator = Orchestrator(api_keys, llm, mission_engine)
    discover_plugins(
        plugins_dir=BASE_DIR / "plugins",
        core_tool_names=set(),
    )

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    hud = StarkHUD(orchestrator, mission_engine)
    hud.show()

    def signal_handler(sig, frame):
        print("\nJARVIS: Shutting down gracefully, sir.")
        orchestrator.stop()
        app.quit()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
