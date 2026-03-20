import asyncio

from app.core.database import async_session_factory
from app.services.report import generate_weekly_reports
from app.tasks.celery_app import celery


async def run_weekly_report_generation(report_week: str | None = None) -> int:
    async with async_session_factory() as db:
        reports = await generate_weekly_reports(db, report_week)
        await db.commit()
        return len(reports)


@celery.task
def generate_weekly_reports_task(report_week: str | None = None) -> int:
    return asyncio.run(run_weekly_report_generation(report_week))
