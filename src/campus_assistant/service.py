"""Running `campus serve` in the background as a systemd user service, and web UI build checks."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

from .config import Config

UNIT_NAME = "campus-assistant.service"
REPO_ROOT = Path(__file__).resolve().parents[2]


def unit_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "systemd" / "user" / UNIT_NAME


def unit_text(python: str = sys.executable, workdir: Path = REPO_ROOT) -> str:
    # Tied to the graphical session: it needs DISPLAY/WAYLAND_DISPLAY to open the Brightspace sign-in
    # window, and should stop when you log out. Everything it starts (Chromium during syncs) lives in
    # the unit's cgroup, so stopping the unit stops all of it; TasksMax caps threads+processes.
    exe = f'"{python}"' if " " in python else python
    return f"""[Unit]
Description=Campus Assistant (local API, web UI, Brightspace sync)
Documentation=file://{workdir}/README.md
PartOf=graphical-session.target
After=graphical-session.target
StartLimitIntervalSec=300
StartLimitBurst=10

[Service]
Type=simple
ExecStart={exe} -m campus_assistant.cli serve
WorkingDirectory={workdir}
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=30
KillMode=control-group
TimeoutStopSec=15
TasksMax=256

[Install]
WantedBy=graphical-session.target
"""


def _systemctl(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *args], check=check, text=True, capture_output=True)


def _require_systemd() -> bool:
    if sys.platform != "linux" or not shutil.which("systemctl"):
        print("systemd user services are only available on Linux. Run `campus serve` from your "
              "desktop's autostart instead.", file=sys.stderr)
        return False
    return True


def installed() -> bool:
    return unit_path().exists()


def install(cfg: Config, start: bool = True) -> int:
    if not _require_systemd():
        return 1
    path = unit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(unit_text())
    _systemctl("daemon-reload")
    _systemctl("reset-failed", UNIT_NAME, check=False)  # manual restarts count toward the start limit
    _systemctl("enable", *(["--now"] if start else []), UNIT_NAME)
    if start:
        _systemctl("restart", UNIT_NAME)  # pick up a changed unit / new code if it was already running
    print(f"Installed {path}")
    print(f"{'Started; ' if start else ''}starts automatically when you log in to your desktop.")
    ui = ui_state(cfg)
    print(f"Web UI: {cfg.base_url}/ui/" if ui == "ok" else ui_hint(ui))
    return 0


def uninstall() -> int:
    if not _require_systemd():
        return 1
    _systemctl("disable", "--now", UNIT_NAME, check=False)
    unit_path().unlink(missing_ok=True)
    _systemctl("daemon-reload")
    print("Service stopped and removed.")
    return 0


def restart_if_installed() -> None:
    if installed() and shutil.which("systemctl"):
        _systemctl("reset-failed", UNIT_NAME, check=False)
        _systemctl("restart", UNIT_NAME, check=False)


def exec_status() -> int:
    if not _require_systemd():
        return 1
    os.execvp("systemctl", ["systemctl", "--user", "status", "--no-pager", UNIT_NAME])


def exec_logs(follow: bool) -> int:
    if not _require_systemd():
        return 1
    os.execvp("journalctl", ["journalctl", "--user", "-u", UNIT_NAME, "-n", "100", "--no-pager",
                             *(["-f"] if follow else [])])


# ── Is the server already running? ──────────────────────────────────────────

def server_running(cfg: Config) -> bool:
    try:
        return httpx.get(f"{cfg.base_url}/health", timeout=0.5).status_code == 200
    except httpx.HTTPError:
        return False


# ── Web UI build ────────────────────────────────────────────────────────────

def ui_state(cfg: Config) -> str:
    """ok | missing | stale (sources newer than the build, only checked in a source checkout)."""
    index = cfg.web_dist / "index.html"
    if not index.exists():
        return "missing"
    web = cfg.web_dist.parent
    sources = [web / "index.html", web / "package.json", web / "vite.config.ts",
               *(p for d in (web / "src", web / "public") if d.is_dir() for p in d.rglob("*") if p.is_file())]
    built = index.stat().st_mtime
    return "stale" if any(p.exists() and p.stat().st_mtime > built for p in sources) else "ok"


def ui_hint(state: str) -> str:
    return {
        "missing": "Web UI not built — run ./setup.sh (or `cd web && npm ci && npm run build`).",
        "stale": "Web UI build is older than its sources — run `cd web && npm run build` (no restart needed).",
    }.get(state, "")
