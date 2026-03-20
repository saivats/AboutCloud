"""
FastAPI Application - Core API Endpoints

Endpoints:
  POST /metrics   — ingest metric batch
  GET  /metrics   — query stored metrics
  GET  /anomalies — query anomaly results
  GET  /health    — cluster/tenant health summary
"""

import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.api.auth import get_auth_manager, AuthenticationError, AuthorizationError, setup_demo_keys
from backend.api.schemas import (
    MetricIngestRequest,
    MetricSeriesResponse,
    AnomalyQueryResponse,
    AnomalyResultResponse,
    HealthResponse,
    HealthClusterScore,
    HealthNodeScore,
    IngestResponse,
    ErrorResponse,
)
from backend.analytics.types import MetricSeries, AggregatedAnomalyScore
from backend.storage.interface import get_storage, configure_storage
from backend.storage.sqlite_storage import SQLiteStorage
from backend.monitoring.logging_config import get_logger, log_request

# ---- App Setup ----

app = FastAPI(
    title="AboutCloud API",
    description="Cloud infrastructure anomaly detection platform",
    version="0.3.0",
)

logger = get_logger("api")

# Initialize storage and auth on startup
@app.on_event("startup")
async def startup():
    """Initialize storage and demo keys on startup."""
    storage = SQLiteStorage("aboutcloud.db")
    configure_storage(storage)
    demo_keys = setup_demo_keys()
    logger.info("API started", extra={"demo_keys_created": len(demo_keys)})


# ---- Auth Helper ----

def _authenticate(x_api_key: Optional[str]) -> str:
    """
    Authenticate request using API key header.

    Args:
        x_api_key: Value of X-API-Key header

    Returns:
        tenant_id for the authenticated key

    Raises:
        HTTPException 401 if authentication fails
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    try:
        tenant_id = get_auth_manager().authenticate(x_api_key)
        return tenant_id
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))


def _authorize(authenticated_tenant: str, requested_tenant: str) -> None:
    """
    Check tenant isolation.

    Raises:
        HTTPException 403 if cross-tenant access
    """
    try:
        get_auth_manager().authorize(authenticated_tenant, requested_tenant)
    except AuthorizationError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ---- Endpoints ----

@app.post("/metrics", response_model=IngestResponse)
async def ingest_metrics(
    request: MetricIngestRequest,
    x_api_key: Optional[str] = Header(None),
):
    """
    Ingest a batch of metric data points.

    Requires authentication. Enforces tenant isolation.
    """
    tenant_id = _authenticate(x_api_key)
    _authorize(tenant_id, request.tenant_id)

    log_request(logger, "POST /metrics", tenant_id, {
        "metric_name": request.metric_name,
        "points": len(request.data_points),
    })

    try:
        storage = get_storage()

        timestamps = [dp.timestamp for dp in request.data_points]
        values = [dp.value for dp in request.data_points]

        series = MetricSeries(
            tenant_id=request.tenant_id,
            cluster_id=request.cluster_id,
            node_id=request.node_id,
            metric_name=request.metric_name,
            timestamps=timestamps,
            values=values,
            metadata=request.metadata,
        )

        storage.store_metric(series)

        return IngestResponse(
            status="success",
            tenant_id=request.tenant_id,
            metric_name=request.metric_name,
            points_stored=len(values),
            message=f"Stored {len(values)} data points for {request.metric_name}",
        )

    except Exception as e:
        logger.error(f"Ingest failed: {e}", extra={"tenant_id": tenant_id})
        raise HTTPException(status_code=500, detail=f"Ingest failed: {e}")


@app.get("/metrics", response_model=MetricSeriesResponse)
async def query_metrics(
    tenant_id: str = Query(...),
    cluster_id: str = Query(...),
    node_id: str = Query(...),
    metric_name: str = Query(...),
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    x_api_key: Optional[str] = Header(None),
):
    """
    Query stored metric time series.

    Returns data points within the specified time range.
    """
    auth_tenant = _authenticate(x_api_key)
    _authorize(auth_tenant, tenant_id)

    log_request(logger, "GET /metrics", tenant_id, {
        "metric_name": metric_name,
    })

    try:
        storage = get_storage()
        series = storage.get_metric_series(
            tenant_id=tenant_id,
            cluster_id=cluster_id,
            node_id=node_id,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
        )

        return MetricSeriesResponse(
            tenant_id=series.tenant_id,
            cluster_id=series.cluster_id,
            node_id=series.node_id,
            metric_name=series.metric_name,
            num_points=len(series.values),
            timestamps=series.timestamps,
            values=series.values,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Query failed: {e}", extra={"tenant_id": tenant_id})
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")


@app.get("/anomalies", response_model=AnomalyQueryResponse)
async def query_anomalies(
    tenant_id: str = Query(...),
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    cluster_id: Optional[str] = Query(None),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    x_api_key: Optional[str] = Header(None),
):
    """
    Query anomaly detection results.

    Returns anomalies matching the time range and score threshold.
    """
    auth_tenant = _authenticate(x_api_key)
    _authorize(auth_tenant, tenant_id)

    log_request(logger, "GET /anomalies", tenant_id, {
        "cluster_id": cluster_id,
        "min_score": min_score,
    })

    try:
        storage = get_storage()
        results = storage.query_anomalies(
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time,
            cluster_id=cluster_id,
            min_score=min_score,
        )

        response_results = [
            AnomalyResultResponse(
                tenant_id=r["tenant_id"],
                cluster_id=r["cluster_id"],
                node_id=r["node_id"],
                metric_name=r["metric_name"],
                anomaly_score=r["anomaly_score"],
                anomaly_label=r["anomaly_label"],
                window_start=r["window_start"],
                window_end=r["window_end"],
                explanation=r.get("explanation"),
            )
            for r in results
        ]

        return AnomalyQueryResponse(
            total=len(response_results),
            results=response_results,
        )

    except Exception as e:
        logger.error(f"Anomaly query failed: {e}", extra={"tenant_id": tenant_id})
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")


@app.get("/health", response_model=HealthResponse)
async def get_health(
    tenant_id: str = Query(...),
    x_api_key: Optional[str] = Header(None),
):
    """
    Get cluster/tenant health summary.

    Returns aggregated anomaly scores for the tenant's clusters and nodes.
    """
    auth_tenant = _authenticate(x_api_key)
    _authorize(auth_tenant, tenant_id)

    log_request(logger, "GET /health", tenant_id, {})

    try:
        storage = get_storage()

        # Try to get aggregated scores
        clusters_data = {}
        if hasattr(storage, "get_aggregated_scores"):
            scores = storage.get_aggregated_scores(tenant_id)
            for score in scores:
                cid = score.cluster_id or "default"
                if cid not in clusters_data:
                    clusters_data[cid] = {"cluster_score": None, "nodes": []}

                if score.node_id:
                    clusters_data[cid]["nodes"].append(
                        HealthNodeScore(
                            node_id=score.node_id,
                            score=score.aggregate_score,
                            num_anomalies=score.num_anomalies_detected,
                        )
                    )
                else:
                    clusters_data[cid]["cluster_score"] = score.aggregate_score

        # Build response
        cluster_responses = []
        overall_scores = []

        for cid, data in clusters_data.items():
            c_score = data["cluster_score"] or 0.0
            overall_scores.append(c_score)
            cluster_responses.append(
                HealthClusterScore(
                    cluster_id=cid,
                    score=c_score,
                    num_nodes=len(data["nodes"]),
                    node_scores=data["nodes"],
                )
            )

        overall = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0

        return HealthResponse(
            tenant_id=tenant_id,
            overall_score=overall,
            clusters=cluster_responses,
            timestamp=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Health query failed: {e}", extra={"tenant_id": tenant_id})
        raise HTTPException(status_code=500, detail=f"Health query failed: {e}")


# ---- Run ----

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
