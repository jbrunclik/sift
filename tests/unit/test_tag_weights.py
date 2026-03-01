import pytest

from backend.preferences.tag_weights import (
    DELTA_MISSED,
    DELTA_NEGATIVE,
    DELTA_POSITIVE,
    WEIGHT_MAX,
    WEIGHT_MIN,
    TagWithConfidence,
    adjust_weights,
    clamp,
    prune_zero_weights,
)


class TestClamp:
    def test_within_bounds(self) -> None:
        assert clamp(5.0) == 5.0

    def test_lower_bound(self) -> None:
        assert clamp(-10.0) == WEIGHT_MIN

    def test_upper_bound(self) -> None:
        assert clamp(20.0) == WEIGHT_MAX

    def test_exact_min(self) -> None:
        assert clamp(WEIGHT_MIN) == WEIGHT_MIN

    def test_exact_max(self) -> None:
        assert clamp(WEIGHT_MAX) == WEIGHT_MAX


class TestAdjustWeights:
    def test_new_tag(self) -> None:
        result = adjust_weights({}, [TagWithConfidence("python")], DELTA_POSITIVE)
        assert result == {"python": DELTA_POSITIVE}

    def test_existing_tag(self) -> None:
        result = adjust_weights({"python": 1.0}, [TagWithConfidence("python")], DELTA_POSITIVE)
        assert result["python"] == pytest.approx(1.1)

    def test_negative_delta(self) -> None:
        result = adjust_weights({"python": 1.0}, [TagWithConfidence("python")], DELTA_NEGATIVE)
        assert result["python"] == pytest.approx(0.9)

    def test_confidence_scaling(self) -> None:
        result = adjust_weights({}, [TagWithConfidence("python", confidence=0.5)], DELTA_POSITIVE)
        assert result["python"] == pytest.approx(DELTA_POSITIVE * 0.5)

    def test_multiple_tags(self) -> None:
        tags = [TagWithConfidence("python"), TagWithConfidence("ai")]
        result = adjust_weights({}, tags, DELTA_POSITIVE)
        assert result == {"python": DELTA_POSITIVE, "ai": DELTA_POSITIVE}

    def test_clamping_at_max(self) -> None:
        result = adjust_weights(
            {"python": WEIGHT_MAX}, [TagWithConfidence("python")], DELTA_POSITIVE
        )
        assert result["python"] == WEIGHT_MAX

    def test_clamping_at_min(self) -> None:
        result = adjust_weights(
            {"python": WEIGHT_MIN}, [TagWithConfidence("python")], DELTA_NEGATIVE
        )
        assert result["python"] == WEIGHT_MIN

    def test_immutability(self) -> None:
        original = {"python": 1.0}
        adjust_weights(original, [TagWithConfidence("python")], DELTA_POSITIVE)
        assert original == {"python": 1.0}

    def test_preserves_unrelated_tags(self) -> None:
        result = adjust_weights(
            {"python": 1.0, "rust": 2.0},
            [TagWithConfidence("python")],
            DELTA_POSITIVE,
        )
        assert result["rust"] == 2.0

    def test_missed_delta_stronger(self) -> None:
        result = adjust_weights({}, [TagWithConfidence("ai")], DELTA_MISSED)
        assert result["ai"] == DELTA_MISSED
        assert DELTA_MISSED > DELTA_POSITIVE


class TestPruneZeroWeights:
    def test_removes_near_zero(self) -> None:
        result = prune_zero_weights({"a": 0.005, "b": 1.0})
        assert result == {"b": 1.0}

    def test_keeps_above_threshold(self) -> None:
        result = prune_zero_weights({"a": 0.01, "b": 1.0})
        assert result == {"a": 0.01, "b": 1.0}

    def test_custom_threshold(self) -> None:
        result = prune_zero_weights({"a": 0.05, "b": 1.0}, threshold=0.1)
        assert result == {"b": 1.0}
