"""Stark Protocols plugin: House Party, Clean Slate, Lockdown, Shadow, Rescue, Forge, Exam, Archive."""

import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class StarkProtocols:
    """Collection of Stark-era system protocols."""

    def house_party_protocol(self, task: str, count: int = 5) -> dict:
        """Spawn Docker swarm workers for a task."""
        try:
            service_name = f"jarvis-party-{int(time.time())}"
            subprocess.run(
                [
                    "docker", "run", "-d",
                    "--name", f"{service_name}-head",
                    "--label", f"task={task}",
                    "alpine", "echo", f"House Party: {task}",
                ],
                check=True, timeout=10,
            )
            workers = []
            for i in range(count):
                wname = f"{service_name}-worker-{i}"
                subprocess.run(
                    [
                        "docker", "run", "-d",
                        "--name", wname,
                        "--label", f"task={task}",
                        "alpine", "sh", "-c",
                        f"echo Worker {i} processing {task} && sleep 60",
                    ],
                    check=True, timeout=10,
                )
                workers.append(wname)
            return {"status": "success", "head": f"{service_name}-head", "workers": workers}
        except FileNotFoundError:
            return {"status": "error", "message": "Docker not installed"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": e.stderr}

    def clean_slate_protocol(self) -> dict:
        """Full system cleanup: RAM, /tmp, journal, pacman, docker, DNS."""
        results = {}
        cmds = {
            "ram": ["sync; echo 3 | sudo tee /proc/sys/vm/drop_caches"],
            "tmp": ["sudo", "rm", "-rf", "/tmp/*"],
            "journal": ["sudo", "journalctl", "--vacuum-time=7d"],
            "pacman": ["sudo", "pacman", "-Scc", "--noconfirm"],
            "docker": ["docker", "system", "prune", "-a", "-f"],
            "dns": ["sudo", "systemd-resolve", "--flush-caches"],
        }
        for key, cmd in cmds.items():
            try:
                r = subprocess.run(cmd, shell=(key == "ram"), capture_output=True, text=True, timeout=120, check=False)
                results[key] = {"code": r.returncode, "stdout": r.stdout[:500], "stderr": r.stderr[:500]}
            except Exception as e:
                results[key] = {"error": str(e)}
        return results

    def lockdown_protocol(self) -> dict:
        """Lockdown: iptables DROP, WiFi off, Bluetooth off, screen lock, kill browsers."""
        results = {}
        try:
            r = subprocess.run(["sudo", "iptables", "-P", "INPUT", "DROP"], capture_output=True, text=True, timeout=5)
            results["iptables"] = r.returncode == 0
        except Exception as e:
            results["iptables"] = {"error": str(e)}
        try:
            subprocess.run(["nmcli", "radio", "wifi", "off"], check=False, timeout=5)
            results["wifi"] = True
        except Exception:
            results["wifi"] = False
        try:
            subprocess.run(["sudo", "rfkill", "block", "bluetooth"], check=False, timeout=5)
            results["bluetooth"] = True
        except Exception:
            results["bluetooth"] = False
        try:
            subprocess.run(["i3lock", "-c", "000000"], check=False, timeout=5)
            results["screen_lock"] = True
        except Exception:
            results["screen_lock"] = False
        try:
            subprocess.run(["pkill", "-f", "firefox|chrome|chromium|brave"], check=False, timeout=5)
            results["browsers_killed"] = True
        except Exception:
            results["browsers_killed"] = False
        return results

    def shadow_protocol(self, command: str) -> dict:
        """Execute command in Xvfb virtual display."""
        display = f":{99 + hash(command) % 100}"
        try:
            xvfb = subprocess.Popen(["Xvfb", display, "-screen", "0", "1920x1080x24"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
            env = os.environ.copy()
            env["DISPLAY"] = display
            r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60, env=env)
            xvfb.terminate()
            return {"status": "success", "exit_code": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
        except FileNotFoundError:
            return {"status": "error", "message": "Xvfb not installed"}
        except subprocess.TimeoutExpired:
            xvfb.terminate()
            return {"status": "error", "message": "Command timed out"}
        except Exception as e:
            xvfb.terminate()
            return {"status": "error", "message": str(e)}

    def rescue_protocol(self) -> dict:
        """Snapshot, flush RAM, kill zombies, report top consumers."""
        results = {}
        try:
            r = subprocess.run(["sudo", "btrfs", "subvolume", "snapshot", "-r", "/", f"/.snapshots/rescue-{int(time.time())}"], capture_output=True, text=True, timeout=30)
            results["snapshot"] = r.returncode == 0
        except Exception as e:
            results["snapshot"] = {"error": str(e)}
        try:
            subprocess.run("sync; echo 3 | sudo tee /proc/sys/vm/drop_caches", shell=True, check=False, timeout=10)
            results["ram_flushed"] = True
        except Exception:
            results["ram_flushed"] = False
        try:
            subprocess.run(["sudo", "killall", "-9", "-w", "Z"], check=False, timeout=5)
            results["zombies_killed"] = True
        except Exception:
            results["zombies_killed"] = False
        try:
            r = subprocess.run(["ps", "-eo", "pid,ppid,cmd,%mem,%cpu", "--sort=-%mem"], capture_output=True, text=True, timeout=5, check=True)
            lines = r.stdout.strip().splitlines()[:10]
            results["top_consumers"] = lines
        except Exception as e:
            results["top_consumers"] = {"error": str(e)}
        return results

    def forge_protocol(self, plugin_name: str, description: str) -> dict:
        """Auto-generate a new plugin from template."""
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(plugin_dir, "_template.py")
        new_path = os.path.join(plugin_dir, f"{plugin_name}.py")
        try:
            with open(template_path, "r") as f:
                content = f.read()
            content = content.replace('PLUGIN_NAME: str = "template"', f'PLUGIN_NAME: str = "{plugin_name}"')
            content = content.replace('PLUGIN_DESCRIPTION: str = "Auto-generated plugin template for JARVIS NEXUS"', f'PLUGIN_DESCRIPTION: str = "{description}"')
            with open(new_path, "w") as f:
                f.write(content)
            return {"status": "success", "file": new_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def exam_protocol(self, subject: str) -> dict:
        """Create mission for study material generation."""
        mission = {
            "id": f"exam-{int(time.time())}",
            "subject": subject,
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending",
            "subtasks": [
                f"Gather reference material for {subject}",
                f"Generate study notes for {subject}",
                f"Create practice questions for {subject}",
                f"Build revision timeline for {subject}",
            ],
        }
        mission_path = f"/tmp/mission-{mission['id']}.json"
        with open(mission_path, "w") as f:
            json.dump(mission, f, indent=2)
        return {"status": "success", "mission": mission, "path": mission_path}

    def archive_protocol(self, folder: str) -> dict:
        """Create tar.gz archive with sha256 checksum."""
        if not os.path.isdir(folder):
            return {"status": "error", "message": f"Folder not found: {folder}"}
        base = os.path.basename(folder.rstrip("/"))
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        archive_name = f"{base}-{timestamp}.tar.gz"
        archive_path = os.path.join(tempfile.gettempdir(), archive_name)
        try:
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(folder, arcname=base)
            sha256 = self._sha256_file(archive_path)
            with open(f"{archive_path}.sha256", "w") as f:
                f.write(f"{sha256}  {archive_name}\n")
            return {"status": "success", "archive": archive_path, "sha256": sha256}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _sha256_file(self, path: str) -> str:
        import hashlib
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()


def get_tools() -> list[dict]:
    return [
        {"name": "house_party_protocol", "description": "Spawn Docker swarm for a task.", "parameters": {"type": "object", "properties": {"task": {"type": "string"}, "count": {"type": "integer"}}, "required": ["task"]}},
        {"name": "clean_slate_protocol", "description": "Full system cleanup."},
        {"name": "lockdown_protocol", "description": "Lockdown system."},
        {"name": "shadow_protocol", "description": "Execute in Xvfb virtual display.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
        {"name": "rescue_protocol", "description": "Snapshot, flush RAM, kill zombies."},
        {"name": "forge_protocol", "description": "Auto-generate plugin.", "parameters": {"type": "object", "properties": {"plugin_name": {"type": "string"}, "description": {"type": "string"}}, "required": ["plugin_name", "description"]}},
        {"name": "exam_protocol", "description": "Create exam mission.", "parameters": {"type": "object", "properties": {"subject": {"type": "string"}}, "required": ["subject"]}},
        {"name": "archive_protocol", "description": "Archive folder with checksum.", "parameters": {"type": "object", "properties": {"folder": {"type": "string"}}, "required": ["folder"]}},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = StarkProtocols()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(json.dumps(execute("rescue_protocol", {}), indent=2, default=str))
