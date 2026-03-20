## ✅ **README_PHASE_REMAINING.md (Detailed Work Left)**

# AboutCloud — Remaining Work & Issues

This document clearly explains **what is still left to do**, what is **currently broken**, and what each part of the team needs to fix.

This is not a high-level plan — this is a **ground-level reality check + task assignment**.

---

# 📌 Current Status (Honest)

Right now, the project is **NOT complete up to hot/cold storage**.

What we actually have:
- A **partially working Phase 3 (anomaly detection pipeline)**
- No API layer
- No dashboard
- No real storage system (only in-memory)
- No deployment setup

So think of this as:
👉 *“Analytics core exists, but system is not complete yet”*

---

# 🔴 Major Issues (Must Fix First)

## 1. Storage & Query Mismatch

### Problem
- `AnomalyResult` stores:
  - single score
  - window_start / window_end
- But `memory_storage.py` expects:
  - timestamps list
  - multiple scores

👉 This breaks querying completely.

### What needs to be done
- Fix `query_anomalies()` to match `AnomalyResult`
- Query should:
  - filter by time range (window overlap)
  - filter by score threshold
  - return valid results

---

## 2. Detection Pipeline → Aggregation Broken

### Problem
- Pipeline calls:
```

ClusterAnomalyAggregator.aggregate(results=..., tenant_id=...)

```
- But aggregator expects:
```

aggregate(node_scores: List)

```

👉 This will fail when cluster aggregation runs.

### Fix
- First convert detection output → node-level scores
- Then pass proper list into aggregator

---

## 3. Verification Scripts Are Misleading

### Problem
- `verify_phase3.py` shows success even when things fail
- CSV replay verifier is broken:
- bad imports
- wrong storage usage
- wrong query calls

👉 This gives false confidence.

### Fix
- Make verification strict:
- if anything fails → exit with error
- Fix CSV replay script completely
- Ensure:
- detection works
- storage works
- query works

---

## 4. No Real Data Validation

### Problem
- Everything is simulator-based
- No real-world data testing

### Fix
- Add at least ONE:
- CSV replay
- or real metric dataset
- Ensure:
- pipeline runs end-to-end
- results are queryable

---

## 5. Phase Sync Issues

### Problem
- Phase 1, 2, 3 are not fully validated together
- Some scripts missing / not runnable

### Fix
- Ensure:
- Phase 1 contracts still work
- Phase 2 ingestion works with Phase 3 pipeline
- Add one integration test:
```

ingestion → detection → storage → query

```

---

# 🧠 Analytics Tasks (Abhigyan — You)

This is what YOU need to fix and own.

## Phase 3 Completion Work

- [ ] Fix detection → storage data compatibility
- [ ] Fix aggregation pipeline (node → cluster)
- [ ] Clean anomaly explanation logic
- [ ] Ensure sliding windows behave deterministically
- [ ] Add proper threshold usage in scoring

## Verification

- [ ] Fix `verify_phase3.py` (no false success)
- [ ] Fix CSV replay pipeline
- [ ] Ensure real-data validation works

## Integration

- [ ] Ensure output works with storage layer
- [ ] Ensure output works with future APIs

---

# ⚙️ Backend Tasks (Saivats)

## Core Fixes

- [ ] Fix storage interface consistency
- [ ] Implement proper query logic
- [ ] Ensure ingestion → analytics pipeline compatibility

## Phase 4 Preparation

- [ ] Build API endpoints:
- `/metrics`
- `/anomalies`
- `/health`

## Missing Features

- [ ] Implement tenant enforcement at API level
- [ ] Add persistent storage (not just memory)

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

👉 Take raw anomaly data and make it **understandable**

---

# 🧊 Phase 5 Work (Later)

## Storage

- [ ] Implement hot storage (recent data)
- [ ] Implement cold storage (archival)
- [ ] Add retention policy

## System

- [ ] Add Docker (deployment)
- [ ] Add basic auth (optional)
- [ ] Optimize performance

---

# ❌ What We DO NOT Have (Important)

- No hot/cold storage
- No AI deciding storage tier
- No dashboard system
- No API layer
- No production deployment

---

# 🎯 Final Goal

We want to reach:

```

Ingestion → Detection → Storage → API → Dashboard → Hot/Cold Storage

```

Right now we are here:

```

Ingestion → Detection (partial)

```

---

# 🧭 How to Move Forward

1. Fix Phase 3 completely (no shortcuts)
2. Then move to Phase 4 (API + UI)
3. Then Phase 5 (storage + deployment)

---

# ⚠️ Rule

No skipping phases.

If Phase 3 is broken, Phase 4 will collapse.
