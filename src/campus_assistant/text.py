"""Small text helpers."""

import re
from html.parser import HTMLParser

_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    p = _TextExtractor()
    p.feed(html)
    p.close()
    text = "".join(p.parts).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def rich_text(rt: dict | None) -> str:
    """Brightspace RichText {Text, Html} → plain text."""
    if not rt:
        return ""
    return (rt.get("Text") or "").strip() or html_to_text(rt.get("Html"))


def safe_filename(name: str, limit: int = 120) -> str:
    name = re.sub(r"[^\w.\- ]+", "_", name).strip(" ._")
    return (name or "file")[:limit]


_URL = re.compile(r"https?://[^\s<>\"')\]]+")
# Query parameters worth keeping (they identify the target, not the click).
_KEEP_PARAMS = {"id", "ou", "db", "qi", "v", "p", "q", "page", "form", "eventid", "event"}


def tidy_url(url: str, max_len: int = 150) -> str:
    """Unwrap Outlook safelinks, drop tracking query strings, cap the length."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    if parts.netloc.endswith("safelinks.protection.outlook.com"):
        inner = dict(parse_qsl(parts.query)).get("url")
        if inner:
            parts = urlsplit(inner)  # parse_qsl has already decoded it
    kept = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() in _KEEP_PARAMS]
    out = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))
    return out if len(out) <= max_len else out[: max_len - 1] + "…"


def tidy_urls(text: str) -> str:
    """Shorten every URL in text (LLM input: tracking links waste context)."""
    return _URL.sub(lambda m: tidy_url(m.group(0)), text)
