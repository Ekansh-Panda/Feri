"""Thread-safe bridge between Gemini Live (asyncio) and PyQt6 (Qt main thread).

The Gemini Live API requires an asyncio event loop. PyQt6 requires a blocking
main thread with its own event loop. Running them in the same thread causes
either UI freezes or audio drops. Running them in different threads without
proper Qt object parentage causes "QObject: Cannot create children for a
parent that is in a different thread" crashes.

The solution: Qt signals. Signals are the only Qt-idiomatic way to cross
thread boundaries safely. The async thread emits signals; the Qt main thread
receives them and updates widgets.

This module defines the bridge object that lives on the Qt main thread, plus
a worker thread that runs the asyncio loop and emits signals into the bridge.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable, Optional

from PyQt6.QtCore import QObject, pyqtSignal


class JarvisBridge(QObject):
    """Signal hub between the asyncio worker and the Qt main thread.

    All slots connected to these signals run on the Qt main thread because
    the bridge itself lives there. This is the only safe way to call Qt
    methods from a background thread.
    """

    # User voice transcript (audio was processed by Gemini)
    user_transcript = pyqtSignal(str)

    # JARVIS reply text (delta — many of these per reply)
    jarvis_transcript_delta = pyqtSignal(str)

    # JARVIS reply complete
    jarvis_transcript_done = pyqtSignal(str)

    # Audio level updates for waveform animation (0.0 - 1.0)
    audio_level = pyqtSignal(float)

    # Tool call from the LLM: (tool_name, params_dict)
    tool_call = pyqtSignal(str, dict)

    # Tool result being sent back to the LLM
    tool_result = pyqtSignal(str, str)

    # Connection state changes
    state_changed = pyqtSignal(str)  # "connecting" | "connected" | "disconnected" | "error"

    # Generic log message
    log_message = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._worker: Optional[threading.Thread] = None
        self._session_factory: Optional[Callable] = None
        self._connected = False

    def set_session_factory(self, factory: Callable[["JarvisBridge"], Any]) -> None:
        """Register the async session coroutine. Called once at startup.

        The factory receives the bridge and returns a coroutine that runs
        the entire Gemini Live session — open stream, send audio, receive
        transcripts, handle tool calls. The factory's coroutine is what
        runs inside the asyncio event loop on the worker thread.
        """
        self._session_factory = factory

    def start(self) -> bool:
        """Start the worker thread. Returns False if already running."""
        if self._worker is not None and self._worker.is_alive():
            return False
        if self._session_factory is None:
            self.log_message.emit("Bridge: no session factory registered")
            return False

        self._worker = threading.Thread(
            target=self._run_async,
            name="jarvis-gemini-loop",
            daemon=True,
        )
        self._worker.start()
        return True

    def stop(self) -> None:
        """Stop the worker thread. The asyncio loop will exit on next iteration."""
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def is_connected(self) -> bool:
        return self._connected

    def set_connected(self, connected: bool) -> None:
        self._connected = connected

    def _run_async(self) -> None:
        """Worker thread target. Owns the asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._session_factory(self))
        except Exception as e:
            self.log_message.emit(f"Bridge: session crashed — {e}")
        finally:
            self._loop.close()
            self._loop = None
            self.set_connected(False)
            self.state_changed.emit("disconnected")

    # ─────────────────────────────────────────────────────────────
    # Convenience emitters used by the async session
    # These are thread-safe because pyqtSignal.emit is thread-safe.
    # ─────────────────────────────────────────────────────────────

    def emit_user_text(self, text: str) -> None:
        self.user_transcript.emit(text)

    def emit_jarvis_delta(self, text: str) -> None:
        self.jarvis_transcript_delta.emit(text)

    def emit_jarvis_done(self, text: str) -> None:
        self.jarvis_transcript_done.emit(text)

    def emit_audio_level(self, level: float) -> None:
        self.audio_level.emit(max(0.0, min(1.0, level)))

    def emit_tool_call(self, name: str, params: dict) -> None:
        self.tool_call.emit(name, params)

    def emit_tool_result(self, name: str, result: str) -> None:
        self.tool_result.emit(name, result)

    def emit_state(self, state: str) -> None:
        self.state_changed.emit(state)

    def emit_log(self, msg: str) -> None:
        self.log_message.emit(msg)
