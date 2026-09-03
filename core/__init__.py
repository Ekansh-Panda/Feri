"""
JARVIS NEXUS — Core Infrastructure Package.

This package contains the foundational subsystems for JARVIS NEXUS:
orchestration, planning, mission lifecycle, task DAGs, agent runtime,
memory, safety, auditing, plugin management, sandboxing, scheduling,
watchdog, encrypted sync, network security, holographic UI, audio,
LLM, STT/TTS, and platform-specific installers.
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR: Path = Path(__file__).resolve().parent.parent
CORE_DIR: Path = Path(__file__).resolve().parent
CONFIG_DIR: Path = BASE_DIR / "config"
MISSION_DIR: Path = BASE_DIR / "missions"
MEMORY_DIR: Path = BASE_DIR / "memory"

__version__ = "3.0.0-nexus"
__all__ = [
    "__version__",
    "BASE_DIR",
    "CORE_DIR",
    "CONFIG_DIR",
    "MISSION_DIR",
    "MEMORY_DIR",
]
