"""BrowserAgent — Playwright + Xvfb shadow workspace."""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional


class BrowserAgent:
    """Headless Chromium browser running in an Xvfb shadow workspace."""

    def __init__(self, display: str = ":99", workspace_dir: Optional[str] = None) -> None:
        self.display = display
        self.xvfb_proc: Optional[subprocess.Popen] = None
        self._pw = None
        self._context = None
        self._page = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._workspace = Path(workspace_dir) if workspace_dir else (
            Path(__file__).resolve().parent.parent / "shadow_workspace" / "browser_profiles"
        )
        self._workspace.mkdir(parents=True, exist_ok=True)

    def init(self) -> str:
        """Start Xvfb on :99 and launch headless Chromium.

        Returns:
            Status message.
        """
        if self._thread and self._thread.is_alive():
            return "BrowserAgent already initialized."

        self._start_xvfb()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="BrowserAgentLoop")
        self._thread.start()
        self._ready.wait(timeout=30)
        return "BrowserAgent initialized (Xvfb + Chromium)."

    def _start_xvfb(self) -> None:
        if self.xvfb_proc and self.xvfb_proc.poll() is None:
            return
        cmd = [
            "Xvfb",
            self.display,
            "-screen", "0", "1920x1080x24",
            "-ac", "+extension", "RANDR",
        ]
        self.xvfb_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
        os.environ.setdefault("DISPLAY", self.display)

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_init())
        finally:
            self._ready.set()
            self._loop.run_forever()

    async def _async_init(self) -> None:
        from playwright.async_api import async_playwright

        pw_mgr = await async_playwright().start()
        self._pw = pw_mgr

        chromium = pw_mgr.chromium
        profile_dir = str(self._workspace / "chromium_shadow")
        Path(profile_dir).mkdir(parents=True, exist_ok=True)

        self._context = await chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            no_viewport=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--disable-popup-blocking",
                "--disable-translate",
                "--disable-background-networking",
                "--disable-sync",
                "--metrics-recording-only",
                "--mute-audio",
                "--no-first-run",
            ],
        )
        self._page = await self._context.new_page()

    def _run(self, coro, timeout: int = 60) -> Any:
        if not self._loop:
            raise RuntimeError("BrowserAgent not initialized.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def navigate(self, url: str) -> str:
        """Navigate to a URL.

        Args:
            url: Target URL.

        Returns:
            Status string.
        """
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            result = self._run(self._page.goto(url, wait_until="domcontentloaded", timeout=30000))
            return f"Navigated to: {result.url}"
        except Exception as exc:
            return f"Navigation failed: {exc}"

    def click(self, selector: str) -> str:
        """Click an element matching the CSS selector.

        Args:
            selector: CSS selector.

        Returns:
            Status string.
        """
        try:
            self._run(self._page.click(selector, timeout=10000))
            return f"Clicked: {selector}"
        except Exception as exc:
            return f"Click failed: {exc}"

    def type(self, selector: str, text: str, clear: bool = True) -> str:
        """Type text into an input element.

        Args:
            selector: CSS selector.
            text: Text to type.
            clear: Whether to clear the field first.

        Returns:
            Status string.
        """
        try:
            el = self._run(self._page.locator(selector).first)
            if clear:
                self._run(el.fill(""))
            self._run(el.type(text, delay=30))
            return f"Typed into {selector}: {text[:50]}"
        except Exception as exc:
            return f"Type failed: {exc}"

    def screenshot(self, path: Optional[str] = None) -> str:
        """Capture a screenshot.

        Args:
            path: Optional file path. Defaults to shadow_workspace/screenshot.png.

        Returns:
            Path to saved screenshot.
        """
        save_path = path or str(self._workspace / "screenshot.png")
        try:
            self._run(self._page.screenshot(path=save_path, full_page=False))
            return f"Screenshot saved: {save_path}"
        except Exception as exc:
            return f"Screenshot failed: {exc}"

    def extract_text(self) -> str:
        """Extract visible text from the current page.

        Returns:
            Page text content.
        """
        try:
            text = self._run(self._page.inner_text("body"))
            return text[:8000]
        except Exception as exc:
            return f"Text extraction failed: {exc}"

    def extract_links(self) -> list[dict[str, str]]:
        """Extract all links from the current page.

        Returns:
            List of dicts with 'text' and 'href'.
        """
        links: list[dict[str, str]] = []
        try:
            elements = self._run(self._page.locator("a[href]").all())
            for el in elements:
                try:
                    text = self._run(el.inner_text())
                    href = self._run(el.get_attribute("href"))
                    if text and href:
                        links.append({"text": text.strip()[:120], "href": href.strip()})
                except Exception:
                    continue
        except Exception as exc:
            logger.error("extract_links failed: %s", exc)
        return links

    def fill_form(self, form_data: dict[str, str]) -> str:
        """Automate form filling.

        Args:
            form_data: Mapping of CSS selectors to values.

        Returns:
            Status string.
        """
        results = []
        for selector, value in form_data.items():
            try:
                el = self._run(self._page.locator(selector).first)
                self._run(el.fill(str(value)))
                results.append(f"✓ {selector}")
            except Exception as exc:
                results.append(f"✗ {selector}: {exc}")
        return "Form fill: " + ", ".join(results)

    def scroll_and_capture(self, path: Optional[str] = None) -> str:
        """Full page capture by scrolling and stitching screenshots.

        Args:
            path: Output path for the final image.

        Returns:
            Status string.
        """
        save_path = path or str(self._workspace / "full_page.png")
        try:
            self._run(self._page.screenshot(path=save_path, full_page=True))
            return f"Full page captured: {save_path}"
        except Exception as exc:
            # Fallback: single viewport screenshot
            return self.screenshot(save_path)

    def close(self) -> str:
        """Clean up browser, context, and Xvfb."""
        errors = []
        try:
            if self._context:
                self._run(self._context.close())
        except Exception as exc:
            errors.append(f"context: {exc}")
        try:
            if self._pw:
                self._run(self._pw.stop())
        except Exception as exc:
            errors.append(f"playwright: {exc}")
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        if self.xvfb_proc and self.xvfb_proc.poll() is None:
            try:
                self.xvfb_proc.terminate()
                self.xvfb_proc.wait(timeout=5)
            except Exception as exc:
                errors.append(f"xvfb: {exc}")
        self._page = self._context = self._pw = None
        self._loop = None
        self._thread = None
        if errors:
            return f"Closed with errors: {'; '.join(errors)}"
        return "BrowserAgent closed."
