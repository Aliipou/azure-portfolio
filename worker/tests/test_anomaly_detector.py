"""Unit tests for AnomalyDetector — 100% coverage."""

import pytest

from src.anomaly_detector import AnomalyDetector, AnomalyResult


@pytest.fixture
def detector() -> AnomalyDetector:
    return AnomalyDetector()


class TestAnomalyDetector:
    def test_normal_measurement_not_anomaly(self, detector: AnomalyDetector) -> None:
        result = detector.analyze(
            measured_value=100.0,
            reference_value=100.0,
            uncertainty=0.5,
        )
        assert not result.is_anomaly
        assert result.anomaly_score == 0.0
        assert result.deviation_pct == 0.0
        assert result.confidence > 0.9

    def test_high_deviation_is_anomaly(self, detector: AnomalyDetector) -> None:
        # Z-score = |105 - 100| / 0.5 = 10.0 >> 3.0 threshold
        result = detector.analyze(
            measured_value=105.0,
            reference_value=100.0,
            uncertainty=0.5,
        )
        assert result.is_anomaly
        assert result.anomaly_score == pytest.approx(10.0, abs=1e-6)
        assert result.deviation_pct == pytest.approx(5.0, abs=1e-4)

    def test_boundary_just_below_threshold_not_anomaly(self, detector: AnomalyDetector) -> None:
        # Z-score = 2.99 < 3.0
        result = detector.analyze(
            measured_value=100.0 + 2.99 * 0.1,
            reference_value=100.0,
            uncertainty=0.1,
        )
        assert not result.is_anomaly

    def test_boundary_just_above_threshold_is_anomaly(self, detector: AnomalyDetector) -> None:
        # Z-score = 3.01 > 3.0
        result = detector.analyze(
            measured_value=100.0 + 3.01 * 0.1,
            reference_value=100.0,
            uncertainty=0.1,
        )
        assert result.is_anomaly

    def test_zero_uncertainty_raises(self, detector: AnomalyDetector) -> None:
        with pytest.raises(ValueError, match="Uncertainty must be > 0"):
            detector.analyze(100.0, 100.0, 0.0)

    def test_negative_uncertainty_raises(self, detector: AnomalyDetector) -> None:
        with pytest.raises(ValueError, match="Uncertainty must be > 0"):
            detector.analyze(100.0, 100.0, -1.0)

    def test_infinite_measured_value_raises(self, detector: AnomalyDetector) -> None:
        import math
        with pytest.raises(ValueError, match="finite"):
            detector.analyze(math.inf, 100.0, 0.5)

    def test_nan_reference_value_raises(self, detector: AnomalyDetector) -> None:
        import math
        with pytest.raises(ValueError, match="finite"):
            detector.analyze(100.0, math.nan, 0.5)

    def test_zero_reference_value_deviation_is_zero(self, detector: AnomalyDetector) -> None:
        result = detector.analyze(0.1, 0.0, 0.5)
        assert result.deviation_pct == 0.0  # avoids division by zero

    def test_exact_match_returns_zero_score(self, detector: AnomalyDetector) -> None:
        result = detector.analyze(50.0, 50.0, 1.0)
        assert result.anomaly_score == 0.0
        assert not result.is_anomaly

    def test_result_is_dataclass(self, detector: AnomalyDetector) -> None:
        result = detector.analyze(100.0, 100.0, 1.0)
        assert isinstance(result, AnomalyResult)
        assert result.model_version == detector.model_version

    def test_model_version_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANOMALY_MODEL_VERSION", "2.1.0")
        d = AnomalyDetector()
        assert d.model_version == "2.1.0"

    def test_custom_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANOMALY_Z_SCORE_THRESHOLD", "1.0")
        d = AnomalyDetector()
        # Z = (101 - 100) / 0.5 = 2.0 > 1.0 → anomaly
        result = d.analyze(101.0, 100.0, 0.5)
        assert result.is_anomaly

    def test_confidence_high_for_clear_anomaly(self, detector: AnomalyDetector) -> None:
        result = detector.analyze(200.0, 100.0, 0.5)
        assert result.confidence > 0.9

    def test_confidence_lower_near_boundary(self, detector: AnomalyDetector) -> None:
        # Z-score ≈ 3.0 → near boundary
        result = detector.analyze(100.0 + 3.0 * 0.1, 100.0, 0.1)
        assert result.confidence < 0.6

    def test_details_contains_expected_keys(self, detector: AnomalyDetector) -> None:
        result = detector.analyze(100.5, 100.0, 0.5)
        assert "z_score" in result.details
        assert "threshold" in result.details
        assert "uncertainty" in result.details
        assert "absolute_deviation" in result.details
