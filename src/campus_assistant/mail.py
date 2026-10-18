"""Mail from the Outlook (Prospect Mail fork) archive → ItemIn.

The fork pushes each message it archives to POST /ingest/email, as raw
RFC 822 MIME when it has it, else as the HTML body OWA rendered. The same
messages can be bulk-imported from the archive directory (`campus import-mail`).
Both paths derive external_id = sha1(EWS ItemId)[:16], which is the key the
fork's own index.json uses, so they never duplicate each other.
"""

import base64
import hashlib
import json
import logging
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .models import ItemIn, to_utc_iso
from .text import html_to_text

log = logging.getLogger(__name__)

SOURCE = "outlook"
MAX_BODY_CHARS = 100_000


class EmailIn(BaseModel):
    account: str | None = None
    item_id: str | None = None      # EWS ItemId; hashed into external_id
    key: str | None = None          # or the fork's index key (already hashed)
    folder: str | None = None
    received_at: str | None = None
    subject: str | None = None
    sender: str | None = None
    mime_base64: str | None = None
    html: str | None = None
    eml_path: str | None = None


class EmailBatch(BaseModel):
    messages: list[EmailIn]


def short_hash(item_id: str) -> str:
    """Same as the fork's parsers.shortHash."""
    return hashlib.sha1(item_id.encode()).hexdigest()[:16]


def _addresses(msg: EmailMessage, header: str) -> list[str]:
    values = msg.get_all(header) or []
    return [f"{name} <{addr}>" if name else addr for name, addr in getaddresses([str(v) for v in values]) if addr]


def _body_and_attachments(msg: EmailMessage) -> tuple[str, list[dict]]:
    attachments = []
    for part in msg.iter_attachments():
        try:
            size = len(part.get_payload(decode=True) or b"")
        except Exception:
            size = None
        attachments.append({"name": part.get_filename(), "type": part.get_content_type(), "size": size})
    body = ""
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is not None:
            content = part.get_content()
            body = html_to_text(content) if part.get_content_type() == "text/html" else content
    except Exception as err:
        log.debug("Could not decode body: %s", err)
    return body.strip()[:MAX_BODY_CHARS], attachments


def parse_mime(raw: bytes) -> dict[str, Any]:
    msg: EmailMessage = BytesParser(policy=policy.default).parsebytes(raw)  # type: ignore[assignment]
    body, attachments = _body_and_attachments(msg)
    date = None
    if msg["Date"]:
        try:
            date = to_utc_iso(parsedate_to_datetime(str(msg["Date"])))
        except Exception:
            pass
    sender = _addresses(msg, "From")
    return {
        "subject": str(msg["Subject"] or ""),
        "from": sender[0] if sender else None,
        "to": _addresses(msg, "To"),
        "cc": _addresses(msg, "Cc"),
        "reply_to": _addresses(msg, "Reply-To"),
        "date": date,
        "message_id": str(msg["Message-ID"] or "") or None,
        "in_reply_to": str(msg["In-Reply-To"] or "") or None,
        # Mailing-list / bulk signals, useful for classification later.
        "list_id": str(msg["List-Id"] or "") or None,
        "bulk": bool(msg["List-Unsubscribe"]) or str(msg["Precedence"] or "").lower() in ("bulk", "list"),
        "auto_submitted": str(msg["Auto-Submitted"] or "").lower() not in ("", "no"),
        "body": body,
        "attachments": attachments,
    }


def email_item(m: EmailIn) -> ItemIn:
    key = m.key or (short_hash(m.item_id) if m.item_id else None)
    if not key:
        raise ValueError("item_id or key is required")
    if m.mime_base64:
        p = parse_mime(base64.b64decode(m.mime_base64))
    elif m.eml_path and Path(m.eml_path).suffix == ".eml" and Path(m.eml_path).exists():
        p = parse_mime(Path(m.eml_path).read_bytes())
    else:
        p = {"subject": m.subject or "", "from": m.sender, "body": html_to_text(m.html)[:MAX_BODY_CHARS],
             "date": None, "to": [], "cc": [], "attachments": []}
    has_mime = bool(m.mime_base64) or bool(m.eml_path and m.eml_path.endswith(".eml"))
    data = {k: v for k, v in p.items() if k not in ("subject", "body", "date")}
    data.update({"folder": m.folder, "has_mime": has_mime,
                 # Where the message lives on disk; not a change to the message itself.
                 "meta": {"account": m.account, "eml_path": m.eml_path}})
    return ItemIn(
        source=SOURCE, kind="email", external_id=key, title=p["subject"] or m.subject or "",
        body=p["body"], occurred_at=m.received_at or p["date"], data=data,
    )


def iter_archive(root: Path):
    """Yield one EmailIn per message in a Prospect Mail archive directory.

    An item can appear under several account directories (the fork has named
    the same mailbox differently over time); only the copy from the most
    recently updated index is yielded.
    """
    latest: dict[str, EmailIn] = {}
    for index_path in sorted(root.glob("*/index.json"), key=lambda p: p.stat().st_mtime):
        for m in _iter_account(index_path):
            latest.pop(m.key, None)  # re-insert so order follows the winning copy
            latest[m.key] = m
    yield from latest.values()


def _iter_account(index_path: Path):
    account_dir = index_path.parent
    try:
        index = json.loads(index_path.read_text())
    except Exception as err:
        log.warning("Skipping %s: %s", index_path, err)
        return
    folders = index.get("folders") or {}
    for key, entry in (index.get("items") or {}).items():
        files = [account_dir / f for f in entry.get("files") or []]
        folder = (folders.get(entry.get("folderId")) or {}).get("name")
        eml = next((f for f in files if f.suffix == ".eml"), None)
        if eml:
            yield EmailIn(account=account_dir.name, key=key, folder=folder, eml_path=str(eml))
            continue
        html = next((f for f in files if f.suffix == ".html"), None)
        raw_json = next((f for f in files if f.suffix == ".json"), None)
        if not html or not html.exists():
            continue
        subject = sender = received = None
        if raw_json and raw_json.exists():
            try:
                raw = json.loads(raw_json.read_text())
                subject = raw.get("Subject")
                mb = (raw.get("From") or raw.get("Sender") or {}).get("Mailbox") or {}
                sender = mb.get("EmailAddress") or mb.get("Name")
                received = raw.get("DateTimeReceived") or raw.get("DateTimeSent")
            except Exception:
                pass
        yield EmailIn(account=account_dir.name, key=key, folder=folder, html=html.read_text(errors="replace"),
                      subject=subject, sender=sender, received_at=received, eml_path=str(html))
