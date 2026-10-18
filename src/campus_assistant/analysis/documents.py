"""Plain text from downloaded course files (cached next to the file)."""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

TEXT_SUFFIXES = {".txt", ".md", ".csv", ".py", ".json", ".rtf"}


def _pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n\n".join(f"[page {i + 1}]\n{(p.extract_text() or '').strip()}" for i, p in enumerate(reader.pages))


def _docx(path: Path) -> str:
    import docx

    doc = docx.Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(parts)


def _pptx(path: Path) -> str:
    from pptx import Presentation

    out = []
    for i, slide in enumerate(Presentation(str(path)).slides, 1):
        texts = [s.text_frame.text.strip() for s in slide.shapes if s.has_text_frame and s.text_frame.text.strip()]
        if texts:
            out.append(f"[slide {i}]\n" + "\n".join(texts))
    return "\n\n".join(out)


def _ipynb(path: Path) -> str:
    nb = json.loads(path.read_text(errors="replace"))
    return "\n\n".join("".join(c.get("source") or []) for c in nb.get("cells", []))


def _html(path: Path) -> str:
    from ..text import html_to_text

    return html_to_text(path.read_text(errors="replace"))


EXTRACTORS = {".pdf": _pdf, ".docx": _docx, ".pptx": _pptx, ".ipynb": _ipynb, ".html": _html, ".htm": _html}


def extract_text(path: str | Path) -> str:
    """Extracted text, cached as <file>.txt-extract; '' if unsupported or unreadable."""
    path = Path(path)
    cache = path.with_name(path.name + ".txt-extract")
    if cache.exists() and cache.stat().st_mtime >= path.stat().st_mtime:
        return cache.read_text(errors="replace")
    suffix = path.suffix.lower()
    try:
        if suffix in EXTRACTORS:
            text = EXTRACTORS[suffix](path)
        elif suffix in TEXT_SUFFIXES:
            text = path.read_text(errors="replace")
        else:
            return ""
    except Exception as err:
        log.warning("Could not extract %s: %s", path.name, err)
        text = ""
    cache.write_text(text)
    return text
