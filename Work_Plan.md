
## Upcoming Phases 
- Phase 3 (Real Anomaly Detection): Saivats
- Phase 4 (API/Dashboard): Bhavi
- Phase 5 (Production Readiness): Saivats + Bhavi

---

## Phase 3 — Saivats (Real Anomaly Detection)

### Goal
Implement real anomaly detection and explanation logic on top of the existing ingestion + analytics pipeline.

### Required Work Items
1. **Merlion Integration (Engine Implementation)**
	- Add a concrete engine class, e.g. `MerlionAnomalyEngine`, implementing `AnomalyDetectionEngine`.
	- Map Merlion outputs to `AnomalyResult` fields:
	  - `anomaly_score` in $[0, 1]$
	  - `anomaly_label` in {spike, trend, seasonal, normal}
	  - `window_start/window_end` set correctly
	- Ensure multi-tenant metadata is preserved (`tenant_id`, `cluster_id`, `node_id`, `metric_name`).

2. **Detection Pipeline Wiring**
	- Fetch `MetricSeries` from storage (via `get_metric_series`).
	- Run detection engine over sliding windows or full series.
	- Return `AnomalyResult` and feed into aggregation.
	- Store per-metric results using `StorageBackend.store_anomaly_result()`.

3. **Explanation Logic**
	- Implement real logic in `backend/analytics/explain.py`:
	  - Detect spikes, trends, seasonality.
	  - Assign labels and explanation text.
	- Provide confidence or severity (optional).

4. **Calibration + Thresholds**
	- Add configurable thresholds (global defaults + per-metric overrides).
	- Include safe defaults for cloud metrics (CPU, memory, disk, network).

5. **Verification**
	- Add a `benchmark_phase3.py` benchmark script as the single centralized test runner:
	  - Cover Phase 1 contract validation.
	  - Cover Phase 2 ingestion + storage validation.
	  - Run simulator → ingestion → detection → aggregation.
	  - Replay sample CSV metrics through the real pipeline.
	  - Ensure anomalies are detected when injected.
	- Update `test_all_features.py` to call real detection (remove mocks).

### Expected Deliverables
- New engine implementation file(s) under `backend/analytics/`.
- Updated `explain.py` with working classification.
- Verification script proving real detection works end-to-end.

---

## Phase 4 — Bhavi (API + Dashboard)

### Goal
Expose ingestion and analytics via HTTP API and provide a simple dashboard view.

### Required Work Items
1. **REST API (FastAPI or Flask)**
	- Endpoints:
	  - `POST /metrics` → ingest metrics batch
	  - `GET /metrics` → query stored metrics
	  - `GET /anomalies` → query anomaly results
	  - `GET /health` → cluster/tenant health summary
	- Validate payloads and enforce tenant isolation.

2. **API → Pipeline Wiring**
	- Use `IngestionPipeline` for writes.
	- Use storage + analytics modules for reads.
	- Return JSON with clear schemas.

3. **Dashboard (Lightweight)**
	- Minimal UI showing:
	  - Cluster health score
	  - Top anomalous nodes
	  - Latest anomalies list
	- Can be a static HTML page or a simple React/Vite app.

4. **Persistence Upgrade (Optional but Recommended)**
	- Replace `InMemoryStorage` with real DB backend.
	- Add migrations or setup notes.

5. **Verification**
	- API tests using curl or pytest.
	- Document example requests/responses.

### Expected Deliverables
- API server files (e.g. `backend/api/`).
- API docs (routes + example payloads).
- Basic dashboard that consumes the API.

---

## Phase 5 — Saivats + Bhavi (Production Readiness)

### Goal
Make the system fully functional in real usage (persistent, secure, observable, scalable).

### Required Work Items
1. **Persistent Storage** (Owner: Saivats)
	- Implement DB-backed storage (PostgreSQL/TimescaleDB or equivalent).
	- Migrate from `InMemoryStorage` to a real backend.
	- Add data retention strategy (hot vs cold storage).

2. **Authentication & Authorization** (Owner: Bhavi)
	- Add API auth (API keys or JWT).
	- Enforce tenant isolation at the API boundary.
	- Role-based access for dashboards.

3. **Monitoring & Logging** (Owner: Saivats)
	- Structured logging (request IDs, tenant IDs).
	- Metrics: ingestion rate, detection latency, error rate.
	- Alerts for pipeline failure or anomaly spikes.

4. **Configuration & Deployment** (Owner: Bhavi)
	- Environment configs (dev/staging/prod).
	- Dockerization (optional but recommended).
	- Deployment notes and runbook.

5. **Performance & Scaling** (Owner: Saivats)
	- Batch ingestion optimization.
	- Cache frequently queried results.
	- Handle multi-tenant load gracefully.

6. **Data Backfill & Replay** (Owner: Saivats)
	- Ability to reprocess historical data.
	- Backfill anomalies for older data ranges.

7. **API Hardening** (Owner: Bhavi)
	- Pagination, rate limiting, error normalization.
	- Request validation with clear error responses.

### Expected Deliverables
- Persistent storage backend implemented.
- Auth-secured API with rate limits.
- Monitoring + logging integrated.
- Deployment documentation and configs.

---

## Handoff Notes
- Phase 3 depends on Phase 2 storage + ingestion (already working).
- Phase 4 depends on Phase 3 anomaly results being available via storage.
- Phase 5 makes the system production-ready and fully functional.
- Keep multi-tenant isolation intact in all new components.
