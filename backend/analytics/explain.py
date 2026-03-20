"""
Updated Anomaly Explanation & Classification

This now implements REAL detection logic for classifying anomalies.
"""

from enum import Enum
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

from .types import MetricSeries, AnomalyResult


class AnomalyType(Enum):
    """Enumeration of anomaly classification types"""
    SPIKE = "spike"
    TREND = "trend"
    SEASONAL = "seasonal"
    NORMAL = "normal"


@dataclass
class AnomalyExplanation:
    """Structured explanation for a detected anomaly"""
    anomaly_type: AnomalyType
    baseline_value: Optional[float] = None
    observed_value: Optional[float] = None
    deviation_percent: Optional[float] = None
    confidence: float = 0.5
    severity: float = 0.5
    description: str = ""
    additional_context: Dict[str, any] = field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        """Check if this is a critical anomaly"""
        return self.severity >= 0.7 and self.confidence >= 0.6


class ExplanationClassifier:
    """Classify detected anomalies with REAL logic"""

    def __init__(self):
        """Initialize classifier"""
        pass

    def classify(
            self,
            metric_series: MetricSeries,
            anomaly_result: AnomalyResult,
    ) -> AnomalyExplanation:
        """
        Classify anomaly into type with real detection parameters.
        """

        # Get window data
        window_values = []
        for ts, val in zip(metric_series.timestamps, metric_series.values):
            if anomaly_result.window_start <= ts <= anomaly_result.window_end:
                window_values.append(val)

        if not window_values:
            return AnomalyExplanation(
                anomaly_type=AnomalyType.NORMAL,
                description="No data in window",
            )

        window_values = np.array(window_values)
        baseline_value = np.mean(metric_series.values)
        observed_value = np.mean(window_values)

        # Calculate deviation percentage
        if baseline_value != 0:
            deviation_percent = ((observed_value - baseline_value) / abs(baseline_value)) * 100
        else:
            deviation_percent = 0

        # REAL DETECTION LOGIC HERE
        anomaly_type = self._detect_type(
            window_values,
            baseline_value,
            anomaly_result.anomaly_label,
        )

        # Calculate severity
        severity = min(1.0, abs(deviation_percent) / 50)  # Normalize

        return AnomalyExplanation(
            anomaly_type=anomaly_type,
            baseline_value=baseline_value,
            observed_value=observed_value,
            deviation_percent=deviation_percent,
            confidence=anomaly_result.anomaly_score,
            severity=severity,
            description=f"Detected {anomaly_type.value} in {metric_series.metric_name}",
        )

    def _detect_type(
            self,
            window_values: np.ndarray,
            baseline: float,
            label: str,
    ) -> AnomalyType:
        """Map detected label to anomaly type"""
        type_map = {
            "spike": AnomalyType.SPIKE,
            "trend": AnomalyType.TREND,
            "seasonal": AnomalyType.SEASONAL,
            "normal": AnomalyType.NORMAL,
        }
        return type_map.get(label, AnomalyType.NORMAL)

    def classify_batch(
            self,
            metric_series: MetricSeries,
            anomaly_results: List[AnomalyResult],
    ) -> List[AnomalyExplanation]:
        """Classify multiple anomalies"""
        return [self.classify(metric_series, result) for result in anomaly_results]


# Detection helper classes
class SpikeDetector:
    """Detect spike anomalies"""

    @staticmethod
    def is_spike(
            values: List[float],
            baseline: float,
            threshold: float = 2.0,
    ) -> bool:
        """Check if values represent a spike"""
        if not values:
            return False
        values_array = np.array(values)
        max_val = np.max(values_array)
        std_dev = np.std(values_array)
        return (max_val - baseline) > (threshold * std_dev)


class TrendDetector:
    """Detect trend anomalies"""

    @staticmethod
    def detect_trend(values: List[float]) -> Optional[str]:
        """Detect uptrend, downtrend, or None"""
        if len(values) < 2:
            return None

        values_array = np.array(values)
        diffs = np.diff(values_array)

        # All positive = uptrend
        if np.all(diffs > 0):
            return "up"
        # All negative = downtrend
        elif np.all(diffs < 0):
            return "down"
        else:
            return None


class SeasonalityDetector:
    """Detect seasonal anomalies"""

    @staticmethod
    def detect_seasonality(values: List[float]) -> bool:
        """Check if values show seasonal patterns"""
        if len(values) < 4:
            return False

        # Simple seasonality check: repeating variance
        values_array = np.array(values)
        # Check if standard deviation is consistent
        half = len(values_array) // 2
        std1 = np.std(values_array[:half])
        std2 = np.std(values_array[half:])

        # Similar variance suggests seasonality
        return abs(std1 - std2) < max(std1, std2) * 0.5


@dataclass
class ExplanationTemplate:
    """Template for generating explanations"""
    anomaly_type: AnomalyType
    template: str

    def render(self, explanation: AnomalyExplanation) -> str:
        """Render explanation text"""
        try:
            return self.template.format(
                baseline=explanation.baseline_value,
                observed=explanation.observed_value,
                deviation_percent=explanation.deviation_percent,
                type=explanation.anomaly_type.value,
            )
        except (KeyError, ValueError):
            return self.template


class ExplanationTemplateRegistry:
    """Registry of explanation templates"""

    _templates: Dict[AnomalyType, ExplanationTemplate] = {
        AnomalyType.SPIKE: ExplanationTemplate(
            anomaly_type=AnomalyType.SPIKE,
            template=(
                "🔴 SPIKE: Value jumped from {baseline:.2f} to {observed:.2f} "
                "({deviation_percent:+.1f}%). Quick recovery expected."
            ),
        ),
        AnomalyType.TREND: ExplanationTemplate(
            anomaly_type=AnomalyType.TREND,
            template=(
                "📈 TREND: Sustained directional change detected. "
                "Current {observed:.2f} vs baseline {baseline:.2f} "
                "({deviation_percent:+.1f}%). May indicate resource saturation."
            ),
        ),
        AnomalyType.SEASONAL: ExplanationTemplate(
            anomaly_type=AnomalyType.SEASONAL,
            template=(
                "🔄 SEASONAL: Pattern deviation. "
                "Current {observed:.2f} deviates from expected baseline {baseline:.2f} "
                "({deviation_percent:+.1f}%). Check activity patterns."
            ),
        ),
        AnomalyType.NORMAL: ExplanationTemplate(
            anomaly_type=AnomalyType.NORMAL,
            template="✅ NORMAL: Value {observed:.2f} is within expected range.",
        ),
    }

    @classmethod
    def get_template(cls, anomaly_type: AnomalyType) -> ExplanationTemplate:
        """Get template for anomaly type"""
        return cls._templates.get(
            anomaly_type,
            ExplanationTemplate(
                anomaly_type=anomaly_type,
                template="Anomaly of type {type} detected.",
            ),
        )

    @classmethod
    def register_template(
            cls,
            anomaly_type: AnomalyType,
            template: ExplanationTemplate,
    ) -> None:
        """Register custom template"""
        cls._templates[anomaly_type] = template