#!/usr/bin/env python3
"""Bundle the Brightspace MCP bridge and required backend, without local state."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
NAME = "brightspace-mcp"


def source_files(root: Path) -> list[Path]:
    # Deliberate allowlist: never archive the whole working tree or user data.
    files = [root / name for name in (
        "pyproject.toml", "uv.lock", ".python-version", "README.md",
        "docs/brightspace-mcp.md", "examples/brightspace.mcp.json",
    )]
    files.extend((root / "src/campus_assistant").rglob("*.py"))
    files.append(root / "src/campus_assistant/py.typed")
    for path in files:
        if not path.is_file() or path.is_symlink() or any(
            (root / parent).is_symlink() for parent in path.relative_to(root).parents
        ):
            raise ValueError(f"Missing file or symlink in source bundle: {path}")
    return sorted(files)


def build_bundle(root: Path = ROOT) -> Path:
    files = source_files(root)
    destination = root / "dist" / f"{NAME}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, f"{NAME}/{path.relative_to(root).as_posix()}")
        archive.write(root / "docs/brightspace-mcp.md", f"{NAME}/START-HERE.md")
    return destination


if __name__ == "__main__":
    print(build_bundle())
