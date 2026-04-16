import os
import structlog
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict

import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd

from backend.core.config import get_settings

logger = structlog.get_logger("aboutcloud.cold_storage")


METRIC_SCHEMA = pa.schema([
    ("time", pa.timestamp("us", tz="UTC")),
    ("tenant_id", pa.string()),
    ("cluster_id", pa.string()),
    ("node_id", pa.string()),
    ("metric_name", pa.string()),
    ("value", pa.float64()),
])


class ColdStorage:
    def __init__(self, base_path: Optional[str] = None):
        settings = get_settings()
        self.base_path = Path(base_path or settings.COLD_STORAGE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _build_path(
        self,
        tenant_id: str,
        cluster_id: str,
        node_id: str,
        metric_name: str,
        dt: datetime,
    ) -> Path:
        return (
            self.base_path
            / tenant_id
            / cluster_id
            / node_id
            / metric_name
            / str(dt.year)
            / f"{dt.month:02d}"
            / f"{dt.day:02d}.parquet"
        )

    def archive_data(
        self,
        tenant_id: str,
        cluster_id: str,
        node_id: str,
        metric_name: str,
        timestamps: List[datetime],
        values: List[float],
    ) -> int:
        if not timestamps:
            return 0

        df = pd.DataFrame({
            "time": pd.to_datetime(timestamps, utc=True),
            "tenant_id": tenant_id,
            "cluster_id": cluster_id,
            "node_id": node_id,
            "metric_name": metric_name,
            "value": values,
        })

        df["date"] = df["time"].dt.date
        archived = 0

        for date_val, group in df.groupby("date"):
            dt = datetime.combine(date_val, datetime.min.time())
            file_path = self._build_path(tenant_id, cluster_id, node_id, metric_name, dt)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            write_df = group.drop(columns=["date"])
            table = pa.Table.from_pandas(write_df, schema=METRIC_SCHEMA)

            if file_path.exists():
                existing_table = pq.read_table(str(file_path))
                table = pa.concat_tables([existing_table, table])

            pq.write_table(table, str(file_path), compression="snappy")
            archived += len(group)

        logger.info(
            "cold_archive_complete",
            tenant_id=tenant_id,
            metric=metric_name,
            rows=archived,
        )

        return archived

    def read_data(
        self,
        tenant_id: str,
        cluster_id: str,
        node_id: str,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        all_frames = []
        current = start_time.replace(hour=0, minute=0, second=0, microsecond=0)

        while current <= end_time:
            file_path = self._build_path(tenant_id, cluster_id, node_id, metric_name, current)

            if file_path.exists():
                try:
                    table = pq.read_table(str(file_path))
                    df = table.to_pandas()
                    df["time"] = pd.to_datetime(df["time"], utc=True)
                    mask = (df["time"] >= pd.Timestamp(start_time, tz="UTC")) & (
                        df["time"] <= pd.Timestamp(end_time, tz="UTC")
                    )
                    filtered = df[mask]
                    if not filtered.empty:
                        all_frames.append(filtered)
                except Exception as exc:
                    logger.warning("cold_read_error", path=str(file_path), error=str(exc))

            current += timedelta(days=1)

        if not all_frames:
            return pd.DataFrame(columns=["time", "tenant_id", "cluster_id", "node_id", "metric_name", "value"])

        result = pd.concat(all_frames, ignore_index=True)
        return result.sort_values("time").reset_index(drop=True)

    def list_partitions(self, tenant_id: str) -> List[str]:
        tenant_path = self.base_path / tenant_id
        if not tenant_path.exists():
            return []

        partitions = []
        for root, dirs, files in os.walk(str(tenant_path)):
            for f in files:
                if f.endswith(".parquet"):
                    partitions.append(os.path.join(root, f))

        return partitions

    def get_storage_stats(self, tenant_id: str) -> Dict:
        partitions = self.list_partitions(tenant_id)
        total_size = sum(os.path.getsize(p) for p in partitions)

        return {
            "tenant_id": tenant_id,
            "num_partitions": len(partitions),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
