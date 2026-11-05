#!/usr/bin/env bash
# Install the Campus Assistant KDE integration:
#   - Plasma plasmoid (widget)
#   - .desktop launcher
#   - Optional: autostart entry for the tray app
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PLASMOID_DIR="$SCRIPT_DIR/plasmoid/org.campus-assistant.widget"
DESKTOP_SRC="$SCRIPT_DIR/app/personal-app.desktop"
APPLICATIONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

# ── 1. Install the plasmoid ────────────────────────────────────────────────────
echo "Installing Plasma widget..."
if command -v kpackagetool6 &>/dev/null; then
    # clean any stale/orphaned directory before install
    PLASMOID_DEST="${XDG_DATA_HOME:-$HOME/.local/share}/plasma/plasmoids/org.campus-assistant.widget"
    rm -rf "$PLASMOID_DEST"
    kpackagetool6 --type Plasma/Applet --install "$PLASMOID_DIR"
    echo "  Plasmoid installed (restart Plasma shell to pick it up)"
else
    echo "  kpackagetool6 not found — skipping plasmoid install"
fi

# ── 2. Install the .desktop launcher ──────────────────────────────────────────
echo "Installing .desktop launcher..."
mkdir -p "$APPLICATIONS_DIR"
python3 - "$DESKTOP_SRC" "$APPLICATIONS_DIR/personal-app.desktop" "$SCRIPT_DIR/app/launch.sh" <<'PY'
from pathlib import Path
import sys

source, destination, launcher = sys.argv[1:]
# Escape a quoted Desktop Entry Exec argument, including literal field-code markers.
launcher = launcher.replace('\\', '\\\\\\\\').replace('"', '\\\\"').replace('`', '\\\\`').replace('$', '\\\\$').replace('%', '%%')
Path(destination).write_text(Path(source).read_text().replace('@LAUNCHER@', launcher))
PY
echo "  Installed to $APPLICATIONS_DIR/personal-app.desktop"

# ── 3. Ensure campus-kde is on PATH (uv-managed venv) ─────────────────────────
echo "Syncing Python entry point..."
cd "$REPO_ROOT"
uv sync --quiet
BIN="$(uv run --no-sync python -c 'import sys, os; print(os.path.dirname(sys.executable))')"
if [[ ":$PATH:" != *":$BIN:"* ]]; then
    echo "  Note: add $BIN to your PATH to run campus-kde directly"
    echo "  Or run via: uv run campus-kde"
fi
echo "  campus-kde entry point available via: uv run campus-kde"

# ── 4. Optional autostart ──────────────────────────────────────────────────────
if [[ "${1:-}" == "--autostart" ]]; then
    echo "Installing autostart entry..."
    mkdir -p "$AUTOSTART_DIR"
    cat > "$AUTOSTART_DIR/campus-assistant-tray.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Campus Assistant Tray
Comment=Campus Assistant system tray (autostart)
Exec=uv --directory "$REPO_ROOT" run campus-kde
Icon=view-calendar-upcoming-events
X-GNOME-Autostart-enabled=true
StartupNotify=false
EOF
    echo "  Autostart entry installed — tray app will launch on next login"
fi

echo ""
echo "Done! To add the widget to your desktop: right-click the desktop → Add Widgets → search 'Campus Assistant'"
echo "To launch the app: campus-kde  (or 'uv run campus-kde' from $REPO_ROOT)"
