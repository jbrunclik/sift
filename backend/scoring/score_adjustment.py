"""Deterministic post-LLM score adjustment based on user tag weights."""

from backend.scoring.scorer import TagScore

ADJUSTMENT_FACTOR = 0.3
MAX_ADJUSTMENT = 1.5


def compute_adjustment(tags: list[TagScore], weights: dict[str, float]) -> float:
    """Compute score adjustment as sum(weight * confidence * FACTOR), clamped."""
    total = 0.0
    for tag in tags:
        name = tag.name.lstrip("+").lower().strip()
        weight = weights.get(name, 0.0)
        total += weight * tag.confidence * ADJUSTMENT_FACTOR
    return max(-MAX_ADJUSTMENT, min(MAX_ADJUSTMENT, total))
