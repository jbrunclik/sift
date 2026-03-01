from dataclasses import dataclass

DELTA_POSITIVE = 0.1
DELTA_NEGATIVE = -0.1
DELTA_MISSED = 0.2

WEIGHT_MIN = -5.0
WEIGHT_MAX = 10.0


@dataclass(frozen=True)
class TagWithConfidence:
    name: str
    confidence: float = 1.0


def clamp(value: float) -> float:
    """Clamp a weight value to [WEIGHT_MIN, WEIGHT_MAX]."""
    return max(WEIGHT_MIN, min(WEIGHT_MAX, value))


def adjust_weights(
    current: dict[str, float],
    tags: list[TagWithConfidence],
    delta: float,
) -> dict[str, float]:
    """Apply delta * confidence per tag to current weights, returning a new dict."""
    result = dict(current)
    for tag in tags:
        old = result.get(tag.name, 0.0)
        result[tag.name] = clamp(old + delta * tag.confidence)
    return result


def prune_zero_weights(
    weights: dict[str, float],
    threshold: float = 0.01,
) -> dict[str, float]:
    """Remove entries whose absolute value is below threshold."""
    return {k: v for k, v in weights.items() if abs(v) >= threshold}
