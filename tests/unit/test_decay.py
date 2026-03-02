import pytest

from backend.preferences.decay import DECAY_FACTOR, PRUNE_THRESHOLD, apply_decay


class TestApplyDecay:
    def test_reduces_weights(self) -> None:
        weights = {"python": 2.0, "rust": 1.0}
        result = apply_decay(weights)
        assert result["python"] == pytest.approx(2.0 * DECAY_FACTOR)
        assert result["rust"] == pytest.approx(1.0 * DECAY_FACTOR)

    def test_prunes_near_zero(self) -> None:
        weights = {"tiny": 0.005}  # Below PRUNE_THRESHOLD after decay
        result = apply_decay(weights)
        assert "tiny" not in result

    def test_handles_negatives(self) -> None:
        weights = {"sports": -2.0}
        result = apply_decay(weights)
        assert result["sports"] == pytest.approx(-2.0 * DECAY_FACTOR)

    def test_prunes_near_zero_negative(self) -> None:
        weights = {"tiny": -0.005}
        result = apply_decay(weights)
        assert "tiny" not in result

    def test_empty_dict(self) -> None:
        assert apply_decay({}) == {}

    def test_does_not_mutate_input(self) -> None:
        weights = {"python": 2.0}
        apply_decay(weights)
        assert weights["python"] == 2.0

    def test_preserves_at_threshold(self) -> None:
        # PRUNE_THRESHOLD / DECAY_FACTOR should survive decay
        weights = {"edge": PRUNE_THRESHOLD / DECAY_FACTOR + 0.001}
        result = apply_decay(weights)
        assert "edge" in result
