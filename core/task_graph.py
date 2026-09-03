from collections import deque
from typing import Dict, List, Callable, Any
import time


class Task:
    def __init__(self, name: str, func: Callable, dependencies: List[str] = None, max_retries: int = 3):
        self.name = name
        self.func = func
        self.dependencies = dependencies or []
        self.max_retries = max_retries
        self.retries = 0
        self.result = None
        self.error = None
        self.completed = False

    def execute(self, context: Dict[str, Any]) -> bool:
        try:
            self.result = self.func(context)
            self.completed = True
            return True
        except Exception as e:
            self.error = str(e)
            self.retries += 1
            return False


class TaskGraph:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.execution_order: List[str] = []

    def add_task(self, name: str, func: Callable, dependencies: List[str] = None, max_retries: int = 3):
        self.tasks[name] = Task(name, func, dependencies, max_retries)

    def _topological_sort(self) -> List[str]:
        in_degree = {name: 0 for name in self.tasks}
        graph = {name: [] for name in self.tasks}

        for name, task in self.tasks.items():
            for dep in task.dependencies:
                if dep in graph:
                    graph[dep].append(name)
                    in_degree[name] += 1

        queue = deque([name for name, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.tasks):
            raise ValueError("Cycle detected in task graph")

        return order

    def execute(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        if context is None:
            context = {}
        self.execution_order = self._topological_sort()
        results = {}

        for name in self.execution_order:
            task = self.tasks[name]
            success = False
            for attempt in range(task.max_retries):
                if task.execute(context):
                    success = True
                    results[name] = task.result
                    context[name] = task.result
                    break
                time.sleep(2 ** attempt)
            if not success:
                raise RuntimeError(f"Task '{name}' failed after {task.max_retries} retries: {task.error}")

        return results
