## File roles (current files)

### Root
- [backend_README.md](../backend_README.md): Centralized project documentation (Phase 1 + 2).
- [PHASE2_SUMMARY.md](../PHASE2_SUMMARY.md): Phase 2 summary.
- [benchmark_phase3.py](../benchmark_phase3.py): Single centralized benchmark runner for Phases 1, 2, and 3.

### Analytics module
- [backend/analytics/__init__.py](analytics/__init__.py): Public exports for analytics.
- [backend/analytics/types.py](analytics/types.py): Core data contracts (MetricSeries, AnomalyResult, AggregatedAnomalyScore).
- [backend/analytics/engine.py](analytics/engine.py): Abstract detection engine interface.
- [backend/analytics/windows.py](analytics/windows.py): Sliding window extraction logic.
- [backend/analytics/aggregation.py](analytics/aggregation.py): Node → Cluster → Tenant aggregation.
- [backend/analytics/explain.py](analytics/explain.py): Explanation scaffolding (stub).
- [backend/analytics/INTEGRATION_CONTRACT.py](analytics/INTEGRATION_CONTRACT.py): Required integration contract for storage/ingestion.
- [backend/analytics/README.md](analytics/README.md): Analytics module documentation.

### Ingestion layer
- [backend/ingestion/__init__.py](ingestion/__init__.py): Public exports.
- [backend/ingestion/collector.py](ingestion/collector.py): Metric collection (SimulatorSource now; future external sources).
- [backend/ingestion/validator.py](ingestion/validator.py): Data quality checks + tenant isolation.
- [backend/ingestion/pipeline.py](ingestion/pipeline.py): Collect → Validate → Store pipeline.

### Simulator
- [backend/simulator/__init__.py](simulator/__init__.py): Public exports.
- [backend/simulator/generator.py](simulator/generator.py): Synthetic data generation + anomaly injection.

### Storage layer
- [backend/storage/__init__.py](storage/__init__.py): Public exports.
- [backend/storage/interface.py](storage/interface.py): Storage contract + global configuration.
- [backend/storage/memory_storage.py](storage/memory_storage.py): In-memory reference storage.
