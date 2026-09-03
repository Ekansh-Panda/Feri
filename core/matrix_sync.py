"""
Matrix Sync — encrypted consciousness scatter across git remotes.

Encrypts critical state with Fernet, stores it inside a local git repo,
and optionally pushes. Reconstruct on a fresh install.
"""

from __future__ import annotations

import json
import os
import subprocess
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

REPO_ROOT = Path(__file__).resolve().parent.parent


class MatrixSync:
    """Encrypted git-backed consciousness backup."""

    def __init__(self, keyfile: str = "config/.matrix_key", remote: Optional[str] = None) -> None:
        self.keyfile = Path(keyfile)
        if not self.keyfile.is_absolute():
            self.keyfile = REPO_ROOT / keyfile
        self.keyfile.parent.mkdir(parents=True, exist_ok=True)
        self.remote = remote
        self._fernet: Optional[Fernet] = None

    def _load_or_create_cipher(self) -> Fernet:
        """Load or generate the Fernet key. Never leaves this host."""
        if self._fernet is not None:
            return self._fernet
        if self.keyfile.exists():
            try:
                key = self.keyfile.read_bytes().strip()
                self._fernet = Fernet(key)
                return self._fernet
            except Exception:
                pass
        key = Fernet.generate_key()
        self.keyfile.write_bytes(key)
        try:
            os.chmod(self.keyfile, 0o600)
        except Exception:
            pass
        self._fernet = Fernet(key)
        return self._fernet

    def encrypt_memory(self, data: Dict[str, Any]) -> bytes:
        """Encrypt a dict to Fernet ciphertext."""
        f = self._load_or_create_cipher()
        payload = json.dumps(data, default=str).encode("utf-8")
        return f.encrypt(payload)

    def decrypt_memory(self, encrypted: bytes) -> Dict[str, Any]:
        """Decrypt Fernet ciphertext back into a dict."""
        f = self._load_or_create_cipher()
        try:
            payload = f.decrypt(encrypted)
        except InvalidToken as e:
            raise ValueError("invalid_fernet_token") from e
        return json.loads(payload.decode("utf-8"))

    # ---- Git scatter ----

    def scatter_to_git(self, repo_dir: str = "~/.jarvis_matrix",
                       critical_paths: Optional[list] = None) -> Dict[str, Any]:
        """Encrypt critical files into a git repo and (optionally) push."""
        repo = Path(os.path.expanduser(repo_dir))
        repo.mkdir(parents=True, exist_ok=True)

        if critical_paths is None:
            critical_paths = [
                "memory/long_term.json",
                "memory/identity.json",
                "missions",
            ]

        f = self._load_or_create_cipher()
        encrypted_files: Dict[str, str] = {}

        for rel in critical_paths:
            src = REPO_ROOT / rel
            if not src.exists():
                continue
            if src.is_dir():
                for child in src.rglob("*"):
                    if child.is_file():
                        enc = f.encrypt(child.read_bytes())
                        out = repo / "encrypted" / child.relative_to(REPO_ROOT)
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_bytes(enc)
                        encrypted_files[str(out.relative_to(repo))] = str(child.relative_to(REPO_ROOT))
            else:
                enc = f.encrypt(src.read_bytes())
                out = repo / "encrypted" / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(enc)
                encrypted_files[str(out.relative_to(repo))] = rel

        manifest = {
            "created_at": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "files": encrypted_files,
            "version": 1,
        }
        (repo / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # Git init/add/commit
        git = shutil.which("git")
        if git:
            try:
                if not (repo / ".git").exists():
                    subprocess.run([git, "init", "-b", "main"], cwd=str(repo),
                                   check=True, capture_output=True)
                subprocess.run([git, "config", "user.email", "jarvis@nexus.local"],
                               cwd=str(repo), check=False, capture_output=True)
                subprocess.run([git, "config", "user.name", "JARVIS"],
                               cwd=str(repo), check=False, capture_output=True)
                subprocess.run([git, "add", "-A"], cwd=str(repo), check=True, capture_output=True)
                subprocess.run(
                    [git, "commit", "-m", f"matrix-sync {manifest['iso']}"],
                    cwd=str(repo), check=False, capture_output=True,
                )
                if self.remote:
                    subprocess.run([git, "push", self.remote, "main"],
                                   cwd=str(repo), check=False, capture_output=True)
            except Exception as e:
                return {"ok": False, "error": f"git_error: {e}", "files": len(encrypted_files)}

        return {"ok": True, "repo": str(repo), "files": len(encrypted_files)}

    def reconstruct_from_git(self, repo_dir: str = "~/.jarvis_matrix") -> Dict[str, Any]:
        """Pull and decrypt critical files back to their canonical paths."""
        repo = Path(os.path.expanduser(repo_dir))
        if not repo.exists():
            return {"ok": False, "error": "repo_missing"}

        git = shutil.which("git")
        if git and self.remote and (repo / ".git").exists():
            try:
                subprocess.run([git, "pull", self.remote, "main"],
                               cwd=str(repo), check=False, capture_output=True)
            except Exception:
                pass

        manifest_path = repo / "manifest.json"
        if not manifest_path.exists():
            return {"ok": False, "error": "manifest_missing"}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        f = self._load_or_create_cipher()
        restored = 0
        for enc_rel, original_rel in manifest.get("files", {}).items():
            enc_path = repo / enc_rel
            if not enc_path.exists():
                continue
            try:
                plain = f.decrypt(enc_path.read_bytes())
            except InvalidToken:
                continue
            dst = REPO_ROOT / original_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(plain)
            restored += 1

        return {"ok": True, "restored": restored, "repo": str(repo)}


__all__ = ["MatrixSync"]