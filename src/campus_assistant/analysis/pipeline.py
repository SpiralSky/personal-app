"""Triage of messages and briefs for upcoming tasks.

Each result is stored with an input hash (item content + prompt version, plus
related files for briefs); an item is only re-analysed when that changes, so
re-running is cheap. Errors are stored too and retried on the next run.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from email.utils import parseaddr
from typing import Any
from zoneinfo import ZoneInfo

from ..llm import LLMError, LLMRefused, Provider, provider_for
from ..llm.classify import LogprobClassifier, classifier_for
from ..store import Store
from ..text import tidy_urls
from .documents import extract_text
from .prompts import (BRIEF_SYSTEM, CATEGORY_OPTIONS, CATEGORY_QUESTION, PRIORITY_OPTIONS, PRIORITY_QUESTION,
                      PROMPT_VERSION, TRIAGE_SYSTEM, brief_user, triage_user)
from .schemas import MessageTriage, TaskBrief

log = logging.getLogger(__name__)

SGT = ZoneInfo("Asia/Singapore")
FMT = "%Y-%m-%dT%H:%M:%SZ"
CONCURRENCY = 4
TRIAGE_MAX_TOKENS = 900
# Per-run caps (a backlog is spread over several runs instead of saturating a local GPU).
MAX_CLASSIFY_PER_RUN = int(os.environ.get("CAMPUS_ANALYZE_MAX_CLASSIFY", "60"))
MAX_LLM_PER_RUN = int(os.environ.get("CAMPUS_ANALYZE_MAX_LLM", "15"))
# A classifier call is trusted when the winning option has at least this probability and
# enough of the next-token mass fell on option letters. Uncalibrated until checked against labels.
CLASSIFY_CUTOFF = float(os.environ.get("CAMPUS_CLASSIFY_CUTOFF", "0.8"))
MIN_COVERAGE = float(os.environ.get("CAMPUS_CLASSIFY_MIN_COVERAGE", "0.5"))
# Confidently low-value messages skip LLM extraction entirely.
LOW_VALUE_CATEGORIES = {"newsletter", "system", "other"}
# How far the classifier is trusted (CAMPUS_CLASSIFIER_MODE):
#   shadow  recorded only; the LLM decides everything
#   gate    decides only confident low-value messages (they skip the LLM); otherwise the LLM decides
#   trust   its confident calls override the LLM's category/priority
# Raw instruct-model probabilities are badly overconfident (most calls come out at ~1.00), so
# "trust" is only for after `campus eval` shows the cutoff holds on the user's labels.
CLASSIFIER_MODE = os.environ.get("CAMPUS_CLASSIFIER_MODE", "gate")

# Senders whose mail is an automated copy of something synced elsewhere or a ping.
SYSTEM_SENDERS = re.compile(r"@(?:splms|lms)\.polite\.edu\.sg$|@teams\.mail\.microsoft$", re.I)


def _hash(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:32]


def _today() -> str:
    return datetime.now(SGT).strftime("%A %Y-%m-%d %H:%M (+08:00)")


def _address(sender: str | None) -> str:
    return parseaddr(sender or "")[1].lower()


class Analyzer:
    def __init__(self, store: Store, triage_provider: Provider | None = None, brief_provider: Provider | None = None,
                 classifier: LogprobClassifier | None = None, use_defaults: bool = True):
        self.store = store
        self.triage_llm = triage_provider or (provider_for("triage") if use_defaults else None)
        self.brief_llm = brief_provider or (provider_for("brief") if use_defaults else None)
        self.classifier = classifier or (classifier_for() if use_defaults else None)
        self.sem = asyncio.Semaphore(CONCURRENCY)

    def my_addresses(self) -> set[str]:
        addrs = {a.strip().lower() for a in os.environ.get("CAMPUS_USER_EMAILS", "").split(",") if a.strip()}
        auth = self.store.get_meta("auth:brightspace", {}) or {}
        addrs |= {(v.get("user") or "").lower() for v in auth.values() if v.get("user")}
        return addrs

    # ── Triage ──────────────────────────────────────────────────────────────
    def triage_rule(self, item: dict, mine: set[str]) -> dict | None:
        """Cheap deterministic triage for mail that needs no model."""
        if item["kind"] != "email":
            return None
        sender = _address(item["data"].get("from"))
        base = {"actions": [], "dates": [], "opportunity": None, "links": []}
        if sender and sender in mine:
            return {**base, "category": "personal", "priority": "ignore", "summary": "Sent by you."}
        if SYSTEM_SENDERS.search(sender):
            return {**base, "category": "system", "priority": "ignore",
                    "summary": f"Automated notification: {item['title']}"}
        return None

    def triage_candidates(self, since_days: int, force: bool) -> list[dict]:
        cutoff = (datetime.now(UTC) - timedelta(days=since_days)).strftime(FMT)
        rows = self.store.conn.execute(
            """SELECT id, content_hash FROM items WHERE kind IN ('email', 'announcement')
               AND deleted_at IS NULL AND occurred_at >= ? ORDER BY occurred_at DESC""", (cutoff,)).fetchall()
        out = []
        for r in rows:
            want = _hash(r["content_hash"], "triage", PROMPT_VERSION["triage"])
            prev = self.store.get_analysis(r["id"], "triage")
            if force or not prev or prev["input_hash"] != want or prev["error"]:
                out.append({"id": r["id"], "hash": want})
        return out

    async def triage(self, since_days: int = 30, limit: int | None = None, force: bool = False,
                     capped: bool = True) -> Counter:
        """Rules → classifier (category, priority with probabilities) → LLM extraction where worth it.

        Per-run caps keep a backlog from saturating a local GPU; the rest is picked up by later runs.
        """
        counts: Counter = Counter()
        todo = self.triage_candidates(since_days, force)[:limit]
        mine = self.my_addresses()
        jobs = []
        for c in todo:
            item = self.store.get(c["id"])
            if rule := self.triage_rule(item, mine):
                self.store.save_analysis(item["id"], "triage", c["hash"], "rules", None,
                                         {**rule, "decided_by": "rules", "needs_review": False, "extracted": False})
                counts["rules"] += 1
            else:
                jobs.append((item, c["hash"]))
        if not jobs:
            return counts
        if not self.classifier and not self.triage_llm:
            counts["skipped_no_llm"] += len(jobs)
            return counts
        budget = {"classify": MAX_CLASSIFY_PER_RUN if capped else len(jobs),
                  "llm": MAX_LLM_PER_RUN if capped else len(jobs)}
        for item, h in jobs:  # sequential: local servers handle one request at a time anyway
            if budget["classify"] <= 0 or (not self.classifier and budget["llm"] <= 0):
                counts["deferred"] += 1
                continue
            await self._triage_one(item, h, counts, budget)
        return counts

    def _context(self, item: dict, max_chars: int) -> str:
        body = tidy_urls(item.get("body") or "")
        # Leave room for the system prompt, headers and question within the input budget.
        budget = max(1000, max_chars - 2000)
        if len(body) > budget:
            body = body[:budget] + "\n[... truncated]"
        return triage_user(item, body, _today())

    async def _triage_one(self, item: dict, input_hash: str, counts: Counter, budget: dict) -> None:
        clf, llm = self.classifier, self.triage_llm
        result: dict[str, Any] = {}
        confident = False
        if clf:
            budget["classify"] -= 1
            try:
                ctx = self._context(item, clf.max_input_chars)
                cat = await clf.classify(ctx, CATEGORY_QUESTION, CATEGORY_OPTIONS)
                pri = await clf.classify(ctx, PRIORITY_QUESTION, PRIORITY_OPTIONS)
            except LLMError as err:
                log.warning("Classification failed for %s: %s", item["id"], err)
                self.store.save_analysis(item["id"], "triage", input_hash, clf.name, clf.model, error=str(err))
                counts["errors"] += 1
                return
            confident = all(d.p >= CLASSIFY_CUTOFF and d.coverage >= MIN_COVERAGE for d in (cat, pri))
            result = {"category": cat.label, "priority": pri.label,
                      "classification": {"category": cat.as_dict(), "priority": pri.as_dict()}}
            counts["classified"] += 1
            low_value = cat.label in LOW_VALUE_CATEGORIES or pri.label == "ignore"
            if confident and low_value and CLASSIFIER_MODE in ("gate", "trust"):
                result.update(summary="", actions=[], dates=[], opportunity=None, links=[],
                              decided_by="classifier", needs_review=False, extracted=False)
                self.store.save_analysis(item["id"], "triage", input_hash, clf.name, clf.model, result)
                counts["classifier_only"] += 1
                return
        if not llm or budget["llm"] <= 0:
            if result:
                # Classified but extraction deferred: don't store, so the next run picks it up again.
                counts["deferred"] += 1
            else:
                counts["skipped_no_llm"] += 1
            return
        budget["llm"] -= 1
        async with self.sem:
            try:
                out, usage = await llm.structured(system=TRIAGE_SYSTEM, user=self._context(item, llm.max_input_chars),
                                                  schema=MessageTriage, effort="low", max_tokens=TRIAGE_MAX_TOKENS)
            except LLMError as err:
                log.warning("Triage failed for %s: %s", item["id"], err)
                self.store.save_analysis(item["id"], "triage", input_hash, llm.name, llm.model, error=str(err))
                counts["refused" if isinstance(err, LLMRefused) else "errors"] += 1
                return
        extracted = out.model_dump()
        if result and confident and CLASSIFIER_MODE == "trust":
            # The classifier's confident call wins; the LLM supplies the summary/actions/dates.
            extracted.update(category=result["category"], priority=result["priority"])
            decided_by, needs_review = "classifier+llm", False
        elif result:
            # The LLM decides; flag for the user when the two disagree on category or the classifier was unsure.
            decided_by = "llm"
            needs_review = (not confident) or result["category"] != extracted["category"]
        else:
            decided_by, needs_review = "llm", False
        extracted.update(classification=result.get("classification"), decided_by=decided_by,
                         needs_review=needs_review, extracted=True)
        self.store.save_analysis(item["id"], "triage", input_hash, llm.name, llm.model, extracted,
                                 usage={"in": usage.input_tokens, "out": usage.output_tokens})
        counts[llm.name] += 1

    # ── Task briefs ─────────────────────────────────────────────────────────
    def related_files(self, item: dict) -> list[dict]:
        """Downloaded course files most likely to describe this task, best first."""
        rows = self.store.conn.execute(
            """SELECT i.id, i.title, i.data, f.path, f.filename, f.sha256 FROM items i JOIN files f ON f.item_id = i.id
               WHERE i.source = ? AND i.course_id = ? AND i.kind = 'content' AND i.deleted_at IS NULL""",
            (item["source"], item["course_id"]),
        ).fetchall()
        # Course content often holds a link to the task inside a module that also holds its brief.
        links = self.store.conn.execute(
            """SELECT title, json_extract(data, '$.module_path') AS path FROM items
               WHERE source = ? AND course_id = ? AND kind = 'content' AND deleted_at IS NULL
               AND json_extract(data, '$.type') = 'Link'""",
            (item["source"], item["course_id"]),
        ).fetchall()
        anchors = [json.loads(l["path"]) for l in links if _norm(l["title"]) == _norm(item["title"]) and l["path"]]
        return rank_files(item["title"], [dict(r) for r in rows], anchors)

    def brief_candidates(self, horizon_days: int, force: bool) -> list[dict]:
        now = datetime.now(UTC)
        rows = self.store.upcoming((now - timedelta(days=1)).strftime(FMT),
                                   (now + timedelta(days=horizon_days)).strftime(FMT), kinds=("assignment", "quiz"))
        out = []
        for item in rows:
            if item["data"].get("submitted"):
                continue
            files = self.related_files(item)[:5]
            want = _hash(item["content_hash"], "brief", PROMPT_VERSION["brief"], *(f["sha256"] for f in files))
            prev = self.store.get_analysis(item["id"], "brief")
            if force or not prev or prev["input_hash"] != want or prev["error"]:
                out.append({"item": item, "files": files, "hash": want})
        return out

    async def briefs(self, horizon_days: int = 60, limit: int | None = None, force: bool = False,
                     capped: bool = True) -> Counter:
        counts: Counter = Counter()
        todo = self.brief_candidates(horizon_days, force)[:limit]
        if capped and len(todo) > MAX_LLM_PER_RUN:
            counts["deferred"] += len(todo) - MAX_LLM_PER_RUN
            todo = todo[:MAX_LLM_PER_RUN]
        if todo and not self.brief_llm:
            counts["skipped_no_llm"] += len(todo)
            return counts
        await asyncio.gather(*(self._brief_one(c["item"], c["files"], c["hash"], counts) for c in todo))
        return counts

    async def _brief_one(self, item: dict, files: list[dict], input_hash: str, counts: Counter) -> None:
        llm = self.brief_llm
        budget = max(2000, llm.max_input_chars - 4000)
        texts: list[tuple[str, str]] = []
        for f in files:
            if budget <= 500:
                break
            text = (await asyncio.to_thread(extract_text, f["path"])).strip()
            if not text:
                continue
            take = min(len(text), budget if not texts else min(budget, int(budget * 0.6)))
            texts.append((f["title"], text[:take] + ("\n[... truncated]" if take < len(text) else "")))
            budget -= take
        async with self.sem:
            try:
                result, usage = await llm.structured(system=BRIEF_SYSTEM, user=brief_user(item, texts, _today()),
                                                     schema=TaskBrief, effort="medium", max_tokens=4000)
            except LLMError as err:
                log.warning("Brief failed for %s: %s", item["id"], err)
                self.store.save_analysis(item["id"], "brief", input_hash, llm.name, llm.model, error=str(err))
                counts["refused" if isinstance(err, LLMRefused) else "errors"] += 1
                return
        out = result.model_dump()
        out["files_considered"] = [{"item_id": f["id"], "title": f["title"]} for f in files]
        self.store.save_analysis(item["id"], "brief", input_hash, llm.name, llm.model, out,
                                 usage={"in": usage.input_tokens, "out": usage.output_tokens})
        counts[llm.name] += 1

    async def run(self, *, triage: bool = True, briefs: bool = True, since_days: int = 30,
                  horizon_days: int = 60, limit: int | None = None, force: bool = False,
                  capped: bool = True) -> dict[str, dict]:
        from ..llm.local import unload_used

        report: dict[str, dict] = {}
        try:
            if triage:
                report["triage"] = dict(await self.triage(since_days, limit, force, capped))
            if briefs:
                report["brief"] = dict(await self.briefs(horizon_days, limit, force, capped))
        finally:
            unloaded = await unload_used()
            if unloaded:
                report["unloaded"] = {"models": unloaded}
        return report


# ── File ranking (pure, tested) ──────────────────────────────────────────────
STOPWORDS = {"the", "a", "an", "and", "of", "for", "to", "in", "on", "only", "most", "recent", "is", "kept",
             "submission", "submissions", "due", "folder", "quiz", "upload"}
BRIEF_WORDS = re.compile(r"brief|spec|specification|rubric|requirement|guideline|instruction|assignment|project|"
                         r"\bca\d|marking|criteria", re.I)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+|\d+", text.lower())


def _norm(text: str) -> str:
    return " ".join(_tokens(text))


def rank_files(task_title: str, files: list[dict], anchor_paths: list[list[str]] | None = None) -> list[dict]:
    """Score files by how well they match the task.

    Strongest: the file sits in the same content module as a link to the task.
    Then "Assignment 1" ↔ "ST1522_Assignment1_Brief.pdf" (word + number pair),
    then shared words, then brief-like words in the name.
    """
    toks = _tokens(task_title)
    pairs = [(w, n) for w, n in zip(toks, toks[1:]) if w.isalpha() and n.isdigit()]
    words = {t for t in toks if t.isalpha() and t not in STOPWORDS and len(t) > 2}
    scored = []
    for f in files:
        data = f["data"] if isinstance(f["data"], dict) else json.loads(f["data"])
        hay = " ".join([f["title"] or "", f.get("filename") or "", " ".join(data.get("module_path") or [])])
        hay_l = hay.lower()
        path = data.get("module_path") or []
        score = 0
        if any(path[: len(a)] == a for a in anchor_paths or []):
            score += 15
        for w, n in pairs:
            if re.search(rf"{w}\W*_?0*{int(n)}(?!\d)", hay_l):
                score += 10
        hay_toks = set(_tokens(hay))
        score += sum(2 for w in words if w in hay_toks)
        if score and BRIEF_WORDS.search(hay):
            score += 3
        if score:
            scored.append((score, f))
    scored.sort(key=lambda sf: -sf[0])
    return [f | {"score": s} for s, f in scored]
