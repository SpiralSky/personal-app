"""How good is triage, measured against the user's own labels.

For every labelled message that also has a triage result, compares the user's
category/priority with (a) the final triage decision, (b) the classifier's
call and (c) the LLM's call where both exist, and buckets classifier
confidence to show whether "p >= cutoff" really means "usually right".
"""

import json
from typing import Any

from ..store import Store

BUCKETS = [0.0, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 1.01]


def evaluate(store: Store, cutoff: float = 0.8) -> dict[str, Any]:
    rows = store.conn.execute(
        """SELECT a.result, l.category AS l_cat, l.priority AS l_pri FROM labels l
           JOIN analyses a ON a.item_id = l.item_id AND a.task = 'triage' WHERE a.result IS NOT NULL""").fetchall()
    out: dict[str, Any] = {"labelled": len(rows), "cutoff": cutoff}
    for q, lkey in (("category", "l_cat"), ("priority", "l_pri")):
        n = final_ok = clf_n = clf_ok = above_n = above_ok = 0
        buckets = [{"range": f"{lo:.2f}-{min(hi, 1):.2f}", "n": 0, "correct": 0} for lo, hi in zip(BUCKETS, BUCKETS[1:])]
        for r in rows:
            truth = r[lkey]
            if not truth:
                continue
            res = json.loads(r["result"])
            n += 1
            final_ok += res.get(q) == truth
            d = (res.get("classification") or {}).get(q)
            if d:
                clf_n += 1
                ok = d["label"] == truth
                clf_ok += ok
                for b, lo, hi in zip(buckets, BUCKETS, BUCKETS[1:]):
                    if lo <= d["p"] < hi:
                        b["n"] += 1
                        b["correct"] += ok
                if d["p"] >= cutoff:
                    above_n += 1
                    above_ok += ok
        for b in buckets:
            b["accuracy"] = round(b["correct"] / b["n"], 3) if b["n"] else None
        out[q] = {
            "n": n,
            "final_accuracy": round(final_ok / n, 3) if n else None,
            "classifier_accuracy": round(clf_ok / clf_n, 3) if clf_n else None,
            # The number that decides whether CAMPUS_CLASSIFIER_MODE=trust is safe:
            "classifier_accuracy_above_cutoff": round(above_ok / above_n, 3) if above_n else None,
            "classifier_coverage_above_cutoff": round(above_n / clf_n, 3) if clf_n else None,
            "buckets": [b for b in buckets if b["n"]],
        }
    return out
