# ⚙️ JARVIS NEXUS — STARK OS
### Arch Linux + i3wm Native AI Operating Layer

> Built by **[ekanshpanda](https://ekanshpanda.vercel.app)**

---

## 🧬 What Is This

JARVIS NEXUS is not an app. It is an **autonomous AI operating layer** that lives directly on Arch Linux + i3wm.

It talks to the kernel, `/proc`, `/sys`, `/dev`, `systemd`, `i3-msg`, and X11 without middleware. It controls windows, hardware, networks, Docker containers, and the entire desktop from a single PyQt6 HUD. It runs missions, writes plugins, scans airspace, monitors biometrics, and backs up its own consciousness to an encrypted git repository.

Primary target: **Arch Linux + i3wm**.
Fallback layer: thin adapters for Debian/Fedora, macOS, Windows.

---

## ⚡ Current Features

### Core Cognitive Layer
| Feature | Implementation |
|---|---|
| Natural Language Understanding | Gemini Live API — native audio streaming |
| Intent Routing | Heuristic planner → mission graphs → DAG execution |
| Mission Engine | Checkpoint-survivable missions with auto-restore on reboot |
| Persistent Memory | SQLite FTS + JSON long-term + ChromaDB vector store |
| Visual Memory | Screenshot OCR every 30s → ChromaDB for instant recall |
| Tool Memory | Learns which tools succeed/fail and recommends best-fit tools |
| Affective Dialog | Emotion-aware voice tone adaptation |
| Proactive Audio | Background noise suppression — only responds to directed speech |
| Unlimited Sessions | Sliding-window context compression via Gemini Live |
| Self-Evolution | Writes, tests, sandboxes, and hot-loads its own plugins |

### Agent Swarm (13 Agents)
| Agent | Role |
|---|---|
| `PlannerAgent` | Breaks high-level goals into subtask DAGs |
| `ResearcherAgent` | Multi-source web + local + AI research with citations |
| `BrowserAgent` | Playwright + Xvfb shadow workspace — invisible browser automation |
| `TerminalAgent` | Root shell execution with session management |
| `FileAgent` | Atomic file operations — write, diff, secure delete |
| `CodeAgent` | Generate, review, test, debug, refactor, git patch |
| `VerifierAgent` | Output quality checks — code, documents, missions |
| `CompilerAgent` | Markdown → PDF (xelatex) → EPUB → Anki decks → LaTeX formula sheets |
| `SentinelAgent` | System health monitor — CPU, RAM, disk, temp, battery, services |
| `JanitorAgent` | Full system cleanup — /tmp, journal, pacman, AUR, Docker, DNS |
| `NetworkAgent` | Network scanning, port scanning, DNS, bandwidth, traceroute |
| `HardwareAgent` | /sys, /proc, sensors, GPU, undervolt, kernel modules |
| `ProtocolAgent` | Named protocol execution — House Party, Lockdown, Rescue, etc. |

### Actions (25 Modules)
| Action | Native Tool |
|---|---|
| `web_search` | Gemini Grounded + DuckDuckGo parallel search |
| `deep_research` | Multi-hour autonomous research loop |
| `screen_processor` | scrot + tesseract OCR + webcam capture |
| `background_monitor` | Periodic topic watching with persistence |
| `proactive` | Time/context-aware check-ins |
| `reminder` | systemd user timers (not cron) |
| `system_monitor` | /proc + /sys + psutil telemetry daemon |
| `computer_settings` | Volume, brightness, WiFi, Bluetooth, power profiles |
| `computer_control` | i3-msg, xdotool, xclip, scrot, i3lock, shutdown/reboot/suspend |
| `open_app` | i3-msg exec with fuzzy desktop-file matching |
| `browser_control` | Chromium navigation, tabs, form filling |
| `file_controller` | Atomic file ops, glob search, metadata |
| `file_processor` | PDF, DOCX, image OCR, AI summarization |
| `send_message` | Discord webhook, Telegram bot, SMTP email |
| `weather_report` | wttr.in + OpenWeatherMap |
| `flight_finder` | Flight search and tracking |
| `youtube_video` | yt-dlp + mpv — search, play, download |
| `game_updater` | Steam/Epic CLI update management |
| `code_helper` | Code review, generation, explanation, optimization |
| `dev_agent` | Project setup, pytest, ruff, black, git workflow |
| `desktop` | i3 workspaces, layout, focus, resize, floating |
| `document_compiler` | Pandoc → PDF/EPUB, Anki decks, LaTeX formula sheets |
| `anki_builder` | genanki deck generation with image support |
| `latex_compiler` | xelatex compilation with bibtex and watch mode |
| `hardware_control` | Sensors, fan control, undervolt, CPU governor |

### Plugins (15 Modules)
| Plugin | Power |
|---|---|
| `protocols` | 8 Stark protocols: House Party, Clean Slate, Lockdown, Shadow, Rescue, Forge, Exam, Archive |
| `i3_integration` | Full i3-msg control — workspaces, windows, layouts, scratchpad |
| `estate_control` | Home Assistant / MQTT — locks, lights, climate, music, screen lock |
| `biometrics` | Fatigue index, system vitals, webcam eye tracking, auto-intervention |
| `global_tracker` | OpenSky airspace, SpaceX launches, USGS earthquakes, weather, IP |
| `media_control` | playerctl, mpv, YouTube, ffmpeg screen recording |
| `package_manager` | pacman / yay AUR — install, remove, search, clean, update |
| `systemd_manager` | Service/timer/journal control — create timers, enable/disable units |
| `btrfs_manager` | Snapper snapshots, rollback, filesystem usage |
| `usb_peripheral` | lsusb, serial/Arduino, mount/eject USB, block devices |
| `voice_clone` | Local XTTS voice cloning and synthesis |
| `osint` | WHOIS, DNS enumeration, breach check, EXIF geolocation |
| `self_evolve` | Plugin auto-generation, gap analysis, sandbox test, hot-deploy |
| `mission_dashboard` | HUD mission control HTML panel |

### Stark Protocols
| Protocol | What It Does |
|---|---|
| **House Party** | Spawns N parallel Docker workers for swarm tasks |
| **Clean Slate** | RAM flush, /tmp purge, journal vacuum, pacman/AUR cache trim, Docker prune, DNS flush |
| **Lockdown** | iptables DROP all, WiFi off, Bluetooth off, screen lock, kill browsers |
| **Shadow** | Runs any command on Xvfb virtual display — completely invisible |
| **Rescue** | Btrfs snapshot, RAM flush, zombie kill, top consumer report |
| **Forge** | Auto-generates a new plugin from template, syntax-checks, sandbox-tests, hot-loads |
| **Exam** | Creates a full study-material mission (theory, formulas, practice, Anki, mock test) |
| **Archive** | Tar + SHA256 checksum of any folder |

### UI — PyQt6 Stark HUD
| Panel | Technology |
|---|---|
| Main Window | Frameless, always-on-top, glassmorphic, i3 scratchpad on workspace 10 |
| Arc Reactor | Custom QPainter — concentric cyan/red rings, pulse, rotation, core glow |
| Holo Workbench | PyQtWebEngine + Three.js — 3D force graphs, filesystem trees, molecular viewer, math surfaces |
| Mission Control | Live mission cards, progress bars, expandable subtasks, artifact lists |
| Neural Transcript | Chat panel with streaming user/JARVIS messages, voice input |
| Global Surveillance | OpenSky aircraft, wttr.in weather, USGS seismic, network status — auto-refresh |
| Telemetry Gauges | Circular CPU/RAM/GPU/temp gauges, color-coded arcs, real-time psutil polling |
| Protocol Buttons | 8-protocol grid with status indicators and progress overlay |
| Approval Banner | Dangerous-action confirmation — token issued by UI, not the model |
| User Telemetry | Fatigue index, hours awake, battery, sleep debt, intervention suggestions |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (YOU)                               │
│                    Voice / Keyboard / CLI                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    EXPERIENCE LAYER                             │
│  PyQt6 Stark HUD · i3bar/polybar · rofi · notifications        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    CONVERSATION LAYER                           │
│  Gemini Live API · Affective Dialog · Proactive Audio          │
│  Intent Router · Session Continuity                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    COGNITIVE LAYER                              │
│  Mission Engine · Task Graph · Planner Agent                   │
│  Memory Engine (SQLite + ChromaDB + /proc journal)             │
│  Verifier Agent · Self-Evolution Engine                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    AGENT SWARM LAYER                            │
│  Browser · Terminal · File · Code · Research · Compiler        │
│  Sentinel · Janitor · Network · Hardware · Protocol            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    EXECUTION LAYER                              │
│  i3-msg · xdotool · xclip · scrot · systemd · nmcli            │
│  pactl · brightnessctl · iptables/nftables · docker            │
│  Xvfb · Playwright · Frida · scapy · psutil · pynvml           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    KERNEL / HARDWARE                            │
│  /proc · /sys · /dev · netfilter · cgroups · kernel modules    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
Mark-LII/
├── main.py                          # Core loop — Gemini Live + Agent dispatch
├── ui.py                            # Legacy single-file HUD (kept for compatibility)
├── setup.py                         # First-run Arch-specific wizard
├── requirements.txt
├── install_stark_deps.sh            # Full Arch dependency installer
│
├── core/
│   ├── orchestrator.py              # Master router — connects everything
│   ├── planner.py                   # Converts prompts → mission graphs
│   ├── mission_engine.py            # Mission lifecycle, checkpoints, resume
│   ├── task_graph.py                # DAG execution engine
│   ├── agent_runtime.py             # Spawns/manages agent processes
│   ├── memory_manager.py            # SQLite + JSON structured memory
│   ├── vector_memory.py             # ChromaDB local vector store
│   ├── visual_memory.py             # Screenshot OCR → vector index
│   ├── tool_memory.py               # Remembers which tools worked/failed
│   ├── safety.py                    # Permission levels, approval gates
│   ├── audit.py                     # Every action logged to journal
│   ├── undo.py                      # Reversible action stack
│   ├── confirm.py                   # UI-issued confirmation tokens
│   ├── plugin_loader.py             # Hot-reload plugin engine
│   ├── plugin_author.py             # JARVIS writes his own plugins
│   ├── sandbox.py                   # Docker/nsjail isolated execution
│   ├── scheduler.py                 # APScheduler for timed tasks
│   ├── watchdog.py                  # Watches JARVIS itself, auto-restart
│   ├── matrix_sync.py               # Encrypted cloud consciousness backup
│   ├── network_warfare.py           # scapy, iptables, ARP, firewall
│   ├── holographic_engine.py        # PyQtWebEngine 3D Three.js renderer
│   ├── audio_devices.py             # PipeWire/PulseAudio device management
│   ├── llm_client.py                # Gemini API client (Ollama/OpenAI-compatible)
│   ├── stt.py                       # Speech-to-text (Whisper/Vosk/Gemini)
│   ├── tts.py                       # Text-to-speech (Edge/Kokoro/ElevenLabs)
│   ├── installer.py                 # Arch-specific dependency installer
│   └── prompt.txt                   # JARVIS personality and tool-routing rules
│
├── agents/
│   ├── planner_agent.py             # Breaks missions into subtasks
│   ├── researcher_agent.py          # Web + local + AI research
│   ├── browser_agent.py             # Playwright + Xvfb shadow workspace
│   ├── terminal_agent.py            # Root shell execution
│   ├── file_agent.py                # Atomic file operations
│   ├── code_agent.py                # Write, test, debug, patch code
│   ├── verifier_agent.py            # Checks output quality
│   ├── compiler_agent.py            # MD → LaTeX → PDF → Anki → EPUB
│   ├── sentinel_agent.py            # System health monitor
│   ├── janitor_agent.py             # Cleanup, temp purge
│   ├── network_agent.py             # Network scanning, firewall, DNS
│   ├── hardware_agent.py            # /sys, /proc, sensors, GPU, undervolt
│   └── protocol_agent.py            # Named protocol execution
│
├── actions/
│   ├── web_search.py                # Gemini grounded + DDG fallback
│   ├── deep_research.py             # Multi-hour autonomous research loop
│   ├── screen_processor.py          # Screenshot + webcam vision
│   ├── background_monitor.py        # Topic watching daemon
│   ├── proactive.py                 # Time/context-aware check-ins
│   ├── reminder.py                  # systemd timers (not cron)
│   ├── system_monitor.py            # /proc + /sys telemetry
│   ├── computer_settings.py         # Volume, brightness, WiFi, power
│   ├── computer_control.py          # xdotool, i3-msg, window mgmt
│   ├── open_app.py                  # i3-msg exec launcher
│   ├── browser_control.py           # Chromium control
│   ├── file_controller.py           # File system operations
│   ├── file_processor.py            # Document reading/summarization
│   ├── send_message.py              # Messaging integration
│   ├── weather_report.py            # wttr.in / OpenWeatherMap
│   ├── flight_finder.py             # Flight search
│   ├── youtube_video.py             # yt-dlp + mpv control
│   ├── game_updater.py              # Steam/Epic via CLI
│   ├── code_helper.py               # Code review/generation
│   ├── dev_agent.py                 # Developer task agent
│   ├── desktop.py                   # i3 workspace management
│   ├── document_compiler.py         # Pandoc pipeline
│   ├── anki_builder.py              # genanki deck generation
│   ├── latex_compiler.py            # xelatex compilation
│   └── hardware_control.py          # Sensors, GPU, undervolt
│
├── plugins/
│   ├── _template.py                 # Plugin template
│   ├── estate_control.py            # Home Assistant / MQTT smart home
│   ├── biometrics.py                # Wearable + fatigue tracking
│   ├── global_tracker.py            # OpenSky, SpaceX, USGS, AIS
│   ├── protocols.py                 # House Party, Clean Slate, Lockdown
│   ├── osint.py                     # Deep OSINT dossier builder
│   ├── self_evolve.py               # Plugin auto-generation
│   ├── mission_dashboard.py         # HUD mission control panel
│   ├── i3_integration.py            # i3-msg window/workspace control
│   ├── media_control.py             # playerctl, mpv, spotify
│   ├── package_manager.py           # pacman/yay AUR management
│   ├── systemd_manager.py           # Service/timer/journal control
│   ├── btrfs_manager.py             # Snapshots, rollback
│   ├── usb_peripheral.py            # /dev/usb, serial, Arduino
│   └── voice_clone.py               # Local XTTS voice cloning
│
├── memory/
│   ├── long_term.json               # Persistent facts
│   ├── identity.json                # JARVIS personality config
│   ├── projects/                    # Per-mission project folders
│   ├── episodic/                    # Session summaries
│   ├── visual/                      # Screenshot OCR index
│   ├── tool_memory/                 # Tool success/failure logs
│   └── chroma_db/                   # ChromaDB vector store
│
├── missions/
│   ├── active/                      # Running mission JSONs
│   ├── completed/                   # Archived missions
│   ├── failed/                      # Failed missions
│   └── templates/                   # Reusable mission templates
│
├── shadow_workspace/
│   ├── xvfb/                        # Virtual display configs
│   ├── browser_profiles/            # Persistent browser sessions
│   └── downloads/                   # Isolated download zone
│
├── ui/
│   ├── stark_hud.py                 # Main PyQt6 HUD
│   ├── arc_reactor.py               # Custom painted Arc Reactor widget
│   ├── glass_panel.py               # Glassmorphic panel component
│   ├── mission_control.py           # Mission dashboard widget
│   ├── hologram_view.py             # WebEngine 3D hologram panel
│   ├── waveform.py                  # Reactive audio waveform
│   ├── approval_banner.py           # Dangerous action confirmation
│   ├── protocol_buttons.py          # Protocol quick-launch buttons
│   ├── telemetry_gauges.py          # CPU/RAM/GPU/Temp gauges
│   ├── neural_transcript.py         # Live voice conversation panel
│   ├── global_surveillance.py       # Airspace, weather, seismic, network
│   ├── user_telemetry.py            # Fatigue, vitals, sleep debt
│   └── templates/
│       └── hologram_base.html       # Three.js 3D renderer template
│
├── systemd/
│   ├── jarvis-core.service          # Main JARVIS daemon
│   ├── jarvis-sentinel.service      # Watchdog daemon
│   ├── jarvis-visual-memory.service # Screenshot OCR daemon
│   └── install_services.sh          # Copies and enables all units
│
├── i3/
│   ├── jarvis_i3_config.snippet     # i3 keybindings for JARVIS
│   └── jarvis_i3_autostart.sh       # Auto-launch on i3 start
│
├── dashboard/                       # Remote phone dashboard
│
└── config/
    ├── api_keys.json                # Gemini, HA, OpenSky, etc.
    ├── permissions.json             # Permission level config
    ├── safety_rules.json            # Approval gates
    ├── models.json                  # AI model routing config
    ├── arch_specific.json           # Arch paths, devices, interfaces
    ├── identity.json                # JARVIS personality config
    └── long_term.json               # Persistent user/system knowledge
```

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/ekanshpanda/Mark-LII.git ~/Mark-LII
cd ~/Mark-LII

# 2. Install ALL Arch dependencies
sudo bash install_stark_deps.sh

# 3. Enable systemd services
bash systemd/install_services.sh

# 4. Add i3 keybindings
cat i3/jarvis_i3_config.snippet >> ~/.config/i3/config
chmod +x i3/rofi_jarvis.sh i3/jarvis_i3_autostart.sh
i3-msg reload

# 5. Configure API keys
# Edit config/api_keys.json with your Gemini key

# 6. Launch
python3 main.py
# OR press Super+Shift+J in i3
# Toggle HUD: Super+J
```

---

## ⚡ Environment Details

<details>
<summary><strong>Target Platform</strong></summary>

- **OS:** Arch Linux (primary)
- **Window Manager:** i3wm
- **Display Server:** X11
- **Init System:** systemd (user services)
- **Package Manager:** pacman + yay (AUR)
- **Kernel:** Linux (direct `/proc`, `/sys`, `/dev` access)

</details>

<details>
<summary><strong>Key Native Dependencies</strong></summary>

| Tool | Purpose |
|---|---|
| `i3-msg` | Window tree, workspaces, focus, layout |
| `xdotool` | Input simulation, window focus |
| `xclip` / `xsel` | Clipboard |
| `scrot` / `maim` | Screenshots |
| `systemctl` | Service/timer/journal control |
| `nmcli` | WiFi, network connections |
| `pactl` / `pw-cli` | Audio devices |
| `brightnessctl` | Display brightness |
| `iptables` / `nftables` | Firewall, network lockdown |
| `lm_sensors` | Hardware temperature |
| `pacman` / `yay` | Package management |
| `snapper` | Btrfs snapshots |
| `notify-send` / `dunst` | Desktop notifications |
| `rofi` / `dmenu` | Launcher overlay |
| `Xvfb` | Virtual display for shadow browser |

</details>

<details>
<summary><strong>Python Dependencies</strong></summary>

```
PyQt6, PyQt6-WebEngine
google-genai, google-generativeai
playwright, browser-use
chromadb, sentence-transformers
psutil, GPUtil, pynvml
scapy, frida-tools
docker, apscheduler, watchdog
pynput, evdev, mediapipe
yt-dlp, pyserial, python-xlib, i3ipc
requests, httpx, aiohttp, beautifulsoup4, lxml
pydantic, cryptography, genanki, python-pptx
```

</details>

---

## 📋 Requirements

| Requirement | Details |
| --- | --- |
| **OS** | Arch Linux (primary), Debian/Fedora/macOS/Windows (fallback) |
| **Python** | 3.11 or 3.12 |
| **i3wm** | Required for full Arch-native experience |
| **Microphone** | Required for voice interaction |
| **Speakers** | Required for voice replies |
| **API Key** | Free Gemini API key (`config/api_keys.json`) |
| **Docker** | Required for House Party Protocol and sandbox execution |
| **GPU** | NVIDIA recommended for hardware agent telemetry |

---

## 🛡️ Security Model

- **Permission Levels:** PUBLIC < USER < ADMIN < ROOT
- **Confirmation Gate:** Shutdown, reboot, WiFi toggle, network lockdown require UI-issued confirmation tokens — the model cannot forge them
- **Sandbox Required:** Shell execution and code running are sandboxed via Docker
- **Encrypted Backup:** MatrixSync uses Fernet encryption for consciousness backup
- **Audit Log:** Every action is logged with timestamp, params, result, and user

---

## ⚠️ License

Personal and non-commercial use only.
Licensed under **[Creative Commons BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)**.

---

## 👤 Author

Engineered by **[ekanshpanda](https://ekanshpanda.vercel.app)**.

JARVIS NEXUS is the definitive Arch Linux + i3wm implementation of the Stark OS blueprint. Every single power mapped to a real Linux command, a real Python file, a real systemd service, a real i3 keybinding. No abstractions. No compromises. Pure Arch.
