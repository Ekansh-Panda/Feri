"""ResearcherAgent — multi-source research (web + local files + AI synthesis)."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.researcher")


@dataclass
class Finding:
    source: str = ""
    title: str = ""
    snippet: str = ""
    url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "title": self.title,
            "snippet": self.snippet,
            "url": self.url,
            "metadata": self.metadata,
        }


class ResearcherAgent:
    """Performs multi-source research and synthesizes findings."""

    def research(self, topic: str, depth: str = "quick") -> dict[str, Any]:
        """Conduct research on a topic at the requested depth.

        Args:
            topic: The research topic.
            depth: "quick" | "deep" — controls breadth/depth of sources.

        Returns:
            Dict with findings, summary, and citations.
        """
        depth = (depth or "quick").lower().strip()
        web_findings = self.web_search(topic)
        local_findings = self.local_search(topic)

        all_findings = web_findings + local_findings

        summary = self.synthesize(all_findings)
        citations = self.cite_sources(all_findings)

        return {
            "topic": topic,
            "depth": depth,
            "findings_count": len(all_findings),
            "findings": [f.to_dict() for f in all_findings],
            "summary": summary,
            "citations": citations,
        }

    def web_search(self, query: str) -> list[Finding]:
        """Search the web using the project's web_search action.

        Args:
            query: Search query string.

        Returns:
            List of Finding objects from web sources.
        """
        findings: list[Finding] = []
        try:
            from actions.web_search import _ddg_search, _gemini_search, _format_ddg

            # Try DDG first (fast, no quota)
            try:
                raw = _ddg_search(query, max_results=8)
                for r in raw:
                    findings.append(Finding(
                        source="web_ddg",
                        title=r.get("title", ""),
                        snippet=r.get("snippet", ""),
                        url=r.get("url", ""),
                    ))
            except Exception as exc:
                logger.warning("DDG search failed: %s", exc)

            # Try Gemini for a synthesized answer
            try:
                text = _gemini_search(query)
                if text:
                    findings.append(Finding(
                        source="web_gemini",
                        title=f"Gemini synthesis: {query}",
                        snippet=text[:2000],
                        url="gemini://synthesis",
                    ))
            except Exception as exc:
                logger.warning("Gemini search failed: %s", exc)

        except ImportError as exc:
            logger.error("Could not import web_search actions: %s", exc)

        return findings

    def local_search(self, query: str) -> list[Finding]:
        """Search local files using ripgrep.

        Args:
            query: Search query string.

        Returns:
            List of Finding objects from local sources.
        """
        findings: list[Finding] = []
        try:
            base = self._base_dir()
            search_roots = [
                base / "agents",
                base / "core",
                base / "actions",
                base / "plugins",
                base / "missions",
                base / "memory",
                base / "docs" if (base / "docs").exists() else None,
            ]
            search_roots = [p for p in search_roots if p]

            query_regex = query.replace(" ", ".*")

            for root in search_roots:
                try:
                    result = subprocess.run(
                        [
                            "rg",
                            "-i",
                            "-l",
                            "--max-columns",
                            "300",
                            query_regex,
                            str(root),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    for line in result.stdout.splitlines():
                        path = line.strip()
                        if not path:
                            continue
                        findings.append(Finding(
                            source="local_file",
                            title=path,
                            snippet=f"Matched file for query: {query}",
                            url=f"file://{path}",
                            metadata={"path": path},
                        ))
                except FileNotFoundError:
                    logger.warning("ripgrep (rg) not found; skipping local search under %s", root)
                except subprocess.TimeoutExpired:
                    logger.warning("Local search timed out under %s", root)
                except Exception as exc:
                    logger.warning("Local search error under %s: %s", root, exc)

        except Exception as exc:
            logger.error("Local search failed: %s", exc)

        return findings

    def synthesize(self, findings: list[Finding]) -> str:
        """Combine findings into a coherent summary.

        Args:
            findings: List of Finding objects.

        Returns:
            Coherent text summary.
        """
        if not findings:
            return "No findings to synthesize."

        snippets = []
        seen = set()
        for f in findings:
            text = f.snippet.strip()
            if text and text not in seen:
                seen.add(text)
                snippets.append(text)

        if not snippets:
            return "No content available to synthesize."

        combined = "\n\n".join(snippets[:10])

        # Try to use the local LLM for synthesis
        try:
            from core.llm_client import call_llm_text
            prompt = (
                "Synthesize the following research findings into a concise, "
                "well-structured summary. Preserve key facts, names, and numbers. "
                "Remove duplicates and noise.\n\n"
                f"{combined}"
            )
            return call_llm_text(prompt, system="You are a research synthesizer.", timeout=60)
        except Exception as exc:
            logger.warning("LLM synthesis failed, using raw aggregation: %s", exc)

        return combined

    def cite_sources(self, findings: list[Finding]) -> str:
        """Format findings as a citation list.

        Args:
            findings: List of Finding objects.

        Returns:
            Formatted citation string.
        """
        if not findings:
            return "No sources cited."

        lines = ["Sources:", "---"]
        for i, f in enumerate(findings, 1):
            title = f.title or "Untitled"
            url = f.url or "N/A"
            source = f.source
            lines.append(f"{i}. [{source}] {title}")
            if url and url not in ("N/A", "gemini://synthesis"):
                lines.append(f"   URL: {url}")
            if f.snippet:
                snippet_preview = f.snippet[:120].replace("\n", " ")
                lines.append(f"   Excerpt: {snippet_preview}...")
            lines.append("")

        return "\n".join(lines)

    # -- helpers --

    def _base_dir(self) -> Path:
        if getattr(self, "_frozen", False):
            return Path(getattr(self, "_executable", "")).parent
        return Path(__file__).resolve().parent.parent

    def _get_api_key(self) -> str:
        base = self._base_dir()
        cfg_path = base / "config" / "api_keys.json"
        try:
            import json
            return json.loads(cfg_path.read_text(encoding="utf-8")).get("gemini_api_key", "")
        except Exception:
            return ""
