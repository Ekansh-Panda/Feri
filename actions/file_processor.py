"""
file_processor.py — document reading and AI summarization.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Union

from config import get_config


def _api_key() -> Optional[str]:
    return (
        get_config().get("gemini_api_key")
        or os.environ.get("GEMINI_API_KEY")
    )


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[…{len(text) - limit} more chars truncated]"


class FileProcessor:
    """Document reader + AI summarization."""

    def read_text(self, path: Union[str, Path]) -> str:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return ""
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def read_pdf(self, path: Union[str, Path], max_pages: int = 0) -> str:
        p = Path(path)
        if not p.exists():
            return ""
        text_parts: list[str] = []

        # Try pdfplumber first
        try:
            import pdfplumber  # type: ignore
            with pdfplumber.open(str(p)) as pdf:
                for i, page in enumerate(pdf.pages):
                    if max_pages and i >= max_pages:
                        break
                    text_parts.append(page.extract_text() or "")
            joined = "\n\n".join(text_parts).strip()
            if joined:
                return joined
        except Exception:
            pass

        # Fallback to PyMuPDF
        try:
            import fitz  # type: ignore
            doc = fitz.open(str(p))
            for i, page in enumerate(doc):
                if max_pages and i >= max_pages:
                    break
                text_parts.append(page.get_text() or "")
            doc.close()
            joined = "\n\n".join(text_parts).strip()
            if joined:
                return joined
        except Exception:
            pass

        return "\n\n".join(text_parts)

    def read_docx(self, path: Union[str, Path]) -> str:
        p = Path(path)
        if not p.exists():
            return ""
        try:
            import docx  # type: ignore
            d = docx.Document(str(p))
            return "\n".join(par.text for par in d.paragraphs).strip()
        except Exception as e:
            return f"[docx read error: {e}]"

    def read_any(self, path: Union[str, Path]) -> str:
        p = Path(path)
        ext = p.suffix.lower()
        if ext in (".txt", ".md", ".rst", ".log", ".csv", ".json", ".py",
                   ".js", ".ts", ".html", ".xml", ".yaml", ".yml", ".ini",
                   ".cfg", ".conf"):
            return self.read_text(p)
        if ext == ".pdf":
            return self.read_pdf(p)
        if ext in (".docx",):
            return self.read_docx(p)
        return self.read_text(p)

    def summarize(self, content: str, max_length: int = 500) -> str:
        """AI summarization via Gemini, with a heuristic fallback."""
        if not content or not content.strip():
            return "(empty content)"

        key = _api_key()
        if key:
            try:
                from google import genai
                client = genai.Client(api_key=key)
                response = client.models.generate_content(
                    model="gemini-flash-latest",
                    contents=(
                        f"Summarize the following content in clear, factual prose. "
                        f"Keep it under {max_length} words.\n\n"
                        f"---\n{_truncate(content, 30_000)}\n---"
                    ),
                )
                text = ""
                for part in response.candidates[0].content.parts:
                    if getattr(part, "text", None):
                        text += part.text
                if text.strip():
                    return text.strip()
            except Exception as e:
                print(f"[FileProcessor] Gemini summarize failed: {e}")

        return self._heuristic_summary(content, max_length)

    def extract_text_from_image(self, image_path: Union[str, Path]) -> str:
        """OCR via tesseract (delegates to ScreenProcessor.ocr when available)."""
        try:
            from actions.screen_processor import ScreenProcessor
            return ScreenProcessor().ocr(image_path)
        except Exception:
            return ""

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _heuristic_summary(text: str, max_length: int) -> str:
        sentences = []
        for raw in text.replace("\n", " ").split(". "):
            s = raw.strip()
            if not s:
                continue
            if len(s) > 30:
                sentences.append(s)
        joined = ". ".join(sentences[: max(3, max_length // 80)])
        return _truncate(joined, max_length * 6)