"""HUD mission control panel plugin."""

import json
import os
from datetime import datetime
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class MissionDashboard:
    """HUD mission control panel."""

    def get_active_missions(self) -> list[dict[str, Any]]:
        """Retrieve active missions from mission engine."""
        mission_dir = "/tmp/missions"
        if not os.path.isdir(mission_dir):
            return []
        missions = []
        for fname in os.listdir(mission_dir):
            if fname.endswith(".json"):
                path = os.path.join(mission_dir, fname)
                try:
                    with open(path, "r") as f:
                        missions.append(json.load(f))
                except Exception:
                    continue
        return missions

    def get_mission_details(self, mission_id: str) -> dict[str, Any]:
        """Get subtasks and progress for a mission."""
        mission_path = f"/tmp/mission-{mission_id}.json"
        if not os.path.exists(mission_path):
            return {"status": "error", "message": f"Mission {mission_id} not found"}
        try:
            with open(mission_path, "r") as f:
                data = json.load(f)
            subtasks = data.get("subtasks", [])
            completed = sum(1 for s in subtasks if s.get("status") == "completed")
            progress = round((completed / len(subtasks)) * 100, 1) if subtasks else 0.0
            return {
                "status": "success",
                "mission_id": mission_id,
                "subtasks": subtasks,
                "progress_pct": progress,
                "completed": completed,
                "total": len(subtasks),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def render_html(self) -> str:
        """Render HTML for HUD panel."""
        missions = self.get_active_missions()
        rows = ""
        for m in missions:
            m_id = m.get("id", "unknown")
            subject = m.get("subject", m.get("task", "Unknown"))
            status = m.get("status", "unknown")
            rows += f"<tr><td>{m_id}</td><td>{subject}</td><td>{status}</td></tr>\n"

        agents = self.get_agent_status()
        agent_rows = ""
        for a in agents:
            agent_rows += f"<tr><td>{a.get('id')}</td><td>{a.get('status')}</td><td>{a.get('task')}</td></tr>\n"

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>JARVIS NEXUS - Mission Dashboard</title>
    <style>
        body {{ background: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; }}
        h1 {{ color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 10px; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 30px; }}
        th, td {{ border: 1px solid #30363d; padding: 8px; text-align: left; }}
        th {{ background: #161b22; color: #58a6ff; }}
        tr:nth-child(even) {{ background: #161b22; }}
        .status-optimal {{ color: #3fb950; }}
        .status-warning {{ color: #d29922; }}
        .status-critical {{ color: #f85149; }}
    </style>
</head>
<body>
    <h1>JARVIS NEXUS // MISSION CONTROL</h1>
    <h2>Active Missions</h2>
    <table>
        <tr><th>ID</th><th>Subject</th><th>Status</th></tr>
        {rows if rows else '<tr><td colspan="3">No active missions</td></tr>'}
    </table>
    <h2>Agent Status</h2>
    <table>
        <tr><th>ID</th><th>Status</th><th>Task</th></tr>
        {agent_rows if agent_rows else '<tr><td colspan="3">No active agents</td></tr>'}
    </table>
    <script>setTimeout(function(){{location.reload()}}, 5000);</script>
</body>
</html>"""

    def get_agent_status(self) -> list[dict[str, Any]]:
        """Get running agents status."""
        try:
            result = subprocess.run(
                ["ps", "-eo", "pid,ppid,stat,%cpu,%mem,cmd", "--sort=-%cpu"],
                capture_output=True, text=True, check=True, timeout=5,
            )
            lines = result.stdout.strip().splitlines()[1:]
            agents = []
            for line in lines:
                parts = line.split(None, 5)
                if len(parts) >= 6:
                    agents.append({
                        "pid": parts[0],
                        "ppid": parts[1],
                        "status": parts[2],
                        "cpu": parts[3],
                        "mem": parts[4],
                        "cmd": parts[5][:80],
                    })
            return agents[:20]
        except Exception:
            return []


def get_tools() -> list[dict]:
    return [
        {"name": "get_active_missions", "description": "Get active missions."},
        {"name": "get_mission_details", "description": "Get mission details.", "parameters": {"type": "object", "properties": {"mission_id": {"type": "string"}}, "required": ["mission_id"]}},
        {"name": "render_html", "description": "Render HTML for HUD panel."},
        {"name": "get_agent_status", "description": "Get running agents."},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = MissionDashboard()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(MissionDashboard().render_html())
