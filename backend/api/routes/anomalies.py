import structlog
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.core.database import get_db_session
from backend.core.models import Tenant, AnomalyResultRecord
from backend.core.schemas import AnomalyQueryResponse, AnomalyResultSchema, AnomalyInsight
from backend.api.deps import get_current_tenant

router = APIRouter()
logger = structlog.get_logger("aboutcloud.anomalies")


def _build_insight(row: AnomalyResultRecord) -> Optional[AnomalyInsight]:
    if row.anomaly_label == "normal":
        return None

    score = row.anomaly_score or 0.0
    label = row.anomaly_label or "unknown"
    magnitude = row.magnitude
    explanation = row.explanation or ""

    baseline_val = None
    observed_val = None
    deviation_factor = None

    if magnitude is not None and magnitude > 0:
        deviation_factor = round(magnitude * 5.0, 2)

    pattern_map = {
        "spike": "sudden, temporary deviation from baseline",
        "trend": "sustained directional change indicating resource pressure",
        "seasonal": "deviation from expected cyclic behavior pattern",
    }
    pattern_desc = pattern_map.get(label, "anomalous behavior detected")

    severity_word = "critical" if score > 0.7 else "warning" if score > 0.4 else "low"

    if deviation_factor and deviation_factor > 1.0:
        summary = (
            f"This {label} is {deviation_factor:.1f}x above baseline"
            f" and deviates from the expected pattern."
            f" Confidence: {int((row.confidence or score) * 100)}%."
        )
    else:
        summary = (
            f"{label.capitalize()} detected with {int(score * 100)}% anomaly score."
            f" {pattern_desc.capitalize()}."
        )

    recommendation_map = {
        "spike": "Investigate recent deployments or traffic surges that may have caused the spike.",
        "trend": "Monitor resource utilization trends; consider scaling or capacity planning.",
        "seasonal": "Verify if this deviates from expected business-hour patterns.",
    }

    return AnomalyInsight(
        summary=summary,
        baseline_value=baseline_val,
        observed_value=observed_val,
        deviation_factor=deviation_factor,
        pattern_description=pattern_desc,
        recommendation=recommendation_map.get(label, "Review the metric for further analysis."),
    )


@router.get("", response_model=AnomalyQueryResponse)
async def query_anomalies(
    tenant: Tenant = Depends(get_current_tenant),
    cluster_id: Optional[str] = Query(None),
    node_id: Optional[str] = Query(None),
    metric_name: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    min_score: Optional[float] = Query(None, ge=0.0, le=1.0),
    label: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db_session),
):
    tenant_id = str(tenant.id)

    base_query = select(AnomalyResultRecord).where(
        AnomalyResultRecord.tenant_id == tenant_id
    )
    count_query = select(func.count()).select_from(AnomalyResultRecord).where(
        AnomalyResultRecord.tenant_id == tenant_id
    )

    if cluster_id:
        base_query = base_query.where(AnomalyResultRecord.cluster_id == cluster_id)
        count_query = count_query.where(AnomalyResultRecord.cluster_id == cluster_id)

    if node_id:
        base_query = base_query.where(AnomalyResultRecord.node_id == node_id)
        count_query = count_query.where(AnomalyResultRecord.node_id == node_id)

    if metric_name:
        base_query = base_query.where(AnomalyResultRecord.metric_name == metric_name)
        count_query = count_query.where(AnomalyResultRecord.metric_name == metric_name)

    if start_time:
        base_query = base_query.where(AnomalyResultRecord.window_start >= start_time)
        count_query = count_query.where(AnomalyResultRecord.window_start >= start_time)

    if end_time:
        base_query = base_query.where(AnomalyResultRecord.window_end <= end_time)
        count_query = count_query.where(AnomalyResultRecord.window_end <= end_time)

    if min_score is not None:
        base_query = base_query.where(AnomalyResultRecord.anomaly_score >= min_score)
        count_query = count_query.where(AnomalyResultRecord.anomaly_score >= min_score)

    if label:
        base_query = base_query.where(AnomalyResultRecord.anomaly_label == label)
        count_query = count_query.where(AnomalyResultRecord.anomaly_label == label)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        base_query.order_by(AnomalyResultRecord.detected_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = result.scalars().all()

    data = [
        AnomalyResultSchema(
            id=str(r.id),
            tenant_id=str(r.tenant_id),
            cluster_id=str(r.cluster_id),
            node_id=str(r.node_id),
            metric_name=r.metric_name,
            window_start=r.window_start,
            window_end=r.window_end,
            anomaly_score=r.anomaly_score,
            anomaly_label=r.anomaly_label,
            confidence=getattr(r, "confidence", None),
            magnitude=r.magnitude,
            explanation=r.explanation,
            insight=_build_insight(r),
            detected_at=r.detected_at,
        )
        for r in rows
    ]

    return AnomalyQueryResponse(
        data=data,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + page_size) < total,
    )
