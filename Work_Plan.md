## Upcoming Phases
- Phase 3 (Real Anomaly Detection + MVP Storage/API/Auth): Saivats + Bhavi
- Phase 4 (API/Dashboard): Bhavi
- Phase 5 (Deployment, Hardening & Scaling): Saivats + Bhavi

---

## Phase 3 — Saivats + Bhavi (Real Anomaly Detection + MVP Platform)

### Goal
Implement real anomaly detection and complete the MVP platform path needed for:
- persistent storage
- hot/cold storage MVP
- authentication/authorization
- core API endpoints

This phase should deliver a usable backend pipeline:

**ingestion -> detection -> storage -> query -> aggregation -> auth -> API -> benchmark**

### Required Work Items
1. **Merlion Integration (Engine Implementation)**
	- Add and stabilize a concrete engine class, e.g. `MerlionAnomalyEngine`, implementing `AnomalyDetectionEngine`.
	- Map engine outputs to `AnomalyResult` fields:
	  - `anomaly_score` in `[0, 1]`
	  - `anomaly_label` in `{spike, trend, seasonal, normal}`
	  - `window_start/window_end` set correctly
	- Ensure multi-tenant metadata is preserved (`tenant_id`, `cluster_id`, `node_id`, `metric_name`).

2. **Detection Pipeline Wiring**
	- Fetch `MetricSeries` from storage (via `get_metric_series`).
	- Run detection engine over sliding windows or full series.
	- Return `AnomalyResult` and feed into aggregation.
	- Store per-metric results using `StorageBackend.store_anomaly_result()`.

3. **Explanation Logic**
	- Implement real logic in `backend/analytics/explain.py`:
	  - detect spikes, trends, seasonality
	  - assign labels and explanation text
	- Provide confidence or severity where useful.

4. **Calibration + Thresholds**
	- Add configurable thresholds (global defaults + per-metric overrides).
	- Include safe defaults for cloud metrics (CPU, memory, disk, network).

5. **Persistent Storage Backend + Hot/Cold Storage MVP** (Owner: Saivats)
	- Implement a DB-backed storage backend (PostgreSQL/TimescaleDB or equivalent).
	- Migrate from `InMemoryStorage` to a real persistent backend for the MVP path.
	- Add an MVP hot/cold storage split:
	  - hot storage for recent and frequently queried data
	  - cold storage for archived historical data
	- Add retention/archival rules for moving data from hot to cold.
	- Keep anomaly query paths compatible across both tiers.

6. **Authentication & Authorization** (Owner: Bhavi)
	- Add API auth (API keys or JWT).
	- Enforce tenant isolation at the API boundary.
	- Add the minimum authorization rules needed for MVP use.

7. **Core API Endpoints** (Owner: Bhavi)
	- Implement:
	  - `POST /metrics` -> ingest metrics batch
	  - `GET /metrics` -> query stored metrics
	  - `GET /anomalies` -> query anomaly results
	  - `GET /health` -> cluster/tenant health summary
	- Wire endpoints to ingestion, storage, and analytics modules.
	- Return clear JSON schemas.

8. **Monitoring & Logging** (Owner: Saivats)
	- Add structured logging (request IDs, tenant IDs, error context).
	- Add baseline metrics:
	  - ingestion rate
	  - detection latency
	  - error rate
	- Make pipeline failures visible during MVP testing.

9. **Data Backfill & Replay** (Owner: Saivats)
	- Add the ability to reprocess historical data.
	- Support replay/backfill for older data ranges.
	- Ensure backfilled data can be re-detected and queried correctly.

10. **Verification**
	- Add a `benchmark_phase3.py` benchmark script as the single centralized test runner:
	  - cover Phase 1 contract validation
	  - cover Phase 2 ingestion + storage validation
	  - run simulator -> ingestion -> detection -> aggregation
	  - replay sample CSV metrics through the real pipeline
	  - validate persistent storage and hot/cold MVP behavior
	  - validate auth-protected API calls for the MVP path
	  - ensure anomalies are detected when injected

### Expected Deliverables
- New or stabilized engine implementation under `backend/analytics/`.
- Updated `explain.py` with working classification.
- Persistent storage backend implemented for the MVP.
- MVP hot/cold storage path implemented.
- Auth-enabled core API endpoints available.
- Logging and replay/backfill support included.
- Single benchmark script proving Phase 1 + 2 + 3 work end-to-end.

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

## Phase 5 — Saivats + Bhavi (Deployment, Hardening & Scaling)

### Goal
Harden the completed MVP for deployment, scalability, and operational readiness.

### Required Work Items
1. **Configuration & Deployment** (Owner: Bhavi)
	- Environment configs (dev/staging/prod).
	- Dockerization (optional but recommended).
	- Deployment notes and runbook.

2. **Performance & Scaling** (Owner: Saivats)
	- Batch ingestion optimization.
	- Cache frequently queried results.
	- Handle multi-tenant load gracefully.

3. **API Hardening** (Owner: Bhavi)
	- Pagination, rate limiting, error normalization.
	- Request validation with clear error responses.

### Expected Deliverables
- Deployment documentation and environment configs.
- Performance/scaling improvements for real usage.
- Hardened API behavior under larger workloads.

---

## Handoff Notes
- Phase 3 now includes the MVP backend required for persistent storage, hot/cold storage, auth, and core API endpoints.
- Phase 4 remains focused on the dashboard and broader API presentation layer.
- Phase 5 is limited to deployment, scaling, and API hardening.
- Keep multi-tenant isolation intact in all new components.
