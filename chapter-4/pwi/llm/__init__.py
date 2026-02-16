"""LLM integration for Planning with Intent.

This module provides the OpenAI-compatible client wrapper
and OpenRouter integration for multi-model support.
"""

from pwi.llm.client import (
    CompletionResponse,
    LLMClient,
    LLMClientError,
    LLMRateLimitError,
    Message,
)
from pwi.llm.models import (
    MODEL_PRICING,
    ModelPricing,
    calculate_cost,
    format_cost,
    get_model_pricing,
)

__all__ = [
    "CompletionResponse",
    "LLMClient",
    "LLMClientError",
    "LLMRateLimitError",
    "Message",
    "MODEL_PRICING",
    "ModelPricing",
    "calculate_cost",
    "format_cost",
    "get_model_pricing",
]
