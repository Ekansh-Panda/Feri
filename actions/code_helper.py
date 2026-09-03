"""
code_helper.py — AI code review, generation, explanation, optimisation, translation.
"""
from __future__ import annotations

import os
from typing import Optional

from config import get_config


def _api_key() -> Optional[str]:
    return (
        get_config().get("gemini_api_key")
        or os.environ.get("GEMINI_API_KEY")
    )


def _truncate(text: str, limit: int = 24_000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[…{len(text) - limit} chars truncated]"


class CodeHelper:
    """Gemini-backed code review, generation, explanation, optimisation, translation."""

    SYSTEM_RULES = (
        "You are JARVIS Code Helper. Be precise, terse, technically accurate. "
        "Return only the requested artefact — no preamble, no apologies."
    )

    def __init__(self, api_key: Optional[str] = None):
        self._key_override = api_key

    def _client(self):
        from google import genai
        key = self._key_override or _api_key()
        if not key:
            raise RuntimeError("Gemini API key not configured.")
        return genai.Client(api_key=key)

    def _generate(self, prompt: str, model: str = "gemini-flash-latest") -> str:
        try:
            client = self._client()
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"system_instruction": self.SYSTEM_RULES},
            )
            text = ""
            for part in response.candidates[0].content.parts:
                if getattr(part, "text", None):
                    text += part.text
            return text.strip() or "(empty response)"
        except Exception as e:
            return f"[code_helper] error: {e}"

    # ── Public API ─────────────────────────────────────────────────────────

    def review(self, code: str, language: str = "python") -> str:
        prompt = (
            f"Review this {language} code for bugs, security issues, "
            "performance and style. Output:\n"
            "## Summary\n"
            "## Issues (numbered, severity)\n"
            "## Suggested fixes (concrete diff snippets)\n\n"
            f"```\n{_truncate(code)}\n```"
        )
        return self._generate(prompt)

    def generate(self, prompt: str, language: str = "python") -> str:
        instruction = (
            f"Write {language} code that satisfies the request below. "
            "Return ONLY the code in a fenced code block.\n\n"
            f"Request: {prompt}"
        )
        return self._generate(instruction)

    def explain(self, code: str, language: str = "python") -> str:
        prompt = (
            f"Explain the following {language} code line-by-line. "
            "Use clear natural language; assume a competent developer audience.\n\n"
            f"```\n{_truncate(code)}\n```"
        )
        return self._generate(prompt)

    def optimize(self, code: str, language: str = "python") -> str:
        prompt = (
            f"Optimise this {language} code for performance, memory and readability. "
            "Return a single improved code block plus a short list of what changed.\n\n"
            f"```\n{_truncate(code)}\n```"
        )
        return self._generate(prompt)

    def translate(self, code: str, from_lang: str, to_lang: str) -> str:
        prompt = (
            f"Translate this {from_lang} code into idiomatic {to_lang}. "
            "Preserve behaviour; preserve comments. Return only the translated code.\n\n"
            f"```\n{_truncate(code)}\n```"
        )
        return self._generate(prompt)