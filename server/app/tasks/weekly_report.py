import asyncio
import logging

from app.core.database import async_session_factory
from app.services.report import generate_weekly_reports
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)

# Weekly report task retry configuration
WEEKLY_REPORT_MAX_RETRIES = 2
WEEKLY_REPORT_RETRY_DELAY = 300  # 5 minutes


async def run_weekly_report_generation(report_week: str | None = None) -> int:
    async with async_session_factory() as db:
        reports = await generate_weekly_reports(db, report_week)
        await db.commit()
        return len(reports)


@celery.task(bind=True, max_retries=WEEKLY_REPORT_MAX_RETRIES, default_retry_delay=WEEKLY_REPORT_RETRY_DELAY)
def generate_weekly_reports_task(self, report_week: str | None = None) -> int:
    """Generate weekly reports for all active students.
    
    Retry configuration:
    - max_retries: 2
    - retry_delay: 300s (5 minutes)
    - Final failure: Log error, do not regenerate
    """
    try:
        count = asyncio.run(run_weekly_report_generation(report_week))
        logger.info(
            "Weekly report generation completed. report_week=%s, count=%d",
            report_week,
            count,
        )
        return count
    except Exception as exc:
        retry_count = self.request.retries
        
        if retry_count < self.max_retries:
            logger.warning(
                "Weekly report generation failed, retrying. "
                "report_week=%s, retry=%d/%d, error=%s",
                report_week,
                retry_count + 1,
                self.max_retries,
                str(exc),
            )
            raise self.retry(exc=exc)
        
        # Final failure - log and don't regenerate
        logger.error(
            "Weekly report generation failed after all retries. "
            "report_week=%s, error=%s",
            report_week,
            str(exc),
        )
        # Re-raise to mark task as failed
        raise
