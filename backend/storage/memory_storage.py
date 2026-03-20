"""
In-Memory Storage - Fixed Version

Correctly handles AnomalyResult with window_start/window_end and scalar anomaly_score.
"""

import sys
import os
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analytics.types import MetricSeries, AnomalyResult, AggregatedAnomalyScore
from backend.storage.interface import StorageBackend


class InMemoryStorage(StorageBackend):
    """
    In-memory storage backend with correct anomaly handling.

    Stores:
    - Metrics: tenant -> cluster -> node -> metric_name -> MetricSeries
    - Anomalies: tenant -> cluster -> node -> metric_name -> List[AnomalyResult]
    - Aggregated scores: tenant -> List[AggregatedAnomalyScore]
    """

    def __init__(self):
        """Initialize in-memory storage"""
        # Metrics storage
        self.metrics: Dict[str, Dict[str, Dict[str, Dict[str, MetricSeries]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )

        # Anomalies storage - LIST of AnomalyResult, not single
        self.anomalies: Dict[str, Dict[str, Dict[str, Dict[str, List[AnomalyResult]]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        )

        # Aggregated scores: tenant -> list of scores
        self.aggregated_scores: Dict[str, List[AggregatedAnomalyScore]] = defaultdict(list)

    def store_metric(self, series: MetricSeries) -> None:
        """Store a metric time series."""
        self.metrics[series.tenant_id][series.cluster_id][series.node_id][series.metric_name] = series

    def get_metric_series(
            self,
            tenant_id: str,
            cluster_id: str,
            node_id: str,
            metric_name: str,
            start_time: datetime,
            end_time: datetime,
    ) -> MetricSeries:
        """Retrieve a metric time series filtered by time range."""
        try:
            series = self.metrics[tenant_id][cluster_id][node_id][metric_name]
        except KeyError:
            raise ValueError(
                f"No data found for tenant={tenant_id}, cluster={cluster_id}, "
                f"node={node_id}, metric={metric_name}"
            )

        # Filter by time range
        filtered_timestamps = []
        filtered_values = []

        for ts, val in zip(series.timestamps, series.values):
            if start_time <= ts <= end_time:
                filtered_timestamps.append(ts)
                filtered_values.append(val)

        if not filtered_timestamps:
            raise ValueError(
                f"No data in time range {start_time} to {end_time}"
            )

        return MetricSeries(
            tenant_id=series.tenant_id,
            cluster_id=series.cluster_id,
            node_id=series.node_id,
            metric_name=series.metric_name,
            timestamps=filtered_timestamps,
            values=filtered_values,
            metadata=series.metadata,
        )

    def store_anomaly_result(
            self,
            tenant_id: str,
            cluster_id: str,
            node_id: str,
            metric_name: str,
            result: AnomalyResult,
    ) -> None:
        """
        Store anomaly detection result.

        Appends to the list of anomalies for this metric.
        """
        self.anomalies[tenant_id][cluster_id][node_id][metric_name].append(result)

    def store_aggregated_score(
            self,
            score: AggregatedAnomalyScore,
    ) -> None:
        """Store aggregated anomaly score."""
        self.aggregated_scores[score.tenant_id].append(score)

    def query_anomalies(
            self,
            tenant_id: str,
            start_time: datetime,
            end_time: datetime,
            cluster_id: Optional[str] = None,
            min_score: float = 0.5,
    ) -> List[Dict]:
        """
        Query stored anomalies with proper window-based filtering.

        FIXED: Uses window_start/window_end and scalar anomaly_score
        Returns anomalies where window overlaps with query range and score >= min_score
        """
        results = []

        if tenant_id not in self.anomalies:
            return results

        for cid, clusters in self.anomalies[tenant_id].items():
            # Filter by cluster if specified
            if cluster_id and cid != cluster_id:
                continue

            for nid, nodes in clusters.items():
                for metric_name, anomaly_list in nodes.items():
                    # Process each AnomalyResult in the list
                    for anomaly in anomaly_list:
                        # Check window overlap with query range
                        window_overlaps = (
                                anomaly.window_start <= end_time and
                                anomaly.window_end >= start_time
                        )

                        # Check score threshold
                        score_passes = anomaly.anomaly_score >= min_score

                        if window_overlaps and score_passes:
                            results.append({
                                "tenant_id": tenant_id,
                                "cluster_id": cid,
                                "node_id": nid,
                                "metric_name": metric_name,
                                "anomaly_score": anomaly.anomaly_score,
                                "anomaly_label": anomaly.anomaly_label,
                                "window_start": anomaly.window_start,
                                "window_end": anomaly.window_end,
                                "explanation": anomaly.explanation,
                                "magnitude": anomaly.magnitude,
                            })

        # Sort by score descending
        results.sort(key=lambda x: x["anomaly_score"], reverse=True)

        return results

    def get_stats(self) -> Dict:
        """Get storage statistics."""
        total_metrics = 0
        total_anomalies = 0

        for tenant in self.metrics.values():
            for cluster in tenant.values():
                for node in cluster.values():
                    total_metrics += len(node)

        for tenant in self.anomalies.values():
            for cluster in tenant.values():
                for node in cluster.values():
                    for metric_list in node.values():
                        total_anomalies += len(metric_list)

        total_aggregated = sum(len(scores) for scores in self.aggregated_scores.values())

        return {
            "total_metrics": total_metrics,
            "total_anomalies": total_anomalies,
            "total_aggregated_scores": total_aggregated,
        }