"""Claude via the Anthropic Python SDK, with structured outputs (messages.parse)."""

import logging

import anthropic

from . import LLMError, LLMRefused, T, Usage

log = logging.getLogger(__name__)

# On a safety-classifier decline the API re-runs the request on a fallback model
# chosen by refusal category, inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeProvider:
    name = "claude"

    def __init__(self, model: str, max_input_chars: int):
        self.model = model
        self.max_input_chars = max_input_chars
        self.client = anthropic.AsyncAnthropic(max_retries=4)

    async def structured(self, *, system: str, user: str, schema: type[T], effort: str = "low",
                         max_tokens: int = 4000) -> tuple[T, Usage]:
        try:
            response = await self.client.beta.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                # The system prompt is identical across calls of one task, so cache it.
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                output_config={"effort": effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as err:
            raise LLMError("Claude credentials missing or invalid (set ANTHROPIC_API_KEY or run `ant auth login`)") from err
        except anthropic.BadRequestError as err:
            raise LLMError(f"Claude rejected the request: {err.message}") from err
        except anthropic.RateLimitError as err:
            raise LLMError("Claude rate limit (after retries)") from err
        except anthropic.APIStatusError as err:
            raise LLMError(f"Claude API error {err.status_code}: {err.message}") from err
        except anthropic.APIConnectionError as err:
            raise LLMError(f"Could not reach the Claude API: {err}") from err

        if response.stop_reason == "refusal":
            details = response.stop_details
            raise LLMRefused(f"Claude declined ({details.category if details else 'unknown'})")
        if response.stop_reason == "max_tokens":
            raise LLMError(f"Output hit max_tokens={max_tokens}")
        if response.parsed_output is None:
            raise LLMError("No structured output in response")
        usage = Usage(response.usage.input_tokens, response.usage.output_tokens)
        return response.parsed_output, usage
