"""
Analytics Module Initialization

Exposes the primary public API for analytics operations.

Note: Engine implementations (MerlionAnomalyEngine, AnomalyDetectionPipeline)
are imported lazily from their own modules to avoid circular imports with
the storage layer:
  from backend.analytics.merlion_engine import MerlionAnomalyEngine
  from backend.analytics.detection_pipeline import AnomalyDetectionPipeline
"""

from .types import (
    MetricPoint,
    MetricSeries,
    AnomalyResult,
    AggregatedAnomalyScore,
)

from .engine import (
    AnomalyDetectionEngine,
    EngineRegistry,
)

from .windows import (
    SlidingWindowExtractor,
    TimeBasedWindowExtractor,
    TimeWindow,
)

from .aggregation import (
    AggregationStrategy,
    NodeAnomalyAggregator,
    ClusterAnomalyAggregator,
    TenantAnomalyAggregator,
    AggregationPipeline,
    AggregationConfig,
)

from .explain import (
    AnomalyType,
    AnomalyExplanation,
    ExplanationClassifier,
    ExplanationTemplateRegistry,
)

from .config import (
    DetectionConfig,
    get_config,
    set_config,
)

# Note: MerlionAnomalyEngine, AnomalyDetectionPipeline, DetectionPipelineStats
# must be imported directly from their modules to avoid circular imports:
#   from backend.analytics.merlion_engine import MerlionAnomalyEngine
#   from backend.analytics.detection_pipeline import AnomalyDetectionPipeline

__all__ = [
    # Types
    "MetricPoint",
    "MetricSeries",
    "AnomalyResult",
    "AggregatedAnomalyScore",
    # Engine
    "AnomalyDetectionEngine",
    "EngineRegistry",
    # Windows
    "SlidingWindowExtractor",
    "TimeBasedWindowExtractor",
    "TimeWindow",
    # Aggregation
    "AggregationStrategy",
    "NodeAnomalyAggregator",
    "ClusterAnomalyAggregator",
    "TenantAnomalyAggregator",
    "AggregationPipeline",
    "AggregationConfig",
    # Explanation
    "AnomalyType",
    "AnomalyExplanation",
    "ExplanationClassifier",
    "ExplanationTemplateRegistry",
    # Config
    "DetectionConfig",
    "get_config",
    "set_config",
]

__version__ = "0.3.0-phase3"
__description__ = "Analytics Module - Full Anomaly Detection Pipeline (Phase 3)"
