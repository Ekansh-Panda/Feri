"""CompilerAgent — MD → LaTeX → PDF → Anki → EPUB batch compilation."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.compiler")


class CompilerAgent:
    """Compiles Markdown into PDF, EPUB, LaTeX formula sheets, and Anki decks."""

    def markdown_to_pdf(self, md_path: str | Path, output_path: str | Path) -> dict[str, Any]:
        """Convert Markdown to PDF via pandoc + xelatex.

        Args:
            md_path: Input Markdown file.
            output_path: Output PDF path.

        Returns:
            Dict with status, output_path, and any stderr.
        """
        md = Path(md_path).expanduser().resolve()
        out = Path(output_path).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        if not md.exists():
            return {"status": "error", "error": f"Markdown file not found: {md}"}

        try:
            proc = subprocess.run(
                [
                    "pandoc",
                    str(md),
                    "-o", str(out),
                    "--pdf-engine=xelatex",
                    "-V", "CJKmainfont=Noto Sans CJK JP",
                    "-V", "geometry:margin=1in",
                    "-V", "fontsize=11pt",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode != 0:
                return {"status": "error", "error": proc.stderr or "pandoc failed", "stderr": proc.stderr}
            return {"status": "ok", "output_path": str(out)}
        except FileNotFoundError:
            return {"status": "error", "error": "pandoc not found. Install pandoc."}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "pandoc timed out."}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def markdown_to_epub(self, md_path: str | Path, output_path: str | Path) -> dict[str, Any]:
        """Convert Markdown to EPUB via pandoc.

        Args:
            md_path: Input Markdown file.
            output_path: Output EPUB path.

        Returns:
            Dict with status and output_path.
        """
        md = Path(md_path).expanduser().resolve()
        out = Path(output_path).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        if not md.exists():
            return {"status": "error", "error": f"Markdown file not found: {md}"}

        try:
            proc = subprocess.run(
                ["pandoc", str(md), "-o", str(out), "--toc"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode != 0:
                return {"status": "error", "error": proc.stderr or "pandoc epub failed"}
            return {"status": "ok", "output_path": str(out)}
        except FileNotFoundError:
            return {"status": "error", "error": "pandoc not found."}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def build_anki_deck(self, questions: list[dict[str, Any]], output_path: str | Path) -> dict[str, Any]:
        """Build an Anki .apkg deck from question cards.

        Args:
            questions: List of dicts with 'front' and 'back' keys.
            output_path: Output .apkg path.

        Returns:
            Dict with status and output_path.
        """
        try:
            import genanki
        except ImportError:
            return {"status": "error", "error": "genanki not installed. Run: pip install genanki"}

        out = Path(output_path).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        model = genanki.Model(
            1607392319,
            "JARVIS Model",
            fields=[{"name": "Front"}, {"name": "Back"}],
            templates=[
                {"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{FrontSide}}<hr id=answer>{{Back}}"},
            ],
        )

        deck = genanki.Deck(2059400110, "JARVIS Deck")
        for q in questions:
            front = str(q.get("front", "")).strip()
            back = str(q.get("back", "")).strip()
            if not front:
                continue
            note = genanki.Note(model=model, fields=[front, back])
            deck.add_note(note)

        try:
            genanki.Package(deck).write_to_file(str(out))
            return {"status": "ok", "output_path": str(out), "cards_added": len(deck.notes)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def build_latex_formula_sheet(self, formulas: list[dict[str, str]], output_path: str | Path) -> dict[str, Any]:
        """Build a LaTeX formula sheet and compile to PDF.

        Args:
            formulas: List of dicts with 'name' and 'latex' keys.
            output_path: Output PDF path.

        Returns:
            Dict with status and output_path.
        """
        out = Path(output_path).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            r"\documentclass[11pt]{article}",
            r"\usepackage{amsmath,amssymb,geometry}",
            r"\geometry{margin=1in}",
            r"\title{Formula Sheet}",
            r"\begin{document}",
            r"\maketitle",
            r"\section*{Formulas}",
            r"\begin{itemize}",
        ]
        for item in formulas:
            name = str(item.get("name", "Unnamed")).strip()
            latex = str(item.get("latex", "")).strip()
            if not latex:
                continue
            lines.append(rf"\item \textbf{{{name}}} \quad $${latex}$$")
        lines.extend([
            r"\end{itemize}",
            r"\end{document}",
        ])

        tex_content = "\n".join(lines)
        tmp_dir = Path(tempfile.mkdtemp(prefix="jarvis_latex_"))
        tex_file = tmp_dir / "formulas.tex"
        tex_file.write_text(tex_content, encoding="utf-8")

        try:
            proc = subprocess.run(
                ["xelatex", "-interaction=nonstopmode", str(tex_file)],
                cwd=str(tmp_dir),
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                return {"status": "error", "error": proc.stderr or "xelatex failed"}
            generated = tmp_dir / "formulas.pdf"
            if generated.exists():
                shutil.copy2(str(generated), str(out))
                return {"status": "ok", "output_path": str(out)}
            return {"status": "error", "error": "PDF not generated"}
        except FileNotFoundError:
            return {"status": "error", "error": "xelatex not found. Install texlive."}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
        finally:
            try:
                shutil.rmtree(str(tmp_dir), ignore_errors=True)
            except Exception:
                pass

    def compile_document(self, input_dir: str | Path, output_format: str = "pdf") -> dict[str, Any]:
        """Batch compile all Markdown files in a directory.

        Args:
            input_dir: Directory containing Markdown files.
            output_format: "pdf" or "epub".

        Returns:
            Dict with results for each file.
        """
        base = Path(input_dir).expanduser().resolve()
        if not base.is_dir():
            return {"status": "error", "error": f"Not a directory: {base}"}

        results: list[dict[str, Any]] = []
        for md_file in sorted(base.glob("*.md")):
            if output_format == "pdf":
                out_path = md_file.with_suffix(".pdf")
                res = self.markdown_to_pdf(md_file, out_path)
            else:
                out_path = md_file.with_suffix(".epub")
                res = self.markdown_to_epub(md_file, out_path)
            results.append({"input": str(md_file), "result": res})

        success = [r for r in results if r["result"].get("status") == "ok"]
        failed = [r for r in results if r["result"].get("status") != "ok"]
        return {
            "status": "ok" if not failed else "partial",
            "total": len(results),
            "success": len(success),
            "failed": len(failed),
            "results": results,
        }
