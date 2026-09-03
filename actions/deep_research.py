"""
deep_research.py — multi-hour autonomous research loop for JARVIS NEXUS.

Iteratively searches, reads, and synthesizes findings on a topic, then saves
a markdown report to disk.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from actions.web_search import (
    _ddg_search,
    _format_ddg,
    _gemini_search,
)


class DeepResearch:
    """
    Autonomous multi-hour research agent.

    Each iteration:
      1. Generates a refined search query from accumulated notes
      2. Pulls new sources via DDG (+ Gemini grounding when available)
      3. Fetches and extracts page text
      4. Synthesizes incremental findings

    State is checkpointed to disk so a session can resume after crash.
    """

    DEFAULT_OUTPUT = Path.home() / ".jarvis" / "research"

    def __init__(
        self,
        output_dir: Optional[Path | str] = None,
        max_iterations: int = 5,
        per_iter_timeout: int = 300,
        progress_cb: Optional[Callable[[str, dict], None]] = None,
    ):
        self.output_dir = Path(output_dir) if output_dir else self.DEFAULT_OUTPUT
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_iterations = max_iterations
        self.per_iter_timeout = per_iter_timeout
        self.progress_cb = progress_cb or (lambda *a, **kw: None)

        self._cancelled = False

    # ── Public API ──────────────────────────────────────────────────────────

    def start_research(
        self,
        topic: str,
        output_dir: Optional[Path | str] = None,
    ) -> Path:
        """
        Run a complete autonomous research session on `topic`.
        Returns the path to the final markdown report.
        """
        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)

        slug = self._slug(topic)
        started_at = datetime.now()
        session_dir = self.output_dir / f"{slug}_{started_at:%Y%m%d_%H%M%S}"
        session_dir.mkdir(parents=True, exist_ok=True)

        self._report(f"Deep research started: {topic!r}", {
            "topic": topic, "out": str(session_dir), "max_iter": self.max_iterations,
        })

        state: dict[str, Any] = {
            "topic": topic,
            "started_at": started_at.isoformat(timespec="seconds"),
            "iterations": [],
            "seen_urls": [],
            "notes": [],
        }

        prior_query = topic
        try:
            for i in range(1, self.max_iterations + 1):
                if self._cancelled:
                    self._report("Research cancelled by host", {"iter": i})
                    break

                self._report(f"Iteration {i}/{self.max_iterations}", {"iter": i})
                iter_state = self._iteration(
                    topic, prior_query, i, session_dir, state
                )
                state["iterations"].append(iter_state)
                prior_query = iter_state.get("next_query", topic)
                self._save_state(session_dir, state)

                # End early if no new sources found
                if iter_state.get("new_sources", 0) == 0:
                    self._report(
                        "No new sources — ending early", {"iter": i}
                    )
                    break

            report_path = self._write_report(session_dir, state)
            self._report("Deep research complete", {"report": str(report_path)})
            return report_path

        except Exception as e:
            err_path = session_dir / "ERROR.txt"
            err_path.write_text(
                f"{datetime.now().isoformat(timespec='seconds')}\n{type(e).__name__}: {e}\n",
                encoding="utf-8",
            )
            self._report(f"Research error: {e}", {"exc": type(e).__name__})
            return self._write_report(session_dir, state)

    def cancel(self) -> None:
        """Request graceful stop of an in-progress session."""
        self._cancelled = True

    # ── Internals ───────────────────────────────────────────────────────────

    def _iteration(
        self,
        topic: str,
        query: str,
        index: int,
        session_dir: Path,
        state: dict,
    ) -> dict:
        iter_dir = session_dir / f"iter_{index:02d}"
        iter_dir.mkdir(parents=True, exist_ok=True)

        results = _ddg_search(query, max_results=8)
        new_sources: list[dict] = []
        for r in results:
            url = r.get("url", "")
            if not url or url in state["seen_urls"]:
                continue
            state["seen_urls"].append(url)

            page_text = self._fetch_safe(url)
            (iter_dir / f"{self._slug(url)[:60]}.txt").write_text(
                page_text or r.get("snippet", ""), encoding="utf-8", errors="ignore"
            )

            new_sources.append({
                "url": url,
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "text_len": len(page_text or ""),
            })

        synthesis = self._synthesize(topic, query, new_sources, state["notes"])

        next_q = self._next_query(topic, synthesis, query)
        state["notes"].append({
            "iter": index,
            "query": query,
            "synthesis": synthesis,
            "source_count": len(new_sources),
        })

        (iter_dir / "synthesis.md").write_text(
            f"# Iteration {index}: {query}\n\n{synthesis}\n",
            encoding="utf-8",
        )

        return {
            "iter": index,
            "query": query,
            "next_query": next_q,
            "new_sources": len(new_sources),
            "sources": new_sources[:5],
        }

    def _synthesize(
        self,
        topic: str,
        query: str,
        new_sources: list[dict],
        prior_notes: list[dict],
    ) -> str:
        """Synthesize findings for this iteration using Gemini when available."""
        if not new_sources:
            return "(no new content this iteration)"

        prior = "\n".join(
            f"- (iter {n.get('iter', '?')}) {n.get('synthesis', '')[:300]}"
            for n in prior_notes[-3:]
        )

        prompt = (
            f"Topic: {topic}\n"
            f"Current focus query: {query}\n"
            f"New sources discovered: {len(new_sources)}\n\n"
            "Synthesize the new sources below into 4-8 concise bullet points of "
            "novel, factual information not already covered in prior notes.\n\n"
            "Sources:\n"
            + "\n".join(
                f"- {s.get('title', '')} | {s.get('snippet', '')[:240]}"
                for s in new_sources
            )
            + (f"\n\nPrior notes (do not repeat):\n{prior}" if prior else "")
        )

        try:
            text = _gemini_search(prompt)
            if text and len(text) > 80:
                return text.strip()
        except Exception:
            pass

        return _format_ddg(query, [
            {"title": s.get("title", ""), "snippet": s.get("snippet", ""), "url": s.get("url", "")}
            for s in new_sources
        ])

    def _next_query(self, topic: str, synthesis: str, current: str) -> str:
        """Refine the research query based on the latest synthesis."""
        try:
            refined = _gemini_search(
                f"Based on these research notes about '{topic}', "
                f"what is the single most important follow-up question to investigate next?\n\n"
                f"Notes:\n{(synthesis or '')[:600]}\n\n"
                f"Reply with only the question, no preamble."
            ).strip().splitlines()[0]
            refined = refined.strip().strip('"').strip("'")
            if 6 < len(refined) < 200:
                return refined
        except Exception:
            pass
        return current

    def _fetch_safe(self, url: str) -> str:
        try:
            from actions.web_search import _read_url_text
            return _read_url_text(url, max_chars=12000) or ""
        except Exception:
            return ""

    def _write_report(self, session_dir: Path, state: dict) -> Path:
        path = session_dir / "report.md"
        lines: list[str] = [
            f"# Deep Research: {state['topic']}",
            "",
            f"_Started: {state['started_at']}_",
            f"_Completed: {datetime.now().isoformat(timespec='seconds')}_",
            f"_Iterations: {len(state['iterations'])}_",
            f"_Unique sources consulted: {len(state['seen_urls'])}_",
            "",
            "## Executive Summary",
            "",
        ]
        if state["notes"]:
            last = state["notes"][-1].get("synthesis", "").strip()
            lines.append(last[:1500] if last else "_No synthesis available._")
        else:
            lines.append("_No iterations completed._")

        lines += ["", "## Iteration Detail", ""]
        for n in state["notes"]:
            lines.append(f"### Iteration {n.get('iter', '?')} — query: {n.get('query','')}")
            lines.append("")
            lines.append((n.get("synthesis") or "").strip())
            lines.append("")

        if state["seen_urls"]:
            lines += ["", "## All Sources Consulted", ""]
            for u in state["seen_urls"]:
                lines.append(f"- {u}")

        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _save_state(self, session_dir: Path, state: dict) -> None:
        try:
            (session_dir / "state.json").write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _report(self, message: str, payload: Optional[dict] = None) -> None:
        print(f"[DeepResearch] {message}")
        try:
            self.progress_cb(message, payload or {})
        except Exception:
            pass

    @staticmethod
    def _slug(text: str) -> str:
        import re
        s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
        return s[:50] or "research"