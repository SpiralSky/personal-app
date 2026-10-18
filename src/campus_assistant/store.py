"""SQLite store for ingested items, with change tracking.

Every upsert hashes the item's meaningful fields. A new hash means the item
changed: the previous version goes to `item_history` and a row is added to
`changes` naming the fields that differ (so "due date moved" is queryable).
Items that disappear from a source are soft-deleted, never dropped.
"""

import hashlib
import json
import sqlite3
import threading
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .models import ItemIn

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id            TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    kind          TEXT NOT NULL,
    external_id   TEXT NOT NULL,
    title         TEXT NOT NULL DEFAULT '',
    body          TEXT NOT NULL DEFAULT '',
    url           TEXT,
    course_id     TEXT,
    course_name   TEXT,
    occurred_at   TEXT,
    due_at        TEXT,
    starts_at     TEXT,
    ends_at       TEXT,
    data          TEXT NOT NULL DEFAULT '{}',
    content_hash  TEXT NOT NULL,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    deleted_at    TEXT
);
CREATE INDEX IF NOT EXISTS items_source_kind ON items(source, kind);
CREATE INDEX IF NOT EXISTS items_course ON items(source, course_id);
CREATE INDEX IF NOT EXISTS items_due ON items(due_at) WHERE due_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS item_history (
    item_id      TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    snapshot     TEXT NOT NULL,
    replaced_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS item_history_item ON item_history(item_id);

CREATE TABLE IF NOT EXISTS changes (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id TEXT NOT NULL,
    at      TEXT NOT NULL,
    change  TEXT NOT NULL,          -- created | updated | removed | restored
    fields  TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS changes_at ON changes(at);

-- LLM / rule outputs per item and task ("triage", "brief").
CREATE TABLE IF NOT EXISTS analyses (
    item_id     TEXT NOT NULL,
    task        TEXT NOT NULL,
    input_hash  TEXT NOT NULL,          -- item content + prompt version (+ related files)
    provider    TEXT NOT NULL,          -- claude | local | rules
    model       TEXT,
    result      TEXT,                   -- JSON, NULL on error
    error       TEXT,
    usage       TEXT,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (item_id, task)
);

-- The user's own corrections; they override the model and become training data later.
CREATE TABLE IF NOT EXISTS labels (
    item_id    TEXT PRIMARY KEY,
    category   TEXT,
    priority   TEXT,
    note       TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    item_id         TEXT PRIMARY KEY,
    path            TEXT NOT NULL,
    filename        TEXT NOT NULL,
    content_type    TEXT,
    size            INTEGER,
    sha256          TEXT,
    source_modified TEXT,
    fetched_at      TEXT NOT NULL
);
"""

# Fields whose changes are reported by name; "data.<key>" covers the rest.
TRACKED = ("title", "body", "url", "course_name", "occurred_at", "due_at", "starts_at", "ends_at")


ANY_COURSE = object()


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# data keys excluded from change detection: "raw" (full source object) and
# "meta" (bookkeeping such as where a file lives).
UNHASHED_DATA = ("raw", "meta")


def _hashable(item: dict[str, Any]) -> dict[str, Any]:
    data = {k: v for k, v in item["data"].items() if k not in UNHASHED_DATA}
    return {**{f: item[f] for f in TRACKED}, "data": data}


def content_hash(item: dict[str, Any]) -> str:
    blob = json.dumps(_hashable(item), sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def changed_fields(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    a, b = _hashable(old), _hashable(new)
    out = [f for f in TRACKED if a[f] != b[f]]
    for key in sorted(set(a["data"]) | set(b["data"])):
        if a["data"].get(key) != b["data"].get(key):
            out.append(f"data.{key}")
    return out


class Store:
    def __init__(self, path: Path | str):
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.lock = threading.RLock()

    def close(self) -> None:
        self.conn.close()

    # ── Writing ──────────────────────────────────────────────────────────────
    def upsert(self, item: ItemIn, now: str | None = None) -> str:
        """Insert or update one item. Returns created | updated | restored | unchanged."""
        now = now or now_iso()
        new = item.model_dump()
        new_hash = content_hash(new)
        data_json = json.dumps(new["data"], ensure_ascii=False, default=str)
        with self.lock:
            row = self.conn.execute("SELECT * FROM items WHERE id = ?", (item.id,)).fetchone()
            if row is None:
                self.conn.execute(
                    """INSERT INTO items (id, source, kind, external_id, title, body, url, course_id, course_name,
                       occurred_at, due_at, starts_at, ends_at, data, content_hash, first_seen, last_seen, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (item.id, item.source, item.kind, item.external_id, item.title, item.body, item.url,
                     item.course_id, item.course_name, item.occurred_at, item.due_at, item.starts_at,
                     item.ends_at, data_json, new_hash, now, now, now),
                )
                self._log(item.id, now, "created", [])
                return "created"

            was_deleted = row["deleted_at"] is not None
            if row["content_hash"] == new_hash and not was_deleted:
                # Unchanged, but refresh "raw"/"meta" (not hashed) and last_seen.
                self.conn.execute("UPDATE items SET last_seen = ?, data = ? WHERE id = ?", (now, data_json, item.id))
                return "unchanged"

            old = self._row_dict(row)
            fields = changed_fields(old, new)
            if row["content_hash"] != new_hash:
                self.conn.execute(
                    "INSERT INTO item_history (item_id, content_hash, snapshot, replaced_at) VALUES (?,?,?,?)",
                    (item.id, row["content_hash"], json.dumps(old, ensure_ascii=False, default=str), now),
                )
            self.conn.execute(
                """UPDATE items SET title=?, body=?, url=?, course_id=?, course_name=?, occurred_at=?, due_at=?,
                   starts_at=?, ends_at=?, data=?, content_hash=?, last_seen=?, updated_at=?, deleted_at=NULL
                   WHERE id = ?""",
                (item.title, item.body, item.url, item.course_id, item.course_name, item.occurred_at, item.due_at,
                 item.starts_at, item.ends_at, data_json, new_hash, now, now, item.id),
            )
            change = "restored" if was_deleted else "updated"
            self._log(item.id, now, change, fields)
            return change

    def upsert_many(self, items: Iterable[ItemIn], now: str | None = None) -> Counter:
        now = now or now_iso()
        counts: Counter = Counter()
        with self.lock:
            self.conn.execute("BEGIN")
            try:
                for item in items:
                    counts[self.upsert(item, now)] += 1
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
        return counts

    def mark_missing(self, source: str, kind: str, course_id: "str | None | object", seen_ids: set[str],
                     now: str | None = None) -> int:
        """Soft-delete items of this source/kind/course that a complete fetch no longer returned.

        Pass ANY_COURSE as course_id to consider every course of the source.
        """
        now = now or now_iso()
        sql = "SELECT id FROM items WHERE source = ? AND kind = ? AND deleted_at IS NULL"
        args: list[Any] = [source, kind]
        if course_id is not ANY_COURSE:
            sql += " AND course_id IS ?"
            args.append(course_id)
        with self.lock:
            rows = self.conn.execute(sql, args).fetchall()
            gone = [r["id"] for r in rows if r["id"] not in seen_ids]
            for item_id in gone:
                self.conn.execute("UPDATE items SET deleted_at = ? WHERE id = ?", (now, item_id))
                self._log(item_id, now, "removed", [])
            return len(gone)

    def record_file(self, item_id: str, path: str, filename: str, content_type: str | None, size: int,
                    sha256: str, source_modified: str | None) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT INTO files (item_id, path, filename, content_type, size, sha256, source_modified, fetched_at)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(item_id) DO UPDATE SET path=excluded.path, filename=excluded.filename,
                     content_type=excluded.content_type, size=excluded.size, sha256=excluded.sha256,
                     source_modified=excluded.source_modified, fetched_at=excluded.fetched_at""",
                (item_id, path, filename, content_type, size, sha256, source_modified, now_iso()),
            )

    # ── Analyses and labels ──────────────────────────────────────────────────
    def get_analysis(self, item_id: str, task: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM analyses WHERE item_id = ? AND task = ?", (item_id, task)).fetchone()
        return self._analysis_dict(row) if row else None

    def analyses_for(self, item_id: str) -> dict[str, dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM analyses WHERE item_id = ?", (item_id,)).fetchall()
        return {r["task"]: self._analysis_dict(r) for r in rows}

    @staticmethod
    def _analysis_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        for k in ("result", "usage"):
            d[k] = json.loads(d[k]) if d[k] else None
        return d

    def save_analysis(self, item_id: str, task: str, input_hash: str, provider: str, model: str | None,
                      result: dict | None = None, error: str | None = None, usage: dict | None = None) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT INTO analyses (item_id, task, input_hash, provider, model, result, error, usage, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(item_id, task) DO UPDATE SET input_hash=excluded.input_hash, error=excluded.error,
                     -- A failed attempt (e.g. LLM server down) keeps the previous result; the error still
                     -- marks it for retry.
                     provider=IIF(excluded.result IS NULL, analyses.provider, excluded.provider),
                     model=IIF(excluded.result IS NULL, analyses.model, excluded.model),
                     usage=IIF(excluded.result IS NULL, analyses.usage, excluded.usage),
                     created_at=IIF(excluded.result IS NULL AND analyses.result IS NOT NULL,
                                    analyses.created_at, excluded.created_at),
                     result=COALESCE(excluded.result, analyses.result)""",
                (item_id, task, input_hash, provider, model,
                 json.dumps(result, ensure_ascii=False) if result is not None else None,
                 error, json.dumps(usage) if usage else None, now_iso()),
            )

    def set_label(self, item_id: str, category: str | None, priority: str | None, note: str | None) -> None:
        with self.lock:
            self.conn.execute(
                """INSERT INTO labels (item_id, category, priority, note, created_at) VALUES (?,?,?,?,?)
                   ON CONFLICT(item_id) DO UPDATE SET category=excluded.category, priority=excluded.priority,
                     note=excluded.note, created_at=excluded.created_at""",
                (item_id, category, priority, note, now_iso()),
            )

    def get_label(self, item_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM labels WHERE item_id = ?", (item_id,)).fetchone()
        return dict(row) if row else None

    def triaged(self, *, since: str | None = None, until: str | None = None,
                categories: list[str] | None = None, priorities: list[str] | None = None,
                kinds: list[str] | None = None, include_ignored: bool = False, needs_review: bool | None = None,
                limit: int = 200) -> list[dict[str, Any]]:
        """Messages with their triage; the user's label wins over the model's."""
        sql = """SELECT i.id, i.source, i.kind, i.title, i.url, i.course_name, i.occurred_at,
                        json_extract(i.data, '$.from') AS sender,
                        a.result AS result, a.provider, a.model, a.error,
                        l.category AS label_category, l.priority AS label_priority, l.note AS label_note
                 FROM items i
                 JOIN analyses a ON a.item_id = i.id AND a.task = 'triage'
                 LEFT JOIN labels l ON l.item_id = i.id
                 WHERE i.deleted_at IS NULL AND a.result IS NOT NULL"""
        args: list[Any] = []
        if since:
            sql += " AND i.occurred_at >= ?"
            args.append(since)
        if until:
            sql += " AND i.occurred_at <= ?"
            args.append(until)
        if kinds:
            placeholders = ", ".join("?" * len(kinds))
            sql += f" AND i.kind IN ({placeholders})"
            args.extend(kinds)
        sql += " ORDER BY i.occurred_at DESC"
        out = []
        for r in self.conn.execute(sql, args).fetchall():
            d = dict(r)
            res = json.loads(d.pop("result"))
            d["triage"] = res
            d["category"] = d["label_category"] or res.get("category")
            d["priority"] = d["label_priority"] or res.get("priority")
            d["corrected"] = bool(d["label_category"] or d["label_priority"])
            d["decided_by"] = res.get("decided_by")
            # Needs the user's eye: the classifier was unsure and nobody has labelled it yet.
            d["needs_review"] = bool(res.get("needs_review")) and not d["corrected"]
            if needs_review is not None and d["needs_review"] != needs_review:
                continue
            if categories and d["category"] not in categories:
                continue
            if priorities and d["priority"] not in priorities:
                continue
            if not include_ignored and d["priority"] == "ignore" and not (priorities and "ignore" in priorities):
                continue
            out.append(d)
            if len(out) >= limit:
                break
        return out

    def get_meta(self, key: str, default: Any = None) -> Any:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set_meta(self, key: str, value: Any) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value, default=str)),
            )

    def _log(self, item_id: str, at: str, change: str, fields: list[str]) -> None:
        self.conn.execute(
            "INSERT INTO changes (item_id, at, change, fields) VALUES (?,?,?,?)",
            (item_id, at, change, json.dumps(fields)),
        )

    # ── Reading ──────────────────────────────────────────────────────────────
    @staticmethod
    def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        if "data" in d:
            d["data"] = json.loads(d["data"])
        return d

    def get(self, item_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return self._row_dict(row) if row else None

    def file_for(self, item_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM files WHERE item_id = ?", (item_id,)).fetchone()
        return dict(row) if row else None

    def history(self, item_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT content_hash, snapshot, replaced_at FROM item_history WHERE item_id = ? ORDER BY replaced_at",
            (item_id,),
        ).fetchall()
        return [{**dict(r), "snapshot": json.loads(r["snapshot"])} for r in rows]

    def query(self, *, source: str | None = None, kind: str | None = None, course_id: str | None = None,
              q: str | None = None, include_deleted: bool = False, limit: int = 100,
              offset: int = 0) -> list[dict[str, Any]]:
        where, args = [], []
        if source:
            # "brightspace" matches "brightspace:splms" etc.
            where.append("(source = ? OR source LIKE ?)")
            args += [source, f"{source}:%"]
        if kind:
            where.append("kind = ?")
            args.append(kind)
        if course_id:
            where.append("course_id = ?")
            args.append(course_id)
        if q:
            where.append("(title LIKE ? OR body LIKE ?)")
            args += [f"%{q}%", f"%{q}%"]
        if not include_deleted:
            where.append("deleted_at IS NULL")
        sql = "SELECT * FROM items"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY COALESCE(occurred_at, updated_at) DESC LIMIT ? OFFSET ?"
        rows = self.conn.execute(sql, (*args, limit, offset)).fetchall()
        return [self._row_dict(r) for r in rows]

    def upcoming(self, start: str, end: str, kinds: tuple[str, ...] = ("assignment", "quiz", "content", "event")
                 ) -> list[dict[str, Any]]:
        marks = ",".join("?" * len(kinds))
        rows = self.conn.execute(
            f"""SELECT * FROM items WHERE deleted_at IS NULL AND due_at IS NOT NULL
                AND due_at >= ? AND due_at <= ? AND kind IN ({marks}) ORDER BY due_at""",
            (start, end, *kinds),
        ).fetchall()
        return [self._row_dict(r) for r in rows]

    def changes(self, since: str | None = None, limit: int = 200,
                include_created: bool = True) -> list[dict[str, Any]]:
        sql = """SELECT c.id, c.item_id, c.at, c.change, c.fields, i.source, i.kind, i.title, i.course_name, i.due_at
                 FROM changes c LEFT JOIN items i ON i.id = c.item_id WHERE 1=1"""
        args: list[Any] = []
        if since:
            sql += " AND c.at > ?"
            args.append(since)
        if not include_created:
            sql += " AND c.change != 'created'"
        sql += " ORDER BY c.id DESC LIMIT ?"
        rows = self.conn.execute(sql, (*args, limit)).fetchall()
        return [{**dict(r), "fields": json.loads(r["fields"])} for r in rows]

    def stats(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT source, kind, COUNT(*) AS n FROM items WHERE deleted_at IS NULL GROUP BY source, kind ORDER BY source, kind"
        ).fetchall()
        return [dict(r) for r in rows]
