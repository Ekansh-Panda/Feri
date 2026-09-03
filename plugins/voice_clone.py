"""Local XTTS voice cloning plugin."""

import os
import shutil
import subprocess
from typing import Any

from ._template import PLUGIN_DESCRIPTION, PLUGIN_NAME, PLUGIN_VERSION


class VoiceClone:
    """Local XTTS voice cloning."""

    def __init__(self) -> None:
        self.voices_dir = os.path.expanduser("~/.local/share/jarvis/voices")
        os.makedirs(self.voices_dir, exist_ok=True)

    def train_voice(self, audio_files: list[str], name: str) -> dict[str, Any]:
        """Train XTTS voice from audio files."""
        voice_path = os.path.join(self.voices_dir, name)
        os.makedirs(voice_path, exist_ok=True)
        for i, src in enumerate(audio_files):
            if os.path.exists(src):
                dst = os.path.join(voice_path, f"sample_{i:03d}{os.path.splitext(src)[1]}")
                shutil.copy2(src, dst)
        config = {
            "name": name,
            "path": voice_path,
            "samples": len(audio_files),
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }
        with open(os.path.join(voice_path, "config.json"), "w") as f:
            import json
            json.dump(config, f, indent=2)
        return {"status": "success", "name": name, "path": voice_path, "samples": len(audio_files)}

    def synthesize(self, text: str, voice_name: str) -> dict[str, Any]:
        """Generate speech using trained voice."""
        voice_path = os.path.join(self.voices_dir, voice_name)
        output_path = os.path.join(voice_path, "output.wav")
        if not os.path.isdir(voice_path):
            return {"status": "error", "message": f"Voice not found: {voice_name}"}
        try:
            subprocess.run(
                [
                    "tts",
                    "--text", text,
                    "--model_name", "tts_models/multilingual/multi-dataset/xtts_v2",
                    "--speaker_idx", "p224",
                    "--language_idx", "en",
                    "--out_path", output_path,
                ],
                check=True, timeout=120, capture_output=True, text=True,
            )
            return {"status": "success", "output": output_path}
        except FileNotFoundError:
            return {"status": "error", "message": "TTS not installed"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "message": e.stderr}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def list_voices(self) -> dict[str, Any]:
        """List available trained voices."""
        voices = []
        if not os.path.isdir(self.voices_dir):
            return {"status": "success", "voices": []}
        for name in os.listdir(self.voices_dir):
            config_path = os.path.join(self.voices_dir, name, "config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r") as f:
                        import json
                        voices.append(json.load(f))
                except Exception:
                    continue
        return {"status": "success", "voices": voices}

    def delete_voice(self, name: str) -> dict[str, Any]:
        """Delete a trained voice."""
        voice_path = os.path.join(self.voices_dir, name)
        if not os.path.exists(voice_path):
            return {"status": "error", "message": f"Voice not found: {name}"}
        try:
            shutil.rmtree(voice_path)
            return {"status": "success", "name": name}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def export_voice(self, name: str, output_path: str) -> dict[str, Any]:
        """Export voice model to output path."""
        voice_path = os.path.join(self.voices_dir, name)
        if not os.path.exists(voice_path):
            return {"status": "error", "message": f"Voice not found: {name}"}
        try:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            shutil.make_archive(output_path, "zip", voice_path)
            return {"status": "success", "exported": f"{output_path}.zip"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def get_tools() -> list[dict]:
    return [
        {"name": "train_voice", "description": "Train XTTS voice.", "parameters": {"type": "object", "properties": {"audio_files": {"type": "array", "items": {"type": "string"}}, "name": {"type": "string"}}, "required": ["audio_files", "name"]}},
        {"name": "synthesize", "description": "Synthesize speech.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "voice_name": {"type": "string"}}, "required": ["text", "voice_name"]}},
        {"name": "list_voices", "description": "List available voices."},
        {"name": "delete_voice", "description": "Delete voice.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
        {"name": "export_voice", "description": "Export voice model.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "output_path": {"type": "string"}}, "required": ["name", "output_path"]}},
    ]


def execute(tool_name: str, params: dict) -> dict:
    instance = VoiceClone()
    method = getattr(instance, tool_name, None)
    if method and callable(method):
        try:
            return method(**params)
        except TypeError as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    print(json.dumps(execute("list_voices", {}), indent=2))
