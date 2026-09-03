import re
from typing import List

from core.mission_engine import MissionEngine


class SubTaskSpec:
    def __init__(self, name: str, dependencies: List[str] = None, priority: int = 5):
        self.name = name
        self.dependencies = dependencies or []
        self.priority = priority

    def __repr__(self):
        return f"SubTaskSpec({self.name}, deps={self.dependencies})"


class Plan:
    def __init__(self, goal: str, subtasks: List[SubTaskSpec], estimated_time: str):
        self.goal = goal
        self.subtasks = subtasks
        self.estimated_time = estimated_time

    def get_subtask_names(self) -> List[str]:
        return [s.name for s in self.subtasks]


class Planner:
    def __init__(self, mission_engine: MissionEngine = None):
        self.mission_engine = mission_engine

    def plan(self, prompt: str) -> Plan:
        subtasks = self._heuristic_parse(prompt)
        if not subtasks:
            subtasks = [SubTaskSpec(prompt)]
        return Plan(
            goal=prompt,
            subtasks=subtasks,
            estimated_time="unknown"
        )

    def generate_mission(self, prompt: str) -> Plan:
        return self.plan(prompt)

    def _heuristic_parse(self, prompt: str) -> List[SubTaskSpec]:
        subtasks = []
        lower = prompt.lower()
        if "research" in lower:
            subtasks.append(SubTaskSpec("Research topic and gather sources", priority=1))
            subtasks.append(SubTaskSpec("Analyze and synthesize findings", priority=2))
            subtasks.append(SubTaskSpec("Generate final report", priority=3))
        elif "code" in lower or "build" in lower or "create" in lower:
            subtasks.append(SubTaskSpec("Analyze requirements and design solution", priority=1))
            subtasks.append(SubTaskSpec("Implement core functionality", priority=2))
            subtasks.append(SubTaskSpec("Test and verify implementation", priority=3))
            subtasks.append(SubTaskSpec("Document code and usage", priority=4))
        elif "fix" in lower or "debug" in lower or "error" in lower:
            subtasks.append(SubTaskSpec("Identify and isolate the error", priority=1))
            subtasks.append(SubTaskSpec("Implement fix", priority=2))
            subtasks.append(SubTaskSpec("Test fix and verify resolution", priority=3))
        elif "document" in lower or "write" in lower:
            subtasks.append(SubTaskSpec("Gather source material", priority=1))
            subtasks.append(SubTaskSpec("Draft content", priority=2))
            subtasks.append(SubTaskSpec("Review and polish", priority=3))
        elif "deploy" in lower or "setup" in lower or "install" in lower:
            subtasks.append(SubTaskSpec("Check prerequisites", priority=1))
            subtasks.append(SubTaskSpec("Execute deployment steps", priority=2))
            subtasks.append(SubTaskSpec("Verify deployment", priority=3))
        elif "clean" in lower or "organize" in lower:
            subtasks.append(SubTaskSpec("Scan and categorize files", priority=1))
            subtasks.append(SubTaskSpec("Remove temporary/unnecessary files", priority=2))
            subtasks.append(SubTaskSpec("Organize and archive important files", priority=3))
        else:
            subtasks.append(SubTaskSpec("Analyze the request", priority=1))
            subtasks.append(SubTaskSpec("Execute primary task", priority=2))
            subtasks.append(SubTaskSpec("Verify and report results", priority=3))
        return subtasks
