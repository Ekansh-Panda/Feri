"""
document_compiler.py — pandoc + xelatex + genanki pipeline.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return subprocess.CompletedProcess(cmd, -1, "", str(e))


class DocumentCompiler:
    """Pandoc, xelatex and genanki pipeline for PDFs, EPUBs and Anki decks."""

    # ── Markdown → PDF ──────────────────────────────────────────────────────

    def markdown_to_pdf(self, input_dir: Path | str, output: Path | str,
                        title: str = "Document",
                        author: str = "JARVIS NEXUS") -> bool:
        if not _which("pandoc"):
            print("[DocumentCompiler] pandoc not installed.")
            return False
        if not _which("xelatex"):
            print("[DocumentCompiler] xelatex not installed (texlive-xetex).")
            return False

        input_dir = Path(input_dir)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "pandoc",
            "--from=markdown",
            "--to=pdf",
            "--pdf-engine=xelatex",
            "-V", f"title={title}",
            "-V", f"author={author}",
            "-V", "geometry:margin=1in",
            "-V", "mainfont=DejaVu Sans",
            "-V", "monofont=DejaVu Sans Mono",
            "--output", str(output),
            str(input_dir),
        ]
        r = _run(cmd, timeout=600)
        if r.returncode != 0:
            print(f"[DocumentCompiler] pandoc → pdf failed: {r.stderr.strip()}")
        return r.returncode == 0 and output.exists()

    # ── Markdown → EPUB ─────────────────────────────────────────────────────

    def markdown_to_epub(self, input_dir: Path | str, output: Path | str,
                         title: str = "Document",
                         author: str = "JARVIS NEXUS") -> bool:
        if not _which("pandoc"):
            return False
        input_dir = Path(input_dir)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "pandoc",
            "--from=markdown",
            "--to=epub3",
            "--metadata", f"title={title}",
            "--metadata", f"author={author}",
            "--output", str(output),
            str(input_dir),
        ]
        r = _run(cmd, timeout=300)
        return r.returncode == 0 and output.exists()

    # ── Anki deck from list of {q, a} ───────────────────────────────────────

    def build_anki_deck(self, questions: list[dict], output: Path | str,
                         deck_name: str = "JARVIS Deck") -> bool:
        """`questions` is a list of {'front': str, 'back': str} dicts."""
        try:
            import genanki  # type: ignore
        except ImportError:
            print("[DocumentCompiler] genanki not installed.")
            return False

        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        deck_id = _stable_id(deck_name)
        model_id = _stable_id(f"{deck_name}-model")
        model = genanki.Model(
            model_id,
            "JARVIS Card",
            fields=[{"name": "Front"}, {"name": "Back"}],
            templates=[{
                "name": "Card 1",
                "qfmt": "{{Front}}",
                "afmt": '{{Front}}<hr id="answer">{{Back}}',
            }],
        )
        deck = genanki.Deck(deck_id, deck_name)
        for q in questions:
            deck.add_note(genanki.Note(
                model=model,
                fields=[str(q.get("front", "")), str(q.get("back", ""))],
            ))

        try:
            genanki.Package(deck).write_to_file(str(output))
            return output.exists()
        except Exception as e:
            print(f"[DocumentCompiler] genanki error: {e}")
            return False

    # ── Formula sheet (xelatex standalone) ──────────────────────────────────

    def build_latex_formula_sheet(self, formulas: list[str],
                                  output: Path | str,
                                  title: str = "Formula Sheet") -> bool:
        if not _which("xelatex"):
            print("[DocumentCompiler] xelatex not installed.")
            return False
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        body = "\n".join(f"\\[{f.strip()}\\]" for f in formulas if f.strip())
        tex = (
            "\\documentclass[12pt]{article}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\usepackage{geometry}\n"
            "\\geometry{margin=1in}\n"
            f"\\title{title}\n"
            "\\date{\\today}\n"
            "\\begin{document}\n"
            f"\\maketitle\n\n{body}\n"
            "\\end{document}\n"
        )

        tmp_dir = output.parent / "_formula_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tex_path = tmp_dir / f"{output.stem}.tex"
        tex_path.write_text(tex, encoding="utf-8")

        for _ in range(2):
            r = _run(["xelatex", "-interaction=nonstopmode", "-halt-on-error",
                      tex_path.name], cwd=tmp_dir, timeout=120)
            if r.returncode != 0:
                print(f"[DocumentCompiler] xelatex error: {r.stderr.strip()[:300]}")
                break

        pdf = tmp_dir / f"{output.stem}.pdf"
        if not pdf.exists():
            return False
        shutil.move(str(pdf), str(output))
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return output.exists()


def _stable_id(seed: str) -> int:
    """Deterministic positive 63-bit ID for Anki deck/model."""
    import hashlib
    h = hashlib.sha1(seed.encode("utf-8")).digest()
    val = int.from_bytes(h[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF
    return val