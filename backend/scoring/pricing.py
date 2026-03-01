"""Gemini model pricing per million tokens (USD)."""

# {model_name: {"input": price_per_1M_tokens, "output": price_per_1M_tokens}}
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash-lite": {"input": 0.025, "output": 0.10},
    "gemini-2.5-flash-preview-04-17": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro-preview-05-06": {"input": 1.25, "output": 10.00},
    "gemini-3-flash-preview": {"input": 0.15, "output": 0.60},
}

# Default pricing for unknown models
DEFAULT_PRICING: dict[str, float] = {"input": 0.15, "output": 0.60}


def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate USD cost for a given model and token counts."""
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    cost = (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000
    return round(cost, 8)
