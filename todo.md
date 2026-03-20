## ✅ README_PHASE_REMAINING.md (Detailed Work Left)

# AboutCloud — Remaining Work & Issues

This document is the current reality check for the repo.

The key scope rule is now:

**Phase 3 includes the MVP backend platform work**
- real anomaly detection
- persistent storage backend
- hot/cold storage MVP
- authentication/authorization
- core API endpoints

**Phase 4 stays dashboard-focused**

**Phase 5 is only**
- configuration/deployment
- performance/scaling
- API hardening

---

# 📌 Current Status (Honest)

Right now, the project is **not complete for the full Phase 3 MVP**.

What we actually have:
- a partially working analytics core
- incomplete storage integration
- no finished persistent backend
- no finished hot/cold storage MVP
- no finished auth layer
- no finished core API layer
- no deployment setup

So the project is still before true Phase 3 completion.

---

# 🔴 Major Issues (Must Fix First)

## 1. Storage & Query Contract

### Problem
- anomaly storage/query behavior must fully match `AnomalyResult`
- multi-window anomalies must be preserved
- query logic must work across the intended storage path

### What needs to be done
- fix storage contract consistency
- ensure overlap-based anomaly queries work
- ensure persistent storage and hot/cold tiers use the same contract

---

## 2. Detection Pipeline → Aggregation Integration

### Problem
- the cluster aggregation path has had integration mismatches
- end-to-end execution must be validated using the actual pipeline path

### What needs to be done
- ensure node aggregation feeds cluster aggregation correctly
- ensure stored outputs are queryable and rankable
- benchmark the real path, not just isolated pieces

---

## 3. Phase 3 MVP Scope Is Bigger Than Detection Alone

### Problem
Phase 3 is not just:
- anomaly scoring

It must also include the MVP backend platform pieces:
- persistent storage backend
- hot/cold storage MVP
- auth
- core API endpoints

### What needs to be done
- implement those pieces as part of Phase 3 completion
- stop treating them as later-phase-only work

---

## 4. No Real Persistent Backend Yet

### Problem
- storage is still effectively in-memory or incomplete for the final MVP path

### Fix
- add a real persistent backend
- wire analytics and queries to it
- make replay/backfill possible

---

## 5. No Hot/Cold Storage MVP Yet

### Problem
- recent vs archival storage behavior is not delivered yet

### Fix
- define hot tier for recent data
- define cold tier for archived data
- add retention/movement rules
- keep query behavior usable across both tiers

---

## 6. No Finished Auth Or API MVP Yet

### Problem
- there is still no finished auth-protected API layer for the MVP

### Fix
- add auth
- enforce tenant isolation at API entry points
- implement:
  - `/metrics`
  - `/anomalies`
  - `/health`
  - any required ingestion/query endpoints for MVP use

---

## 7. Benchmark Must Be The Gate

### Problem
- phase completion should not depend on scattered scripts

### Fix
- keep one centralized benchmark runner
- benchmark:
  - contracts
  - ingestion/storage
  - detection
  - replay
  - aggregation
  - MVP storage/auth/API path

---

# 🧠 Analytics Tasks (Abhigyan — You)

## Phase 3 Completion Work

- [ ] Fix detection → storage data compatibility
- [ ] Fix aggregation pipeline (node → cluster)
- [ ] Clean anomaly explanation logic
- [ ] Ensure sliding windows behave deterministically
- [ ] Add proper threshold usage in scoring
- [ ] Ensure analytics outputs work with persistent storage
- [ ] Ensure analytics outputs work through the MVP API layer

## Verification

- [ ] Keep one centralized benchmark
- [ ] Ensure simulator + real CSV replay both work
- [ ] Ensure benchmark failure is strict and honest

---

# ⚙️ Backend Tasks (Saivats + Bhavi)

## Phase 3 MVP Backend Work

- [ ] Fix storage interface consistency
- [ ] Implement proper persistent storage backend
- [ ] Implement hot storage and cold storage MVP behavior
- [ ] Add retention/archival rules
- [ ] Ensure ingestion → analytics → storage compatibility
- [ ] Build API endpoints:
- `POST /metrics`
- `GET /metrics`
- `GET /anomalies`
- `GET /health`
- [ ] Add authentication/authorization
- [ ] Enforce tenant isolation at API level
- [ ] Add structured logging and basic metrics
- [ ] Add backfill/replay support

---

# 🎨 UI Tasks (Vabhravi)

## Phase 4 Work

- [ ] Build dashboard pages:
- overview
- anomaly trends
- node ranking
- drill-down
- [ ] Connect to backend APIs
- [ ] Design clean visualization (not fancy, just clear)

## Goal

Take raw anomaly data and make it understandable.

---

# 🧊 Phase 5 Work (Later)

## Configuration & Deployment

- [ ] Add environment configs
- [ ] Add Docker/deployment setup
- [ ] Write deployment/runbook docs

## Performance & Scaling

- [ ] Optimize throughput and batch behavior
- [ ] Improve query/cache performance
- [ ] Tune for larger tenant/node loads

## API Hardening

- [ ] Add pagination
- [ ] Add rate limiting
- [ ] Normalize API errors
- [ ] Tighten request validation

---

# ❌ What We DO NOT Have Yet

- No completed hot/cold storage MVP
- No completed persistent backend
- No completed auth layer
- No completed MVP API layer
- No dashboard system
- No deployment setup

---

# 🎯 Final Goal

Target for Phase 3 completion:

```text
Ingestion -> Detection -> Persistent Storage -> Hot/Cold MVP -> Auth -> Core API -> Benchmark
```

Phase 4 then builds on top of that for dashboard/UI delivery.

---

# 🧭 How To Move Forward

1. Finish the full Phase 3 MVP backend
2. Keep Phase 4 focused on dashboard/UI
3. Use Phase 5 only for deployment, scaling, and API hardening

---

# ⚠️ Rule

No fake phase completion.

If the MVP backend pieces are missing, Phase 3 is still incomplete.
