"""VerifierAgent — output quality checks and artifact validation."""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.verifier")


class VerifierAgent:
    """Validates output quality against criteria and artifact integrity."""

    def verify_output(self, output: str, criteria: dict[str, Any]) -> dict[str, Any]:
        """Check output against quality criteria.

        Args:
            output: Text output to verify.
            criteria: Dict of checks (min_length, max_length, required_phrases, forbidden_phrases, regex).

        Returns:
            Dict with passed bool, score, and detailed feedback.
        """
        checks: list[dict[str, Any]] = []
        score = 0.0
        total = 0.0

        min_len = criteria.get("min_length")
        if min_len is not None:
            total += 1
            ok = len(output) >= int(min_len)
            checks.append({"check": "min_length", "passed": ok, "detail": f"len={len(output)} >= {min_len}"})
            if ok:
                score += 1

        max_len = criteria.get("max_length")
        if max_len is not None:
            total += 1
            ok = len(output) <= int(max_len)
            checks.append({"check": "max_length", "passed": ok, "detail": f"len={len(output)} <= {max_len}"})
            if ok:
                score += 1

        required = criteria.get("required_phrases", [])
        for phrase in required:
            total += 1
            ok = phrase.lower() in output.lower()
            checks.append({"check": "required_phrase", "passed": ok, "detail": f"'{phrase}' present"})
            if ok:
                score += 1

        forbidden = criteria.get("forbidden_phrases", [])
        for phrase in forbidden:
            total += 1
            ok = phrase.lower() not in output.lower()
            checks.append({"check": "forbidden_phrase", "passed": ok, "detail": f"'{phrase}' absent"})
            if ok:
                score += 1

        regex = criteria.get("regex")
        if regex:
            total += 1
            ok = bool(re.search(regex, output))
            checks.append({"check": "regex", "passed": ok, "detail": f"matches {regex}"})
            if ok:
                score += 1

        score_pct = (score / total * 100) if total else 100.0
        return {
            "passed": score_pct >= 80.0,
            "score": round(score_pct, 1),
            "checks": checks,
            "feedback": self._checks_to_feedback(checks),
        }

    def verify_code(self, code: str, language: str) -> dict[str, Any]:
        """Syntax check and lint a code snippet.

        Args:
            code: Source code.
            language: Programming language.

        Returns:
            Dict with syntax_ok, lint_issues, and score.
        """
        issues: list[dict[str, str]] = []
        lang = (language or "").lower().strip()

        if lang == "python":
            try:
                ast.parse(code)
            except SyntaxError as exc:
                issues.append({"severity": "error", "message": f"SyntaxError at line {exc.lineno}: {exc.msg}"})

            try:
                result = subprocess.run(
                    ["python", "-m", "py_compile", "-"],
                    input=code,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    for line in result.stderr.splitlines():
                        if line.strip():
                            issues.append({"severity": "error", "message": line.strip()})
            except FileNotFoundError:
                logger.warning("python not found for py_compile")
            except Exception as exc:
                logger.warning("py_compile failed: %s", exc)

            try:
                result = subprocess.run(
                    ["flake8", "--stdin-display-name=stdin", "-"],
                    input=code,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                for line in result.stdout.splitlines():
                    if line.strip():
                        issues.append({"severity": "warning", "message": line.strip()})
            except FileNotFoundError:
                pass
            except Exception as exc:
                logger.warning("flake8 failed: %s", exc)

        elif lang in ("javascript", "js"):
            try:
                result = subprocess.run(
                    ["node", "--check", "-"],
                    input=code,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    for line in result.stderr.splitlines():
                        if line.strip():
                            issues.append({"severity": "error", "message": line.strip()})
            except FileNotFoundError:
                pass
            except Exception as exc:
                logger.warning("node --check failed: %s", exc)

        score = 100.0 if not issues else max(0.0, 100.0 - len([i for i in issues if i["severity"] == "error"]) * 20 - len([i for i in issues if i["severity"] == "warning"]) * 5)
        syntax_ok = not any(i["severity"] == "error" for i in issues)

        return {
            "syntax_ok": syntax_ok,
            "lint_issues": issues,
            "score": round(score, 1),
            "status": "pass" if syntax_ok else "fail",
        }

    def verify_document(self, doc_path: str | Path) -> dict[str, Any]:
        """Check a document for formatting and completeness.

        Args:
            doc_path: Path to document (Markdown, LaTeX, etc.).

        Returns:
            Dict with checks and score.
        """
        p = Path(doc_path).expanduser().resolve()
        if not p.exists():
            return {"status": "error", "error": f"Document not found: {p}"}

        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

        checks: list[dict[str, Any]] = []
        total = 0.0
        score = 0.0

        if text.strip():
            total += 1
            checks.append({"check": "non_empty", "passed": True})
            score += 1
        else:
            checks.append({"check": "non_empty", "passed": False})

        if len(text) > 100:
            total += 1
            checks.append({"check": "min_length", "passed": True})
            score += 1
        else:
            checks.append({"check": "min_length", "passed": False, "detail": f"len={len(text)}"})

        if p.suffix.lower() == ".md":
            if text.startswith("#"):
                total += 1
                checks.append({"check": "has_title", "passed": True})
                score += 1
            else:
                checks.append({"check": "has_title", "passed": False})

        score_pct = (score / total * 100) if total else 0.0
        return {
            "path": str(p),
            "checks": checks,
            "score": round(score_pct, 1),
            "status": "pass" if score_pct >= 70 else "fail",
        }

    def verify_mission(self, mission_id: str) -> dict[str, Any]:
        """Validate artifacts for a mission.

        Args:
            mission_id: Mission identifier.

        Returns:
            Dict with artifact statuses.
        """
        base = Path(__file__).resolve().parent.parent
        mission_dir = base / "missions" / mission_id
        artifacts: list[dict[str, Any]] = []

        if not mission_dir.exists():
            return {"mission_id": mission_id, "status": "error", "error": f"Mission dir not found: {mission_dir}", "artifacts": []}

        for entry in sorted(mission_dir.rglob("*")):
            if entry.is_file():
                try:
                    st = entry.stat()
                    artifacts.append({
                        "path": str(entry.relative_to(mission_dir)),
                        "size_bytes": st.st_size,
                        "exists": True,
                    })
                except OSError:
                    artifacts.append({"path": str(entry.relative_to(mission_dir)), "exists": False})

        status = "pass" if all(a.get("exists") for a in artifacts) else "fail" if artifacts else "empty"
        return {"mission_id": mission_id, "status": status, "artifact_count": len(artifacts), "artifacts": artifacts}

    # -- helpers --

    def _checks_to_feedback(self, checks: list[dict[str, Any]]) -> str:
        failed = [c for c in checks if not c["passed"]]
        if not failed:
            return "All checks passed."
        return f"{len(failed)} check(s) failed: " + "; ".join(c.get("detail", c["check"]) for c in failed)
