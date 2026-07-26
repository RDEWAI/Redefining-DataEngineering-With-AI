"""LiteLLM-backed client: env-driven config + provider-agnostic call shape (no network)."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from patient_360.semantic.llm import (
    DEFAULT_MODEL,
    LiteLLMClient,
    LLMClient,
    Message,
    build_llm_from_env,
)

_ENV = ("LLM_MODEL", "LLM_API_BASE", "LLM_BASE_URL", "LLM_API_KEY")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _ENV:
        monkeypatch.delenv(var, raising=False)


def _install_fake_litellm(monkeypatch: pytest.MonkeyPatch, reply: str = "SELECT 1") -> dict:
    """Inject a stand-in ``litellm`` module and return the dict its completion() records into."""
    captured: dict[str, Any] = {}
    fake = types.ModuleType("litellm")
    fake.drop_params = False

    def completion(**kwargs: Any) -> Any:
        captured.update(kwargs)
        message = types.SimpleNamespace(content=reply)
        choice = types.SimpleNamespace(message=message)
        return types.SimpleNamespace(choices=[choice])

    fake.completion = completion  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "litellm", fake)
    return captured


def test_client_satisfies_protocol() -> None:
    assert isinstance(LiteLLMClient(), LLMClient)


def test_build_from_env_returns_litellm_client() -> None:
    assert isinstance(build_llm_from_env(), LiteLLMClient)


def test_default_model_is_anthropic_claude() -> None:
    assert LiteLLMClient().model == DEFAULT_MODEL == "anthropic/claude-opus-5"


def test_model_and_base_come_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "ollama/qwen2.5-coder:7b")
    monkeypatch.setenv("LLM_API_BASE", "http://localhost:11434")
    c = LiteLLMClient()
    assert c.model == "ollama/qwen2.5-coder:7b"
    assert c.api_base == "http://localhost:11434"


def test_llm_base_url_is_accepted_as_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    assert LiteLLMClient().api_base == "http://localhost:11434/v1"


def test_complete_passes_messages_and_config_through(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _install_fake_litellm(monkeypatch, reply="SELECT count(*)")
    client = LiteLLMClient(model="anthropic/claude-opus-5", api_key="sk-ant-test")

    out = client.complete(
        [Message("system", "you are an analyst"), Message("user", "how many?")],
        temperature=0.0,
        max_tokens=256,
    )

    assert out == "SELECT count(*)"
    assert captured["model"] == "anthropic/claude-opus-5"
    # system turn is passed through untouched — LiteLLM does provider-native placement
    assert captured["messages"] == [
        {"role": "system", "content": "you are an analyst"},
        {"role": "user", "content": "how many?"},
    ]
    assert captured["temperature"] == 0.0
    assert captured["max_tokens"] == 256
    assert captured["api_key"] == "sk-ant-test"
    # drop_params is enabled so unsupported params don't break non-Anthropic providers
    assert sys.modules["litellm"].drop_params is True


def test_complete_omits_api_base_and_key_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _install_fake_litellm(monkeypatch)
    LiteLLMClient(model="gpt-4o").complete([Message("user", "hi")])
    assert "api_base" not in captured  # let LiteLLM resolve provider defaults
    assert "api_key" not in captured   # let LiteLLM read the provider-native key env var
