#!/usr/bin/env python3
"""Structural check for the spec corpus.

Enforces structure, not prose:

* status values are from the vocabulary in ``specs/README.md``;
* INDEX status counts and per-row statuses match the spec files;
* every required section is present (warnings while a spec is Draft,
  errors once it is Accepted);
* FR/AC/ADR/document IDs are unique and well-formed;
* acceptance criteria only reference FR IDs that exist in the same spec;
* relative links from spec files resolve.

Usage:
    python scripts/check_specs.py [--strict] [--root PATH]

Exit codes: 0 = clean (or warnings without ``--strict``), 1 = errors.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VALID_STATUSES = {
    "Baseline",
    "Draft",
    "In review",
    "Accepted",
    "Implementing",
    "Implemented",
    "Superseded",
}

# Section names are matched by keyword so a spec may use its own numbering.
REQUIRED_SECTIONS = {
    "Summary": ("summary",),
    "Functional rules": ("functional rules", "rules"),
    "Acceptance criteria": ("acceptance criteria",),
    "Edge cases": ("edge cases",),
    "Compatibility and migration": ("compatibility",),
    "Open questions": ("open questions",),
    "Change log": ("change log",),
}

# Sections that are allowed to be an explicit empty scaffold.
SCAFFOLD_HINTS = ("Scaffold:", "_Scaffold", "No entries yet", "to be completed")

STATUS_RE = re.compile(r"^\|\s*(?:\*\*)?Status(?:\*\*)?\s*\|\s*([^|]+?)\s*\|", re.M)
ID_RE = re.compile(r"^\|\s*(?:\*\*)?ID(?:\*\*)?\s*\|\s*([A-Z]+-\d+)\s*\|", re.M)
H2_RE = re.compile(r"^##\s+(.*)$", re.M)
FR_ID_RE = re.compile(r"\bFR-\d+(?:[-.]\d+)*\b")
AC_ID_RE = re.compile(r"\bAC-\d+(?:[-.]\d+)*\b")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def spec_files(features_dir: Path) -> list[Path]:
    return sorted(p for p in features_dir.glob("F-*.md") if p.name != "INDEX.md")


def check_status(path: Path, text: str, report: Report, root: Path) -> str | None:
    match = STATUS_RE.search(text)
    if not match:
        report.error(f"{rel(path, root)}: no metadata Status row")
        return None
    status = match.group(1).strip()
    if status not in VALID_STATUSES:
        report.error(
            f"{rel(path, root)}: invalid status {status!r} "
            f"(expected one of {', '.join(sorted(VALID_STATUSES))})"
        )
    return status


def check_doc_id(path: Path, text: str, report: Report, root: Path) -> str | None:
    match = ID_RE.search(text)
    expected = path.name.split("-", 2)[:2]
    expected_id = "-".join(expected)
    if not match:
        report.error(f"{rel(path, root)}: no metadata ID row")
        return None
    doc_id = match.group(1)
    if doc_id != expected_id:
        report.error(
            f"{rel(path, root)}: metadata ID {doc_id} does not match filename {path.name}"
        )
    return doc_id


def check_sections(
    path: Path, text: str, status: str | None, report: Report, root: Path
) -> None:
    headings = [h.strip("*_ ").lower() for h in H2_RE.findall(text)]
    body_by_heading: dict[str, str] = {}
    lines = text.splitlines()
    current: str | None = None
    buffer: list[str] = []
    for line in lines:
        if H2_RE.match(line):
            if current is not None:
                body_by_heading[current] = "\n".join(buffer)
            current = line.strip("#").strip("*_ ").lower()
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        body_by_heading[current] = "\n".join(buffer)

    missing: list[str] = []
    for label, keywords in REQUIRED_SECTIONS.items():
        heading = next((h for h in headings if any(k in h for k in keywords)), None)
        if heading is None:
            missing.append(label)
            continue
        if any(hint in body_by_heading.get(heading, "") for hint in SCAFFOLD_HINTS):
            report.warn(
                f"{rel(path, root)}: required section {label!r} is still an empty scaffold"
            )
            continue
        if not body_by_heading.get(heading, "").strip():
            report.warn(f"{rel(path, root)}: section {label!r} is empty")

    for label in missing:
        msg = f"{rel(path, root)}: missing required section {label!r}"
        if status == "Accepted":
            report.error(msg)
        else:
            report.warn(msg)


DEFINITION_RE = re.compile(
    r"^\s*(?:\||- )\s*(?:\*\*)?((?:FR|AC)-\d+(?:[-.]\d+)*)(?:\*\*)?", re.M
)


def check_ids(path: Path, text: str, report: Report, root: Path) -> None:
    definitions = DEFINITION_RE.findall(text)
    fr_ids = [i for i in definitions if i.startswith("FR-")]
    ac_ids = [i for i in definitions if i.startswith("AC-")]
    for kind, ids in (("FR", fr_ids), ("AC", ac_ids)):
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            report.warn(
                f"{rel(path, root)}: duplicate {kind} ids {', '.join(duplicates)}"
            )
    if not ac_ids:
        report.warn(f"{rel(path, root)}: no acceptance criteria")

    # AC rows that cite FRs must cite FRs defined in this spec.
    defined = set(fr_ids)
    for line in text.splitlines():
        if "|" in line and AC_ID_RE.search(line):
            for ref in FR_ID_RE.findall(line):
                if ref not in defined:
                    report.warn(
                        f"{rel(path, root)}: AC row references undefined {ref}"
                    )


def check_links(path: Path, text: str, report: Report, root: Path) -> None:
    for target in LINK_RE.findall(text):
        if target.startswith(("#",)) or "://" in target:
            continue
        target_path = target.split("#", 1)[0]
        if not target_path:
            continue
        if not (path.parent / target_path).resolve().exists():
            report.error(f"{rel(path, root)}: broken link {target}")


def parse_index_counts(index_text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status, count in re.findall(r"^\|\s*([A-Za-z ()]+?)\s*\|\s*(\d+)\s*\|", index_text, re.M):
        key = status.replace(" (needs spec)", "").strip()
        if key in VALID_STATUSES:
            counts[key] = int(count)
    return counts


def check_index(features_dir: Path, statuses: dict[str, str], report: Report, root: Path) -> None:
    index = features_dir / "INDEX.md"
    if not index.exists():
        report.error("specs/features/INDEX.md: missing")
        return
    text = read(index)
    counts = parse_index_counts(text)
    rows = re.findall(
        r"^\|\s*(F-\d{3})\s*\|[^|]*\|\s*([^|]+?)\s*\|", text, re.M
    )
    actual: dict[str, int] = {}
    for _doc_id, row_status in rows:
        if row_status.strip() in VALID_STATUSES:
            actual[row_status] = actual.get(row_status, 0) + 1
    for status in VALID_STATUSES:
        expected = actual.get(status, 0)
        declared = counts.get(status, 0)
        if declared != expected:
            report.error(
                f"specs/features/INDEX.md: status count for {status!r} is {declared}, expected {expected}"
            )

    for doc_id, row_status in rows:
        row_status = row_status.strip()
        file_status = statuses.get(doc_id)
        if file_status is None:
            if row_status != "Baseline":
                report.error(
                    f"specs/features/INDEX.md: {doc_id} has status {row_status!r} but no spec file"
                )
            continue
        if row_status != file_status:
            report.error(
                f"specs/features/INDEX.md: {doc_id} row says {row_status!r}, file says {file_status!r}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1], type=Path)
    args = parser.parse_args()
    root: Path = args.root
    features_dir = root / "specs" / "features"
    report = Report()

    if not features_dir.is_dir():
        print(f"error: {features_dir} not found", file=sys.stderr)
        return 1

    statuses: dict[str, str] = {}
    doc_ids: dict[str, Path] = {}
    for path in spec_files(features_dir):
        text = read(path)
        doc_id = check_doc_id(path, text, report, root)
        status = check_status(path, text, report, root)
        if status:
            statuses[path.stem[:5]] = status
        if doc_id:
            if doc_id in doc_ids:
                report.error(
                    f"{rel(path, root)}: duplicate document ID {doc_id} "
                    f"(also {rel(doc_ids[doc_id], root)})"
                )
            doc_ids[doc_id] = path
        check_sections(path, text, status, report, root)
        check_ids(path, text, report, root)
        check_links(path, text, report, root)

    check_index(features_dir, statuses, report, root)

    for warning in report.warnings:
        print(f"warning: {warning}")
    for error in report.errors:
        print(f"error: {error}")

    if report.errors or (args.strict and report.warnings):
        print(
            f"\n{len(report.errors)} error(s), {len(report.warnings)} warning(s)",
            file=sys.stderr,
        )
        return 1
    print(f"ok: {len(statuses)} specs checked, {len(report.warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
