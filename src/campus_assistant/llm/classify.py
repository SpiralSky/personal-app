"""Jev-style classification on a local model: probabilities over typed options in one pass.

No text is generated. The model reads the message and a question whose options
are labelled with neutral letters; we request a single token with
top_logprobs and renormalise the probability mass over the option letters.

Design notes (see README):
- Neutral letter labels with the definitions spelled out: decision heads follow
  semantically loaded option names ("yes"/"no") over the rubric bound to them.
- The message goes first and the question last, so llama-server's prompt cache
  reuses the message's KV for every further question about it.
- `coverage` is how much of the next-token mass fell on valid letters; low
  coverage means the model wanted to say something else and the result is
  unreliable regardless of the top probability.
- Raw probabilities are not calibrated. Cutoffs must be checked against the
  user's own labels before they are trusted.
"""

import math
import os
import random
import zlib
from dataclasses import dataclass, field

import httpx

from . import LLMError
from .local import LocalProvider, local_request

LETTERS = "ABCDEFGHIJKLMNOP"

SYSTEM = ("You are a precise classifier. Read the message, then answer the question with the single letter "
          "of the best option. Output only the letter.")


@dataclass
class Decision:
    label: str                       # winning option key
    p: float                         # its probability (renormalised over options)
    probs: dict[str, float]          # option key -> probability
    coverage: float                  # next-token mass on valid letters (0..1)
    permutations: int = 1
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"label": self.label, "p": round(self.p, 4), "coverage": round(self.coverage, 4),
                "probs": {k: round(v, 4) for k, v in self.probs.items()}, "permutations": self.permutations}


class LogprobClassifier:
    name = "local-logprobs"

    def __init__(self, provider: LocalProvider, permutations: int | None = None,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.provider = provider
        self.permutations = permutations or int(os.environ.get("CAMPUS_CLASSIFY_PERMUTATIONS", "1"))
        self.transport = transport

    @property
    def model(self) -> str:
        return self.provider.model

    @property
    def max_input_chars(self) -> int:
        return self.provider.max_input_chars

    async def classify(self, context: str, question: str, options: dict[str, str]) -> Decision:
        """options: key -> definition. Returns probabilities per key."""
        if not self.provider._probed:
            await self.provider.probe()
        keys = list(options)
        if len(keys) > len(LETTERS):
            raise ValueError("too many options")
        total = {k: 0.0 for k in keys}
        coverage = 0.0
        # Permutation 0 keeps the given order; others shuffle which letter goes with which option,
        # averaging out position/letter bias.
        rng = random.Random(zlib.crc32(question.encode()))
        for i in range(self.permutations):
            order = keys[:] if i == 0 else rng.sample(keys, len(keys))
            probs, cov = await self._one(context, question, order, options)
            coverage += cov / self.permutations
            for k, v in probs.items():
                total[k] += v / self.permutations
        label = max(total, key=total.get)
        return Decision(label, total[label], total, coverage, self.permutations)

    async def _one(self, context: str, question: str, order: list[str], options: dict[str, str]):
        letters = {LETTERS[i]: key for i, key in enumerate(order)}
        lines = [f"{letter}) {options[key]}" for letter, key in letters.items()]
        user = f"<message>\n{context}\n</message>\n\nQuestion: {question}\n" + "\n".join(lines) + \
            f"\n\nAnswer with one letter ({', '.join(letters)})."
        body = {
            "model": self.provider.model,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            "max_tokens": 1,
            "temperature": 0,
            "logprobs": True,
            "top_logprobs": 20,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        resp = await local_request(self.provider.base_url, self.provider.model, body, self.provider.headers,
                                   transport=self.transport)
        if resp.status_code != 200:
            raise LLMError(f"Local classifier error {resp.status_code}: {resp.text[:300]}")
        content = ((resp.json()["choices"][0].get("logprobs") or {}).get("content") or [])
        if not content:
            raise LLMError("Server returned no logprobs (does it support top_logprobs?)")
        mass: dict[str, float] = {}
        for alt in content[0].get("top_logprobs") or []:
            tok = (alt.get("token") or "").strip().strip(")").upper()
            if tok in letters:
                mass[letters[tok]] = mass.get(letters[tok], 0.0) + math.exp(alt["logprob"])
        cov = sum(mass.values())
        if cov <= 0:
            raise LLMError("No option letter among the top tokens")
        return {k: mass.get(k, 0.0) / cov for k in order}, min(1.0, cov)


def classifier_for() -> LogprobClassifier | None:
    """The configured classifier (CAMPUS_CLASSIFIER = local | off), independent of the triage LLM."""
    if os.environ.get("CAMPUS_CLASSIFIER", "local") == "off":
        return None
    from . import LLMConfig

    cfg = LLMConfig()
    return LogprobClassifier(LocalProvider(cfg.local_url, cfg.local_model, cfg.local_api_key,
                                           cfg.local_max_input_chars))
