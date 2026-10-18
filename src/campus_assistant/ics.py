"""Deadlines as an iCalendar feed, so they show up in any calendar app."""

from .store import now_iso


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines over 75 octets continue on the next line after a space."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode()
        if len(cur) + len(b) > 74:
            out.append(cur.decode())
            cur = b" "
        cur += b
    out.append(cur.decode())
    return "\r\n".join(out)


def _dt(iso: str) -> str:
    return iso.replace("-", "").replace(":", "")  # 2026-11-20T10:00:00Z → 20261120T100000Z


def build_ics(items: list[dict], name: str = "Campus deadlines") -> str:
    stamp = _dt(now_iso())
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//campus-assistant//EN", f"X-WR-CALNAME:{_esc(name)}",
             "CALSCALE:GREGORIAN"]
    for it in items:
        due = _dt(it["due_at"])
        course = it.get("course_name") or ""
        summary = f"{it['title']} ({course})" if course else it["title"]
        desc = "\n".join(x for x in (it["kind"].title(), it.get("url") or "", (it.get("body") or "")[:500]) if x)
        lines += ["BEGIN:VEVENT", f"UID:{_esc(it['id'])}@campus-assistant", f"DTSTAMP:{stamp}",
                  f"DTSTART:{due}", f"DTEND:{due}", f"SUMMARY:{_esc(summary)}", f"DESCRIPTION:{_esc(desc)}"]
        if it.get("url"):
            lines.append(f"URL:{it['url']}")
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:-P1D", f"DESCRIPTION:{_esc(summary)}", "END:VALARM",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"
