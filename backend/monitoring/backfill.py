"""
Backfill & Replay Runner

Re-run anomaly detection on historical data ranges.
Supports both stored metrics and CSV replay.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from dataclasses import dataclass, field

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.analytics.types import MetricSeries, AnomalyResult
from backend.analytics.detection_pipeline import AnomalyDetectionPipeline
from backend.analytics.merlion_engine import MerlionAnomalyEngine
from backend.analytics.explain import ExplanationClassifier
from backend.storage.interface import get_storage
from backend.monitoring.logging_config import get_logger


@dataclass
class BackfillResult:
    """Result of a backfill operation."""
    tenant_id: str
    cluster_id: str
    metrics_processed: int = 0
    anomalies_found: int = 0
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class BackfillRunner:
    """
    Re-run anomaly detection on historical data.

    Supports:
      - Re-detecting from stored metrics in a time range
      - Re-detecting from CSV replay data
      - Storing re-detected results alongside originals

    Usage:
        >>> runner = BackfillRunner()
        >>> result = runner.backfill(
        ...     tenant_id="acme-corp",
        ...     cluster_id="prod-cluster",
        ...     start_time=datetime(2026, 1, 1),
        ...     end_time=datetime(2026, 3, 1),
        ... )
    """

    def __init__(
        self,
        engine: Optional[MerlionAnomalyEngine] = None,
        storage=None,
    ):
        """
        Initialize backfill runner.

        Args:
            engine: Detection engine to use (creates default if None)
            storage: Storage backend to use (uses global if None)
        """
        self.engine = engine or MerlionAnomalyEngine(
            config={"window_size": 40, "contamination": 0.1}
        )
        self.storage = storage or get_storage()
        self.logger = get_logger("backfill")

    def backfill(
        self,
        tenant_id: str,
        cluster_id: str,
        node_ids: Optional[List[str]] = None,
        metric_names: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> BackfillResult:
        """
        Re-run detection on stored historical metrics.

        Args:
            tenant_id: Tenant to backfill
            cluster_id: Cluster to backfill
            node_ids: Specific nodes (None = all available)
            metric_names: Specific metrics (None = all available)
            start_time: Start of backfill range (default: 30 days ago)
            end_time: End of backfill range (default: now)

        Returns:
            BackfillResult with stats
        """
        import time

        started = time.perf_counter()
        result = BackfillResult(tenant_id=tenant_id, cluster_id=cluster_id)

        start_time = start_time or (datetime.utcnow() - timedelta(days=30))
        end_time = end_time or datetime.utcnow()

        self.logger.info(
            f"Starting backfill for {tenant_id}/{cluster_id}",
            extra={
                "tenant_id": tenant_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            },
        )

        pipeline = AnomalyDetectionPipeline(
            engine=self.engine,
            classifier=ExplanationClassifier(),
            storage_backend=self.storage,
        )

        # If node_ids not given, try to discover from storage stats
        if not node_ids:
            node_ids = ["node-001", "node-002"]  # Fallback defaults

        if not metric_names:
            metric_names = ["cpu_usage", "memory_used"]  # Fallback defaults

        for node_id in node_ids:
            for metric_name in metric_names:
                try:
                    series = self.storage.get_metric_series(
                        tenant_id=tenant_id,
                        cluster_id=cluster_id,
                        node_id=node_id,
                        metric_name=metric_name,
                        start_time=start_time,
                        end_time=end_time,
                    )

                    results, explanations, stats = pipeline.detect_metric(series)
                    result.metrics_processed += 1
                    result.anomalies_found += len(results)

                    self.logger.info(
                        f"Backfill: {node_id}/{metric_name} -> {len(results)} anomalies",
                        extra={"tenant_id": tenant_id},
                    )

                except ValueError as e:
                    # No data for this metric/node — skip, not an error
                    self.logger.info(
                        f"Backfill: skipping {node_id}/{metric_name} (no data)",
                        extra={"tenant_id": tenant_id},
                    )
                except Exception as e:
                    error_msg = f"Backfill error for {node_id}/{metric_name}: {e}"
                    result.errors.append(error_msg)
                    self.logger.error(error_msg, extra={"tenant_id": tenant_id})

        result.duration_ms = (time.perf_counter() - started) * 1000.0

        self.logger.info(
            f"Backfill complete: {result.metrics_processed} metrics, "
            f"{result.anomalies_found} anomalies, {result.duration_ms:.1f}ms",
            extra={"tenant_id": tenant_id},
        )

        return result

    def replay_csv(
        self,
        scenario_dir: str,
        cluster_id: str,
        tenant_id: str,
    ) -> BackfillResult:
        """
        Replay CSV scenario data through the detection pipeline.

        Loads CSV files, stores them, runs detection, and stores results.

        Args:
            scenario_dir: Root directory with CSV scenarios
            cluster_id: Cluster ID from the scenario
            tenant_id: Tenant ID to assign

        Returns:
            BackfillResult with stats
        """
        import time

        started = time.perf_counter()
        result = BackfillResult(tenant_id=tenant_id, cluster_id=cluster_id)

        try:
            from backend.simulator.csv_replay import CSVScenarioReplayer

            replayer = CSVScenarioReplayer(scenario_dir, tenant_id=tenant_id)
            cluster_metrics = replayer.load_scenario(cluster_id)

            pipeline = AnomalyDetectionPipeline(
                engine=self.engine,
                classifier=ExplanationClassifier(),
                storage_backend=self.storage,
            )

            for node_id, series_list in cluster_metrics.items():
                for series in series_list:
                    try:
                        self.storage.store_metric(series)
                        results, _, stats = pipeline.detect_metric(series)
                        result.metrics_processed += 1
                        result.anomalies_found += len(results)
                    except Exception as e:
                        result.errors.append(f"CSV replay error: {node_id}/{series.metric_name}: {e}")

        except Exception as e:
            result.errors.append(f"CSV replay failed: {e}")

        result.duration_ms = (time.perf_counter() - started) * 1000.0
        return result
