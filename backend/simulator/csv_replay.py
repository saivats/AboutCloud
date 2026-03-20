"""
CSV Replay Module - Load real or CSV-based metric data

Allows Phase 3 verification to test with real data instead of just simulated data.
"""

import sys
import os
import csv
from datetime import datetime
from typing import List, Optional, Dict
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.types import MetricSeries


class CSVReplayError(Exception):
    """CSV replay-specific errors"""
    pass


class CSVMetricLoader:
    """
    Load metrics from CSV files.

    Expected CSV format:
    timestamp,value
    2026-03-09T10:00:00,65.5
    2026-03-09T10:01:00,67.2
    ...

    Or with metadata:
    tenant_id,cluster_id,node_id,metric_name,timestamp,value,unit
    acme-corp,prod-us-east,node-001,cpu_usage,2026-03-09T10:00:00,65.5,%
    """

    def __init__(self):
        """Initialize CSV loader"""
        self.loaded_files = {}

    def load_from_csv(
            self,
            filepath: str,
            tenant_id: str,
            cluster_id: str,
            node_id: str,
            metric_name: str,
            timestamp_format: str = "%Y-%m-%dT%H:%M:%S",
    ) -> MetricSeries:
        """
        Load metric series from CSV file.

        Args:
            filepath: Path to CSV file
            tenant_id: Tenant identifier
            cluster_id: Cluster identifier
            node_id: Node identifier
            metric_name: Metric name
            timestamp_format: Strptime format for timestamps

        Returns:
            MetricSeries object

        Raises:
            CSVReplayError: If file not found or format invalid
        """

        if not os.path.exists(filepath):
            raise CSVReplayError(f"CSV file not found: {filepath}")

        timestamps = []
        values = []

        try:
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)

                if reader.fieldnames is None:
                    raise CSVReplayError(f"Empty CSV file: {filepath}")

                # Detect format
                has_metadata = 'tenant_id' in reader.fieldnames

                for row_num, row in enumerate(reader, start=2):  # Start at 2 (skip header)
                    try:
                        # Parse timestamp
                        ts_str = row.get('timestamp')
                        if not ts_str:
                            raise CSVReplayError(f"Row {row_num}: missing timestamp")

                        try:
                            timestamp = datetime.strptime(ts_str, timestamp_format)
                        except ValueError as e:
                            raise CSVReplayError(
                                f"Row {row_num}: invalid timestamp '{ts_str}' "
                                f"(expected format: {timestamp_format})"
                            )

                        # Parse value
                        val_str = row.get('value')
                        if not val_str:
                            raise CSVReplayError(f"Row {row_num}: missing value")

                        try:
                            value = float(val_str)
                        except ValueError:
                            raise CSVReplayError(f"Row {row_num}: invalid value '{val_str}' (must be numeric)")

                        timestamps.append(timestamp)
                        values.append(value)

                    except CSVReplayError:
                        raise
                    except Exception as e:
                        raise CSVReplayError(f"Row {row_num}: {e}")

        except CSVReplayError:
            raise
        except Exception as e:
            raise CSVReplayError(f"Failed to read CSV: {e}")

        if not timestamps:
            raise CSVReplayError(f"No valid data rows in CSV: {filepath}")

        # Create MetricSeries
        series = MetricSeries(
            tenant_id=tenant_id,
            cluster_id=cluster_id,
            node_id=node_id,
            metric_name=metric_name,
            timestamps=timestamps,
            values=values,
            metadata={
                'source': 'csv_replay',
                'filepath': filepath,
                'loaded_at': datetime.utcnow().isoformat(),
            }
        )

        self.loaded_files[filepath] = series

        return series

    def create_sample_csv(self, filepath: str, num_points: int = 100) -> str:
        """
        Create a sample CSV file for testing.

        Args:
            filepath: Where to write the CSV
            num_points: Number of data points

        Returns:
            Path to created file
        """
        from datetime import timedelta
        import random

        # Generate synthetic data
        start_time = datetime(2026, 3, 1, 0, 0, 0)
        timestamps = []
        values = []

        baseline = 50.0
        for i in range(num_points):
            ts = start_time + timedelta(minutes=i)
            # Add some variation
            value = baseline + random.gauss(0, 5)
            # Inject spike at middle
            if i == num_points // 2:
                value *= 3
            value = max(0, min(100, value))  # Clip to [0, 100]

            timestamps.append(ts)
            values.append(value)

        # Write CSV
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)

        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'value'])

            for ts, val in zip(timestamps, values):
                writer.writerow([ts.strftime("%Y-%m-%dT%H:%M:%S"), f"{val:.2f}"])

        return filepath


class CSVScenarioReplayer:
    """
    Replay multi-metric, multi-node scenarios from CSV files.

    Directory structure:
    scenarios/
    └── prod-us-east/
        ├── node-001/
        │   ├── cpu_usage.csv
        │   ├── memory_used.csv
        │   └── disk_io.csv
        └── node-002/
            ├── cpu_usage.csv
            ├── memory_used.csv
            └── disk_io.csv
    """

    def __init__(self, scenario_dir: str, tenant_id: str):
        """
        Initialize scenario replayer.

        Args:
            scenario_dir: Root directory containing scenario data
            tenant_id: Tenant identifier for all loaded metrics
        """
        self.scenario_dir = scenario_dir
        self.tenant_id = tenant_id
        self.loader = CSVMetricLoader()

    def load_scenario(
            self,
            cluster_id: str,
    ) -> Dict[str, List[MetricSeries]]:
        """
        Load all metrics for a cluster from CSV files.

        Structure: scenario_dir/cluster_id/node_id/metric_name.csv

        Args:
            cluster_id: Cluster to load

        Returns:
            Dict[node_id, List[MetricSeries]]

        Raises:
            CSVReplayError: If scenario not found
        """

        cluster_path = os.path.join(self.scenario_dir, cluster_id)

        if not os.path.exists(cluster_path):
            raise CSVReplayError(f"Cluster not found: {cluster_path}")

        results = {}

        # Iterate over nodes
        for node_dir in os.listdir(cluster_path):
            node_path = os.path.join(cluster_path, node_dir)

            if not os.path.isdir(node_path):
                continue

            node_metrics = []

            # Load each metric CSV
            for csv_file in os.listdir(node_path):
                if not csv_file.endswith('.csv'):
                    continue

                metric_name = csv_file[:-4]  # Remove .csv
                csv_path = os.path.join(node_path, csv_file)

                try:
                    series = self.loader.load_from_csv(
                        filepath=csv_path,
                        tenant_id=self.tenant_id,
                        cluster_id=cluster_id,
                        node_id=node_dir,
                        metric_name=metric_name,
                    )
                    node_metrics.append(series)
                except CSVReplayError as e:
                    print(f"⚠️  Skipping {csv_path}: {e}")

            if node_metrics:
                results[node_dir] = node_metrics

        if not results:
            raise CSVReplayError(f"No valid metrics found in {cluster_path}")

        return results