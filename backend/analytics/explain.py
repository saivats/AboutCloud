"""
Anomaly Explanation Logic

Implements real classification of detected anomalies into categories:
  SPIKE:    Sudden, temporary spike in metric value
  TREND:    Sustained increase or decrease over time
  SEASONAL: Cyclic pattern deviation from expected
  NORMAL:   No anomaly detected (baseline for comparison)
"""

from enum import Enum
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime
import math

from .types import MetricSeries, AnomalyResult


class AnomalyType(Enum):
    """
    Enumeration of anomaly classification types.

    This maps to the anomaly_label field in AnomalyResult.
    """
    SPIKE = "spike"           # Sudden deviation, quickly recovers
    TREND = "trend"           # Sustained change in direction
    SEASONAL = "seasonal"     # Deviation from expected cyclic pattern
    NORMAL = "normal"         # No anomaly (baseline state)


@dataclass
class AnomalyExplanation:
    """
    Structured explanation for a detected anomaly.

    This contains:
      - What type of anomaly it is
      - Severity/confidence score
      - Key statistics
      - Human-readable description
    """
    anomaly_type: AnomalyType

    # Statistics
    baseline_value: Optional[float] = None     # Expected "normal" value
    observed_value: Optional[float] = None     # What we actually saw
    deviation_percent: Optional[float] = None  # Percent deviation from baseline

    # Severity
    confidence: float = 0.5  # [0, 1] how confident in this classification
    severity: float = 0.5    # [0, 1] how severe this anomaly is

    # Context
    description: str = ""
    additional_context: Dict[str, any] = field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        """Quick check: is this a critical anomaly?"""
        return self.severity >= 0.7 and self.confidence >= 0.6


class ExplanationClassifier:
    """
    Classifies anomalies into types using statistical analysis.

    Uses SpikeDetector, TrendDetector, and SeasonalityDetector
    to determine the pattern of an anomaly.
    """

    def __init__(self):
        """Initialize classifier with real detectors"""
        self.spike_detector = SpikeDetector()
        self.trend_detector = TrendDetector()
        self.seasonality_detector = SeasonalityDetector()

    def classify(
        self,
        metric_series: MetricSeries,
        anomaly_result: AnomalyResult,
    ) -> AnomalyExplanation:
        """
        Classify an anomaly into one of the standard types.

        Uses real statistical analysis to determine whether the anomaly
        is a spike, trend, or seasonal deviation.

        Args:
            metric_series: Original time series that was analyzed
            anomaly_result: Detection result to classify

        Returns:
            AnomalyExplanation with category and details
        """
        # Extract window values
        window_values = []
        for ts, val in zip(metric_series.timestamps, metric_series.values):
            if anomaly_result.window_start <= ts <= anomaly_result.window_end:
                window_values.append(val)

        if not window_values:
            return AnomalyExplanation(
                anomaly_type=AnomalyType.NORMAL,
                description="No data in anomaly window",
            )

        all_values = metric_series.values
        baseline = sum(all_values) / len(all_values) if all_values else 0.0

        # Compute observed statistics
        observed_mean = sum(window_values) / len(window_values)
        observed_max = max(window_values)

        # Compute deviation
        deviation_pct = 0.0
        if baseline != 0:
            deviation_pct = ((observed_mean - baseline) / abs(baseline)) * 100

        # If score is very low, classify as normal
        if anomaly_result.anomaly_score < 0.05:
            return AnomalyExplanation(
                anomaly_type=AnomalyType.NORMAL,
                baseline_value=baseline,
                observed_value=observed_mean,
                deviation_percent=deviation_pct,
                confidence=0.9,
                severity=anomaly_result.anomaly_score,
                description=f"Normal behavior: {observed_mean:.2f} within baseline {baseline:.2f}",
            )

        # Run detectors
        is_spike = SpikeDetector.is_spike(window_values, baseline, threshold=2.0)
        trend_dir = TrendDetector.detect_trend(window_values)
        is_seasonal = SeasonalityDetector.detect_seasonality(all_values)

        # Determine type — spike takes priority, then trend, then seasonal
        if is_spike:
            anomaly_type = AnomalyType.SPIKE
            spike_val = observed_max
            spike_dev = ((spike_val - baseline) / abs(baseline)) * 100 if baseline != 0 else 0.0
            description = (
                f"Spike detected: peak {spike_val:.2f} "
                f"({spike_dev:+.1f}% from baseline {baseline:.2f})"
            )
            confidence = min(1.0, anomaly_result.anomaly_score + 0.3)
            severity = min(1.0, abs(spike_dev) / 100.0)

        elif trend_dir is not None:
            anomaly_type = AnomalyType.TREND
            description = (
                f"Trend detected ({trend_dir}): window mean {observed_mean:.2f} "
                f"({deviation_pct:+.1f}% from baseline {baseline:.2f})"
            )
            confidence = min(1.0, anomaly_result.anomaly_score + 0.2)
            severity = min(1.0, abs(deviation_pct) / 50.0)

        elif is_seasonal:
            anomaly_type = AnomalyType.SEASONAL
            description = (
                f"Seasonal anomaly: value {observed_mean:.2f} deviates "
                f"{deviation_pct:+.1f}% from expected pattern (baseline {baseline:.2f})"
            )
            confidence = min(1.0, anomaly_result.anomaly_score + 0.1)
            severity = min(1.0, abs(deviation_pct) / 80.0)

        else:
            # Fall back to the label from the detector
            label = anomaly_result.anomaly_label
            if label in ("spike", "trend", "seasonal"):
                anomaly_type = AnomalyType(label)
            else:
                anomaly_type = AnomalyType.NORMAL

            description = (
                f"Anomaly in {anomaly_result.metric_name}: "
                f"score {anomaly_result.anomaly_score:.2f}, "
                f"mean {observed_mean:.2f} vs baseline {baseline:.2f}"
            )
            confidence = anomaly_result.anomaly_score
            severity = anomaly_result.anomaly_score

        return AnomalyExplanation(
            anomaly_type=anomaly_type,
            baseline_value=baseline,
            observed_value=observed_mean,
            deviation_percent=deviation_pct,
            confidence=min(1.0, confidence),
            severity=min(1.0, severity),
            description=description,
        )

    def classify_batch(
        self,
        metric_series: MetricSeries,
        anomaly_results: List[AnomalyResult],
    ) -> List[AnomalyExplanation]:
        """
        Classify multiple anomalies from the same series.

        Args:
            metric_series: Original series
            anomaly_results: Multiple detection results

        Returns:
            List of explanations (same order as input)
        """
        return [self.classify(metric_series, result) for result in anomaly_results]


class SpikeDetector:
    """
    Detects spike anomalies using z-score analysis.

    A spike is characterized by:
      - Sudden jump in value
      - Quick recovery to baseline
      - Localized in time (typically 1-5 observations)
    """

    @staticmethod
    def is_spike(
        values: List[float],
        baseline: float,
        threshold: float = 2.0,
    ) -> bool:
        """
        Check if values represent a spike pattern.

        A spike is detected when:
        1. At least one value deviates more than threshold * std from baseline
        2. The spike is localized (affects < 30% of the window)

        Args:
            values: Time series values to analyze
            baseline: Expected normal value
            threshold: Standard-deviation multiplier for spike detection

        Returns:
            bool: True if spike pattern detected
        """
        if len(values) < 2:
            return False

        # Compute standard deviation
        mean_val = sum(values) / len(values)
        variance = sum((v - mean_val) ** 2 for v in values) / len(values)
        std_dev = math.sqrt(variance) if variance > 0 else 1.0

        # Count values exceeding threshold
        spike_count = 0
        for v in values:
            if abs(v - baseline) > threshold * std_dev:
                spike_count += 1

        # Spike: at least one point exceeds, but fewer than 30% of the window
        if spike_count == 0:
            return False

        spike_ratio = spike_count / len(values)
        return spike_ratio < 0.3

    @staticmethod
    def compute_spike_magnitude(values: List[float], baseline: float) -> float:
        """Compute the maximum deviation from baseline"""
        if not values:
            return 0.0
        max_dev = max(abs(v - baseline) for v in values)
        return max_dev / abs(baseline) if baseline != 0 else max_dev


class TrendDetector:
    """
    Detects trend anomalies using simple linear regression.

    A trend is characterized by:
      - Sustained directional change (increasing/decreasing)
      - Lasts over multiple observations
      - May indicate resource saturation or degradation
    """

    @staticmethod
    def detect_trend(values: List[float]) -> Optional[str]:
        """
        Detect if values show an uptrend, downtrend, or stable.

        Uses simple linear regression: if the slope is significant
        relative to the value range, it's a trend.

        Args:
            values: Time series values

        Returns:
            str: "up", "down", or None for no trend
        """
        if len(values) < 3:
            return None

        n = len(values)
        # Simple linear regression: y = mx + b
        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n

        numerator = 0.0
        denominator = 0.0
        for i, v in enumerate(values):
            numerator += (i - x_mean) * (v - y_mean)
            denominator += (i - x_mean) ** 2

        if denominator == 0:
            return None

        slope = numerator / denominator

        # Determine if slope is significant
        # Slope needs to produce a total change > 10% of mean over the window
        total_change = abs(slope * n)
        if y_mean != 0 and total_change / abs(y_mean) > 0.10:
            return "up" if slope > 0 else "down"

        return None


class SeasonalityDetector:
    """
    Detects seasonality using autocorrelation.

    Seasonality is characterized by:
      - Repeating cyclic patterns
      - Deviation from expected cycle
      - Common in cloud metrics (business hours, daily patterns)
    """

    @staticmethod
    def detect_seasonality(values: List[float]) -> bool:
        """
        Check if values show seasonal patterns using autocorrelation.

        Computes autocorrelation at various lags and checks if any
        lag shows a strong correlation (indicating periodicity).

        Args:
            values: Time series values (should be the full series, not just a window)

        Returns:
            bool: True if seasonality detected
        """
        if len(values) < 20:
            return False

        n = len(values)
        mean_val = sum(values) / n
        variance = sum((v - mean_val) ** 2 for v in values) / n

        if variance < 1e-10:
            return False

        # Check autocorrelation at candidate lags
        # Look for peaks at reasonable periods (10-50% of series length)
        min_lag = max(2, n // 10)
        max_lag = n // 3

        for lag in range(min_lag, min(max_lag + 1, n)):
            autocorr = 0.0
            count = 0
            for i in range(n - lag):
                autocorr += (values[i] - mean_val) * (values[i + lag] - mean_val)
                count += 1

            if count > 0:
                autocorr = autocorr / (count * variance)
                # Strong autocorrelation suggests periodicity
                if autocorr > 0.5:
                    return True

        return False


@dataclass
class ExplanationTemplate:
    """
    Template for generating human-readable explanations.

    Allows consistent, parameterized explanation text generation.
    """
    anomaly_type: AnomalyType
    template: str

    def render(self, explanation: AnomalyExplanation) -> str:
        """
        Render explanation text from template.

        Args:
            explanation: AnomalyExplanation with values to interpolate

        Returns:
            Formatted explanation string
        """
        try:
            return self.template.format(
                baseline=explanation.baseline_value,
                observed=explanation.observed_value,
                deviation_percent=explanation.deviation_percent or 0.0,
                type=explanation.anomaly_type.value,
            )
        except (KeyError, ValueError, TypeError):
            return explanation.description or self.template


class ExplanationTemplateRegistry:
    """
    Registry of explanation templates for each anomaly type.

    Provides default explanations; can be customized per organization.
    """

    _templates: Dict[AnomalyType, ExplanationTemplate] = {
        AnomalyType.SPIKE: ExplanationTemplate(
            anomaly_type=AnomalyType.SPIKE,
            template=(
                "Spike detected: value increased from {baseline:.2f} to {observed:.2f} "
                "({deviation_percent:+.1f}% above baseline). "
                "This represents a sudden, temporary deviation."
            ),
        ),
        AnomalyType.TREND: ExplanationTemplate(
            anomaly_type=AnomalyType.TREND,
            template=(
                "Trend detected: metric shows sustained directional change. "
                "Current value {observed:.2f} deviates {deviation_percent:+.1f}% "
                "from baseline {baseline:.2f}. This may indicate resource saturation."
            ),
        ),
        AnomalyType.SEASONAL: ExplanationTemplate(
            anomaly_type=AnomalyType.SEASONAL,
            template=(
                "Seasonal anomaly: current value {observed:.2f} deviates from "
                "expected seasonal pattern (baseline {baseline:.2f}, "
                "{deviation_percent:+.1f}% off). Check for unusual activity patterns."
            ),
        ),
        AnomalyType.NORMAL: ExplanationTemplate(
            anomaly_type=AnomalyType.NORMAL,
            template="No anomaly detected. Value {observed:.2f} is within normal range.",
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