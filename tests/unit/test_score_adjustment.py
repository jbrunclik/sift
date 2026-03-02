import pytest

from backend.scoring.score_adjustment import (
    ADJUSTMENT_FACTOR,
    MAX_ADJUSTMENT,
    compute_adjustment,
)
from backend.scoring.scorer import TagScore


class TestComputeAdjustment:
    def test_zero_weights_no_adjustment(self) -> None:
        tags = [TagScore(name="python", confidence=0.9)]
        assert compute_adjustment(tags, {}) == 0.0

    def test_positive_weight(self) -> None:
        tags = [TagScore(name="python", confidence=1.0)]
        weights = {"python": 2.0}
        expected = 2.0 * 1.0 * ADJUSTMENT_FACTOR
        assert compute_adjustment(tags, weights) == pytest.approx(expected)

    def test_negative_weight(self) -> None:
        tags = [TagScore(name="sports", confidence=1.0)]
        weights = {"sports": -3.0}
        expected = -3.0 * 1.0 * ADJUSTMENT_FACTOR
        assert compute_adjustment(tags, weights) == pytest.approx(expected)

    def test_clamping_positive(self) -> None:
        tags = [TagScore(name="python", confidence=1.0)]
        weights = {"python": 10.0}  # 10.0 * 1.0 * 0.3 = 3.0 > MAX_ADJUSTMENT
        assert compute_adjustment(tags, weights) == MAX_ADJUSTMENT

    def test_clamping_negative(self) -> None:
        tags = [TagScore(name="sports", confidence=1.0)]
        weights = {"sports": -10.0}  # -10.0 * 1.0 * 0.3 = -3.0 < -MAX_ADJUSTMENT
        assert compute_adjustment(tags, weights) == -MAX_ADJUSTMENT

    def test_multi_tag_accumulation(self) -> None:
        tags = [
            TagScore(name="python", confidence=1.0),
            TagScore(name="testing", confidence=0.8),
        ]
        weights = {"python": 1.0, "testing": 0.5}
        expected = (1.0 * 1.0 + 0.5 * 0.8) * ADJUSTMENT_FACTOR
        assert compute_adjustment(tags, weights) == pytest.approx(expected)

    def test_confidence_scaling(self) -> None:
        tags = [TagScore(name="python", confidence=0.5)]
        weights = {"python": 2.0}
        expected = 2.0 * 0.5 * ADJUSTMENT_FACTOR
        assert compute_adjustment(tags, weights) == pytest.approx(expected)

    def test_suggestion_prefix_stripped(self) -> None:
        tags = [TagScore(name="+quantum-computing", confidence=0.9)]
        weights = {"quantum-computing": 1.5}
        expected = 1.5 * 0.9 * ADJUSTMENT_FACTOR
        assert compute_adjustment(tags, weights) == pytest.approx(expected)

    def test_empty_tags(self) -> None:
        assert compute_adjustment([], {"python": 5.0}) == 0.0
