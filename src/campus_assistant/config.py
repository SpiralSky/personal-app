"""Runtime configuration, read from environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _default_data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "campus-assistant"


@dataclass
class Config:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("CAMPUS_DATA_DIR") or _default_data_dir()))
    # Brightspace instances to sync. splms = Singapore Polytechnic, lms = POLITEMall shared modules.
    bs_hosts: list[str] = field(
        default_factory=lambda: os.environ.get("CAMPUS_BS_HOSTS", "splms.polite.edu.sg,lms.polite.edu.sg").split(",")
    )
    # Courses whose name matches this regex are skipped entirely (e.g. "COVID-19|WSH").
    bs_skip_courses: str | None = field(default_factory=lambda: os.environ.get("CAMPUS_BS_SKIP") or None)
    bs_request_delay: float = float(os.environ.get("CAMPUS_BS_DELAY", "0.25"))
    # Chromium channel for Playwright: "" = Playwright's bundled Chromium, or "chrome" / "msedge".
    browser_channel: str = os.environ.get("CAMPUS_BROWSER_CHANNEL", "")
    sync_interval_min: int = int(os.environ.get("CAMPUS_SYNC_INTERVAL_MIN", "60"))
    max_file_mb: int = int(os.environ.get("CAMPUS_MAX_FILE_MB", "50"))
    host: str = os.environ.get("CAMPUS_API_HOST", "127.0.0.1")
    port: int = int(os.environ.get("CAMPUS_API_PORT", "8765"))
    # Built web UI (`cd web && npm run build`), served at /ui/ when present.
    web_dist: Path = field(default_factory=lambda: Path(
        os.environ.get("CAMPUS_WEB_DIST") or Path(__file__).resolve().parents[2] / "web" / "dist"))

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "campus.db"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @property
    def browser_profile(self) -> Path:
        return self.data_dir / "browser-profile"

    @property
    def cookie_jar(self) -> Path:
        # Playwright storage_state, which (unlike the profile) keeps session cookies.
        return self.data_dir / "session-state.json"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
