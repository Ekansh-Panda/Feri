"""CodeAgent — generate, review, test, debug, refactor, and patch code."""

from __future__ import annotations

import ast
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.code_agent")


class CodeAgent:
    """Write, test, debug, and patch source code."""

    def generate(self, prompt: str, language: str, filename: str) -> dict[str, Any]:
        """Generate code from a prompt using the local LLM.

        Args:
            prompt: Description of what the code should do.
            language: Programming language.
            filename: Target filename.

        Returns:
            Dict with code, language, filename, and status.
        """
        try:
            from core.llm_client import call_llm_text
            system = f"You are an expert {language} programmer. Output ONLY code, no markdown fences, no explanations."
            full_prompt = f"Write {language} code for: {prompt}\n\nSave as: {filename}\n\nReturn ONLY the source code."
            code = call_llm_text(full_prompt, system=system, timeout=120)
            code = self._strip_markdown(code)
            return {"code": code, "language": language, "filename": filename, "status": "generated"}
        except Exception as exc:
            logger.error("generate() failed: %s", exc)
            return {"code": "", "language": language, "filename": filename, "status": "error", "error": str(exc)}

    def review(self, code: str) -> dict[str, Any]:
        """Review code for quality, bugs, and style.

        Args:
            code: Source code string.

        Returns:
            Dict with issues and suggestions.
        """
        issues: list[dict[str, str]] = []
        suggestions: list[str] = []

        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append({"line": i, "severity": "warning", "message": "Line too long (>120 chars)"})
            if line.strip().endswith("=="):
                issues.append({"line": i, "severity": "warning", "message": "Assignment in condition? (use '=' not '==')"})

        try:
            import ast as _ast
            try:
                _ast.parse(code)
            except _ast.SyntaxError as exc:
                issues.append({"line": exc.lineno or 0, "severity": "error", "message": f"SyntaxError: {exc.msg}"})
        except Exception:
            pass

        try:
            from core.llm_client import call_llm_text
            prompt = (
                "Review the following code for bugs, security issues, and style problems.\n"
                "Return a JSON-like list of findings with: line, severity (error|warning|info), message.\n"
                f"```\n{code}\n```"
            )
            response = call_llm_text(prompt, system="You are a code reviewer.", timeout=60)
            suggestions.append(response[:4000])
        except Exception as exc:
            logger.warning("LLM review failed: %s", exc)
            suggestions.append("Static analysis complete. LLM review unavailable.")

        return {"issues": issues, "suggestions": suggestions, "status": "reviewed"}

    def test(self, code: str, language: str, test_cases: list[dict[str, Any]]) -> dict[str, Any]:
        """Run tests against code with given test cases.

        Args:
            code: Source code.
            language: Programming language.
            test_cases: List of test case dicts (input, expected).

        Returns:
            Dict with passed/failed counts and results.
        """
        results: list[dict[str, Any]] = []
        passed = 0
        failed = 0

        if language.lower() == "python":
            try:
                ns: dict[str, Any] = {}
                exec(code, ns)  # noqa: S102
                func_name = self._detect_function_name(code)
                fn = ns.get(func_name)
                if not callable(fn):
                    return {"passed": 0, "failed": len(test_cases), "results": [], "status": "error", "error": "No callable found."}
                for tc in test_cases:
                    inp = tc.get("input", [])
                    expected = tc.get("expected")
                    try:
                        if isinstance(inp, list):
                            got = fn(*inp)
                        elif isinstance(inp, dict):
                            got = fn(**inp)
                        else:
                            got = fn(inp)
                        ok = got == expected
                        results.append({"input": inp, "expected": expected, "got": got, "passed": ok})
                        if ok:
                            passed += 1
                        else:
                            failed += 1
                    except Exception as exc:
                        results.append({"input": inp, "expected": expected, "got": None, "passed": False, "error": str(exc)})
                        failed += 1
            except SyntaxError as exc:
                return {"passed": 0, "failed": len(test_cases), "results": [], "status": "error", "error": f"SyntaxError: {exc}"}
            except Exception as exc:
                return {"passed": 0, "failed": len(test_cases), "results": [], "status": "error", "error": str(exc)}
        else:
            return {
                "passed": 0,
                "failed": len(test_cases),
                "results": [],
                "status": "unsupported",
                "error": f"Testing for {language} not implemented.",
            }

        return {"passed": passed, "failed": failed, "results": results, "status": "completed"}

    def debug(self, code: str, error_message: str) -> dict[str, Any]:
        """Diagnose an error and suggest a fix.

        Args:
            code: Faulty source code.
            error_message: The error message encountered.

        Returns:
            Dict with diagnosis and fixed code.
        """
        diagnosis = []
        if "IndentationError" in error_message or "TabError" in error_message:
            diagnosis.append("Indentation mismatch. Check tabs vs spaces.")
        if "NameError" in error_message:
            diagnosis.append("Undefined variable or function. Check imports and spelling.")
        if "TypeError" in error_message:
            diagnosis.append("Type mismatch. Check argument types.")
        if "SyntaxError" in error_message:
            diagnosis.append("Syntax error. Check for missing colons, parentheses, or quotes.")

        fixed_code = code
        try:
            from core.llm_client import call_llm_text
            prompt = (
                "The following code produces this error:\n"
                f"{error_message}\n\n"
                "Fix the code and return ONLY the corrected source code. No markdown.\n\n"
                f"```\n{code}\n```"
            )
            fixed_code = call_llm_text(prompt, system="You are a debugging assistant.", timeout=120)
            fixed_code = self._strip_markdown(fixed_code)
        except Exception as exc:
            logger.error("LLM debug failed: %s", exc)
            diagnosis.append(f"LLM debug unavailable: {exc}")

        return {"diagnosis": diagnosis, "fixed_code": fixed_code, "status": "debugged"}

    def refactor(self, code: str, style: str = "pep8") -> dict[str, Any]:
        """Improve code quality while preserving behavior.

        Args:
            code: Source code.
            style: Target style guideline.

        Returns:
            Dict with refactored code and changes.
        """
        refactored = code
        changes: list[str] = []

        if style.lower() in ("pep8", "pep257", "clean"):
            try:
                import autopep8
                refactored = autopep8.fix_code(code)
                changes.append("Applied autopep8 formatting")
            except ImportError:
                changes.append("autopep8 not installed; skipping formatting")
            except Exception as exc:
                changes.append(f"autopep8 failed: {exc}")

        try:
            from core.llm_client import call_llm_text
            prompt = (
                f"Refactor the following {style} code for readability, maintainability, and performance. "
                "Preserve all behavior. Return ONLY the refactored source code. No markdown.\n\n"
                f"```\n{code}\n```"
            )
            llm_refactored = call_llm_text(prompt, system=f"You are a {style} refactoring expert.", timeout=120)
            llm_refactored = self._strip_markdown(llm_refactored)
            if llm_refactored and llm_refactored != code:
                refactored = llm_refactored
                changes.append("LLM refactoring applied")
        except Exception as exc:
            logger.error("LLM refactor failed: %s", exc)

        return {"code": refactored, "changes": changes, "status": "refactored"}

    def git_diff(self, repo_path: str | Path) -> dict[str, Any]:
        """Show current git changes in a repository.

        Args:
            repo_path: Path to the git repository.

        Returns:
            Dict with diff string and changed files.
        """
        repo = Path(repo_path).expanduser().resolve()
        if not (repo / ".git").exists():
            return {"status": "error", "error": f"Not a git repository: {repo}"}

        try:
            diff = subprocess.run(
                ["git", "diff", "--no-color"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout

            files = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout.splitlines()

            return {"diff": diff, "changed_files": [f for f in files if f], "status": "ok"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def git_patch(self, repo_path: str | Path, description: str) -> dict[str, Any]:
        """Create and apply a patch from current changes.

        Args:
            repo_path: Path to the git repository.
            description: Commit/patch description.

        Returns:
            Dict with patch content and apply status.
        """
        repo = Path(repo_path).expanduser().resolve()
        if not (repo / ".git").exists():
            return {"status": "error", "error": f"Not a git repository: {repo}"}

        try:
            patch = subprocess.run(
                ["git", "diff", "--no-color"],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout

            patch_path = repo / f".jarvis_patch_{int(time.time())}.patch"
            patch_path.write_text(patch, encoding="utf-8")

            apply = subprocess.run(
                ["git", "apply", "--whitespace=fix", str(patch_path)],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if apply.returncode == 0:
                return {"patch_path": str(patch_path), "status": "applied", "description": description}
            return {"patch_path": str(patch_path), "status": "apply_failed", "error": apply.stderr}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    # -- helpers --

    def _strip_markdown(self, text: str) -> str:
        text = re.sub(r"```[\w]*\n", "", text)
        text = re.sub(r"```", "", text)
        return text.strip()

    def _detect_function_name(self, code: str) -> str:
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    return node.name
        except Exception:
            pass
        return "solve"
