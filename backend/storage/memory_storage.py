"""
In-Memory Storage - Simple storage backend for testing

Fast, no persistence. Good for development and testing.
"""

import sys
import os
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analytics.types import MetricSeries, AnomalyResult, AggregatedAnomalyScore
from .interface import StorageBackend


class InMemoryStorage(StorageBackend):
    """
    In-memory storage backend.

    Stores all data in memory. Fast but not persistent.

    Usage:
        >>> storage = InMemoryStorage()
        >>> storage.store_metric(series)
        >>> retrieved = storage.get_metric_series(...)
    """

    def __init__(self):
        """Initialize in-memory storage"""
        # Metrics: tenant -> cluster -> node -> metric_name -> MetricSeries
        self.metrics: Dict[str, Dict[str, Dict[str, Dict[str, MetricSeries]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict))
        )

        # Anomaly results: tenant -> cluster -> node -> metric_name -> List[AnomalyResult]
        self.anomalies: Dict[str, Dict[str, Dict[str, Dict[str, List[AnomalyResult]]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        )

        # Aggregated scores: tenant -> list of scores
        self.aggregated_scores: Dict[str, List[AggregatedAnomalyScore]] = defaultdict(list)

    def store_metric(self, series: MetricSeries) -> None:
        """
        Store a metric time series.

        Args:
            series: MetricSeries to store
        """
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
        """
        Retrieve a metric time series.

        Args:
            tenant_id: Tenant identifier
            cluster_id: Cluster identifier
            node_id: Node identifier
            metric_name: Metric name
            start_time: Start of time range
            end_time: End of time range

        Returns:
            MetricSeries for the specified query

        Raises:
            ValueError: If no data found
        """
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
                f"No data in time range {start_time} to {end_time} for "
                f"tenant={tenant_id}, cluster={cluster_id}, node={node_id}, metric={metric_name}"
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
        Store anomaly detection results.

        Appends to the list of results for this metric (preserves multi-window results).

        Args:
            tenant_id: Tenant identifier
            cluster_id: Cluster identifier
            node_id: Node identifier
            metric_name: Metric name
            result: AnomalyResult to store
        """
        self.anomalies[tenant_id][cluster_id][node_id][metric_name].append(result)

    def store_aggregated_score(
        self,
        score: AggregatedAnomalyScore,
    ) -> None:
        """
        Store aggregated anomaly score.

        Args:
            score: AggregatedAnomalyScore to store
        """
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
        Query stored anomaly results.

        Uses window overlap for time filtering and scalar score threshold.

        Args:
            tenant_id: Tenant identifier
            start_time: Start of query time range
            end_time: End of query time range
            cluster_id: Optional cluster filter
            min_score: Minimum anomaly score threshold

        Returns:
            List of anomaly result dicts matching filters
        """
        results = []

        if tenant_id not in self.anomalies:
            return results

        for cid, clusters in self.anomalies[tenant_id].items():
            # Filter by cluster if specified
            if cluster_id and cid != cluster_id:
                continue

            for nid, nodes in clusters.items():
                for metric, anomaly_list in nodes.items():
                    for anomaly in anomaly_list:
                        # Overlap-based time filtering:
                        # anomaly window overlaps query range if
                        # anomaly.window_start <= end_time AND anomaly.window_end >= start_time
                        overlaps = (
                            anomaly.window_start <= end_time and
                            anomaly.window_end >= start_time
                        )

                        if overlaps and anomaly.anomaly_score >= min_score:
                            results.append({
                                "tenant_id": tenant_id,
                                "cluster_id": cid,
                                "node_id": nid,
                                "metric_name": metric,
                                "anomaly_score": anomaly.anomaly_score,
                                "anomaly_label": anomaly.anomaly_label,
                                "window_start": anomaly.window_start,
                                "window_end": anomaly.window_end,
                                "explanation": anomaly.explanation,
                            })

        return results

    def get_aggregated_scores(
        self,
        tenant_id: str,
        cluster_id: Optional[str] = None,
    ) -> List[AggregatedAnomalyScore]:
        """Retrieve aggregated scores for a tenant."""
        scores = self.aggregated_scores.get(tenant_id, [])
        if cluster_id:
            scores = [s for s in scores if s.cluster_id == cluster_id]
        return scores

    def get_stats(self) -> Dict:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage stats
        """
        total_metrics = 0
        total_anomalies = 0

        for tenant in self.metrics.values():
            for cluster in tenant.values():
                for node in cluster.values():
                    total_metrics += len(node)

        for tenant in self.anomalies.values():
            for cluster in tenant.values():
                for node in cluster.values():
                    for metric_results in node.values():
                        total_anomalies += len(metric_results)

        total_aggregated = sum(len(scores) for scores in self.aggregated_scores.values())

        return {
            "total_tenants": len(self.metrics),
            "total_metrics": total_metrics,
            "total_anomalies": total_anomalies,
            "total_aggregated_scores": total_aggregated,
        }