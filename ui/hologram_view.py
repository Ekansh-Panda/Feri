
"""WebEngine 3D hologram panel.

Sets Qt.AA_ShareOpenGLContexts at import time so QWebEngineWidgets can
be imported AFTER QApplication is created. This is required by PyQt6 6.11+.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

# MUST be set before QApplication is created (it usually already is when
# this module is imported, so the import of QWebEngineWidgets would fail).
# We do it here at module-load time to be safe.
from PyQt6.QtCore import Qt as _Qt
try:
    from PyQt6.QtWidgets import QApplication as _QA
    if not _QA.instance():
        pass  # no QApplication yet — the attribute will be set elsewhere
    _QA.setAttribute(_Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
except Exception:
    pass

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QVBoxLayout, QWidget


class HologramView(QWebEngineView):
    """3D hologram panel powered by Three.js."""

    data_rendered = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        base = Path(__file__).resolve().parent
        html_path = base / "templates" / "hologram_base.html"
        self.setUrl(QUrl.fromLocalFile(str(html_path)))

    def inject_data(self, data: dict, render_type: str) -> None:
        """Push data to Three.js renderer."""
        payload = {"type": render_type, **data}
        js = f"window.renderHologram({json.dumps(payload)});"
        self.page().runJavaScript(js, lambda res: self.data_rendered.emit(str(res or "")))

    def render_code_topology(self, directory: str) -> None:
        """3D import graph for a directory."""
        nodes = [{"id": "root", "x": 0, "y": 0, "z": 0}]
        links = []
        try:
            files = list(Path(directory).rglob("*.py"))[:40]
            for i, f in enumerate(files):
                nodes.append({
                    "id": str(f.name),
                    "x": (i % 5) * 8 - 16,
                    "y": -(i // 5) * 6,
                    "z": random.uniform(-10, 10),
                })
                links.append({"source": "root", "target": str(f.name)})
        except Exception:
            pass
        self.inject_data({"nodes": nodes, "links": links}, "force_graph")

    def render_filesystem_tree(self, path: str) -> None:
        """3D directory tree."""

        def build(node_path: str, depth: int = 0) -> dict:
            try:
                p = Path(node_path)
                name = p.name or str(p)
                children = []
                if p.is_dir() and depth < 3:
                    for child in sorted(p.iterdir())[:20]:
                        children.append(build(str(child), depth + 1))
                return {"name": name, "children": children}
            except Exception:
                return {"name": "error", "children": []}

        self.inject_data({"root": build(path)}, "file_tree")
