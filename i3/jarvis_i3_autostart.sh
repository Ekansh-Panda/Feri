# JARVIS NEXUS — i3wm Autostart
# Add this to your ~/.config/i3/config to auto-launch JARVIS on i3 start:
#   exec_always --no-startup-id ~/Feri/scripts/feri start

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
FERI_BIN="$SCRIPT_DIR/../scripts/feri"

# Wait for i3 to fully initialize (X11 ready, workspaces loaded)
sleep 3

# Launch JARVIS
"$FERI_BIN" start
