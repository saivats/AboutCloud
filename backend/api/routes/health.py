import structlog
from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from backend.core.database import get_db_session
from backend.core.models import Tenant, AggregatedScoreRecord, Cluster, AnomalyResultRecord
from backend.core.schemas import (
    HealthResponse, ClusterHealthInfo, NodeHealthInfo, ClusterInsight,
)
from backend.api.deps import get_current_tenant

router = APIRouter()
logger = structlog.get_logger("aboutcloud.health")


@router.get("", response_model=HealthResponse)
async def get_health(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
):
    tenant_id = str(tenant.id)

    clusters_result = await db.execute(
        select(Cluster).where(Cluster.tenant_id == tenant_id)
    )
    clusters = clusters_result.scalars().all()

    cluster_health_list = []
    all_insights = []

    for cluster in clusters:
        cluster_id = str(cluster.id)

        cluster_score_result = await db.execute(
            select(AggregatedScoreRecord)
            .where(
                AggregatedScoreRecord.tenant_id == tenant_id,
                AggregatedScoreRecord.cluster_id == cluster_id,
                AggregatedScoreRecord.node_id.is_(None),
            )
            .order_by(desc(AggregatedScoreRecord.computed_at))
            .limit(1)
        )
        cluster_score = cluster_score_result.scalar_one_or_none()
        health_score = cluster_score.aggregate_score if cluster_score else 0.0
        last_updated = cluster_score.computed_at if cluster_score else None

        node_scores_result = await db.execute(
            select(AggregatedScoreRecord)
            .where(
                AggregatedScoreRecord.tenant_id == tenant_id,
                AggregatedScoreRecord.cluster_id == cluster_id,
                AggregatedScoreRecord.node_id.isnot(None),
            )
            .order_by(desc(AggregatedScoreRecord.aggregate_score))
            .limit(10)
        )
        node_score_rows = node_scores_result.scalars().all()

        top_nodes = [
            NodeHealthInfo(
                node_id=str(ns.node_id),
                score=ns.aggregate_score,
                rank=idx + 1,
            )
            for idx, ns in enumerate(node_score_rows)
        ]

        cluster_health_list.append(
            ClusterHealthInfo(
                cluster_id=cluster_id,
                health_score=health_score,
                top_anomalous_nodes=top_nodes,
                last_updated=last_updated,
            )
        )

        insight = await _generate_cluster_insight(db, tenant_id, cluster_id, health_score)
        if insight:
            all_insights.append(insight)

    return HealthResponse(
        tenant_id=tenant_id,
        clusters=cluster_health_list,
        insights=all_insights,
    )


async def _generate_cluster_insight(
    db: AsyncSession,
    tenant_id: str,
    cluster_id: str,
    health_score: float,
) -> Optional[ClusterInsight]:
    recent_anomalies_result = await db.execute(
        select(AnomalyResultRecord)
        .where(
            AnomalyResultRecord.tenant_id == tenant_id,
            AnomalyResultRecord.cluster_id == cluster_id,
            AnomalyResultRecord.anomaly_label != "normal",
            AnomalyResultRecord.anomaly_score >= 0.3,
        )
        .order_by(desc(AnomalyResultRecord.detected_at))
        .limit(50)
    )
    recent_anomalies = recent_anomalies_result.scalars().all()

    if not recent_anomalies:
        return ClusterInsight(
            cluster_id=cluster_id,
            summary="No significant anomalies detected. All metrics operating within normal parameters.",
            severity="low",
        )

    label_counts = Counter(a.anomaly_label for a in recent_anomalies)
    dominant_type = label_counts.most_common(1)[0][0] if label_counts else None

    affected_metrics = list(set(a.metric_name for a in recent_anomalies))
    top_score = max(a.anomaly_score for a in recent_anomalies)

    severity = "critical" if health_score > 0.7 else "warning" if health_score > 0.4 else "low"

    type_descriptions = {
        "spike": "sudden deviations from baseline values",
        "trend": "sustained directional changes suggesting resource pressure",
        "seasonal": "deviations from expected cyclic behavior",
    }
    type_desc = type_descriptions.get(dominant_type, "anomalous patterns")

    summary = (
        f"{len(recent_anomalies)} anomalies detected across {len(affected_metrics)} metric(s). "
        f"Primary pattern: {type_desc}. "
        f"Peak severity: {int(top_score * 100)}%."
    )

    return ClusterInsight(
        cluster_id=cluster_id,
        summary=summary,
        dominant_anomaly_type=dominant_type,
        affected_metrics=affected_metrics[:5],
        severity=severity,
    )
