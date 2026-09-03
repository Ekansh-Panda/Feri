"""
dev_agent.py — developer task agent (project init, tests, lint, format, git).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def _run(cmd: list[str], cwd: Optional[Path | str] = None,
         timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              cwd=str(cwd) if cwd else None, timeout=timeout)
    except Exception as e:
        return subprocess.CompletedProcess(cmd, -1, "", str(e))


_PROJECT_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    # name -> list of (relative_path, content)
    "python": [
        ("pyproject.toml", """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "{name}"
version = "0.1.0"
description = "{name}"
requires-python = ">=3.10"
"""),
        ("README.md",      "# {name}\n\nA Python project.\n"),
        ("src/__init__.py", ""),
        ("tests/test_smoke.py", "def test_import():\n    import {module}\n    assert True\n"),
        (".gitignore", "__pycache__/\n*.pyc\n.venv/\n.pytest_cache/\n.mypy_cache/\n"),
    ],
    "node": [
        ("package.json", """{
  "name": "{name}",
  "version": "0.1.0",
  "type": "module",
  "scripts": { "test": "echo 'no tests yet'" }
}
"""),
        ("README.md", "# {name}\n\nA Node project.\n"),
        ("src/index.js", "// entry point\n"),
        (".gitignore", "node_modules/\ndist/\n.env\n"),
    ],
    "rust": [
        ("Cargo.toml", """[package]
name = "{name}"
version = "0.1.0"
edition = "2021"
"""),
        ("README.md",     "# {name}\n\nA Rust project.\n"),
        ("src/main.rs",   'fn main() { println!("hello {name}"); }\n'),
        (".gitignore",    "target/\nCargo.lock\n"),
    ],
    "go": [
        ("go.mod", "module {name}\n\ngo 1.22\n"),
        ("main.go", "package main\n\nfunc main() {}\n"),
        ("README.md", "# {name}\n\nA Go project.\n"),
        (".gitignore", "bin/\n"),
    ],
}


def _slugify(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9_-]+", "-", name.strip().lower()).strip("-") or "project"


class DevAgent:
    """Developer workflow helpers: project init, tests, lint, format, git."""

    # ── Project init ───────────────────────────────────────────────────────

    def setup_project(self, project_type: str, name: str,
                      root: Optional[Path | str] = None) -> Path:
        """Scaffold a project directory from a template."""
        project_type = project_type.lower().strip()
        if project_type not in _PROJECT_TEMPLATES:
            raise ValueError(f"unknown project type: {project_type}")
        if not name or not name.strip():
            raise ValueError("project name required")

        base = Path(root) if root else Path.cwd() / _slugify(name)
        base.mkdir(parents=True, exist_ok=True)
        module = _slugify(name).replace("-", "_")
        for rel, tmpl in _PROJECT_TEMPLATES[project_type]:
            out = base / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            content = tmpl.format(name=name, module=module)
            out.write_text(content, encoding="utf-8")
        return base

    # ── Tests / lint / format ──────────────────────────────────────────────

    def run_tests(self, path: Path | str = ".") -> tuple[bool, str]:
        cmd = ["pytest", "-q", "--color=no", str(path)]
        r = _run(cmd, timeout=600)
        return r.returncode == 0, (r.stdout + r.stderr).strip()

    def run_linter(self, path: Path | str = ".") -> tuple[bool, str]:
        if _which("ruff"):
            r = _run(["ruff", "check", str(path)], timeout=120)
            return r.returncode == 0, (r.stdout + r.stderr).strip()
        if _which("pylint"):
            r = _run(["pylint", str(path)], timeout=180)
            return r.returncode == 0, (r.stdout + r.stderr).strip()
        return False, "no linter available (install ruff or pylint)"

    def run_formatter(self, path: Path | str = ".") -> tuple[bool, str]:
        if _which("ruff"):
            r = _run(["ruff", "format", str(path)], timeout=60)
            return r.returncode == 0, (r.stdout + r.stderr).strip()
        if _which("black"):
            r = _run(["black", str(path)], timeout=120)
            return r.returncode == 0, (r.stdout + r.stderr).strip()
        return False, "no formatter available (install ruff or black)"

    # ── Git ────────────────────────────────────────────────────────────────

    def git_status(self, cwd: Optional[Path | str] = None) -> tuple[bool, str]:
        r = _run(["git", "status", "--short"], cwd=cwd)
        return r.returncode == 0, r.stdout.strip()

    def git_diff(self, cwd: Optional[Path | str] = None) -> tuple[bool, str]:
        r = _run(["git", "diff"], cwd=cwd)
        return r.returncode == 0, r.stdout

    def git_commit(self, message: str, cwd: Optional[Path | str] = None,
                   add_all: bool = True) -> tuple[bool, str]:
        if not message.strip():
            return False, "empty commit message"
        if add_all:
            _run(["git", "add", "-A"], cwd=cwd)
        r = _run(["git", "commit", "-m", message], cwd=cwd)
        return r.returncode == 0, (r.stdout + r.stderr).strip()

    def create_branch(self, name: str, cwd: Optional[Path | str] = None) -> bool:
        r = _run(["git", "checkout", "-b", name], cwd=cwd)
        return r.returncode == 0

    def switch_branch(self, name: str, cwd: Optional[Path | str] = None) -> bool:
        r = _run(["git", "checkout", name], cwd=cwd)
        return r.returncode == 0

    def merge_branch(self, name: str, cwd: Optional[Path | str] = None) -> tuple[bool, str]:
        r = _run(["git", "merge", name], cwd=cwd)
        return r.returncode == 0, (r.stdout + r.stderr).strip()

    def git_init(self, cwd: Optional[Path | str] = None) -> bool:
        r = _run(["git", "init"], cwd=cwd)
        return r.returncode == 0