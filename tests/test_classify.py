import asyncio
import json
import math

import httpx

from campus_assistant.analysis import pipeline as P
from campus_assistant.analysis.pipeline import Analyzer
from campus_assistant.llm import local as L
from campus_assistant.llm.classify import Decision, LogprobClassifier
from campus_assistant.llm.local import LocalProvider

from .test_analysis import FakeLLM, seeded


def server(answers, seen=None):
    """Mock llama-server: `answers(user_prompt) -> {letter_token: prob}`; also /models and /models/unload."""
    def handler(request: httpx.Request):
        if request.url.path.endswith("/models/unload"):
            (seen if seen is not None else []).append(("unload", json.loads(request.content)["model"]))
            return httpx.Response(200, json={"success": True})
        body = json.loads(request.content)
        user = body["messages"][-1]["content"]
        if seen is not None:
            seen.append(("chat", user))
        assert body["max_tokens"] == 1 and body["logprobs"] and body["top_logprobs"] == 20
        top = [{"token": t, "logprob": math.log(p)} for t, p in answers(user).items()]
        return httpx.Response(200, json={"choices": [{"message": {"content": top[0]["token"]},
                                                      "logprobs": {"content": [{"token": top[0]["token"],
                                                                                "top_logprobs": top}]}}]})
    return httpx.MockTransport(handler)


def clf(answers, seen=None, permutations=1):
    p = LocalProvider("http://llm.test/v1", "m", None, 6000)
    p._probed = True
    return LogprobClassifier(p, permutations=permutations, transport=server(answers, seen))


def test_probabilities_are_renormalised_over_options(monkeypatch):
    monkeypatch.setattr(L, "PAUSE_S", 0)
    c = clf(lambda u: {"B": 0.6, " A": 0.2, "Hello": 0.15, "C)": 0.05})
    d = asyncio.run(c.classify("msg", "Q?", {"x": "first", "y": "second", "z": "third"}))
    assert d.label == "y"
    assert abs(d.p - 0.6 / 0.85) < 1e-9 and abs(d.probs["x"] - 0.2 / 0.85) < 1e-9
    assert abs(d.coverage - 0.85) < 1e-9


def test_letters_are_neutral_and_message_comes_first(monkeypatch):
    monkeypatch.setattr(L, "PAUSE_S", 0)
    seen = []
    asyncio.run(clf(lambda u: {"A": 1.0}, seen).classify("THE MESSAGE", "Q?", {"yes": "it is", "no": "it is not"}))
    user = seen[0][1]
    assert user.startswith("<message>\nTHE MESSAGE") and "A) it is\nB) it is not" in user
    assert "yes" not in user.split("</message>")[1]  # option keys never shown to the model


def test_permutations_average_out_letter_bias(monkeypatch):
    monkeypatch.setattr(L, "PAUSE_S", 0)
    # A model that always says "A" regardless of content: with shuffling, no option can win decisively.
    d = asyncio.run(clf(lambda u: {"A": 0.9, "B": 0.1}, permutations=4).classify(
        "m", "Q?", {"x": "1", "y": "2"}))
    assert d.permutations == 4 and d.p < 0.9


class FakeClassifier:
    name, model, max_input_chars = "fake-clf", "m", 6000

    def __init__(self, cat, pri, p=0.95, coverage=0.9):
        self.answers = {"category": (cat, p), "priority": (pri, p)}
        self.coverage = coverage
        self.calls = 0

    async def classify(self, context, question, options):
        self.calls += 1
        key = "category" if "category" in question else "priority"
        label, p = self.answers[key]
        probs = {k: (p if k == label else (1 - p) / (len(options) - 1)) for k in options}
        return Decision(label, p, probs, self.coverage)


def run_triage(tmp_path, classifier, llm, **kw):
    s = seeded(tmp_path)
    a = Analyzer(s, triage_provider=llm, classifier=classifier, use_defaults=False)
    return s, asyncio.run(a.triage(since_days=30, **kw))


def test_confident_low_value_skips_llm(tmp_path):
    llm = FakeLLM()
    s, counts = run_triage(tmp_path, FakeClassifier("newsletter", "ignore"), llm)
    assert counts["classifier_only"] == 1 and not llm.calls
    res = s.get_analysis("outlook:email:1", "triage")["result"]
    assert res["decided_by"] == "classifier" and res["extracted"] is False
    assert res["classification"]["category"]["label"] == "newsletter"


def test_gate_mode_llm_decides_and_disagreement_flags_review(tmp_path):
    s, _ = run_triage(tmp_path, FakeClassifier("action_required", "urgent"), FakeLLM())
    res = s.get_analysis("outlook:email:1", "triage")["result"]
    assert (res["category"], res["decided_by"], res["needs_review"]) == ("opportunity", "llm", True)
    assert res["classification"]["category"]["label"] == "action_required"


def test_gate_mode_agreement_needs_no_review(tmp_path):
    s, _ = run_triage(tmp_path, FakeClassifier("opportunity", "soon"), FakeLLM())
    assert s.get_analysis("outlook:email:1", "triage")["result"]["needs_review"] is False


def test_shadow_mode_never_skips_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "CLASSIFIER_MODE", "shadow")
    llm = FakeLLM()
    s, counts = run_triage(tmp_path, FakeClassifier("newsletter", "ignore"), llm)
    assert llm.calls and "classifier_only" not in counts


def test_trust_mode_confident_classifier_wins(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "CLASSIFIER_MODE", "trust")
    llm = FakeLLM()  # says opportunity/soon
    s, counts = run_triage(tmp_path, FakeClassifier("action_required", "urgent"), llm)
    res = s.get_analysis("outlook:email:1", "triage")["result"]
    assert (res["category"], res["priority"], res["decided_by"]) == ("action_required", "urgent", "classifier+llm")
    assert res["summary"] == "Fair." and res["needs_review"] is False


def test_unsure_classifier_defers_to_llm_and_flags_review(tmp_path):
    s, counts = run_triage(tmp_path, FakeClassifier("notice", "whenever", p=0.5), FakeLLM())
    res = s.get_analysis("outlook:email:1", "triage")["result"]
    assert (res["category"], res["decided_by"], res["needs_review"]) == ("opportunity", "llm", True)
    assert [r["title"] for r in s.triaged(needs_review=True)] == ["Internship fair"]


def test_low_coverage_is_not_confident(tmp_path):
    llm = FakeLLM()
    s, _ = run_triage(tmp_path, FakeClassifier("newsletter", "ignore", p=0.99, coverage=0.2), llm)
    assert llm.calls  # not trusted → LLM consulted
    assert s.get_analysis("outlook:email:1", "triage")["result"]["needs_review"] is True


def test_llm_cap_defers_without_storing(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "MAX_LLM_PER_RUN", 0)
    s, counts = run_triage(tmp_path, FakeClassifier("opportunity", "soon"), FakeLLM())
    assert counts["deferred"] == 1 and s.get_analysis("outlook:email:1", "triage") is None
    # Uncapped run (e.g. `campus analyze --no-cap`) processes it.
    a = Analyzer(s, triage_provider=FakeLLM(), classifier=FakeClassifier("opportunity", "soon"), use_defaults=False)
    assert asyncio.run(a.triage(since_days=30, capped=False))["fake"] == 1


def test_unload_after_run(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "PAUSE_S", 0)
    seen = []
    c = clf(lambda u: {"A": 1.0}, seen)
    asyncio.run(c.classify("m", "Q?", {"x": "1", "y": "2"}))
    assert asyncio.run(L.unload_used(transport=server(lambda u: {}, seen))) == ["m"]
    assert ("unload", "m") in seen
    assert asyncio.run(L.unload_used(transport=server(lambda u: {}, seen))) == []  # nothing used since
    monkeypatch.setenv("CAMPUS_LOCAL_LLM_UNLOAD", "0")
    asyncio.run(c.classify("m", "Q?", {"x": "1", "y": "2"}))
    assert asyncio.run(L.unload_used()) == []
    L._used.clear()


def test_eval_against_labels(tmp_path):
    from campus_assistant.analysis.evaluate import evaluate
    s, _ = run_triage(tmp_path, FakeClassifier("action_required", "urgent", p=0.97), FakeLLM())
    assert evaluate(s)["labelled"] == 0
    s.set_label("outlook:email:1", "opportunity", "soon", None)
    e = evaluate(s, cutoff=0.9)
    assert e["category"]["final_accuracy"] == 1.0          # LLM decided correctly
    assert e["category"]["classifier_accuracy"] == 0.0     # classifier was confidently wrong
    assert e["category"]["classifier_accuracy_above_cutoff"] == 0.0
    assert e["category"]["buckets"] == [{"range": "0.95-0.99", "n": 1, "correct": 0, "accuracy": 0.0}]
