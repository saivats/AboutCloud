"""
Configuration for Anomaly Detection

Centralized settings for thresholds, detection parameters, etc.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class DetectionConfig:
    """Global detection configuration"""

    # Default thresholds
    anomaly_score_threshold: float = 0.5  # [0, 1]
    critical_threshold: float = 0.8

    # Engine parameters
    window_size_points: int = 100
    stride_points: int = 50

    # Merlion parameters
    contamination: float = 0.05  # Expected % of anomalies
    algorithm: str = "isolation_forest"

    # Metric-specific overrides
    metric_thresholds: Dict[str, float] = field(default_factory=dict)

    def get_threshold_for_metric(self, metric_name: str) -> float:
        """Get threshold for specific metric"""
        return self.metric_thresholds.get(
            metric_name,
            self.anomaly_score_threshold,
        )

    def is_critical(self, score: float) -> bool:
        """Check if score is critical"""
        return score >= self.critical_threshold


# Global configuration instance
_global_config = DetectionConfig()


def get_config() -> DetectionConfig:
    """Get global configuration"""
    return _global_config


def set_config(config: DetectionConfig) -> None:
    """Set global configuration"""
    global _global_config
    _global_config = config


# Preset configurations for different scenarios
CPU_FOCUSED_CONFIG = DetectionConfig(
    anomaly_score_threshold=0.6,
    metric_thresholds={
        "cpu_usage": 0.7,
        "cpu_wait": 0.5,
    },
)

MEMORY_FOCUSED_CONFIG = DetectionConfig(
    anomaly_score_threshold=0.5,
    metric_thresholds={
        "memory_used": 0.6,
        "memory_free": 0.6,
    },
)

STRICT_CONFIG = DetectionConfig(
    anomaly_score_threshold=0.3,
    critical_threshold=0.6,
    contamination=0.1,
)