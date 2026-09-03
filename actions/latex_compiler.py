"""
latex_compiler.py — xelatex compilation, bibtex, watch and clean.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _run(cmd: list[str], cwd: Optional[Path | str] = None,
         timeout: int = 180) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              cwd=str(cwd) if cwd else None, timeout=timeout)
    except Exception as e:
        return subprocess.CompletedProcess(cmd, -1, "", str(e))


class LatexCompiler:
    """xelatex with automatic bibtex detection and a file-watcher helper."""

    def __init__(self, engine: str = "xelatex") -> None:
        if not _which(engine):
            raise RuntimeError(f"{engine} not installed")
        self.engine = engine

    # ── Compile ────────────────────────────────────────────────────────────

    def compile(self, tex_path: Path | str, output_dir: Path | str = ".",
                bibtex: bool = True, runs: int = 2) -> bool:
        return self.compile_pdf(tex_path, output_dir, bibtex=bibtex, runs=runs) is not None

    def compile_pdf(self, tex_path: Path | str, output_dir: Path | str = ".",
                    bibtex: bool = True, runs: int = 2) -> Optional[Path]:
        tex_path = Path(tex_path)
        if not tex_path.exists():
            return None
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Run 1 — generate aux / find bibliography
        r = _run([self.engine, "-interaction=nonstopmode", "-halt-on-error",
                  "-output-directory", str(out_dir), tex_path.name],
                 cwd=str(tex_path.parent), timeout=180)
        if r.returncode != 0:
            print(f"[LatexCompiler] {self.engine} run 1 failed: {r.stderr.strip()[:300]}")
            return None

        used_bib = bibtex and (out_dir / tex_path.with_suffix(".aux").name).exists() \
                   and _aux_has_bib(out_dir / tex_path.with_suffix(".aux").name)

        if used_bib and _which("bibtex"):
            _run(["bibtex", tex_path.stem], cwd=str(out_dir), timeout=60)
            runs = max(runs, 2)

        # Make sure cross-references resolve
        for _ in range(max(1, runs - 1)):
            _run([self.engine, "-interaction=nonstopmode", "-halt-on-error",
                  "-output-directory", str(out_dir), tex_path.name],
                 cwd=str(tex_path.parent), timeout=180)

        pdf = out_dir / f"{tex_path.stem}.pdf"
        return pdf if pdf.exists() else None

    # ── Watch ──────────────────────────────────────────────────────────────

    def watch(self, tex_path: Path | str, poll_seconds: float = 1.0,
              callback=None) -> None:
        """Rebuild whenever the .tex file changes. Run forever."""
        tex_path = Path(tex_path)
        last_mtime = tex_path.stat().st_mtime if tex_path.exists() else 0.0
        print(f"[LatexCompiler] Watching {tex_path} — Ctrl+C to stop.")
        try:
            while True:
                time.sleep(poll_seconds)
                if not tex_path.exists():
                    continue
                mt = tex_path.stat().st_mtime
                if mt == last_mtime:
                    continue
                last_mtime = mt
                print(f"[LatexCompiler] change detected at {tex_path}")
                pdf = self.compile_pdf(tex_path)
                if callback:
                    try:
                        callback(pdf)
                    except Exception:
                        pass
        except KeyboardInterrupt:
            print("[LatexCompiler] watch stopped.")

    # ── Clean ──────────────────────────────────────────────────────────────

    def clean(self, tex_path: Path | str,
              extensions: tuple[str, ...] = (
                  ".aux", ".log", ".toc", ".out", ".bbl", ".blg",
                  ".nav", ".snm", ".vrb", ".fls", ".fdb_latexmk",
                  ".synctex.gz", ".idx", ".ilg", ".ind",
              )) -> int:
        tex_path = Path(tex_path)
        parent = tex_path.parent
        stem = tex_path.stem
        removed = 0
        for ext in extensions:
            for f in parent.glob(f"{stem}{ext}"):
                try:
                    f.unlink()
                    removed += 1
                except Exception:
                    pass
        return removed


def _aux_has_bib(aux_path: Path) -> bool:
    try:
        text = aux_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return "\\bibdata" in text or "\\citation" in text