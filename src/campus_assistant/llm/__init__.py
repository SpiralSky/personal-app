"""LLM providers behind one interface: structured output into a Pydantic model.

Providers:
    claude  Anthropic API (credentials from ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / `ant auth login`)
    local   a server you run yourself, via its OpenAI-compatible API with JSON-schema output:
            llama.cpp's llama-server or a fork (default http://127.0.0.1:8080/v1), Ollama
            (http://127.0.0.1:11434/v1), LM Studio, vLLM... Nothing is bundled.

Which provider each task uses is set by CAMPUS_LLM_<TASK> = claude | local | auto | off
("auto" = claude when credentials are available, else local).
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """The model call failed or returned something unusable."""


class LLMRefused(LLMError):
    """The model declined (Claude stop_reason == "refusal")."""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(Protocol):
    name: str
    model: str
    # Rough cap on characters of source text per request (context-window budget).
    max_input_chars: int

    async def structured(self, *, system: str, user: str, schema: type[T], effort: str = "low",
                         max_tokens: int = 4000) -> tuple[T, Usage]: ...


def claude_credentials_available() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    # Profile written by `ant auth login`.
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "anthropic"
    return base.exists() and any(base.iterdir())


@dataclass
class LLMConfig:
    claude_model: str = os.environ.get("CAMPUS_CLAUDE_MODEL", "claude-opus-5-5")
    local_url: str = os.environ.get("CAMPUS_LOCAL_LLM_URL", "http://127.0.0.1:8080/v1")
    # Empty = the first model the server lists.
    local_model: str = os.environ.get("CAMPUS_LOCAL_LLM_MODEL", "")
    local_api_key: str | None = os.environ.get("CAMPUS_LOCAL_LLM_KEY") or None
    # Unset = derived from the server's context size (llama.cpp /props), else 7000.
    local_max_input_chars: int | None = int(os.environ["CAMPUS_LOCAL_LLM_MAX_CHARS"]) if os.environ.get(
        "CAMPUS_LOCAL_LLM_MAX_CHARS") else None
    claude_max_input_chars: int = int(os.environ.get("CAMPUS_CLAUDE_MAX_CHARS", "400000"))


DEFAULT_PROVIDER = {"triage": "local", "brief": "auto"}
PROVIDER_CHOICES = ("claude", "local", "auto", "off")
PROVIDER_OVERRIDES: dict[str, str] = {}
# Custom provider configs: task -> {endpoint, model, api_key?, thinking?}
CUSTOM_PROVIDER_CONFIGS: dict[str, dict] = {}


class CustomProvider:
    """A custom provider with user-specified endpoint, model, and optional thinking."""
    name = "custom"

    def __init__(self, endpoint: str, model: str, api_key: str | None = None,
                 thinking: bool = False, max_input_chars: int = 50000):
        from .local import LocalProvider
        # Reuse LocalProvider's OpenAI-compatible implementation
        self._inner = LocalProvider(endpoint, model, api_key, max_input_chars)
        self.endpoint = endpoint
        self.model = model
        self.thinking = thinking
        self.max_input_chars = max_input_chars

    async def probe(self):
        """Probe the custom endpoint."""
        info = await self._inner.probe()
        info["thinking"] = self.thinking
        return info

    async def structured(self, *, system: str, user: str, schema: type[T], effort: str = "low",
                         max_tokens: int = 4000) -> tuple[T, Usage]:
        # For now, delegate to LocalProvider's implementation
        # TODO: could add thinking support for Claude-compatible endpoints
        return await self._inner.structured(system=system, user=user, schema=schema,
                                           effort=effort, max_tokens=max_tokens)


def provider_for(task: str, cfg: LLMConfig | None = None) -> Provider | None:
    cfg = cfg or LLMConfig()

    # Check for custom provider config first
    if task in CUSTOM_PROVIDER_CONFIGS:
        custom_cfg = CUSTOM_PROVIDER_CONFIGS[task]
        return CustomProvider(
            endpoint=custom_cfg["endpoint"],
            model=custom_cfg["model"],
            api_key=custom_cfg.get("api_key"),
            thinking=custom_cfg.get("thinking", False),
            max_input_chars=custom_cfg.get("max_input_chars", 50000)
        )

    choice = (PROVIDER_OVERRIDES.get(task) or os.environ.get(
        f"CAMPUS_LLM_{task.upper()}", DEFAULT_PROVIDER.get(task, "auto"))).lower()
    if choice == "off":
        return None
    if choice == "auto":
        choice = "claude" if claude_credentials_available() else "local"
    if choice == "claude":
        from .claude import ClaudeProvider
        return ClaudeProvider(cfg.claude_model, cfg.claude_max_input_chars)
    if choice == "local":
        from .local import LocalProvider
        return LocalProvider(cfg.local_url, cfg.local_model, cfg.local_api_key, cfg.local_max_input_chars)
    raise ValueError(f"Unknown provider {choice!r} for CAMPUS_LLM_{task.upper()}")


async def llm_status(cfg: LLMConfig | None = None) -> dict:
    """Which provider each task uses, and whether the local server answers."""
    cfg = cfg or LLMConfig()
    out: dict = {"claude_credentials": claude_credentials_available(), "tasks": {}}
    for task in DEFAULT_PROVIDER:
        try:
            p = provider_for(task, cfg)
        except ValueError as err:
            out["tasks"][task] = {"error": str(err)}
            continue
        if p is None:
            out["tasks"][task] = None
        elif p.name == "local":
            out["tasks"][task] = {"provider": "local", **(await p.probe())}
        elif p.name == "custom":
            probe_info = await p.probe()
            out["tasks"][task] = {
                "provider": "custom",
                "endpoint": p.endpoint,
                "model": p.model,
                "thinking": p.thinking,
                **probe_info
            }
        else:
            out["tasks"][task] = {"provider": p.name, "model": p.model}
    return out
