#!/usr/bin/env bash
# Set up (or update, after `git pull`) campus-assistant. Safe to re-run.
#   ./setup.sh             install deps, browser, build the web UI; restart the service if installed
#   ./setup.sh --service   ...and install/start the background service (Linux, systemd)
set -euo pipefail
cd "$(dirname "$0")"

want_service=0
for arg in "$@"; do
  case "$arg" in
    --service) want_service=1 ;;
    -h|--help) sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing '$1'. $2" >&2; exit 1; }
}

need uv   "Install it: https://docs.astral.sh/uv/getting-started/installation/"
need node "Install Node.js 20 or newer (e.g. via your package manager or https://nodejs.org)."
need npm  "npm comes with Node.js."
node -e 'process.exit(+process.versions.node.split(".")[0] < 20 ? 1 : 0)' \
  || { echo "Node.js 20+ required (found $(node -v))." >&2; exit 1; }

step "Python environment (uv sync)"
uv sync

step "Browser for Brightspace sync (Playwright Chromium)"
# Without system libraries this may fail on minimal distros; see `uv run playwright install --help` (--with-deps).
uv run playwright install chromium

step "Web UI (npm ci && npm run build)"
(cd web && npm ci --no-fund && npm run build)

if [[ $want_service == 1 ]]; then
  step "Background service"
  uv run campus service install
elif [[ -f "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/campus-assistant.service" ]]; then
  step "Restarting background service to pick up changes"
  uv run campus service restart
fi

cat <<'EOF'

Done. Next:
  uv run campus login              # sign in to Brightspace once (opens a browser window)
  uv run campus service install    # run in the background from now on (or: uv run campus serve)
  open http://127.0.0.1:8765/ui/   # Chrome/Edge: install icon in the address bar → standalone app window
EOF
