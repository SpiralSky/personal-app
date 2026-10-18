"""Local models through any OpenAI-compatible chat endpoint with JSON-schema output.

Nothing is bundled: point CAMPUS_LOCAL_LLM_URL at a server you run yourself:
llama.cpp's llama-server (or a fork of it), Ollama's /v1, LM Studio, vLLM...
llama.cpp-style servers are probed for their context size (/props) so the text
budget fits; the model defaults to whatever the server reports in /models.

One request at a time, with a pause after each (CAMPUS_LOCAL_LLM_PAUSE_S) so a
backlog doesn't keep a shared desktop GPU saturated. After an analysis run the
model can be unloaded from a llama-server router (CAMPUS_LOCAL_LLM_UNLOAD).
"""

import asyncio
import logging
import os
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import ValidationError

from . import LLMError, T, Usage

log = logging.getLogger(__name__)

_lock = asyncio.Lock()
CHARS_PER_TOKEN = 3          # conservative for mixed English text
RESERVED_TOKENS = 1600       # system prompt + headers + output
PAUSE_S = float(os.environ.get("CAMPUS_LOCAL_LLM_PAUSE_S", "3"))
# Models this process sent requests to, per server; unloaded by unload_used().
_used: dict[str, set[str]] = {}


async def local_request(base_url: str, model: str, body: dict, headers: dict,
                        transport: httpx.AsyncBaseTransport | None = None) -> httpx.Response:
    """POST /chat/completions, serialised and followed by a pause."""
    async with _lock:
        try:
            async with httpx.AsyncClient(timeout=300, transport=transport) as client:
                resp = await client.post(f"{base_url}/chat/completions", json=body, headers=headers)
        except httpx.HTTPError as err:
            raise LLMError(f"Local LLM at {base_url} unreachable: {err}") from err
        _used.setdefault(base_url, set()).add(model)
        if PAUSE_S > 0:
            await asyncio.sleep(PAUSE_S)
    return resp


async def unload_used(transport: httpx.AsyncBaseTransport | None = None) -> list[str]:
    """Unload the models this process used from llama-server routers (frees VRAM).

    No-op unless CAMPUS_LOCAL_LLM_UNLOAD is on, and harmless on servers without
    /models/unload (Ollama, single-model llama-server).
    """
    if os.environ.get("CAMPUS_LOCAL_LLM_UNLOAD", "1") == "0":
        return []
    done = []
    for base_url, models in list(_used.items()):
        p = urlsplit(base_url)
        root = urlunsplit((p.scheme, p.netloc, "", "", ""))
        for model in models:
            try:
                async with httpx.AsyncClient(timeout=10, transport=transport) as c:
                    r = await c.post(f"{root}/models/unload", json={"model": model})
                if r.status_code == 200:
                    done.append(model)
            except httpx.HTTPError:
                pass
        _used.pop(base_url, None)
    if done:
        log.info("Unloaded local model(s): %s", ", ".join(done))
    return done


class LocalProvider:
    name = "local"

    def __init__(self, base_url: str, model: str | None, api_key: str | None, max_input_chars: int | None):
        self.base_url = base_url.rstrip("/")
        self.model = model or ""
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._explicit_chars = max_input_chars
        self.max_input_chars = max_input_chars or 7000
        self.n_ctx: int | None = None
        self._probed = False

    def _root(self) -> str:
        """http://host:port (the OpenAI routes live under /v1, llama.cpp extras at the root)."""
        p = urlsplit(self.base_url)
        return urlunsplit((p.scheme, p.netloc, "", "", ""))

    async def probe(self) -> dict[str, Any]:
        """Server reachability, available models, context size. Also fills in model/budget."""
        info: dict[str, Any] = {"url": self.base_url, "reachable": False}
        try:
            async with httpx.AsyncClient(timeout=5, headers=self.headers) as c:
                r = await c.get(f"{self.base_url}/models")
                r.raise_for_status()
                entries = r.json().get("data", [])
                models = [m.get("id") for m in entries]
                # llama-server router mode lists every model with a load status; prefer one already loaded.
                loaded = [m.get("id") for m in entries if (m.get("status") or {}).get("value") == "loaded"]
                info.update(reachable=True, models=models, loaded=loaded or None)
                if not self.model and models:
                    self.model = (loaded or models)[0]
                # Only ask a loaded model: in router mode /props on an unloaded one loads it.
                try:
                    if loaded and self.model not in loaded:
                        raise LookupError
                    props = (await c.get(f"{self._root()}/props", params={"model": self.model})).json()
                    n_ctx = (props.get("default_generation_settings") or {}).get("n_ctx") or props.get("n_ctx")
                    if n_ctx:
                        self.n_ctx = int(n_ctx)
                except Exception:
                    pass  # not llama.cpp; keep the configured budget
        except Exception as err:
            info["error"] = str(err)
        if self.n_ctx and not self._explicit_chars:
            self.max_input_chars = max(2000, (self.n_ctx - RESERVED_TOKENS) * CHARS_PER_TOKEN)
        self._probed = True
        info.update(model=self.model or None, n_ctx=self.n_ctx, max_input_chars=self.max_input_chars)
        return info

    async def structured(self, *, system: str, user: str, schema: type[T], effort: str = "low",
                         max_tokens: int = 4000) -> tuple[T, Usage]:
        if not self._probed:
            await self.probe()
        if not self.model:
            raise LLMError(f"No model available at {self.base_url} (set CAMPUS_LOCAL_LLM_MODEL)")
        if self.n_ctx:
            max_tokens = min(max_tokens, max(256, self.n_ctx // 3))
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "strict": True, "schema": schema.model_json_schema()},
            },
            "max_tokens": max_tokens,
            "temperature": 0.2,
            # Qwen3-style models: skip the reasoning preamble; the schema constrains the output anyway.
            "chat_template_kwargs": {"enable_thinking": False},
        }
        resp = await local_request(self.base_url, self.model, body, self.headers)
        if resp.status_code != 200:
            raise LLMError(f"Local LLM error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        choice = data["choices"][0]
        content = choice["message"].get("content") or ""
        if choice.get("finish_reason") == "length":
            raise LLMError(f"Local output hit max_tokens={max_tokens} (or the context window)")
        try:
            parsed = schema.model_validate_json(content)
        except ValidationError as err:
            raise LLMError(f"Local model returned invalid JSON for {schema.__name__}: {err.errors()[:2]}") from err
        u = data.get("usage") or {}
        return parsed, Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
