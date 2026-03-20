"""
Detection Pipeline - FIXED VERSION

Correctly converts node results to aggregated scores before calling aggregator.
"""

import sys
import os
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .types import MetricSeries, AnomalyResult, AggregatedAnomalyScore
from .engine import AnomalyDetectionEngine
from .explain import ExplanationClassifier, ExplanationTemplateRegistry
from .aggregation import (
    NodeAnomalyAggregator,
    ClusterAnomalyAggregator,
)
from .config import get_config
from backend.storage.interface import get_storage


@dataclass
class DetectionPipelineStats:
    """Statistics from detection run"""
    metrics_processed: int = 0
    anomalies_detected: int = 0
    critical_anomalies: int = 0
    storage_errors: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def has_critical_errors(self) -> bool:
        """Check if any critical errors occurred"""
        return self.storage_errors > 0 or len(self.errors) > 0


class AnomalyDetectionPipeline:
    """
    End-to-end anomaly detection pipeline.

    Fixed flow:
    1. Fetch MetricSeries from storage
    2. Run detection engine
    3. Classify anomalies
    4. Generate explanations
    5. Store individual results
    6. Aggregate to node-level AggregatedAnomalyScore
    7. Aggregate to cluster level (if multiple nodes)
    8. Store aggregated results
    """

    def __init__(
            self,
            engine: AnomalyDetectionEngine,
            classifier: Optional[ExplanationClassifier] = None,
            storage_backend=None,
    ):
        """Initialize pipeline"""
        self.engine = engine
        self.classifier = classifier or ExplanationClassifier()
        self.storage = storage_backend or get_storage()
        self.config = get_config()
        self.node_aggregator = NodeAnomalyAggregator()
        self.cluster_aggregator = ClusterAnomalyAggregator()

    def detect_metric(
            self,
            metric_series: MetricSeries,
    ) -> tuple:
        """
        Run detection on a single metric.

        Returns:
            (AnomalyResult list, explanation list, stats)
        """
        stats = DetectionPipelineStats(metrics_processed=1)

        try:
            # 1. Run detection engine
            anomaly_results = self.engine.detect(metric_series)
            stats.anomalies_detected = len(anomaly_results)

            # 2. Classify and explain
            explanations = []
            critical_count = 0

            for result in anomaly_results:
                explanation = self.classifier.classify(metric_series, result)
                explanations.append(explanation)

                if explanation.is_critical:
                    critical_count += 1

                # Add explanation to result
                template = ExplanationTemplateRegistry.get_template(explanation.anomaly_type)
                result.explanation = template.render(explanation)

            stats.critical_anomalies = critical_count

            # 3. Store individual results
            try:
                for result in anomaly_results:
                    self.storage.store_anomaly_result(
                        tenant_id=metric_series.tenant_id,
                        cluster_id=metric_series.cluster_id,
                        node_id=metric_series.node_id,
                        metric_name=metric_series.metric_name,
                        result=result,
                    )
            except Exception as e:
                stats.storage_errors += 1
                stats.errors.append(f"Failed to store individual results: {e}")

            return anomaly_results, explanations, stats

        except Exception as e:
            stats.errors.append(f"Detection failed: {str(e)}")
            return [], [], stats

    def detect_cluster(
            self,
            tenant_id: str,
            cluster_id: str,
            node_ids: List[str],
            metric_names: List[str],
    ):
        """
        Run detection across a cluster.

        FIXED: Correctly aggregates node results to cluster level
        """
        all_results = []
        stats = DetectionPipelineStats()

        # Per-node aggregated scores (for cluster aggregation)
        node_aggregated_scores = []

        try:
            # Process each node's metrics
            for node_id in node_ids:
                node_anomalies = []

                for metric_name in metric_names:
                    try:
                        # Fetch metric
                        series = self.storage.get_metric_series(
                            tenant_id=tenant_id,
                            cluster_id=cluster_id,
                            node_id=node_id,
                            metric_name=metric_name,
                            start_time=datetime.min,
                            end_time=datetime.max,
                        )

                        # Detect
                        results, _, metric_stats = self.detect_metric(series)
                        all_results.extend(results)
                        node_anomalies.extend(results)

                        stats.metrics_processed += metric_stats.metrics_processed
                        stats.anomalies_detected += metric_stats.anomalies_detected
                        stats.critical_anomalies += metric_stats.critical_anomalies
                        stats.storage_errors += metric_stats.storage_errors
                        stats.errors.extend(metric_stats.errors)

                    except Exception as e:
                        stats.errors.append(f"{node_id}/{metric_name}: {e}")

                # FIXED: Aggregate node-level anomalies to node score
                if node_anomalies:
                    try:
                        node_score = self.node_aggregator.aggregate(
                            anomaly_results=node_anomalies,
                            timestamp=datetime.utcnow(),
                        )
                        node_aggregated_scores.append(node_score)

                        # Store node-level score
                        self.storage.store_aggregated_score(node_score)
                    except Exception as e:
                        stats.errors.append(f"Node aggregation failed for {node_id}: {e}")

            # FIXED: Aggregate node scores to cluster level
            cluster_score = None
            if node_aggregated_scores:
                try:
                    cluster_score = self.cluster_aggregator.aggregate(
                        node_scores=node_aggregated_scores,
                        timestamp=datetime.utcnow(),
                    )
                    # Store cluster-level score
                    self.storage.store_aggregated_score(cluster_score)
                except Exception as e:
                    stats.errors.append(f"Cluster aggregation failed: {e}")

            return all_results, cluster_score, stats

        except Exception as e:
            stats.errors.append(f"Cluster detection failed: {e}")
            return [], None, stats


# Backward compatibility alias
DetectionPipeline = AnomalyDetectionPipeline
