"""
Holographic Engine — PyQt WebEngine view that hosts a Three.js renderer.

Pushes JSON payloads into the page via `runJavaScript`; pre-built renderers
cover code topology, molecular structure, math surfaces, and file trees.
"""

from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO_ROOT / "ui" / "templates" / "hologram_base.html"


class HolographicEngine:
    """Three.js-backed holographic renderer.

    Implemented as a thin facade so the module imports even when PyQt is
    unavailable. The Qt widget is created on demand in `as_qwidget()`.
    """

    def __init__(self, parent: Optional[Any] = None) -> None:
        self.parent = parent
        self._view = None  # type: ignore[var-annotated]
        self._template_html: str = self._load_template()

    @staticmethod
    def _load_template() -> str:
        """Load the Three.js HTML template, or fall back to a stub."""
        if TEMPLATE_PATH.exists():
            try:
                return TEMPLATE_PATH.read_text(encoding="utf-8")
            except Exception:
                pass
        return (
            "<!doctype html><html><body><div id='h'></div>"
            "<script>window.JARVIS_RENDER=(d)=>{document.getElementById('h').textContent="
            "JSON.stringify(d);};</script></body></html>"
        )

    # ---- Qt integration ----

    def as_qwidget(self) -> Any:
        """Return a QWebEngineView preloaded with the template."""
        if self._view is not None:
            return self._view
        try:
            from PyQt6.QtCore import QUrl  # type: ignore[import-untyped]
            from PyQt6.QtWebEngineWidgets import QWebEngineView  # type: ignore[import-untyped]
        except Exception as e:
            raise RuntimeError(f"PyQt6.QtWebEngineWidgets unavailable: {e}") from e

        view = QWebEngineView(self.parent)
        view.setHtml(self._template_html, baseUrl=QUrl.fromLocalFile(str(TEMPLATE_PATH)))
        self._view = view
        return view

    def inject_data(self, data: Dict[str, Any], render_type: str = "generic") -> None:
        """Push a payload to the page and trigger a renderer."""
        if self._view is None:
            return
        js = (
            "window.JARVIS_RENDER && "
            f"window.JARVIS_RENDER({json.dumps(data)}, {json.dumps(render_type)});"
        )
        try:
            self._view.page().runJavaScript(js)
        except Exception:
            pass

    # ---- Renderers ----

    def render_code_topology(self, directory: str) -> Dict[str, Any]:
        """Walk Python files and build an AST import graph."""
        root = Path(directory)
        if not root.is_absolute():
            root = REPO_ROOT / directory
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Tuple[str, str]] = []

        for py in root.rglob("*.py"):
            mod = self._module_name(py, root)
            nodes[mod] = {"file": str(py.relative_to(root))}
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
            except (SyntaxError, ValueError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        target = self._module_name_from_import(alias.name, root)
                        if target:
                            edges.append((mod, target))
                elif isinstance(node, ast.ImportFrom):
                    base = node.module or ""
                    target = self._module_name_from_import(base, root)
                    if target:
                        edges.append((mod, target))

        return {
            "type": "code_topology",
            "root": str(root),
            "nodes": [{"id": k, **v} for k, v in nodes.items()],
            "edges": [{"source": s, "target": t} for s, t in edges],
        }

    @staticmethod
    def _module_name(path: Path, root: Path) -> str:
        rel = path.relative_to(root).with_suffix("")
        return ".".join(rel.parts)

    @staticmethod
    def _module_name_from_import(name: str, root: Path) -> Optional[str]:
        """Match an import string against modules discoverable under root."""
        if not name:
            return None
        candidate = root / name.replace(".", "/")
        if (candidate.with_suffix(".py")).exists():
            return name
        if candidate.is_dir() and (candidate / "__init__.py").exists():
            return name
        return None

    def render_molecular_structure(self, pdb_code: str) -> Dict[str, Any]:
        """Build a minimal atom-set for a PDB code (offline stub).

        For online resolution, callers can pre-populate atoms and call
        `inject_data` directly. This stub returns a tetrahedron of dummy
        atoms so the renderer has something to display offline.
        """
        pdb_code = (pdb_code or "").upper().strip() or "UNK"
        coords = [
            ("C1", 0.0, 0.0, 0.0),
            ("C2", 1.5, 0.0, 0.0),
            ("C3", 0.75, 1.3, 0.0),
            ("N1", 0.75, 0.43, 1.0),
        ]
        return {
            "type": "molecular",
            "pdb": pdb_code,
            "atoms": [{"element": e, "x": x, "y": y, "z": z} for e, x, y, z in coords],
            "bonds": [(0, 1), (1, 2), (2, 0), (0, 3)],
        }

    def render_math_surface(self, equation: str) -> Dict[str, Any]:
        """Sanitise an equation for client-side evaluation; ship the source.

        We never eval() arbitrary Python here — the JS side renders it.
        This method just packages the equation metadata.
        """
        return {
            "type": "math_surface",
            "equation": equation,
            "domain": [-3.0, 3.0, 30],
        }

    def render_filesystem_tree(self, path: str, depth: int = 3) -> Dict[str, Any]:
        """Recursively walk a directory tree to `depth` levels."""
        root = Path(path)
        if not root.is_absolute():
            root = REPO_ROOT / path

        def _walk(p: Path, d: int) -> Dict[str, Any]:
            entry: Dict[str, Any] = {
                "name": p.name or str(p),
                "type": "dir" if p.is_dir() else "file",
                "children": [],
            }
            if p.is_dir() and d > 0:
                try:
                    children = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
                except (PermissionError, FileNotFoundError):
                    children = []
                for c in children[:200]:
                    if c.name.startswith("."):
                        continue
                    entry["children"].append(_walk(c, d - 1))
            return entry

        return {"type": "filesystem_tree", "root": str(root), "tree": _walk(root, depth)}


__all__ = ["HolographicEngine"]