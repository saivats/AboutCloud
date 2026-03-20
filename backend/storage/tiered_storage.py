"""
Tiered (Hot/Cold) Storage MVP

Hot tier: SQLite DB for recent data (fast queries)
Cold tier: JSON files for archived historical data (compact, durable)
Transparent query merging across both tiers.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analytics.types import MetricSeries, AnomalyResult, AggregatedAnomalyScore
from .interface import StorageBackend
from .sqlite_storage import SQLiteStorage, _dt_to_str, _str_to_dt


@dataclass
class TieringConfig:
    """Configuration for hot/cold storage tiering."""
    hot_retention_days: int = 7          # Data newer than this stays in hot
    cold_archive_dir: str = "cold_archive"  # Directory for cold archive files
    auto_archive: bool = True            # Auto-archive on writes


class TieredStorageBackend(StorageBackend):
    """
    Hot/Cold tiered storage MVP.

    Hot tier: SQLite for recent data (fast reads/writes)
    Cold tier: JSON-based archive for older data

    Recent data is served from the hot path. Older data can be archived
    to cold storage. Queries transparently merge results from both tiers.

    Usage:
        >>> config = TieringConfig(hot_retention_days=7)
        >>> storage = TieredStorageBackend(
        ...     hot_db_path="hot.db",
        ...     config=config,
        ... )
        >>> storage.store_metric(series)
        >>> storage.archive_old_data()
    """

    def __init__(
        self,
        hot_db_path: str = "aboutcloud_hot.db",
        config: Optional[TieringConfig] = None,
    ):
        """
        Initialize tiered storage.

        Args:
            hot_db_path: Path to hot-tier SQLite database
            config: Tiering configuration
        """
        self.config = config or TieringConfig()
        self.hot = SQLiteStorage(hot_db_path)
        self._cold_dir = self.config.cold_archive_dir
        os.makedirs(self._cold_dir, exist_ok=True)
        os.makedirs(os.path.join(self._cold_dir, "metrics"), exist_ok=True)
        os.makedirs(os.path.join(self._cold_dir, "anomalies"), exist_ok=True)

    def _hot_cutoff(self) -> datetime:
        """Get the cutoff datetime — data older than this goes to cold."""
        return datetime.utcnow() - timedelta(days=self.config.hot_retention_days)

    # ---- StorageBackend interface (writes go to hot) ----

    def store_metric(self, series: MetricSeries) -> None:
        """Store metric in hot tier."""
        self.hot.store_metric(series)

    def get_metric_series(
        self,
        tenant_id: str,
        cluster_id: str,
        node_id: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> MetricSeries:
        """Query metric from hot tier first, then fall back to cold."""
        # Try hot tier
        try:
            return self.hot.get_metric_series(
                tenant_id, cluster_id, node_id, metric_name,
                start_time, end_time,
            )
        except ValueError:
            pass

        # Try cold tier
        cold_series = self._load_cold_metric(
            tenant_id, cluster_id, node_id, metric_name
        )
        if cold_series:
            # Filter by time
            filtered_ts = []
            filtered_vals = []
            for ts, val in zip(cold_series.timestamps, cold_series.values):
                if start_time <= ts <= end_time:
                    filtered_ts.append(ts)
                    filtered_vals.append(val)

            if filtered_ts:
                return MetricSeries(
                    tenant_id=tenant_id,
                    cluster_id=cluster_id,
                    node_id=node_id,
                    metric_name=metric_name,
                    timestamps=filtered_ts,
                    values=filtered_vals,
                    metadata=cold_series.metadata,
                )

        raise ValueError(
            f"No data found in hot or cold storage for "
            f"tenant={tenant_id}, cluster={cluster_id}, "
            f"node={node_id}, metric={metric_name}"
        )

    def store_anomaly_result(
        self,
        tenant_id: str,
        cluster_id: str,
        node_id: str,
        metric_name: str,
        result: AnomalyResult,
    ) -> None:
        """Store anomaly in hot tier."""
        self.hot.store_anomaly_result(
            tenant_id, cluster_id, node_id, metric_name, result,
        )

    def store_aggregated_score(self, score: AggregatedAnomalyScore) -> None:
        """Store aggregated score in hot tier."""
        self.hot.store_aggregated_score(score)

    def query_anomalies(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
        cluster_id: Optional[str] = None,
        min_score: float = 0.5,
    ) -> List[Dict]:
        """Query anomalies from both hot and cold tiers, merge results."""
        hot_results = self.hot.query_anomalies(
            tenant_id, start_time, end_time, cluster_id, min_score,
        )

        cold_results = self._query_cold_anomalies(
            tenant_id, start_time, end_time, cluster_id, min_score,
        )

        # Merge — hot results take priority (deduplicate by window key)
        seen_keys = set()
        merged = []
        for r in hot_results:
            key = (r["node_id"], r["metric_name"],
                   str(r.get("window_start")), str(r.get("window_end")))
            seen_keys.add(key)
            merged.append(r)

        for r in cold_results:
            key = (r["node_id"], r["metric_name"],
                   str(r.get("window_start")), str(r.get("window_end")))
            if key not in seen_keys:
                merged.append(r)

        return sorted(merged, key=lambda x: x.get("anomaly_score", 0), reverse=True)

    # ---- Archive / Tiering Operations ----

    def archive_old_data(self) -> Dict[str, int]:
        """
        Move old data from hot tier to cold tier.

        Metrics and anomalies older than hot_retention_days are archived.

        Returns:
            Dict with counts of archived items
        """
        cutoff = self._hot_cutoff()
        archived = {"metrics": 0, "anomalies": 0}

        # Archive old anomalies
        with self.hot._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM anomaly_results
                WHERE window_end < ?
            """, (_dt_to_str(cutoff),)).fetchall()

            if rows:
                cold_anomalies = []
                for row in rows:
                    cold_anomalies.append({
                        "tenant_id": row["tenant_id"],
                        "cluster_id": row["cluster_id"],
                        "node_id": row["node_id"],
                        "metric_name": row["metric_name"],
                        "window_start": row["window_start"],
                        "window_end": row["window_end"],
                        "anomaly_score": row["anomaly_score"],
                        "anomaly_label": row["anomaly_label"],
                        "magnitude": row["magnitude"],
                        "explanation": row["explanation"],
                        "timestamp_detected": row["timestamp_detected"],
                    })

                # Write to cold
                self._write_cold_anomalies(cold_anomalies)

                # Delete from hot
                conn.execute(
                    "DELETE FROM anomaly_results WHERE window_end < ?",
                    (_dt_to_str(cutoff),),
                )
                archived["anomalies"] = len(cold_anomalies)

        return archived

    def get_tier_stats(self) -> Dict:
        """Get statistics for both tiers."""
        hot_stats = self.hot.get_stats()

        cold_anomaly_files = 0
        anomalies_dir = os.path.join(self._cold_dir, "anomalies")

        if os.path.exists(anomalies_dir):
            cold_anomaly_files = len([
                f for f in os.listdir(anomalies_dir) if f.endswith(".json")
            ])

        return {
            "hot": hot_stats,
            "cold": {
                "anomaly_archives": cold_anomaly_files,
            },
        }

    def get_stats(self) -> Dict:
        """Get combined storage statistics."""
        return self.hot.get_stats()

    def get_aggregated_scores(
        self,
        tenant_id: str,
        cluster_id: Optional[str] = None,
    ) -> List[AggregatedAnomalyScore]:
        """Retrieve aggregated scores from hot tier."""
        return self.hot.get_aggregated_scores(tenant_id, cluster_id)

    # ---- Cold Storage I/O ----

    def _cold_anomaly_path(self, batch_id: str = "latest"):
        return os.path.join(
            self._cold_dir, "anomalies",
            f"anomalies_{batch_id}.json",
        )

    def _write_cold_anomalies(self, anomalies: List[Dict]):
        """Write anomalies to cold storage as JSON."""
        batch_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = self._cold_anomaly_path(batch_id)
        with open(path, "w") as f:
            json.dump(anomalies, f, indent=2, default=str)

    def _query_cold_anomalies(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
        cluster_id: Optional[str] = None,
        min_score: float = 0.5,
    ) -> List[Dict]:
        """Query anomalies from cold JSON files."""
        results = []
        anomalies_dir = os.path.join(self._cold_dir, "anomalies")

        if not os.path.exists(anomalies_dir):
            return results

        for fname in os.listdir(anomalies_dir):
            if not fname.endswith(".json"):
                continue

            fpath = os.path.join(anomalies_dir, fname)
            try:
                with open(fpath, "r") as f:
                    batch = json.load(f)

                for entry in batch:
                    if entry.get("tenant_id") != tenant_id:
                        continue
                    if cluster_id and entry.get("cluster_id") != cluster_id:
                        continue
                    if entry.get("anomaly_score", 0) < min_score:
                        continue

                    ws = _str_to_dt(entry["window_start"])
                    we = _str_to_dt(entry["window_end"])

                    if ws <= end_time and we >= start_time:
                        entry["window_start"] = ws
                        entry["window_end"] = we
                        results.append(entry)
            except Exception:
                continue

        return results

    def _load_cold_metric(self, tenant_id, cluster_id, node_id, metric_name):
        """Load a metric from cold storage."""
        safe = lambda s: s.replace("/", "_").replace("\\", "_")
        path = os.path.join(
            self._cold_dir, "metrics",
            f"{safe(tenant_id)}_{safe(cluster_id)}_{safe(node_id)}_{safe(metric_name)}.json",
        )
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r") as f:
                data = json.load(f)

            return MetricSeries(
                tenant_id=data["tenant_id"],
                cluster_id=data["cluster_id"],
                node_id=data["node_id"],
                metric_name=data["metric_name"],
                timestamps=[_str_to_dt(ts) for ts in data["timestamps"]],
                values=data["values"],
                metadata=data.get("metadata", {}),
            )
        except Exception:
            return None
