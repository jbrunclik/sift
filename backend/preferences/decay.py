"""Weight decay — gradually reduces tag weights toward zero over time."""

DECAY_FACTOR = 0.995
PRUNE_THRESHOLD = 0.01


def apply_decay(weights: dict[str, float]) -> dict[str, float]:
    """Multiply all weights by DECAY_FACTOR, prune those below threshold."""
    result: dict[str, float] = {}
    for tag, weight in weights.items():
        decayed = weight * DECAY_FACTOR
        if abs(decayed) >= PRUNE_THRESHOLD:
            result[tag] = decayed
    return result
