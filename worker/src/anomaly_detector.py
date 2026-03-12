"""Z-score based anomaly detector for calibration measurements.

Intentionally simple and replaceable — the interface is stable
so a real ML model can drop in without changing processor.py.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass


@dataclass
class AnomalyResult:
    anomaly_score: float
    is_anomaly: bool
    deviation_pct: float
    confidence: float
    model_version: str
    details: dict[str, float]


class AnomalyDetector:
    """Z-score anomaly detection for calibration measurements."""

    def __init__(self) -> None:
        self.threshold = float(os.getenv("ANOMALY_Z_SCORE_THRESHOLD", "3.0"))
        self._model_version = os.getenv("ANOMALY_MODEL_VERSION", "1.0.0")

    @property
    def model_version(self) -> str:
        return self._model_version

    def analyze(
        self,
        measured_value: float,
        reference_value: float,
        uncertainty: float,
    ) -> AnomalyResult:
        """
        Calculate Z-score: |measured - reference| / uncertainty.
        Anomaly if Z > threshold (default 3.0).

        Returns anomaly_score, is_anomaly, deviation_pct, confidence.
        """
        if uncertainty <= 0:
            raise ValueError(f"Uncertainty must be > 0, got {uncertainty}")
        if not (math.isfinite(measured_value) and math.isfinite(reference_value)):
            raise ValueError("measured_value and reference_value must be finite")

        absolute_deviation = abs(measured_value - reference_value)
        z_score = absolute_deviation / uncertainty

        # Deviation as percentage of reference value
        deviation_pct = (
            (absolute_deviation / abs(reference_value)) * 100
            if reference_value != 0
            else 0.0
        )

        is_anomaly = z_score > self.threshold

        # Confidence: 1.0 for clear pass/fail, lower near boundary
        margin = abs(z_score - self.threshold) / self.threshold
        confidence = min(1.0, 0.5 + margin * 0.5)

        return AnomalyResult(
            anomaly_score=round(z_score, 6),
            is_anomaly=is_anomaly,
            deviation_pct=round(deviation_pct, 6),
            confidence=round(confidence, 4),
            model_version=self._model_version,
            details={
                "absolute_deviation": absolute_deviation,
                "z_score": z_score,
                "threshold": self.threshold,
                "uncertainty": uncertainty,
            },
        )
