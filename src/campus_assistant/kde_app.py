"""Entry point shim — delegates to kde/app/campus_kde.py."""
import importlib.util
import sys
from pathlib import Path


def main() -> None:
    kde_path = Path(__file__).resolve().parents[2] / "kde" / "app" / "campus_kde.py"
    spec = importlib.util.spec_from_file_location("campus_kde", kde_path)
    if spec is None or spec.loader is None:
        sys.exit(f"campus-kde: cannot find {kde_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    mod.main()
