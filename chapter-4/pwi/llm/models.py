"""Model registry and pricing for Planning with Intent.

This module provides model metadata including pricing information
for cost tracking across different LLM providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ModelPricing:
    """Pricing information for a model (per million tokens)."""

    input_price: Decimal  # USD per million input tokens
    output_price: Decimal  # USD per million output tokens
    context_window: int = 128000  # Max context length


# Model pricing registry (prices in USD per million tokens)
# Last updated: January 2025
MODEL_PRICING: dict[str, ModelPricing] = {
    # OpenAI models
    "gpt-4o": ModelPricing(Decimal("2.50"), Decimal("10.00"), 128000),
    "gpt-4o-mini": ModelPricing(Decimal("0.15"), Decimal("0.60"), 128000),
    "gpt-4-turbo": ModelPricing(Decimal("10.00"), Decimal("30.00"), 128000),
    "gpt-4": ModelPricing(Decimal("30.00"), Decimal("60.00"), 8192),
    "gpt-3.5-turbo": ModelPricing(Decimal("0.50"), Decimal("1.50"), 16385),
    "o1": ModelPricing(Decimal("15.00"), Decimal("60.00"), 200000),
    "o1-mini": ModelPricing(Decimal("3.00"), Decimal("12.00"), 128000),
    # OpenRouter paths for OpenAI
    "openai/gpt-4o": ModelPricing(Decimal("2.50"), Decimal("10.00"), 128000),
    "openai/gpt-4o-mini": ModelPricing(Decimal("0.15"), Decimal("0.60"), 128000),
    "openai/gpt-4-turbo": ModelPricing(Decimal("10.00"), Decimal("30.00"), 128000),
    "openai/o1": ModelPricing(Decimal("15.00"), Decimal("60.00"), 200000),
    "openai/o1-mini": ModelPricing(Decimal("3.00"), Decimal("12.00"), 128000),
    # Anthropic models
    "claude-3-5-sonnet-20241022": ModelPricing(Decimal("3.00"), Decimal("15.00"), 200000),
    "claude-3-5-haiku-20241022": ModelPricing(Decimal("0.80"), Decimal("4.00"), 200000),
    "claude-3-opus-20240229": ModelPricing(Decimal("15.00"), Decimal("75.00"), 200000),
    "claude-3-sonnet-20240229": ModelPricing(Decimal("3.00"), Decimal("15.00"), 200000),
    "claude-3-haiku-20240307": ModelPricing(Decimal("0.25"), Decimal("1.25"), 200000),
    # OpenRouter paths for Anthropic
    "anthropic/claude-3.5-sonnet": ModelPricing(Decimal("3.00"), Decimal("15.00"), 200000),
    "anthropic/claude-3-5-sonnet": ModelPricing(Decimal("3.00"), Decimal("15.00"), 200000),
    "anthropic/claude-3.5-haiku": ModelPricing(Decimal("0.80"), Decimal("4.00"), 200000),
    "anthropic/claude-3-opus": ModelPricing(Decimal("15.00"), Decimal("75.00"), 200000),
    "anthropic/claude-3-sonnet": ModelPricing(Decimal("3.00"), Decimal("15.00"), 200000),
    "anthropic/claude-3-haiku": ModelPricing(Decimal("0.25"), Decimal("1.25"), 200000),
    # Google models via OpenRouter
    "google/gemini-pro-1.5": ModelPricing(Decimal("1.25"), Decimal("5.00"), 2000000),
    "google/gemini-flash-1.5": ModelPricing(Decimal("0.075"), Decimal("0.30"), 1000000),
    "google/gemini-2.0-flash-exp": ModelPricing(Decimal("0.00"), Decimal("0.00"), 1000000),
    # Meta models via OpenRouter
    "meta-llama/llama-3.1-405b-instruct": ModelPricing(
        Decimal("2.70"), Decimal("2.70"), 131072
    ),
    "meta-llama/llama-3.1-70b-instruct": ModelPricing(
        Decimal("0.52"), Decimal("0.75"), 131072
    ),
    "meta-llama/llama-3.1-8b-instruct": ModelPricing(
        Decimal("0.055"), Decimal("0.055"), 131072
    ),
    # Mistral models
    "mistral/mistral-large": ModelPricing(Decimal("2.00"), Decimal("6.00"), 128000),
    "mistral/mistral-medium": ModelPricing(Decimal("2.70"), Decimal("8.10"), 32000),
    "mistral/mistral-small": ModelPricing(Decimal("0.20"), Decimal("0.60"), 32000),
    # DeepSeek
    "deepseek/deepseek-chat": ModelPricing(Decimal("0.14"), Decimal("0.28"), 64000),
    "deepseek/deepseek-coder": ModelPricing(Decimal("0.14"), Decimal("0.28"), 64000),
}

# Default pricing for unknown models (conservative estimate)
DEFAULT_PRICING = ModelPricing(Decimal("3.00"), Decimal("15.00"), 128000)


def get_model_pricing(model: str) -> ModelPricing:
    """Get pricing information for a model.

    Args:
        model: Model name or identifier.

    Returns:
        ModelPricing for the model, or default pricing if unknown.
    """
    # Try exact match first
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]

    # Try normalized name (lowercase, remove version suffixes)
    normalized = model.lower()
    for key, pricing in MODEL_PRICING.items():
        if key.lower() in normalized or normalized in key.lower():
            return pricing

    return DEFAULT_PRICING


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> Decimal:
    """Calculate the cost of a completion.

    Args:
        model: Model name or identifier.
        prompt_tokens: Number of input tokens.
        completion_tokens: Number of output tokens.

    Returns:
        Cost in USD as a Decimal.
    """
    pricing = get_model_pricing(model)

    # Calculate cost (prices are per million tokens)
    input_cost = (Decimal(prompt_tokens) / Decimal(1_000_000)) * pricing.input_price
    output_cost = (Decimal(completion_tokens) / Decimal(1_000_000)) * pricing.output_price

    return input_cost + output_cost


def format_cost(cost: Decimal) -> str:
    """Format a cost value for display.

    Args:
        cost: Cost in USD.

    Returns:
        Formatted string like "$0.0123" or "<$0.01".
    """
    if cost < Decimal("0.01"):
        if cost == Decimal("0"):
            return "$0.00"
        return "<$0.01"
    return f"${cost:.4f}"
