from __future__ import annotations

"""
Centralized benchmark runner for Phases 1, 2, and 3.

This is the single benchmark entrypoint for the current project. It exercises:
  1. Phase 1 data contract checks
  2. Phase 2 ingestion/storage checks
  3. Phase 3 controlled anomaly detection
  4. Phase 3 real CSV replay over the sample cluster
  5. Storage/query validation and aggregation timings

Exit code:
  0 = benchmark passed
  1 = benchmark failed
"""

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import perf_counter
from typing import Dict, List

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

IMPORT_FAILURE = None

try:
    from backend.analytics.aggregation import ClusterAnomalyAggregator, TenantAnomalyAggregator
    from backend.analytics.detection_pipeline import AnomalyDetectionPipeline
    from backend.analytics.explain import ExplanationClassifier
    from backend.analytics.merlion_engine import MerlionAnomalyEngine
    from backend.analytics.types import (
        AggregatedAnomalyScore,
        AnomalyResult,
        MetricPoint,
        MetricSeries,
    )
    from backend.ingestion.collector import MetricCollector, SimulatorSource
    from backend.ingestion.pipeline import IngestionPipeline
    from backend.ingestion.validator import MetricValidator
    from backend.simulator.csv_replay import CSVScenarioReplayer
    from backend.simulator.generator import AnomalyInjector, MetricSimulator, SimulatorConfig
    from backend.storage.interface import configure_storage
    from backend.storage.memory_storage import InMemoryStorage
except Exception as exc:
    IMPORT_FAILURE = exc


class BenchmarkFailure(RuntimeError):
    """Raised when a benchmark gate fails."""


@dataclass
class BenchmarkConfig:
    scenario_dir: str
    cluster_id: str
    tenant_id: str
    control_window_size: int
    real_window_size: int
    control_contamination: float
    real_contamination: float


def _print_section(title: str) -> None:
    print("\n" + "-" * 80)
    print(title.center(80))
    print("-" * 80)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise BenchmarkFailure(message)


def _elapsed_ms(start_time: float) -> float:
    return (perf_counter() - start_time) * 1000.0


def _windows_overlap(
    left_start,
    left_end,
    right_start,
    right_end,
) -> bool:
    return left_start <= right_end and left_end >= right_start


def _build_engine(window_size: int, contamination: float) -> MerlionAnomalyEngine:
    return MerlionAnomalyEngine(
        config={
            "window_size": window_size,
            "contamination": contamination,
        }
    )


def _flatten_series_by_metric(
    cluster_metrics: Dict[str, List[MetricSeries]],
) -> tuple[List[str], List[str], List[MetricSeries]]:
    node_ids = sorted(cluster_metrics.keys())
    all_series: List[MetricSeries] = []
    metric_names = set()

    for node_id in node_ids:
        node_series = sorted(cluster_metrics[node_id], key=lambda series: series.metric_name)
        all_series.extend(node_series)
        metric_names.update(series.metric_name for series in node_series)

    return node_ids, sorted(metric_names), all_series


def run_phase1_contract_benchmark() -> Dict[str, float]:
    now = datetime.utcnow()

    point = MetricPoint(timestamp=now, value=42.5)
    _assert(point.timestamp == now, "MetricPoint timestamp mismatch")
    _assert(point.value == 42.5, "MetricPoint value mismatch")

    timestamps = [now + timedelta(minutes=index) for index in range(10)]
    values = [float(50 + index) for index in range(10)]
    series = MetricSeries(
        tenant_id="phase1-tenant",
        cluster_id="phase1-cluster",
        node_id="node-001",
        metric_name="cpu_usage",
        timestamps=timestamps,
        values=values,
    )
    _assert(series.length == 10, "MetricSeries length mismatch")
    _assert(series.time_range == (timestamps[0], timestamps[-1]), "MetricSeries time range mismatch")

    try:
        MetricSeries(
            tenant_id="phase1-tenant",
            cluster_id="phase1-cluster",
            node_id="node-001",
            metric_name="cpu_usage",
            timestamps=timestamps,
            values=values[:-1],
        )
    except ValueError:
        pass
    else:
        raise BenchmarkFailure("MetricSeries should reject mismatched timestamp/value lengths")

    anomaly = AnomalyResult(
        tenant_id="phase1-tenant",
        cluster_id="phase1-cluster",
        node_id="node-001",
        metric_name="cpu_usage",
        window_start=now,
        window_end=now + timedelta(minutes=5),
        anomaly_score=0.75,
        anomaly_label="spike",
    )
    _assert(anomaly.is_anomaly, "AnomalyResult should mark spike labels as anomalous")

    try:
        AnomalyResult(
            tenant_id="phase1-tenant",
            cluster_id="phase1-cluster",
            node_id="node-001",
            metric_name="cpu_usage",
            window_start=now,
            window_end=now + timedelta(minutes=5),
            anomaly_score=1.5,
            anomaly_label="spike",
        )
    except ValueError:
        pass
    else:
        raise BenchmarkFailure("AnomalyResult should reject scores outside [0, 1]")

    aggregate = AggregatedAnomalyScore(
        tenant_id="phase1-tenant",
        cluster_id="phase1-cluster",
        node_id="node-001",
        aggregate_score=0.60,
        num_metrics_analyzed=5,
        num_anomalies_detected=2,
    )
    _assert(aggregate.aggregate_score == 0.60, "AggregatedAnomalyScore value mismatch")

    return {
        "checks": 6.0,
        "series_length": float(series.length),
        "aggregate_score": aggregate.aggregate_score,
    }


def run_phase2_ingestion_benchmark() -> Dict[str, float]:
    storage = InMemoryStorage()
    configure_storage(storage)

    validator = MetricValidator()
    simulator = MetricSimulator()

    series = simulator.generate(
        tenant_id="phase2-tenant",
        cluster_id="phase2-cluster",
        node_id="node-001",
        metric_name="cpu_usage",
        num_points=100,
    )

    validation = validator.validate(series)
    _assert(validation.is_valid, f"Phase 2 validation rejected a valid series: {validation.errors}")

    storage.store_metric(series)
    retrieved = storage.get_metric_series(
        tenant_id=series.tenant_id,
        cluster_id=series.cluster_id,
        node_id=series.node_id,
        metric_name=series.metric_name,
        start_time=series.timestamps[0],
        end_time=series.timestamps[-1],
    )
    _assert(len(retrieved.values) == len(series.values), "Stored metric length mismatch on retrieval")

    collector = MetricCollector(SimulatorSource())
    pipeline = IngestionPipeline(collector, validator, storage)

    ingest_started = perf_counter()
    ingested_series, stats = pipeline.ingest_metric(
        tenant_id="phase2-tenant",
        cluster_id="phase2-cluster",
        node_id="node-002",
        metric_name="memory_used",
        start_time=datetime.utcnow() - timedelta(hours=1),
        end_time=datetime.utcnow(),
    )
    ingest_ms = _elapsed_ms(ingest_started)

    _assert(ingested_series is not None, "Ingestion pipeline returned no series")
    _assert(stats.total_valid == 1, f"Expected 1 valid ingested metric, got {stats.total_valid}")
    _assert(stats.total_stored == 1, f"Expected 1 stored ingested metric, got {stats.total_stored}")
    _assert(stats.success_rate() == 1.0, f"Expected 100% success rate, got {stats.success_rate():.2f}")

    tenant_a = simulator.generate(
        tenant_id="tenant-a",
        cluster_id="cluster-1",
        node_id="node-1",
        metric_name="cpu",
        num_points=10,
    )
    tenant_b = simulator.generate(
        tenant_id="tenant-b",
        cluster_id="cluster-1",
        node_id="node-1",
        metric_name="cpu",
        num_points=10,
    )
    storage.store_metric(tenant_a)
    storage.store_metric(tenant_b)

    isolated_series = storage.get_metric_series(
        tenant_id="tenant-a",
        cluster_id="cluster-1",
        node_id="node-1",
        metric_name="cpu",
        start_time=tenant_a.timestamps[0],
        end_time=tenant_a.timestamps[-1],
    )
    _assert(isolated_series.tenant_id == "tenant-a", "Tenant isolation retrieval check failed")

    storage_stats = storage.get_stats()
    _assert(storage_stats["total_metrics"] >= 4, "Phase 2 benchmark stored fewer metrics than expected")

    return {
        "stored_metrics": float(storage_stats["total_metrics"]),
        "ingest_ms": ingest_ms,
        "success_rate": stats.success_rate(),
    }


def run_control_benchmark(config: BenchmarkConfig) -> Dict[str, float]:
    storage = InMemoryStorage()
    configure_storage(storage)

    simulator = MetricSimulator(
        SimulatorConfig(
            baseline_mean=45.0,
            baseline_std=3.0,
            noise_level=0.05,
            inject_spikes=False,
        )
    )

    base_series = simulator.generate(
        tenant_id="benchmark-tenant",
        cluster_id="benchmark-cluster",
        node_id="node-control",
        metric_name="cpu_usage",
        num_points=240,
    )
    injected_series, spike_meta = AnomalyInjector.inject_spike(
        base_series,
        spike_index=120,
        magnitude=6.0,
        duration=10,
    )

    validation = MetricValidator().validate(injected_series)
    _assert(validation.is_valid, f"Injected control series failed validation: {validation.errors}")

    storage.store_metric(injected_series)

    pipeline = AnomalyDetectionPipeline(
        engine=_build_engine(
            window_size=config.control_window_size,
            contamination=config.control_contamination,
        ),
        classifier=ExplanationClassifier(),
        storage_backend=storage,
    )

    detect_started = perf_counter()
    results, explanations, stats = pipeline.detect_metric(injected_series)
    detect_ms = _elapsed_ms(detect_started)

    _assert(not stats.has_critical_errors(), f"Control detection had critical errors: {stats.errors}")
    _assert(results, "Control benchmark produced no detection windows")
    _assert(len(explanations) == len(results), "Control explanations count mismatched detection results")
    _assert(
        all(result.explanation for result in results),
        "Control benchmark produced results without rendered explanations",
    )

    spike_start = injected_series.timestamps[spike_meta["index"]]
    spike_end = injected_series.timestamps[min(
        spike_meta["index"] + spike_meta["duration"] - 1,
        len(injected_series.timestamps) - 1,
    )]

    overlapping_results = [
        result for result in results
        if _windows_overlap(result.window_start, result.window_end, spike_start, spike_end)
    ]
    _assert(overlapping_results, "No detection window overlapped the injected anomaly range")

    overlap_max_score = max(result.anomaly_score for result in overlapping_results)
    _assert(overlap_max_score > 0.0, "Injected anomaly did not increase anomaly score above zero")

    query_started = perf_counter()
    queried = storage.query_anomalies(
        tenant_id=injected_series.tenant_id,
        cluster_id=injected_series.cluster_id,
        start_time=min(result.window_start for result in results),
        end_time=max(result.window_end for result in results),
        min_score=0.0,
    )
    query_ms = _elapsed_ms(query_started)

    _assert(len(queried) == len(results), "Control query result count mismatched stored anomaly count")

    return {
        "windows": float(len(results)),
        "max_overlap_score": overlap_max_score,
        "detect_ms": detect_ms,
        "query_ms": query_ms,
    }


def run_realworld_benchmark(config: BenchmarkConfig) -> Dict[str, float]:
    storage = InMemoryStorage()
    configure_storage(storage)

    load_started = perf_counter()
    replayer = CSVScenarioReplayer(config.scenario_dir, tenant_id=config.tenant_id)
    cluster_metrics = replayer.load_scenario(config.cluster_id)
    load_ms = _elapsed_ms(load_started)

    node_ids, metric_names, all_series = _flatten_series_by_metric(cluster_metrics)
    _assert(node_ids, "CSV replay benchmark loaded no nodes")
    _assert(metric_names, "CSV replay benchmark loaded no metrics")
    _assert(all_series, "CSV replay benchmark loaded no metric series")

    validator = MetricValidator()
    for series in all_series:
        validation = validator.validate(series)
        _assert(
            validation.is_valid,
            f"CSV series failed validation for {series.node_id}/{series.metric_name}: {validation.errors}",
        )
        storage.store_metric(series)

    pipeline = AnomalyDetectionPipeline(
        engine=_build_engine(
            window_size=config.real_window_size,
            contamination=config.real_contamination,
        ),
        classifier=ExplanationClassifier(),
        storage_backend=storage,
    )

    detect_started = perf_counter()
    results, cluster_score, stats = pipeline.detect_cluster(
        tenant_id=config.tenant_id,
        cluster_id=config.cluster_id,
        node_ids=node_ids,
        metric_names=metric_names,
    )
    detect_ms = _elapsed_ms(detect_started)

    _assert(not stats.has_critical_errors(), f"Cluster detection had critical errors: {stats.errors}")
    _assert(results, "CSV replay benchmark produced no detection results")
    _assert(cluster_score is not None, "Cluster-level aggregate score was not produced")
    _assert(0.0 <= cluster_score.aggregate_score <= 1.0, "Cluster score fell outside [0, 1]")

    query_started = perf_counter()
    queried = storage.query_anomalies(
        tenant_id=config.tenant_id,
        cluster_id=config.cluster_id,
        start_time=min(result.window_start for result in results),
        end_time=max(result.window_end for result in results),
        min_score=0.0,
    )
    query_ms = _elapsed_ms(query_started)

    _assert(len(queried) == len(results), "CSV query result count mismatched stored anomaly count")

    stored_scores = storage.aggregated_scores[config.tenant_id]
    node_scores = [score for score in stored_scores if score.cluster_id == config.cluster_id and score.node_id]
    cluster_scores = [score for score in stored_scores if score.cluster_id == config.cluster_id and score.node_id is None]

    _assert(len(node_scores) == len(node_ids), "Node aggregate count mismatched cluster node count")
    _assert(len(cluster_scores) == 1, "Expected exactly one stored cluster aggregate score")

    ranked_nodes = ClusterAnomalyAggregator().rank_nodes(node_scores)
    ranked_scores = [score.aggregate_score for score in ranked_nodes]
    _assert(
        ranked_scores == sorted(ranked_scores, reverse=True),
        "Node ranking is not sorted by descending anomaly score",
    )

    tenant_score = TenantAnomalyAggregator().aggregate([cluster_score])
    _assert(0.0 <= tenant_score.aggregate_score <= 1.0, "Tenant score fell outside [0, 1]")

    return {
        "nodes": float(len(node_ids)),
        "metrics": float(len(metric_names)),
        "series": float(len(all_series)),
        "windows": float(len(results)),
        "cluster_score": cluster_score.aggregate_score,
        "tenant_score": tenant_score.aggregate_score,
        "load_ms": load_ms,
        "detect_ms": detect_ms,
        "query_ms": query_ms,
    }


def parse_args() -> BenchmarkConfig:
    parser = argparse.ArgumentParser(
        description="Run the centralized Phase 1/2/3 benchmark."
    )
    parser.add_argument(
        "--scenario-dir",
        default="scenarios",
        help="Root scenario directory containing the sample cluster CSV files.",
    )
    parser.add_argument(
        "--cluster-id",
        default="prod-cluster",
        help="Cluster directory name to replay during the real-world benchmark.",
    )
    parser.add_argument(
        "--tenant-id",
        default="benchmark-tenant",
        help="Tenant id used for the CSV replay benchmark.",
    )
    parser.add_argument(
        "--control-window-size",
        type=int,
        default=40,
        help="Window size used for the injected-anomaly control benchmark.",
    )
    parser.add_argument(
        "--real-window-size",
        type=int,
        default=8,
        help="Window size used for the CSV replay benchmark.",
    )
    parser.add_argument(
        "--control-contamination",
        type=float,
        default=0.10,
        help="Isolation Forest contamination for the injected-anomaly control benchmark.",
    )
    parser.add_argument(
        "--real-contamination",
        type=float,
        default=0.15,
        help="Isolation Forest contamination for the CSV replay benchmark.",
    )
    args = parser.parse_args()
    return BenchmarkConfig(
        scenario_dir=args.scenario_dir,
        cluster_id=args.cluster_id,
        tenant_id=args.tenant_id,
        control_window_size=args.control_window_size,
        real_window_size=args.real_window_size,
        control_contamination=args.control_contamination,
        real_contamination=args.real_contamination,
    )


def main() -> int:
    config = parse_args()

    print("\n" + "=" * 80)
    print("CENTRALIZED PHASE BENCHMARK".center(80))
    print("=" * 80)

    if IMPORT_FAILURE is not None:
        print("\nBENCHMARK FAILED: runtime environment is not ready")
        print(f"Missing dependency or import error: {IMPORT_FAILURE}")
        return 1

    try:
        phase1_metrics = run_phase1_contract_benchmark()
        phase2_metrics = run_phase2_ingestion_benchmark()
        control_metrics = run_control_benchmark(config)
        real_metrics = run_realworld_benchmark(config)
    except BenchmarkFailure as exc:
        print(f"\nBENCHMARK FAILED: {exc}")
        return 1
    except Exception as exc:
        print(f"\nBENCHMARK FAILED WITH UNEXPECTED ERROR: {exc}")
        return 1

    _print_section("PHASE 1 CONTRACT BENCHMARK")
    print(f"  Checks passed: {int(phase1_metrics['checks'])}")
    print(f"  Series length: {int(phase1_metrics['series_length'])}")
    print(f"  Aggregate score sample: {phase1_metrics['aggregate_score']:.2f}")

    _print_section("PHASE 2 INGESTION/STORAGE BENCHMARK")
    print(f"  Stored metrics: {int(phase2_metrics['stored_metrics'])}")
    print(f"  Ingest latency: {phase2_metrics['ingest_ms']:.1f} ms")
    print(f"  Success rate: {phase2_metrics['success_rate']:.1%}")

    _print_section("PHASE 3 CONTROL BENCHMARK")
    print(f"  Detection windows: {int(control_metrics['windows'])}")
    print(f"  Max overlapping score: {control_metrics['max_overlap_score']:.3f}")
    print(f"  Detect latency: {control_metrics['detect_ms']:.1f} ms")
    print(f"  Query latency: {control_metrics['query_ms']:.1f} ms")

    _print_section("PHASE 3 REAL-WORLD CSV BENCHMARK")
    print(f"  Nodes replayed: {int(real_metrics['nodes'])}")
    print(f"  Metrics replayed: {int(real_metrics['metrics'])}")
    print(f"  Series loaded: {int(real_metrics['series'])}")
    print(f"  Detection windows: {int(real_metrics['windows'])}")
    print(f"  Cluster score: {real_metrics['cluster_score']:.3f}")
    print(f"  Tenant score: {real_metrics['tenant_score']:.3f}")
    print(f"  Load latency: {real_metrics['load_ms']:.1f} ms")
    print(f"  Detect latency: {real_metrics['detect_ms']:.1f} ms")
    print(f"  Query latency: {real_metrics['query_ms']:.1f} ms")

    print("\nCENTRALIZED BENCHMARK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
