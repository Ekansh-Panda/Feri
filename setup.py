"""
JARVIS NEXUS — First-Run Setup Wizard

Replaces the old install_stark_deps-only flow. Walks the user through:
  1. OS detection
  2. Dependency install (optional, with skip)
  3. Gemini API key entry
  4. Audio device probe (mic + speaker measurement)
  5. HUD color theme
  6. Approval gate policy
  7. Symlink to ~/.local/bin/feri

All steps are optional — you can skip any of them. The wizard never
deletes existing config unless you tell it to.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_DIR / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.table import Table
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None


def _print(msg: str) -> None:
    if console:
        console.print(msg)
    else:
        print(msg)


def _header(title: str) -> None:
    if console:
        console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
    else:
        print(f"\n=== {title} ===\n")


def detect_os() -> str:
    if os.path.exists("/etc/arch-release"):
        return "arch"
    if os.path.exists("/etc/debian_version"):
        return "debian"
    if os.path.exists("/etc/fedora-release"):
        return "fedora"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "win32":
        return "windows"
    return "linux"


def step_os() -> str:
    _header("1. OS Detection")
    os_type = detect_os()
    if console:
        if os_type == "arch":
            console.print("[green]Arch Linux detected. Full Stark OS capabilities unlocked.[/green]")
        elif os_type in ("debian", "fedora"):
            console.print(f"[yellow]{os_type.title()} detected. Fallback adapter will be used.[/yellow]")
        elif os_type == "macos":
            console.print("[yellow]macOS detected. Some Arch-specific features unavailable.[/yellow]")
        elif os_type == "windows":
            console.print("[yellow]Windows detected. Native tooling replaced with portable fallbacks.[/yellow]")
        else:
            console.print("[yellow]Unknown Linux. Generic adapter.[/yellow]")
    return os_type


def step_dependencies() -> None:
    _header("2. Dependencies")
    if Confirm.ask("Install native dependencies?", default=False) if console else \
       input("Install native dependencies? [y/N] ").lower().startswith("y"):
        _print("[cyan]Running install_stark_deps.sh (this takes 10-20 minutes)...[/cyan]")
        script = PROJECT_DIR / "install_stark_deps.sh"
        if script.exists():
            subprocess.run(["sudo", "bash", str(script)], check=False)
        else:
            _print("[red]install_stark_deps.sh not found — skipping.[/red]")
    else:
        _print("[dim]Skipped. You can run it later with: feri install[/dim]")


def step_api_key(config: dict) -> None:
    _header("3. Neural Link — Gemini API Key")
    existing = config.get("gemini_api_key", "")
    if existing and existing != "YOUR_GEMINI_KEY":
        _print(f"[dim]Existing key found (ends in ...{existing[-6:]})[/dim]")
        if not (Confirm.ask("Replace?", default=False) if console else
                input("Replace? [y/N] ").lower().startswith("y")):
            return
    key = Prompt.ask(
        "Gemini API key (get one free at https://aistudio.google.com/apikey)",
        password=True, default=""
    ) if console else input("Gemini API key: ").strip()
    if key:
        config["gemini_api_key"] = key
        _print("[green]API key saved.[/green]")
    else:
        _print("[yellow]No key set. You can edit config/api_keys.json later.[/yellow]")


def step_audio_probe(config: dict) -> None:
    _header("4. Audio Receptor Calibration")
    _print("[cyan]Probing audio devices...[/cyan]")
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from core.audio_devices import list_devices, prefetch
        prefetch()
        inputs = list_devices("input", refresh=True)
        outputs = list_devices("output", refresh=True)
        if console:
            table = Table(title="Detected Devices")
            table.add_column("Direction", style="cyan")
            table.add_column("Device Name", style="green")
            for d in inputs:
                table.add_row("Input", d)
            for d in outputs:
                table.add_row("Output", d)
            console.print(table)
        else:
            _print("Inputs: " + ", ".join(inputs))
            _print("Outputs: " + ", ".join(outputs))
        if inputs:
            config.setdefault("arch_specific", {})["mic_name"] = inputs[0]
        if outputs:
            config.setdefault("arch_specific", {})["speaker_name"] = outputs[0]
        _print(f"[green]Selected mic: {inputs[0] if inputs else 'system default'}[/green]")
    except Exception as e:
        _print(f"[yellow]Audio probe failed: {e}. Falling back to system default.[/yellow]")


def step_hud_theme(config: dict) -> None:
    _header("5. Arc Reactor Color")
    themes = {
        "1": ("Stark Cyan", "#00dcff"),
        "2": ("Iron Man Red", "#ff0000"),
        "3": ("Gold", "#ffcc00"),
        "4": ("Arc Reactor Blue", "#4a9eff"),
    }
    if console:
        table = Table(title="Available Themes")
        for k, (name, hex_) in themes.items():
            table.add_row(k, name, hex_)
        console.print(table)
    choice = Prompt.ask("Choose theme", choices=list(themes.keys()), default="1") \
        if console else input(f"Choose theme {list(themes.keys())} [1]: ").strip() or "1"
    name, hex_ = themes[choice]
    config.setdefault("arch_specific", {})["hud_color"] = hex_
    _print(f"[green]Theme set: {name} ({hex_})[/green]")


def step_feri_symlink() -> None:
    _header("6. Install 'feri' Command")
    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    feri_link = local_bin / "feri"
    feri_src = PROJECT_DIR / "scripts" / "feri"
    if feri_link.exists() or feri_link.is_symlink():
        if feri_link.resolve() == feri_src.resolve():
            _print("[green]feri already installed.[/green]")
            return
    if Confirm.ask(f"Link {feri_src} -> {feri_link}?", default=True) if console else \
       input(f"Link feri to {feri_link}? [Y/n] ").lower() != "n":
        if feri_link.is_symlink() or feri_link.exists():
            feri_link.unlink()
        feri_link.symlink_to(feri_src)
        _print(f"[green]Linked. Add ~/.local/bin to PATH if not already.[/green]")
        path = os.environ.get("PATH", "")
        if str(local_bin) not in path:
            rc_file = Path.home() / ".bashrc"
            if rc_file.exists():
                line = '\n# JARVIS NEXUS\nexport PATH="$HOME/.local/bin:$PATH"\n'
                with open(rc_file, "a") as f:
                    f.write(line)
                _print(f"[green]Added PATH export to {rc_file}[/green]")


def save_config(config: dict) -> None:
    api_path = CONFIG_DIR / "api_keys.json"
    arch_path = CONFIG_DIR / "arch_specific.json"
    api_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    if "arch_specific" in config:
        arch_path.write_text(
            json.dumps(config["arch_specific"], indent=2),
            encoding="utf-8",
        )
    _print(f"[green]Config saved to {api_path}[/green]")


def load_config() -> dict:
    api_path = CONFIG_DIR / "api_keys.json"
    if api_path.exists():
        try:
            return json.loads(api_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def main() -> int:
    if not HAS_RICH:
        _print("[yellow]Install 'rich' for a better setup experience: pip install rich[/yellow]")

    if console:
        console.print(Panel(
            "[bold cyan]J.A.R.V.I.S. NEXUS[/bold cyan]\n"
            "[dim]First-Run Initialization Sequence[/dim]",
            expand=False,
        ))
    else:
        _print("=" * 60)
        _print("J.A.R.V.I.S. NEXUS — First Run Setup")
        _print("=" * 60)

    config = load_config()
    step_os()
    step_dependencies()
    step_api_key(config)
    step_audio_probe(config)
    step_hud_theme(config)
    step_feri_symlink()
    save_config(config)

    if console:
        console.print(Panel(
            "[bold green]NEXUS INITIALIZED[/bold green]\n\n"
            "Run [bold cyan]feri start[/bold cyan] to bring JARVIS online.\n"
            "Run [bold cyan]feri logs[/bold cyan] to watch live output.\n"
            "Run [bold cyan]feri help[/bold cyan] for all commands.",
            expand=False,
        ))
    else:
        _print("\nNEXUS INITIALIZED.")
        _print("Run 'feri start' to launch JARVIS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
