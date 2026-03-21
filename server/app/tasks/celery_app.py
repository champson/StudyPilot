from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery = Celery("studypilot", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    beat_schedule={
        "generate-weekly-reports": {
            "task": "app.tasks.weekly_report.generate_weekly_reports_task",
            "schedule": crontab(minute=30, hour=23, day_of_week="sun"),
        },
        "close-stale-sessions": {
            "task": "app.tasks.session_cleanup.close_stale_sessions",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
        },
    },
)
