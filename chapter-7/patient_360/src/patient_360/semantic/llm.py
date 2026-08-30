"""Provider-agnostic LLM access for the semantic SQL agent, via LiteLLM.

The agent depends only on the :class:`LLMClient` protocol (one ``complete()`` method).
A single :class:`LiteLLMClient` implements it over `LiteLLM <https://docs.litellm.ai>`_, so
the *same* agent runs against any provider by changing configuration only — the model string
selects the backend and LiteLLM translates to that provider's **native** API (for Anthropic
it calls the real Messages API, not an OpenAI-compatible shim):

    LLM_MODEL      provider-routed model id (default: ``anthropic/claude-opus-5``). Examples:
                     anthropic/claude-opus-5       -> native Claude API (ANTHROPIC_API_KEY)
                     ollama/qwen2.5-coder:7b       -> local Ollama      (LLM_API_BASE)
                     openrouter/<vendor>/<model>   -> OpenRouter        (OPENROUTER_API_KEY)
                     gpt-4o                        -> OpenAI            (OPENAI_API_KEY)
                     bedrock/anthropic.claude-*    -> Amazon Bedrock    (AWS creds)
    LLM_API_BASE   base URL for self-hosted/local backends (e.g. http://localhost:11434
                     for Ollama). ``LLM_BASE_URL`` is accepted as an alias.
    LLM_API_KEY    optional explicit key; if unset, LiteLLM reads the provider's own env var
                     (ANTHROPIC_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY / ...).

The ``litellm`` package is imported lazily, so this module (and the unit tests, which inject
a fake) load without it installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# `anthropic/` prefix pins the Anthropic provider regardless of whether the exact model name
# is in LiteLLM's static map, so a brand-new Claude model still routes correctly.
DEFAULT_MODEL = "anthropic/claude-opus-5"


@dataclass(frozen=True)
class Message:
    """A single chat message."""

    role: str  # "system" | "user" | "assistant"
    content: str


@runtime_checkable
class LLMClient(Protocol):
    """Minimal chat-completion surface the agent depends on (easy to fake in tests)."""

    def complete(
        self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 1024
    ) -> str: ...


class LiteLLMClient:
    """One chat-completion client over LiteLLM; the model string picks the provider.

    LiteLLM handles each provider's wire format and system-prompt placement, so ``messages``
    (including a ``system`` turn) is passed through uniformly.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
        self.api_base = (
            api_base or os.environ.get("LLM_API_BASE") or os.environ.get("LLM_BASE_URL")
        )
        # Optional: LiteLLM otherwise reads the provider-native key env var itself.
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        self._timeout = timeout

    def complete(
        self, messages: list[Message], *, temperature: float = 0.0, max_tokens: int = 1024
    ) -> str:
        try:
            import litellm
        except ImportError as exc:  # pragma: no cover - env-specific
            raise RuntimeError(
                "the 'litellm' package is required for LiteLLMClient; run `uv sync`"
            ) from exc
        # Silently drop params a given provider doesn't support (e.g. some local models),
        # so the same call shape works everywhere. Also quiet LiteLLM's banner/debug chatter so
        # a clean CLI shows our message, not the library's.
        litellm.drop_params = True
        litellm.suppress_debug_info = True
        kwargs: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": self._timeout,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        response = litellm.completion(**kwargs)
        return response.choices[0].message.content or ""


def build_llm_from_env() -> LLMClient:
    """Construct the LiteLLM-backed client from the environment (see module docstring)."""
    return LiteLLMClient()
