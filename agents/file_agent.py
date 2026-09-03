"""FileAgent — atomic file operations with robust error handling."""

from __future__ import annotations

import difflib
import fnmatch
import hashlib
import logging
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.file_agent")


class FileAgent:
    """Atomic, safe file operations for JARVIS."""

    def read(self, path: str | Path) -> str:
        """Read text content from a file.

        Args:
            path: File path.

        Returns:
            File content as string.

        Raises:
            FileNotFoundError, PermissionError, OSError.
        """
        p = Path(path).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        if not p.is_file():
            raise ValueError(f"Not a file: {p}")
        return p.read_text(encoding="utf-8", errors="replace")

    def write(self, path: str | Path, content: str, atomic: bool = True) -> str:
        """Write content to a file, optionally using atomic temp-file-rename.

        Args:
            path: Destination path.
            content: Text content to write.
            atomic: If True, write to a temp file then rename.

        Returns:
            Status string.
        """
        p = Path(path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)

        if atomic:
            fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.tmp_")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp, str(p))
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        else:
            p.write_text(content, encoding="utf-8")

        return f"Wrote {len(content)} bytes to {p}"

    def append(self, path: str | Path, content: str) -> str:
        """Append content to a file.

        Args:
            path: File path.
            content: Text to append.

        Returns:
            Status string.
        """
        p = Path(path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended {len(content)} bytes to {p}"

    def delete(self, path: str | Path, secure: bool = False) -> str:
        """Delete a file or directory tree.

        Args:
            path: Target path.
            secure: If True, use shred (single-pass zero).

        Returns:
            Status string.
        """
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return f"Path does not exist: {p}"

        if p.is_dir():
            if secure:
                return self._secure_delete_tree(p)
            shutil.rmtree(str(p), ignore_errors=True)
            return f"Deleted directory: {p}"

        if secure:
            return self._secure_delete_file(p)

        p.unlink()
        return f"Deleted file: {p}"

    def copy(self, src: str | Path, dst: str | Path) -> str:
        """Copy a file or directory.

        Args:
            src: Source path.
            dst: Destination path.

        Returns:
            Status string.
        """
        src_p = Path(src).expanduser().resolve()
        dst_p = Path(dst).expanduser().resolve()
        if not src_p.exists():
            raise FileNotFoundError(f"Source not found: {src_p}")
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        if src_p.is_dir():
            if dst_p.exists():
                shutil.rmtree(str(dst_p))
            shutil.copytree(str(src_p), str(dst_p))
        else:
            shutil.copy2(str(src_p), str(dst_p))
        return f"Copied {src_p} -> {dst_p}"

    def move(self, src: str | Path, dst: str | Path) -> str:
        """Move/rename a file or directory.

        Args:
            src: Source path.
            dst: Destination path.

        Returns:
            Status string.
        """
        src_p = Path(src).expanduser().resolve()
        dst_p = Path(dst).expanduser().resolve()
        if not src_p.exists():
            raise FileNotFoundError(f"Source not found: {src_p}")
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_p), str(dst_p))
        return f"Moved {src_p} -> {dst_p}"

    def list(self, path: str | Path, pattern: str = "*") -> list[dict[str, Any]]:
        """List files matching a glob pattern.

        Args:
            path: Directory path.
            pattern: Glob pattern.

        Returns:
            List of file info dicts.
        """
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return []
        if not p.is_dir():
            return [self._file_info(p)]

        results = []
        for entry in sorted(p.glob(pattern)):
            if entry.exists():
                results.append(self._file_info(entry))
        return results

    def get_metadata(self, path: str | Path) -> dict[str, Any]:
        """Return size, mtime, permissions, and type for a path.

        Args:
            path: File or directory path.

        Returns:
            Metadata dict.
        """
        p = Path(path).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"Path not found: {p}")
        st = p.stat()
        return {
            "path": str(p),
            "size_bytes": st.st_size,
            "mtime": st.st_mtime,
            "ctime": st.st_ctime,
            "mode": oct(stat.S_IMODE(st.st_mode)),
            "is_dir": p.is_dir(),
            "is_file": p.is_file(),
            "is_symlink": p.is_symlink(),
            "owner": pwd.getpwuid(st.st_uid).pw_name if hasattr(pwd, "getpwuid") else str(st.st_uid),
        }

    def diff(self, file1: str | Path, file2: str | Path) -> str:
        """Compute unified diff between two files.

        Args:
            file1: First file path.
            file2: Second file path.

        Returns:
            Unified diff string.
        """
        lines1 = self.read(file1).splitlines(keepends=True)
        lines2 = self.read(file2).splitlines(keepends=True)
        diff = difflib.unified_diff(
            lines1,
            lines2,
            fromfile=str(file1),
            tofile=str(file2),
            lineterm="",
        )
        return "\n".join(line.rstrip("\n") for line in diff)

    # -- helpers --

    def _file_info(self, p: Path) -> dict[str, Any]:
        try:
            st = p.stat()
            return {
                "path": str(p),
                "name": p.name,
                "size_bytes": st.st_size,
                "mtime": st.st_mtime,
                "is_dir": p.is_dir(),
                "is_file": p.is_file(),
                "mode": oct(stat.S_IMODE(st.st_mode)),
            }
        except OSError as exc:
            return {"path": str(p), "error": str(exc)}

    def _secure_delete_file(self, p: Path) -> str:
        try:
            length = p.stat().st_size
            if length > 0:
                with p.open("r+b", buffering=0) as f:
                    f.write(b"\x00" * length)
            p.unlink()
            return f"Securely deleted: {p}"
        except Exception as exc:
            logger.error("Secure delete failed for %s: %s", p, exc)
            return f"Secure delete failed: {exc}"

    def _secure_delete_tree(self, p: Path) -> str:
        errors = []
        for root, dirs, files in os.walk(str(p), topdown=False):
            for name in files:
                fp = Path(root) / name
                try:
                    self._secure_delete_file(fp)
                except Exception as exc:
                    errors.append(str(exc))
            for name in dirs:
                dp = Path(root) / name
                try:
                    dp.rmdir()
                except OSError as exc:
                    errors.append(str(exc))
        try:
            p.rmdir()
        except OSError as exc:
            errors.append(str(exc))
        if errors:
            return f"Partial secure delete of {p}: {'; '.join(errors)}"
        return f"Securely deleted directory: {p}"
