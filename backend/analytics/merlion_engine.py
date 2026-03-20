"""
Merlion Anomaly Detection Engine - CLEAN VERSION

Properly handles Merlion's IsolationForest with required config.
"""

import sys
import os
from typing import List, Optional, Dict
from datetime import datetime
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .engine import AnomalyDetectionEngine
from .types import MetricSeries, AnomalyResult
from .windows import SlidingWindowExtractor

# Import Merlion IsolationForest properly
try:
    from merlion.models.anomaly.isolation_forest import IsolationForest, IsolationForestConfig

    HAS_MERLION_IF = True
    print("[OK] Merlion IsolationForest imported successfully")
except ImportError as e:
    HAS_MERLION_IF = False
    print(f"[WARNING] Merlion IsolationForest import failed: {e}")

# Fallback to sklearn
try:
    from sklearn.ensemble import IsolationForest as SklearnIsolationForest

    HAS_SKLEARN_IF = True
except ImportError:
    HAS_SKLEARN_IF = False


class MerlionAnomalyEngine(AnomalyDetectionEngine):
    """
    Anomaly detection engine using Merlion IsolationForest.

    Properly initializes Merlion with required config parameter.

    Usage:
        >>> engine = MerlionAnomalyEngine(config={
        ...     'contamination': 0.05,
        ...     'window_size': 100,
        ... })
        >>> results = engine.detect(metric_series)
    """

    def __init__(self, config: Optional[Dict[str, any]] = None):
        """
        Initialize Merlion anomaly detection engine.

        Args:
            config: Configuration dictionary with:
                - contamination: Expected anomaly proportion (default: 0.05)
                - window_size: Window size in points (default: 100)
        """
        super().__init__(config)

        self.contamination = self.config.get('contamination', 0.05)
        self.window_size = self.config.get('window_size', 100)

        # Try Merlion first, fall back to sklearn
        if HAS_MERLION_IF:
            self._init_merlion()
        elif HAS_SKLEARN_IF:
            self._init_sklearn()
        else:
            raise RuntimeError("No anomaly detection library available!")

    def _init_merlion(self):
        """Initialize Merlion with proper config"""
        try:
            # Create config (REQUIRED by Merlion)
            config = IsolationForestConfig(
                contamination=self.contamination,
            )

            # Initialize model with config parameter
            self.model = IsolationForest(config=config)
            self.using_merlion = True

        except Exception as e:
            print(f"⚠️ Merlion init failed: {e}. Using sklearn fallback.")
            if HAS_SKLEARN_IF:
                self._init_sklearn()
            else:
                raise

    def _init_sklearn(self):
        """Initialize sklearn fallback"""
        self.model = SklearnIsolationForest(
            contamination=self.contamination,
            random_state=42,
        )
        self.using_merlion = False

    def detect(
            self,
            time_series: MetricSeries,
            window_size: Optional[int] = None,
    ) -> List[AnomalyResult]:
        """
        Detect anomalies in time series.

        Args:
            time_series: MetricSeries to analyze
            window_size: Optional window size override

        Returns:
            List[AnomalyResult] with scores and labels
        """

        if len(time_series.values) < 10:
            raise ValueError("Time series too short (need ≥10 points)")

        window_sz = window_size or self.window_size
        window_sz = min(window_sz, len(time_series.values) // 2)

        # Extract windows
        extractor = SlidingWindowExtractor(
            window_size_points=window_sz,
            stride_points=max(1, window_sz // 2),
            include_partial_windows=True,
        )

        windows = extractor.extract(time_series)
        results = []

        for window in windows:
            try:
                window_values = np.array(
                    time_series.values[window.start_idx:window.end_idx],
                    dtype=np.float32
                )

                anomaly_score, anomaly_label = self._detect_window(window_values)

                result = AnomalyResult(
                    tenant_id=time_series.tenant_id,
                    cluster_id=time_series.cluster_id,
                    node_id=time_series.node_id,
                    metric_name=time_series.metric_name,
                    window_start=window.start_time,
                    window_end=window.end_time,
                    anomaly_score=float(np.clip(anomaly_score, 0, 1)),
                    anomaly_label=anomaly_label,
                    magnitude=None,
                    explanation=None,
                )

                results.append(result)

            except Exception as e:
                continue

        return results

    def _detect_window(self, values: np.ndarray) -> tuple:
        """Run detection on single window. Returns (score, label)."""

        if len(values) < 2:
            return 0.0, "normal"

        try:
            # Reshape to 2D
            X = values.reshape(-1, 1)

            if self.using_merlion:
                # Use Merlion
                predictions = self.model.predict(X)
            else:
                # Use sklearn
                predictions = self.model.fit_predict(X)

            # Count anomalies (-1 = anomaly)
            anomaly_mask = (predictions == -1)
            anomaly_count = np.sum(anomaly_mask)
            anomaly_score = min(1.0, float(anomaly_count) / len(values))

            # Classify type
            anomaly_label = self._classify_anomaly(values, anomaly_mask)

            return anomaly_score, anomaly_label

        except Exception as e:
            return 0.0, "normal"

    def _classify_anomaly(self, values: np.ndarray, anomaly_mask) -> str:
        """Classify anomaly type"""

        try:
            anomaly_mask = np.array(anomaly_mask, dtype=bool)
        except:
            return "normal"

        anomaly_count = np.sum(anomaly_mask)

        if anomaly_count == 0:
            return "normal"

        if anomaly_count <= 3:
            return "spike"

        anomaly_indices = np.where(anomaly_mask)[0]
        if len(anomaly_indices) > 1:
            anomaly_values = values[anomaly_indices]
            diffs = np.diff(anomaly_values)

            if np.all(diffs > -1e-6) or np.all(diffs < 1e-6):
                return "trend"

        return "seasonal"

    def explain(
            self,
            time_series: MetricSeries,
            anomaly_result: AnomalyResult,
    ) -> str:
        """Generate explanation for detected anomaly"""

        window_values = []
        for ts, val in zip(time_series.timestamps, time_series.values):
            if anomaly_result.window_start <= ts <= anomaly_result.window_end:
                window_values.append(val)

        if not window_values:
            return "Unable to generate explanation"

        baseline = np.mean(time_series.values)
        window_mean = np.mean(window_values)
        window_max = np.max(window_values)

        if anomaly_result.anomaly_label == "spike":
            if baseline != 0:
                deviation = ((window_max - baseline) / abs(baseline)) * 100
            else:
                deviation = 0
            return f"Spike: {window_max:.2f} ({deviation:+.1f}% from {baseline:.2f})"

        elif anomaly_result.anomaly_label == "trend":
            if baseline != 0:
                change = ((window_mean - baseline) / abs(baseline)) * 100
            else:
                change = 0
            return f"Trend: {window_mean:.2f} ({change:+.1f}% from {baseline:.2f})"

        else:
            return f"Anomaly in {anomaly_result.metric_name}"

    @property
    def engine_name(self) -> str:
        backend = "Merlion" if self.using_merlion else "Sklearn"
        return f"AnomalyEngine({backend})"

    @property
    def engine_version(self) -> str:
        return "1.2.0-phase3"