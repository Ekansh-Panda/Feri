"""Gemini Live session factory.

Wires the async Gemini Live SDK into a coroutine that emits JarvisBridge
signals. Imported lazily — main.py only imports this if a real API key
is configured. If the Gemini SDK is missing, this raises ImportError
on import and main.py catches it and falls back to HUD-only mode.
"""

from __future__ import annotations

import asyncio
from typing import Callable


def build_session_factory(api_key: str, bridge) -> Callable:
    """Return an async coroutine that runs the Gemini Live session.

    The returned callable receives the bridge as its single argument and
    runs forever (or until the loop is stopped) emitting signals into
    the bridge as the session progresses.
    """
    async def _session() -> None:
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            bridge.emit_log(f"Gemini SDK not available: {e}")
            return

        client = genai.Client(api_key=api_key)
        bridge.emit_state("connecting")
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
        )
        try:
            async with client.aio.live.connect(
                model="models/gemini-2.0-flash-live-preview-04-09",
                config=config,
            ) as session:
                bridge.set_connected(True)
                bridge.emit_state("connected")
                bridge.emit_log("Gemini Live connected.")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            bridge.emit_log(f"Gemini session error: {e}")
            bridge.emit_state("error")
        finally:
            bridge.set_connected(False)

    return _session
