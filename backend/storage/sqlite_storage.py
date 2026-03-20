"""
SQLite Persistent Storage Backend

Durable storage that survives process restarts.
Compatible with the StorageBackend interface.
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analytics.types import MetricSeries, AnomalyResult, AggregatedAnomalyScore
from .interface import StorageBackend

# ISO format for datetime serialization
_DT_FMT = "%Y-%m-%dT%H:%M:%S.%f"


def _dt_to_str(dt: datetime) -> str:
    return dt.strftime(_DT_FMT)


def _str_to_dt(s: str) -> datetime:
    try:
        return datetime.strptime(s, _DT_FMT)
    except ValueError:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


class SQLiteStorage(StorageBackend):
    """
    SQLite-backed persistent storage.

    Zero external dependencies — uses Python's built-in sqlite3 module.
    Data persists across process restarts.

    Usage:
        >>> storage = SQLiteStorage("aboutcloud.db")
        >>> storage.store_metric(series)
        >>> retrieved = storage.get_metric_series(...)
    """

    def __init__(self, db_path: str = "aboutcloud.db"):
        """
        Initialize SQLite storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _get_conn(self):
        """Get a database connection with WAL mode for better concurrency."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Create tables if they don't exist."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    cluster_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    timestamps_json TEXT NOT NULL,
                    values_json TEXT NOT NULL,
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    UNIQUE(tenant_id, cluster_id, node_id, metric_name)
                );

                CREATE INDEX IF NOT EXISTS idx_metrics_tenant
                    ON metrics(tenant_id, cluster_id, node_id);

                CREATE TABLE IF NOT EXISTS anomaly_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    cluster_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    window_start TEXT NOT NULL,
                    window_end TEXT NOT NULL,
                    anomaly_score REAL NOT NULL,
                    anomaly_label TEXT NOT NULL,
                    magnitude REAL,
                    explanation TEXT,
                    timestamp_detected TEXT NOT NULL,
                    engine_metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_anomalies_tenant
                    ON anomaly_results(tenant_id, cluster_id);
                CREATE INDEX IF NOT EXISTS idx_anomalies_time
                    ON anomaly_results(window_start, window_end);
                CREATE INDEX IF NOT EXISTS idx_anomalies_score
                    ON anomaly_results(anomaly_score);

                CREATE TABLE IF NOT EXISTS aggregated_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    cluster_id TEXT,
                    node_id TEXT,
                    aggregate_score REAL NOT NULL,
                    aggregation_strategy TEXT NOT NULL,
                    num_metrics_analyzed INTEGER DEFAULT 0,
                    num_anomalies_detected INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_agg_tenant
                    ON aggregated_scores(tenant_id, cluster_id);
            """)

    def store_metric(self, series: MetricSeries) -> None:
        """Store a metric time series (upsert)."""
        timestamps_json = json.dumps([_dt_to_str(ts) for ts in series.timestamps])
        values_json = json.dumps(series.values)
        metadata_json = json.dumps(series.metadata)
        now = _dt_to_str(datetime.utcnow())

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO metrics (tenant_id, cluster_id, node_id, metric_name,
                                     timestamps_json, values_json, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, cluster_id, node_id, metric_name)
                DO UPDATE SET
                    timestamps_json = excluded.timestamps_json,
                    values_json = excluded.values_json,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at
            """, (
                series.tenant_id, series.cluster_id, series.node_id,
                series.metric_name, timestamps_json, values_json,
                metadata_json, now,
            ))

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
        with self._get_conn() as conn:
            row = conn.execute("""
                SELECT * FROM metrics
                WHERE tenant_id = ? AND cluster_id = ? AND node_id = ? AND metric_name = ?
            """, (tenant_id, cluster_id, node_id, metric_name)).fetchone()

        if row is None:
            raise ValueError(
                f"No data found for tenant={tenant_id}, cluster={cluster_id}, "
                f"node={node_id}, metric={metric_name}"
            )

        timestamps = [_str_to_dt(ts) for ts in json.loads(row["timestamps_json"])]
        values = json.loads(row["values_json"])
        metadata = json.loads(row["metadata_json"])

        # Filter by time range
        filtered_ts = []
        filtered_vals = []
        for ts, val in zip(timestamps, values):
            if start_time <= ts <= end_time:
                filtered_ts.append(ts)
                filtered_vals.append(val)

        if not filtered_ts:
            raise ValueError(
                f"No data in time range {start_time} to {end_time}"
            )

        return MetricSeries(
            tenant_id=tenant_id,
            cluster_id=cluster_id,
            node_id=node_id,
            metric_name=metric_name,
            timestamps=filtered_ts,
            values=filtered_vals,
            metadata=metadata,
        )

    def store_anomaly_result(
        self,
        tenant_id: str,
        cluster_id: str,
        node_id: str,
        metric_name: str,
        result: AnomalyResult,
    ) -> None:
        """Store a single anomaly detection result."""
        now = _dt_to_str(datetime.utcnow())
        engine_meta = json.dumps(
            {k: str(v) for k, v in result.engine_metadata.items()}
            if result.engine_metadata else {}
        )

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO anomaly_results
                    (tenant_id, cluster_id, node_id, metric_name,
                     window_start, window_end, anomaly_score, anomaly_label,
                     magnitude, explanation, timestamp_detected,
                     engine_metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tenant_id, cluster_id, node_id, metric_name,
                _dt_to_str(result.window_start), _dt_to_str(result.window_end),
                result.anomaly_score, result.anomaly_label,
                result.magnitude, result.explanation,
                _dt_to_str(result.timestamp_detected),
                engine_meta, now,
            ))

    def store_aggregated_score(self, score: AggregatedAnomalyScore) -> None:
        """Store aggregated anomaly score."""
        now = _dt_to_str(datetime.utcnow())

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO aggregated_scores
                    (tenant_id, cluster_id, node_id, aggregate_score,
                     aggregation_strategy, num_metrics_analyzed,
                     num_anomalies_detected, timestamp, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                score.tenant_id, score.cluster_id, score.node_id,
                score.aggregate_score, score.aggregation_strategy,
                score.num_metrics_analyzed, score.num_anomalies_detected,
                _dt_to_str(score.timestamp), now,
            ))

    def query_anomalies(
        self,
        tenant_id: str,
        start_time: datetime,
        end_time: datetime,
        cluster_id: Optional[str] = None,
        min_score: float = 0.5,
    ) -> List[Dict]:
        """Query stored anomaly results using window overlap."""
        start_str = _dt_to_str(start_time)
        end_str = _dt_to_str(end_time)

        query = """
            SELECT * FROM anomaly_results
            WHERE tenant_id = ?
              AND window_start <= ?
              AND window_end >= ?
              AND anomaly_score >= ?
        """
        params = [tenant_id, end_str, start_str, min_score]

        if cluster_id:
            query += " AND cluster_id = ?"
            params.append(cluster_id)

        query += " ORDER BY anomaly_score DESC"

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        results = []
        for row in rows:
            results.append({
                "tenant_id": row["tenant_id"],
                "cluster_id": row["cluster_id"],
                "node_id": row["node_id"],
                "metric_name": row["metric_name"],
                "anomaly_score": row["anomaly_score"],
                "anomaly_label": row["anomaly_label"],
                "window_start": _str_to_dt(row["window_start"]),
                "window_end": _str_to_dt(row["window_end"]),
                "explanation": row["explanation"],
            })

        return results

    def get_stats(self) -> Dict:
        """Get storage statistics."""
        with self._get_conn() as conn:
            metrics_count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
            anomalies_count = conn.execute("SELECT COUNT(*) FROM anomaly_results").fetchone()[0]
            agg_count = conn.execute("SELECT COUNT(*) FROM aggregated_scores").fetchone()[0]
            tenants = conn.execute("SELECT COUNT(DISTINCT tenant_id) FROM metrics").fetchone()[0]

        return {
            "total_tenants": tenants,
            "total_metrics": metrics_count,
            "total_anomalies": anomalies_count,
            "total_aggregated_scores": agg_count,
        }

    def clear_all(self) -> None:
        """Clear all data (useful for testing)."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM anomaly_results")
            conn.execute("DELETE FROM aggregated_scores")
            conn.execute("DELETE FROM metrics")

    def get_aggregated_scores(
        self,
        tenant_id: str,
        cluster_id: Optional[str] = None,
    ) -> List[AggregatedAnomalyScore]:
        """Retrieve aggregated scores for a tenant."""
        query = "SELECT * FROM aggregated_scores WHERE tenant_id = ?"
        params = [tenant_id]

        if cluster_id:
            query += " AND cluster_id = ?"
            params.append(cluster_id)

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        scores = []
        for row in rows:
            scores.append(AggregatedAnomalyScore(
                tenant_id=row["tenant_id"],
                cluster_id=row["cluster_id"],
                node_id=row["node_id"],
                aggregate_score=row["aggregate_score"],
                aggregation_strategy=row["aggregation_strategy"],
                num_metrics_analyzed=row["num_metrics_analyzed"],
                num_anomalies_detected=row["num_anomalies_detected"],
                timestamp=_str_to_dt(row["timestamp"]),
            ))

        return scores
