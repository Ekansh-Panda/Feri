"""Wearable + fatigue tracking plugin."""

import time
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class BiometricMonitor:
    """Wearable + fatigue tracking."""

    def __init__(self) -> None:
        self.uptime_start = time.time()

    def get_system_vitals(self) -> dict[str, Any]:
        """Get system vitals including hours awake, cpu temp, battery, fatigue index."""
        uptime_seconds = time.time() - self.uptime_start
        hours_awake = round(uptime_seconds / 3600, 2)

        cpu_temp = self._read_cpu_temp()
        battery = self._read_battery()
        fatigue_index = self._calculate_fatigue(hours_awake, cpu_temp, battery)

        return {
            "hours_awake": hours_awake,
            "cpu_temp_c": cpu_temp,
            "battery_pct": battery,
            "fatigue_index": fatigue_index,
        }

    def assess_user_state(self) -> dict[str, str]:
        """Assess user state as OPTIMAL, WARNING, or CRITICAL."""
        vitals = self.get_system_vitals()
        fatigue = vitals["fatigue_index"]

        if fatigue < 0.3:
            state = "OPTIMAL"
            message = "All systems nominal. User is alert and focused."
        elif fatigue < 0.7:
            state = "WARNING"
            message = "Elevated fatigue detected. Consider a short break."
        else:
            state = "CRITICAL"
            message = "Critical fatigue. Recommend rest or reduced workload."

        return {"state": state, "message": message, "fatigue_index": fatigue}

    def intervene(self, action: str) -> dict[str, Any]:
        """Apply fatigue intervention."""
        import subprocess

        action = action.lower()
        if action == "dim":
            try:
                subprocess.run(["brightnessctl", "set", "30%"], check=True, timeout=5)
                return {"status": "success", "action": "dim"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        elif action == "mute":
            try:
                subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"], check=True, timeout=5)
                return {"status": "success", "action": "mute"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        elif action == "dnd":
            try:
                subprocess.run(["notify-send", "DND mode activated"], check=False, timeout=5)
                return {"status": "success", "action": "dnd"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": f"Unknown action: {action}"}

    def _read_cpu_temp(self) -> float:
        """Read CPU temperature from /sys/class/thermal."""
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                return round(int(f.read().strip()) / 1000.0, 1)
        except Exception:
            return 0.0

    def _read_battery(self) -> int:
        """Read battery percentage."""
        try:
            with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
                return int(f.read().strip())
        except Exception:
            return 100

    def _calculate_fatigue(self, hours_awake: float, cpu_temp: float, battery: int) -> float:
        """Calculate fatigue index (0.0 to 1.0)."""
        time_factor = min(hours_awake / 16.0, 1.0)
        temp_factor = max(0, (cpu_temp - 40.0) / 60.0)
        battery_factor = max(0, (100 - battery) / 100.0)
        return round(time_factor * 0.6 + temp_factor * 0.2 + battery_factor * 0.2, 2)

    def webcam_eye_tracking(self) -> dict[str, Any]:
        """Integrate webcam eye tracking via mediapipe."""
        try:
            import mediapipe as mp
            import cv2
            import numpy as np

            mp_face_mesh = mp.solutions.face_mesh
            face_mesh = mp_face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
            )

            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return {"status": "error", "message": "Could not open webcam"}

            ret, frame = cap.read()
            cap.release()
            if not ret:
                return {"status": "error", "message": "Could not read frame"}

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)

            if results.multi_face_landmarks:
                landmarks = results.multi_face_landmarks[0]
                left_eye = [landmarks[159], landmarks[145]]
                right_eye = [landmarks[386], landmarks[374]]
                ear = self._eye_aspect_ratio(left_eye, right_eye)
                return {"status": "success", "eye_aspect_ratio": round(ear, 3), "eyes_detected": True}
            return {"status": "success", "eyes_detected": False}
        except ImportError:
            return {"status": "error", "message": "mediapipe or opencv not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _eye_aspect_ratio(self, left_eye: list, right_eye: list) -> float:
        """Calculate eye aspect ratio."""
        import numpy as np
        left = np.array([[p.x, p.y] for p in left_eye])
        right = np.array([[p.x, p.y] for p in right_eye])
        h_left = np.linalg.norm(left[0] - left[1])
        h_right = np.linalg.norm(right[0] - right[1])
        return float((h_left + h_right) / 2.0)


def get_tools() -> list[dict]:
    return [
        {"name": "get_system_vitals", "description": "Get system vitals: hours awake, cpu temp, battery, fatigue index."},
        {"name": "assess_user_state", "description": "Assess user state as OPTIMAL/WARNING/CRITICAL."},
        {"name": "intervene", "description": "Apply fatigue intervention (dim, mute, dnd).", "parameters": {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]}},
        {"name": "webcam_eye_tracking", "description": "Webcam eye tracking via mediapipe."},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = BiometricMonitor()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    m = BiometricMonitor()
    print(m.get_system_vitals())
    print(m.assess_user_state())
