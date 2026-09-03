"""PlannerAgent — breaks high-level missions into subtasks with dependency graphs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Subtask:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    title: str = ""
    description: str = ""
    estimated_minutes: int = 5
    priority: int = 5
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Subtask(id={self.id!r}, title={self.title!r}, priority={self.priority})"


class PlannerAgent:
    """Breaks missions into actionable subtasks, estimates effort, and prioritizes."""

    def break_down(self, goal: str, context: dict[str, Any] | None = None) -> list[Subtask]:
        """Decompose a high-level goal into a list of subtasks with dependency chains.

        Args:
            goal: Natural-language description of the mission.
            context: Optional metadata (available tools, constraints, etc.).

        Returns:
            List of Subtask objects forming a dependency graph.
        """
        context = context or {}
        subtasks: list[Subtask] = []

        normalized = goal.strip()
        if not normalized:
            return subtasks

        phases = self._infer_phases(normalized)
        for idx, phase in enumerate(phases):
            deps = [s.id for s in subtasks if s.phase_order < idx] if idx > 0 else []
            task = Subtask(
                title=phase["title"],
                description=phase.get("description", ""),
                estimated_minutes=phase.get("estimated_minutes", 5),
                priority=phase.get("priority", 5),
                dependencies=deps,
                tags=phase.get("tags", []),
                metadata={"phase_order": idx, "goal": normalized, **phase.get("metadata", {})},
            )
            subtasks.append(task)

        return subtasks

    def estimate_complexity(self, subtask: Subtask) -> dict[str, Any]:
        """Return time/resource estimates for a subtask.

        Args:
            subtask: The subtask to evaluate.

        Returns:
            Dict with estimated_minutes, confidence (0-1), and required_resources.
        """
        base = subtask.estimated_minutes
        confidence = 0.7

        if subtask.tags:
            if "research" in subtask.tags or "web" in subtask.tags:
                base += 15
                confidence -= 0.1
            if "testing" in subtask.tags or "debug" in subtask.tags:
                base += 20
                confidence -= 0.15
            if "build" in subtask.tags or "compile" in subtask.tags:
                base += 10
                confidence -= 0.05

        if subtask.dependencies:
            base += len(subtask.dependencies) * 5

        base = max(1, min(base, 480))
        confidence = max(0.2, min(confidence, 0.95))

        return {
            "estimated_minutes": base,
            "confidence": confidence,
            "required_resources": self._infer_resources(subtask),
        }

    def prioritize(self, subtasks: list[Subtask]) -> list[Subtask]:
        """Sort subtasks by importance while respecting dependency order.

        Args:
            subtasks: Unsorted list of Subtask objects.

        Returns:
            Sorted list (highest priority first, dependencies first).
        """
        if not subtasks:
            return []

        by_id = {s.id: s for s in subtasks}
        visited: set[str] = set()
        ordered: list[Subtask] = []

        def visit(task_id: str) -> None:
            if task_id in visited:
                return
            task = by_id.get(task_id)
            if not task:
                return
            for dep in task.dependencies:
                visit(dep)
            visited.add(task_id)
            ordered.append(task)

        sorted_by_priority = sorted(subtasks, key=lambda s: (-s.priority, s.title))
        for task in sorted_by_priority:
            visit(task.id)

        return ordered

    # -- helpers --

    def _infer_phases(self, goal: str) -> list[dict[str, Any]]:
        """Heuristic phase decomposition. Falls back to sensible defaults."""
        lower = goal.lower()
        phases: list[dict[str, Any]] = []

        if any(k in lower for k in ("research", "analyze", "investigate", "study")):
            phases.append({
                "title": "Research & Gather Information",
                "description": f"Collect data relevant to: {goal}",
                "estimated_minutes": 20,
                "priority": 8,
                "tags": ["research", "web"],
            })
        elif any(k in lower for k in ("build", "create", "implement", "develop", "write")):
            phases.append({
                "title": "Design Solution",
                "description": f"Architect a solution for: {goal}",
                "estimated_minutes": 15,
                "priority": 9,
                "tags": ["design"],
            })
            phases.append({
                "title": "Implement",
                "description": f"Build the solution for: {goal}",
                "estimated_minutes": 45,
                "priority": 7,
                "tags": ["build"],
            })
        else:
            phases.append({
                "title": "Analyze Goal",
                "description": f"Understand requirements for: {goal}",
                "estimated_minutes": 5,
                "priority": 9,
                "tags": ["analysis"],
            })

        if any(k in lower for k in ("test", "validate", "verify", "check")):
            phases.append({
                "title": "Test & Validate",
                "description": f"Run tests and verify outcomes for: {goal}",
                "estimated_minutes": 20,
                "priority": 6,
                "tags": ["testing"],
            })

        if any(k in lower for k in ("deploy", "ship", "release", "deliver")):
            phases.append({
                "title": "Deploy & Deliver",
                "description": f"Package and deliver results for: {goal}",
                "estimated_minutes": 15,
                "priority": 5,
                "tags": ["deploy"],
            })

        if not phases:
            phases = [{
                "title": goal,
                "description": goal,
                "estimated_minutes": 10,
                "priority": 5,
                "tags": ["general"],
            }]

        for i, p in enumerate(phases):
            p["phase_order"] = i
        return phases

    def _infer_resources(self, subtask: Subtask) -> list[str]:
        """Guess required resources from tags and metadata."""
        resources = ["cpu", "memory"]
        for tag in subtask.tags:
            if tag in ("web", "research"):
                resources.append("network")
            if tag in ("build", "compile"):
                resources.append("disk")
            if tag in ("testing", "debug"):
                resources.append("cpu")
        return list(set(resources))
