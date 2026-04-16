import structlog
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_session_factory
from backend.core.models import MetricHot
from backend.core.config import get_settings
from backend.storage.cold import ColdStorage

logger = structlog.get_logger("aboutcloud.retention")


class RetentionManager:
    def __init__(self):
        self.settings = get_settings()
        self.cold_storage = ColdStorage()

    async def run_archival(self):
        logger.info("retention_archival_started")
        factory = get_session_factory()

        async with factory() as db:
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.settings.HOT_RETENTION_DAYS)

                result = await db.execute(
                    select(MetricHot)
                    .where(MetricHot.time < cutoff)
                    .order_by(MetricHot.time)
                    .limit(10000)
                )
                old_rows = result.scalars().all()

                if not old_rows:
                    logger.info("retention_no_data_to_archive")
                    return

                by_key = {}
                for row in old_rows:
                    key = (
                        str(row.tenant_id),
                        str(row.cluster_id),
                        str(row.node_id),
                        row.metric_name,
                    )
                    if key not in by_key:
                        by_key[key] = {"timestamps": [], "values": []}
                    by_key[key]["timestamps"].append(row.time)
                    by_key[key]["values"].append(row.value)

                total_archived = 0
                for (tenant_id, cluster_id, node_id, metric_name), data in by_key.items():
                    archived = self.cold_storage.archive_data(
                        tenant_id=tenant_id,
                        cluster_id=cluster_id,
                        node_id=node_id,
                        metric_name=metric_name,
                        timestamps=data["timestamps"],
                        values=data["values"],
                    )
                    total_archived += archived

                await db.execute(
                    delete(MetricHot).where(MetricHot.time < cutoff)
                )
                await db.commit()

                logger.info(
                    "retention_archival_completed",
                    archived_rows=total_archived,
                    groups=len(by_key),
                )

            except Exception as exc:
                await db.rollback()
                logger.error("retention_archival_failed", error=str(exc))

    async def run_compression(self):
        factory = get_session_factory()
        async with factory() as db:
            try:
                await db.execute(
                    text("SELECT compress_chunk(c) FROM show_chunks('metrics_hot', older_than => INTERVAL '7 days') c")
                )
                await db.commit()
                logger.info("retention_compression_completed")
            except Exception as exc:
                logger.warning("retention_compression_skipped", reason=str(exc))


async def start_retention_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    manager = RetentionManager()
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        manager.run_archival,
        "interval",
        hours=6,
        id="archival_job",
        replace_existing=True,
    )

    scheduler.add_job(
        manager.run_compression,
        "interval",
        hours=12,
        id="compression_job",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("retention_scheduler_started")
    return scheduler
