"""
core/safety.py — Permission levels, approval gates, and access control.

Defines the SafetyEngine: a central authority that mediates every
privileged action.  Permission levels escalate from PUBLIC to ROOT;
actions declare the minimum level they require, and the engine checks
the current context (user session, confirmation tokens, whitelists)
before granting or denying access.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Callable, Optional

from core.confirm import ConfirmGate


class PermissionLevel(IntEnum):
    """Escalating privilege tiers for action authorization."""

    PUBLIC = 0    # Read-only, always safe (list files, query status, read memory)
    USER   = 1    # User-level actions (move files, adjust volume, open apps)
    ADMIN  = 2    # System administration (install packages, restart services)
    ROOT   = 3    # Full system control (shutdown, network lockdown, kernel mods)


@dataclass
class PermissionRule:
    """A single allow/deny rule for a pattern of actions."""

    pattern: str                                   # regex matched against action names
    level: PermissionLevel
    action: str = "allow"                          # "allow" or "deny"
    _compiled: re.Pattern = field(init=False)

    def __post_init__(self) -> None:
        self._compiled = re.compile(self.pattern)

    def matches(self, action: str) -> bool:
        return bool(self._compiled.search(action))


@dataclass
class _ApprovalToken:
    action: str
    description: str
    granted_at: float
    expires_at: float
    approved: bool = False
    response: str = ""


class SafetyEngine:
    """Central permission and approval authority.

    Integrates with the ConfirmGate for HUD-mediated confirmation of
    destructive actions.  Whitelist/blacklist rules provide a second
    layer of control independent of interactive approval.

    Attributes:
        config_path: Path to the JSON file storing rules and approvals.
        current_user_level: The effective permission level of the current
            session, derived from session inspection at runtime.
    """

    DEFAULT_CONFIG: dict = {
        "whitelist": [],
        "blacklist": [],
        "rules": [],
        "approvals": {},
    }

    def __init__(
        self,
        config_path: Optional[str | Path] = None,
        confirm_gate: Optional[ConfirmGate] = None,
    ) -> None:
        """Initialise the safety engine.

        Args:
            config_path: Path to the JSON config storing rules and approvals.
                Defaults to <BASE_DIR>/config/safety.json.
            confirm_gate: Optional ConfirmGate instance for interactive approval.
        """
        from core import BASE_DIR
        self.config_path: Path = Path(config_path) if config_path else BASE_DIR / "config" / "safety.json"
        self._confirm: ConfirmGate = confirm_gate or ConfirmGate()
        self._lock = threading.RLock()
        self.current_user_level: PermissionLevel = self._detect_user_level()
        self._rules: list[PermissionRule] = []
        self._whitelist: set[str] = set()
        self._blacklist: set[str] = set()
        self._approvals: dict[str, _ApprovalToken] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load rules, whitelist, and blacklist from the JSON config file."""
        with self._lock:
            if not self.config_path.exists():
                self._save_config()
                return
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = dict(self.DEFAULT_CONFIG)
            self._whitelist = set(data.get("whitelist", []))
            self._blacklist = set(data.get("blacklist", []))
            for rule_dict in data.get("rules", []):
                try:
                    rule = PermissionRule(
                        pattern=rule_dict["pattern"],
                        level=PermissionLevel[rule_dict["level"]],
                        action=rule_dict.get("action", "allow"),
                    )
                    self._rules.append(rule)
                except (KeyError, ValueError):
                    continue
            for token_data in data.get("approvals", {}).values():
                try:
                    token = _ApprovalToken(**token_data)
                    if token.expires_at > time.time():
                        self._approvals[token.action] = token
                except (TypeError, KeyError):
                    continue
            self._save_config()

    def _save_config(self) -> None:
        """Persist current rules and approvals to the config file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "whitelist": sorted(self._whitelist),
            "blacklist": sorted(self._blacklist),
            "rules": [
                {"pattern": r.pattern, "level": r.level.name, "action": r.action}
                for r in self._rules
            ],
            "approvals": {
                token.action: {
                    "action": token.action,
                    "description": token.description,
                    "granted_at": token.granted_at,
                    "expires_at": token.expires_at,
                    "approved": token.approved,
                    "response": token.response,
                }
                for token in self._approvals.values()
            },
        }
        try:
            self.config_path.write_text(
                json.dumps(data, indent=2, default=str), encoding="utf-8"
            )
        except OSError as e:
            print(f"[Safety] Failed to save config: {e}")

    def _detect_user_level(self) -> PermissionLevel:
        """Determine the current user's permission level.

        Uses os.geteuid() on Unix (0 = ROOT, otherwise USER) and
        checks admin group membership on systems that provide it.
        """
        if os.geteuid() == 0:
            return PermissionLevel.ROOT
        try:
            import grp
            groups = {g.gr_name for g in grp.getgrall() if os.geteuid() in g.gr_mem}
            if "wheel" in groups or "sudo" in groups or "admin" in groups:
                return PermissionLevel.ADMIN
        except (KeyError, ImportError, OSError):
            pass
        return PermissionLevel.USER

    def check_permission(self, action: str, level: PermissionLevel) -> bool:
        """Check whether *action* is permitted at the given *level*.

        Evaluation order:
            1. Blacklist — immediate deny.
            2. Whitelist — immediate allow.
            3. Rules — first match wins.
            4. User level — must meet the required level.

        Args:
            action: The action name being requested.
            level: The minimum PermissionLevel required.

        Returns:
            True if the action is permitted, False otherwise.
        """
        action_lower = action.lower()
        with self._lock:
            if action_lower in self._blacklist:
                return False
            if action_lower in self._whitelist:
                return True
            for rule in self._rules:
                if rule.matches(action_lower):
                    if rule.action == "deny":
                        return False
                    if rule.level >= level:
                        return True
                    return False
            return self.current_user_level >= level

    def request_approval(self, action: str, description: str = "", timeout: float = 120.0) -> str:
        """Request interactive approval for a destructive action.

        Generates a confirmation token, displays a HUD prompt via the
        ConfirmGate, and stores the pending approval.  The caller can
        poll :meth:`check_approval` or the UI calls :meth:`approve`.

        Args:
            action: Identifier for the action (used as the token key).
            description: Human-readable detail for the HUD banner.
            timeout: How long the token stays valid (seconds).

        Returns:
            A token string.  If the interface is unavailable, the token
            is returned but will always evaluate as denied.
        """
        token = f"appr_{int(time.time() * 1000)}_{os.urandom(4).hex()}"
        with self._lock:
            self._approvals[action] = _ApprovalToken(
                action=action,
                description=description,
                granted_at=time.time(),
                expires_at=time.time() + timeout,
            )
        sentence = self._confirm.request(
            action,
            title=f"Requesting Approval: {action}",
            detail=description or f"Action '{action}' requires your confirmation.",
            run=lambda: self.approve(action, description),
        )
        return token

    def approve(self, action: str, response: str = "approved") -> bool:
        """Approve a previously requested action.

        Args:
            action: The action identifier from :meth:`request_approval`.
            response: Optional response text to store.

        Returns:
            True if approval was recorded, False if the action was not
            pending or already expired.
        """
        with self._lock:
            token = self._approvals.get(action)
            if token is None:
                return False
            if token.expires_at < time.time():
                del self._approvals[action]
                return False
            token.approved = True
            token.response = response
            self._confirm.approve(token)
            self._save_config()
            return True

    def deny(self, action: str, reason: str = "denied") -> bool:
        """Explicitly deny a pending action.

        Args:
            action: The action identifier.
            reason: Reason for denial.

        Returns:
            True if denial was recorded, False otherwise.
        """
        with self._lock:
            token = self._approvals.get(action)
            if token is None:
                return False
            token.approved = False
            token.response = reason
            self._confirm.deny(token)
            self._save_config()
            return True

    def check_approval(self, action: str) -> bool:
        """Check if an action has been explicitly approved.

        Args:
            action: The action identifier.

        Returns:
            True if the action was approved before its token expired.
        """
        with self._lock:
            if action not in self._approvals:
                return False
            return self._approvals[action].approved

    def add_whitelist(self, action: str) -> None:
        """Add an action to the permanent whitelist."""
        with self._lock:
            self._whitelist.add(action.lower())
        self._save_config()

    def add_blacklist(self, action: str) -> None:
        """Add an action to the permanent blacklist."""
        with self._lock:
            self._blacklist.add(action.lower())
        self._save_config()

    def add_rule(self, pattern: str, level: PermissionLevel, action: str = "allow") -> None:
        """Add a regex-based permission rule.

        Args:
            pattern: Regex pattern matched against action names.
            level: Minimum level required when this rule applies.
            action: "allow" or "deny".
        """
        rule = PermissionRule(pattern=pattern, level=level, action=action)
        with self._lock:
            self._rules.append(rule)
        self._save_config()

    @staticmethod
    def level_name(level: PermissionLevel) -> str:
        """Return a human-readable name for a permission level."""
        names = {
            PermissionLevel.PUBLIC: "public",
            PermissionLevel.USER: "user",
            PermissionLevel.ADMIN: "admin",
            PermissionLevel.ROOT: "root",
        }
        return names.get(level, str(level))
