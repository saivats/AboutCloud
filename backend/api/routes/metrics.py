import structlog
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, func, text

from backend.core.database import get_db_session
from backend.core.models import Tenant, MetricHot, Cluster, Node
from backend.core.schemas import MetricIngestRequest, IngestResponse, MetricQueryResponse, MetricPoint
from backend.api.deps import get_current_tenant, enforce_tenant_isolation

router = APIRouter()
logger = structlog.get_logger("aboutcloud.metrics")


async def ensure_cluster_and_node(
    db: AsyncSession,
    tenant_id: str,
    cluster_id: str,
    node_id: str,
):
    cluster_result = await db.execute(
        select(Cluster).where(Cluster.id == cluster_id, Cluster.tenant_id == tenant_id)
    )
    cluster = cluster_result.scalar_one_or_none()
    if cluster is None:
        cluster = Cluster(id=cluster_id, tenant_id=tenant_id, name=f"cluster-{cluster_id[:8]}")
        db.add(cluster)

    node_result = await db.execute(
        select(Node).where(Node.id == node_id, Node.tenant_id == tenant_id)
    )
    node = node_result.scalar_one_or_none()
    if node is None:
        node = Node(id=node_id, cluster_id=cluster_id, tenant_id=tenant_id, hostname=f"node-{node_id[:8]}")
        db.add(node)

    await db.flush()


@router.post("", response_model=IngestResponse)
async def ingest_metrics(
    body: MetricIngestRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
):
    enforce_tenant_isolation(tenant, body.tenant_id)

    ingested = 0
    failed = 0
    validation_errors = []

    try:
        await ensure_cluster_and_node(db, body.tenant_id, body.cluster_id, body.node_id)
    except Exception as exc:
        logger.warning("cluster_node_ensure_failed", error=str(exc))

    for dp in body.datapoints:
        try:
            metric = MetricHot(
                time=dp.timestamp,
                tenant_id=body.tenant_id,
                cluster_id=body.cluster_id,
                node_id=body.node_id,
                metric_name=body.metric_name,
                value=dp.value,
                extra_metadata=body.metadata,
            )
            db.add(metric)
            ingested += 1
        except Exception as exc:
            failed += 1
            validation_errors.append(f"Point at {dp.timestamp}: {exc}")

    try:
        await db.flush()
    except Exception as exc:
        logger.error("batch_flush_failed", error=str(exc))
        await db.rollback()
        ingested_via_individual = 0
        for dp in body.datapoints:
            try:
                await db.execute(
                    text(
                        "INSERT INTO metrics_hot (time, tenant_id, cluster_id, node_id, metric_name, value, metadata) "
                        "VALUES (:time, :tenant_id, :cluster_id, :node_id, :metric_name, :value, :metadata) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {
                        "time": dp.timestamp,
                        "tenant_id": body.tenant_id,
                        "cluster_id": body.cluster_id,
                        "node_id": body.node_id,
                        "metric_name": body.metric_name,
                        "value": dp.value,
                        "metadata": "{}",
                    },
                )
                ingested_via_individual += 1
            except Exception:
                failed += 1
        ingested = ingested_via_individual

    logger.info(
        "metrics_ingested",
        tenant_id=body.tenant_id,
        metric=body.metric_name,
        ingested=ingested,
        failed=failed,
    )

    return IngestResponse(
        ingested=ingested,
        failed=failed,
        validation_errors=validation_errors,
    )


@router.get("", response_model=MetricQueryResponse)
async def query_metrics(
    tenant: Tenant = Depends(get_current_tenant),
    cluster_id: str = Query(...),
    node_id: str = Query(...),
    metric_name: str = Query(...),
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db_session),
):
    tenant_id = str(tenant.id)

    count_result = await db.execute(
        select(func.count()).select_from(MetricHot).where(
            MetricHot.tenant_id == tenant_id,
            MetricHot.cluster_id == cluster_id,
            MetricHot.node_id == node_id,
            MetricHot.metric_name == metric_name,
            MetricHot.time >= start_time,
            MetricHot.time <= end_time,
        )
    )
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        select(MetricHot).where(
            MetricHot.tenant_id == tenant_id,
            MetricHot.cluster_id == cluster_id,
            MetricHot.node_id == node_id,
            MetricHot.metric_name == metric_name,
            MetricHot.time >= start_time,
            MetricHot.time <= end_time,
        ).order_by(MetricHot.time).offset(offset).limit(page_size)
    )
    rows = result.scalars().all()

    data = [MetricPoint(timestamp=r.time, value=r.value) for r in rows]

    return MetricQueryResponse(
        data=data,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + page_size) < total,
    )
