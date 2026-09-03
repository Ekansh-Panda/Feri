"""
Vector Memory — ChromaDB-backed semantic store.

Uses a persistent local ChromaDB instance with a sentence-transformer
embedding function (or a hash-fallback if the heavy deps aren't installed).
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


def _hash_embed(text: str, dim: int = 256) -> List[float]:
    """Deterministic fallback embedder. Avoids numpy/torch at import time."""
    vec = [0.0] * dim
    for tok in text.lower().split():
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        for i in range(0, len(h), 2):
            idx = h[i] % dim
            sign = 1.0 if (h[i + 1] & 1) else -1.0
            vec[idx] += sign * ((h[i + 1] / 255.0))
    norm = sum(v * v for v in vec) ** 0.5 or 1.0
    return [v / norm for v in vec]


class VectorMemory:
    """Semantic memory via ChromaDB; degrades gracefully if Chroma missing."""

    def __init__(self, db_path: str = "memory/chroma_db", collection: str = "jarvis") -> None:
        self.db_path = Path(db_path)
        if not self.db_path.is_absolute():
            self.db_path = REPO_ROOT / db_path
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection
        self._lock = threading.RLock()
        self._backend = "hash"
        self._client = None  # type: ignore[var-annotated]
        self._collection = None  # type: ignore[var-annotated]
        self._store: Dict[str, Dict[str, Any]] = {}
        self._embed_dim = 256

        try:
            import chromadb  # type: ignore[import-untyped]
            from chromadb.config import Settings  # type: ignore[import-untyped]

            self._client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self._backend = "chroma"
        except Exception:
            # Fallback: simple in-process dict store
            self._backend = "hash"
            index_file = self.db_path / f"{collection}.json"
            if index_file.exists():
                try:
                    import json

                    self._store = json.loads(index_file.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    self._store = {}

    def _persist_fallback(self) -> None:
        if self._backend != "hash":
            return
        import json

        path = self.db_path / f"{self.collection_name}.json"
        path.write_text(json.dumps(self._store, indent=2), encoding="utf-8")

    def _embed(self, text: str) -> List[float]:
        if self._backend == "chroma" and self._collection is not None:
            try:
                ef = getattr(self._collection, "_embedding_function", None)
                if ef is not None:
                    return list(ef([text])[0])
            except Exception:
                pass
        return _hash_embed(text, dim=self._embed_dim)

    def add_document(self, text: str, metadata: Optional[Dict[str, Any]] = None,
                     doc_id: Optional[str] = None) -> str:
        """Index a document; returns the assigned id."""
        meta = metadata or {}
        meta.setdefault("ts", __import__("time").time())
        did = doc_id or uuid.uuid4().hex
        with self._lock:
            if self._backend == "chroma" and self._collection is not None:
                self._collection.add(documents=[text], metadatas=[meta], ids=[did])
            else:
                self._store[did] = {"text": text, "metadata": meta, "embedding": self._embed(text)}
                self._persist_fallback()
        return did

    def query(self, text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Semantic search; returns list of {id, text, metadata, score}."""
        with self._lock:
            if self._backend == "chroma" and self._collection is not None:
                try:
                    res = self._collection.query(query_texts=[text], n_results=n_results)
                    docs = res.get("documents", [[]])[0]
                    metas = res.get("metadatas", [[]])[0]
                    ids = res.get("ids", [[]])[0]
                    dists = res.get("distances", [[]])[0]
                    out = []
                    for i, doc in enumerate(docs):
                        out.append({
                            "id": ids[i],
                            "text": doc,
                            "metadata": metas[i] if i < len(metas) else {},
                            "score": 1.0 - (dists[i] if i < len(dists) else 1.0),
                        })
                    return out
                except Exception:
                    pass
            # Fallback: cosine over hash embeddings
            qv = self._embed(text)
            scored = []
            for did, rec in self._store.items():
                ev = rec.get("embedding") or _hash_embed(rec.get("text", ""), self._embed_dim)
                if len(ev) != len(qv):
                    ev = _hash_embed(rec.get("text", ""), self._embed_dim)
                dot = sum(a * b for a, b in zip(qv, ev))
                scored.append((dot, did, rec))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [
                {"id": did, "text": rec["text"], "metadata": rec["metadata"], "score": score}
                for score, did, rec in scored[:n_results]
            ]

    def delete_document(self, doc_id: str) -> bool:
        """Remove a document by id; returns True if found."""
        with self._lock:
            if self._backend == "chroma" and self._collection is not None:
                try:
                    self._collection.delete(ids=[doc_id])
                    return True
                except Exception:
                    return False
            if doc_id in self._store:
                self._store.pop(doc_id)
                self._persist_fallback()
                return True
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """Return count and approximate dimensions."""
        with self._lock:
            if self._backend == "chroma" and self._collection is not None:
                try:
                    count = self._collection.count()
                    dim = self._embed_dim
                    try:
                        peek = self._collection.peek(1)
                        if peek.get("embeddings") and len(peek["embeddings"][0]):
                            dim = len(peek["embeddings"][0])
                    except Exception:
                        pass
                    return {"backend": "chroma", "count": count, "dimensions": dim}
                except Exception:
                    pass
            return {
                "backend": "hash",
                "count": len(self._store),
                "dimensions": self._embed_dim,
            }


__all__ = ["VectorMemory"]