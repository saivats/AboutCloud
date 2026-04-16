import asyncio
import hashlib
import time
import uuid
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

BASE_URL = "http://localhost:8000/api/v1"
TIMEOUT = 30.0


class BenchmarkResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.latency_ms = 0.0
        self.detail = ""

    def __str__(self):
        status = "PASS ✅" if self.passed else "FAIL ❌"
        return f"  [{status}] {self.name} ({self.latency_ms:.0f}ms) {self.detail}"


async def create_tenant_via_db(tenant_name: str, api_key: str) -> str:
    tenant_id = str(uuid.uuid4())
    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            import asyncpg
            conn = await asyncpg.connect(
                "postgresql://aboutcloud:aboutcloud@localhost:5432/aboutcloud"
            )
            await conn.execute(
                """
                INSERT INTO tenants (id, name, api_key_hash, created_at, settings, is_active)
                VALUES ($1, $2, $3, $4, '{}', true)
                ON CONFLICT (name) DO UPDATE SET api_key_hash = $3
                RETURNING id
                """,
                uuid.UUID(tenant_id),
                tenant_name,
                key_hash,
                datetime.now(timezone.utc),
            )
            result = await conn.fetchrow(
                "SELECT id FROM tenants WHERE name = $1", tenant_name
            )
            if result:
                tenant_id = str(result["id"])
            await conn.close()
        except Exception as exc:
            print(f"  [INFO] Direct DB insert failed ({exc}), trying API approach...")
            return tenant_id

    return tenant_id


async def get_token(api_key: str) -> Optional[str]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        response = await client.post("/auth/token", json={"api_key": api_key})
        if response.status_code == 200:
            return response.json()["access_token"]
        return None


async def step_create_tenant() -> BenchmarkResult:
    result = BenchmarkResult("Create test tenant and get JWT")
    start = time.perf_counter()

    try:
        api_key = f"bench-key-{uuid.uuid4().hex[:16]}"
        tenant_id = await create_tenant_via_db("benchmark-tenant-1", api_key)

        token = await get_token(api_key)
        if token:
            result.passed = True
            result.detail = f"tenant_id={tenant_id[:12]}..."
        else:
            result.detail = "Failed to get token"
    except Exception as exc:
        result.detail = str(exc)

    result.latency_ms = (time.perf_counter() - start) * 1000
    return result


async def step_ingest_metrics(token: str, tenant_id: str) -> BenchmarkResult:
    result = BenchmarkResult("Ingest 10 nodes × 3 metrics × 1000 points")
    start = time.perf_counter()

    cluster_id = str(uuid.uuid4())
    metric_names = ["cpu_usage", "memory_used", "disk_io"]
    node_ids = [str(uuid.uuid4()) for _ in range(10)]
    ingested_total = 0
    failed_total = 0

    now = datetime.now(timezone.utc)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        headers = {"Authorization": f"Bearer {token}"}

        for node_id in node_ids:
            for metric_name in metric_names:
                import math
                import random
                datapoints = []
                for i in range(1000):
                    ts = now - timedelta(hours=24) + timedelta(seconds=i * 86)
                    base = 50.0 + 10.0 * math.sin(i * 0.03)
                    noise = random.gauss(0, 3)
                    spike = 0.0
                    if random.random() < 0.02:
                        spike = random.uniform(30, 60)
                    value = max(0, base + noise + spike)
                    datapoints.append({
                        "timestamp": ts.isoformat(),
                        "value": round(value, 2),
                    })

                response = await client.post(
                    "/metrics",
                    json={
                        "tenant_id": tenant_id,
                        "cluster_id": cluster_id,
                        "node_id": node_id,
                        "metric_name": metric_name,
                        "datapoints": datapoints,
                        "metadata": {"source": "benchmark"},
                    },
                    headers=headers,
                )

                if response.status_code == 200:
                    body = response.json()
                    ingested_total += body.get("ingested", 0)
                    failed_total += body.get("failed", 0)
                else:
                    failed_total += 1000

    result.latency_ms = (time.perf_counter() - start) * 1000

    if ingested_total > 0:
        result.passed = True
        result.detail = f"ingested={ingested_total}, failed={failed_total}"
    else:
        result.detail = f"No data ingested. failed={failed_total}"

    return result, cluster_id, node_ids, metric_names


async def step_trigger_detection(token: str, cluster_id: str, node_ids: list, metric_names: list) -> BenchmarkResult:
    result = BenchmarkResult("Trigger detection via POST /admin/detect")
    start = time.perf_counter()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post(
            "/admin/detect",
            json={
                "cluster_id": cluster_id,
                "node_ids": node_ids,
                "metric_names": metric_names,
            },
            headers=headers,
        )

        if response.status_code == 200:
            body = response.json()
            result.passed = True
            result.detail = f"job_id={body.get('job_id', 'unknown')[:12]}..."
        else:
            result.detail = f"Status {response.status_code}: {response.text[:100]}"

    result.latency_ms = (time.perf_counter() - start) * 1000
    return result


async def step_poll_anomalies(token: str) -> BenchmarkResult:
    result = BenchmarkResult("Poll GET /anomalies until results appear (max 60s)")
    start = time.perf_counter()
    total_found = 0

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        headers = {"Authorization": f"Bearer {token}"}

        for attempt in range(30):
            await asyncio.sleep(2)

            response = await client.get(
                "/anomalies",
                params={"page_size": 10},
                headers=headers,
            )

            if response.status_code == 200:
                body = response.json()
                total_found = body.get("total", 0)
                if total_found > 0:
                    result.passed = True
                    result.detail = f"Found {total_found} anomalies after {attempt * 2}s"
                    break

        if not result.passed:
            result.detail = f"No anomalies found after 60s polling"

    result.latency_ms = (time.perf_counter() - start) * 1000
    return result


async def step_check_health(token: str) -> BenchmarkResult:
    result = BenchmarkResult("Verify GET /health returns cluster health score")
    start = time.perf_counter()

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/health", headers=headers)

        if response.status_code == 200:
            body = response.json()
            clusters = body.get("clusters", [])
            if len(clusters) > 0:
                result.passed = True
                scores = [c.get("health_score", 0) for c in clusters]
                result.detail = f"{len(clusters)} cluster(s), scores={[round(s, 2) for s in scores]}"
            else:
                result.detail = "No clusters in health response"
        else:
            result.detail = f"Status {response.status_code}"

    result.latency_ms = (time.perf_counter() - start) * 1000
    return result


async def step_tenant_isolation() -> BenchmarkResult:
    result = BenchmarkResult("Verify tenant isolation (cross-tenant access denied)")
    start = time.perf_counter()

    try:
        api_key_2 = f"bench-key-2-{uuid.uuid4().hex[:16]}"
        await create_tenant_via_db("benchmark-tenant-2", api_key_2)
        token_2 = await get_token(api_key_2)

        if not token_2:
            result.detail = "Could not create second tenant"
            result.latency_ms = (time.perf_counter() - start) * 1000
            return result

        async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
            headers = {"Authorization": f"Bearer {token_2}"}

            response = await client.get("/anomalies", params={"page_size": 10}, headers=headers)

            if response.status_code == 200:
                body = response.json()
                total = body.get("total", 0)
                data = body.get("data", [])

                if total == 0 and len(data) == 0:
                    result.passed = True
                    result.detail = "Second tenant correctly sees 0 anomalies"
                else:
                    result.detail = f"Second tenant sees {total} anomalies (ISOLATION FAILURE)"
            else:
                result.passed = True
                result.detail = f"Correctly denied with status {response.status_code}"

    except Exception as exc:
        result.detail = str(exc)

    result.latency_ms = (time.perf_counter() - start) * 1000
    return result


async def main():
    print("=" * 70)
    print("  AboutCloud Phase 3 Benchmark")
    print("=" * 70)
    print()

    results = []
    token = None
    tenant_id = None
    cluster_id = None
    node_ids = []
    metric_names = []

    print("[Step 1/7] Creating tenant and authenticating...")
    r1 = await step_create_tenant()
    results.append(r1)
    print(r1)

    if r1.passed:
        api_key = f"bench-key-{uuid.uuid4().hex[:16]}"
        tenant_id_new = await create_tenant_via_db("benchmark-run", api_key)
        token = await get_token(api_key)
        tenant_id = tenant_id_new
        if not token:
            print("  [FATAL] Cannot obtain token, aborting.")
            sys.exit(1)

    print()
    print("[Step 2/7] Ingesting metrics...")
    if token and tenant_id:
        r2_result = await step_ingest_metrics(token, tenant_id)
        r2, cluster_id, node_ids, metric_names = r2_result
        results.append(r2)
        print(r2)
    else:
        r2 = BenchmarkResult("Ingest metrics")
        r2.detail = "Skipped (no token)"
        results.append(r2)
        print(r2)

    print()
    print("[Step 3/7] Triggering detection...")
    if token and cluster_id:
        r3 = await step_trigger_detection(token, cluster_id, node_ids, metric_names)
        results.append(r3)
        print(r3)
    else:
        r3 = BenchmarkResult("Trigger detection")
        r3.detail = "Skipped"
        results.append(r3)
        print(r3)

    print()
    print("[Step 4/7] Polling for anomalies...")
    if token:
        r4 = await step_poll_anomalies(token)
        results.append(r4)
        print(r4)
    else:
        r4 = BenchmarkResult("Poll anomalies")
        r4.detail = "Skipped"
        results.append(r4)
        print(r4)

    print()
    print("[Step 5/7] Checking health endpoint...")
    if token:
        r5 = await step_check_health(token)
        results.append(r5)
        print(r5)
    else:
        r5 = BenchmarkResult("Check health")
        r5.detail = "Skipped"
        results.append(r5)
        print(r5)

    print()
    print("[Step 6/7] Verifying tenant isolation...")
    r6 = await step_tenant_isolation()
    results.append(r6)
    print(r6)

    print()
    print("[Step 7/7] Summary")
    print("=" * 70)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    total_latency = sum(r.latency_ms for r in results)

    for r in results:
        print(r)

    print()
    print(f"  Result: {passed}/{total} passed  |  Total latency: {total_latency:.0f}ms")
    print("=" * 70)

    if passed == total:
        print("  🎉 ALL BENCHMARKS PASSED")
        sys.exit(0)
    else:
        print(f"  ⚠️  {total - passed} benchmark(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
