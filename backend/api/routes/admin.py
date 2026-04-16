import uuid
import asyncio
import structlog
from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db_session, get_session_factory
from backend.core.models import Tenant, MetricHot, AnomalyResultRecord, AggregatedScoreRecord, Node
from backend.core.schemas import DetectRequest, DetectResponse
from backend.api.deps import get_current_tenant
from backend.api.websocket_manager import ws_manager

router = APIRouter()
logger = structlog.get_logger("aboutcloud.admin")


def _compute_confidence(z_score: float, window_std: float, baseline_std: float) -> float:
    z_conf = min(1.0, z_score / 4.0)
    if baseline_std > 0:
        var_ratio = window_std / baseline_std
        variance_conf = min(1.0, abs(var_ratio - 1.0))
    else:
        variance_conf = 0.5
    return round(min(1.0, (z_conf * 0.7 + variance_conf * 0.3)), 4)


async def run_detection_job(
    job_id: str,
    tenant_id: str,
    cluster_id: str,
    node_ids: List[str],
    metric_names: List[str],
    start_time: datetime,
    end_time: datetime,
):
    import numpy as np

    factory = get_session_factory()
    async with factory() as db:
        try:
            logger.info("detection_job_started", job_id=job_id, tenant_id=tenant_id)

            if not node_ids:
                node_result = await db.execute(
                    select(Node.id).where(
                        Node.tenant_id == tenant_id,
                        Node.cluster_id == cluster_id,
                    )
                )
                node_ids = [str(n) for n in node_result.scalars().all()]

            if not metric_names:
                metric_result = await db.execute(
                    select(MetricHot.metric_name).where(
                        MetricHot.tenant_id == tenant_id,
                        MetricHot.cluster_id == cluster_id,
                    ).distinct()
                )
                metric_names = list(metric_result.scalars().all())

            node_scores = []

            for node_id in node_ids:
                node_anomaly_scores = []

                for metric_name in metric_names:
                    metrics_result = await db.execute(
                        select(MetricHot).where(
                            MetricHot.tenant_id == tenant_id,
                            MetricHot.cluster_id == cluster_id,
                            MetricHot.node_id == node_id,
                            MetricHot.metric_name == metric_name,
                            MetricHot.time >= start_time,
                            MetricHot.time <= end_time,
                        ).order_by(MetricHot.time)
                    )
                    data_points = metrics_result.scalars().all()

                    if len(data_points) < 10:
                        continue

                    values = np.array([dp.value for dp in data_points])
                    timestamps = [dp.time for dp in data_points]

                    mean_val = np.mean(values)
                    std_val = np.std(values)
                    if std_val == 0:
                        std_val = 1.0

                    window_size = min(100, len(values) // 2)
                    stride = max(1, window_size // 2)

                    for i in range(0, len(values) - window_size + 1, stride):
                        window = values[i:i + window_size]
                        window_mean = np.mean(window)
                        window_std = np.std(window)
                        window_max = np.max(window)

                        z_score = abs(window_mean - mean_val) / std_val
                        raw_score = 1.0 / (1.0 + np.exp(-z_score + 2.5))
                        anomaly_score = float(np.clip(raw_score, 0.0, 1.0))

                        confidence = _compute_confidence(z_score, float(window_std), float(std_val))

                        max_z = abs(window_max - mean_val) / std_val

                        if anomaly_score > 0.8 and max_z > 2.0:
                            anomaly_label = "spike"
                        elif z_score > 1.5:
                            diffs = np.diff(window)
                            if np.sum(diffs > 0) > len(diffs) * 0.7 or np.sum(diffs < 0) > len(diffs) * 0.7:
                                anomaly_label = "trend"
                            else:
                                anomaly_label = "seasonal"
                        elif anomaly_score > 0.5:
                            anomaly_label = "seasonal"
                        else:
                            anomaly_label = "normal"

                        magnitude = float(np.clip(z_score / 5.0, 0.0, 1.0))

                        deviation_factor = round(float(max_z), 1) if max_z > 1.0 else None

                        if anomaly_label == "spike":
                            explanation = (
                                f"Spike detected: peak {window_max:.1f} "
                                f"({max_z:.1f}σ from baseline {mean_val:.1f}). "
                                f"This spike is {max_z:.1f}x above baseline and deviates from the expected pattern."
                            )
                        elif anomaly_label == "trend":
                            direction = "increasing" if np.mean(np.diff(window)) > 0 else "decreasing"
                            explanation = (
                                f"Trend detected: {direction} pattern, window mean {window_mean:.1f} "
                                f"vs baseline {mean_val:.1f}. Sustained {direction} pressure detected."
                            )
                        elif anomaly_label == "seasonal":
                            explanation = (
                                f"Seasonal deviation: window std {window_std:.2f} vs baseline std {std_val:.2f}. "
                                f"Pattern deviates from expected cyclic behavior."
                            )
                        else:
                            explanation = f"Normal: {metric_name} within expected range"

                        anomaly_record = AnomalyResultRecord(
                            tenant_id=tenant_id,
                            cluster_id=cluster_id,
                            node_id=node_id,
                            metric_name=metric_name,
                            window_start=timestamps[i],
                            window_end=timestamps[min(i + window_size - 1, len(timestamps) - 1)],
                            anomaly_score=anomaly_score,
                            anomaly_label=anomaly_label,
                            confidence=confidence,
                            magnitude=magnitude,
                            explanation=explanation,
                            detected_at=datetime.now(timezone.utc),
                        )
                        db.add(anomaly_record)
                        node_anomaly_scores.append(anomaly_score)

                        if anomaly_label != "normal" and anomaly_score > 0.4:
                            try:
                                await ws_manager.broadcast_anomaly({
                                    "tenant_id": tenant_id,
                                    "cluster_id": cluster_id,
                                    "node_id": node_id,
                                    "metric_name": metric_name,
                                    "anomaly_score": anomaly_score,
                                    "anomaly_label": anomaly_label,
                                    "confidence": confidence,
                                    "explanation": explanation,
                                })
                            except Exception:
                                pass

                if node_anomaly_scores:
                    node_agg_score = max(node_anomaly_scores)
                    num_anomalies = sum(1 for s in node_anomaly_scores if s > 0.5)
                    node_agg = AggregatedScoreRecord(
                        tenant_id=tenant_id,
                        cluster_id=cluster_id,
                        node_id=node_id,
                        aggregate_score=node_agg_score,
                        aggregation_strategy="max",
                        num_metrics_analyzed=len(metric_names),
                        num_anomalies_detected=num_anomalies,
                        computed_at=datetime.now(timezone.utc),
                    )
                    db.add(node_agg)
                    node_scores.append(node_agg_score)

            if node_scores:
                cluster_score = max(node_scores)
                cluster_agg = AggregatedScoreRecord(
                    tenant_id=tenant_id,
                    cluster_id=cluster_id,
                    node_id=None,
                    aggregate_score=cluster_score,
                    aggregation_strategy="max",
                    num_metrics_analyzed=len(node_ids) * len(metric_names),
                    num_anomalies_detected=sum(1 for s in node_scores if s > 0.5),
                    computed_at=datetime.now(timezone.utc),
                )
                db.add(cluster_agg)

                try:
                    await ws_manager.broadcast_health_update(tenant_id, {
                        "cluster_id": cluster_id,
                        "health_score": cluster_score,
                        "nodes_analyzed": len(node_ids),
                    })
                except Exception:
                    pass

            await db.commit()
            logger.info(
                "detection_job_completed",
                job_id=job_id,
                nodes=len(node_ids),
                metrics=len(metric_names),
            )

        except Exception as exc:
            await db.rollback()
            logger.error("detection_job_failed", job_id=job_id, error=str(exc))


@router.post("/detect", response_model=DetectResponse)
async def trigger_detection(
    body: DetectRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session),
):
    tenant_id = str(tenant.id)
    job_id = str(uuid.uuid4())

    start_time = body.start_time or (datetime.now(timezone.utc) - timedelta(days=1))
    end_time = body.end_time or datetime.now(timezone.utc)

    background_tasks.add_task(
        run_detection_job,
        job_id=job_id,
        tenant_id=tenant_id,
        cluster_id=body.cluster_id,
        node_ids=body.node_ids,
        metric_names=body.metric_names,
        start_time=start_time,
        end_time=end_time,
    )

    logger.info("detection_queued", job_id=job_id, tenant_id=tenant_id)

    return DetectResponse(job_id=job_id, status="queued")
