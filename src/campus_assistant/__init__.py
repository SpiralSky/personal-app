"""Local study assistant backend: Brightspace sync + mail ingest + LLM triage."""

import os
from pathlib import Path


def _load_env_file() -> None:
    """KEY=VALUE lines from ~/.config/campus-assistant/env; real environment variables win.

    Runs at import time because config defaults are read from the environment.
    """
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    path = Path(os.environ.get("CAMPUS_ENV_FILE") or base / "campus-assistant" / "env")
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()
