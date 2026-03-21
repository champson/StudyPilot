"""Session cleanup task for automatically closing stale QA sessions."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.qa import QaMessage, QaSession
from app.services.qa import evaluate_session_quality
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)

# Session cleanup configuration
STALE_SESSION_MINUTES = 30  # Close sessions with no new messages for 30 minutes
MAX_SESSIONS_PER_CLEANUP = 100  # Limit sessions processed per cleanup run


async def _close_stale_sessions(db: AsyncSession) -> int:
    """Close QA sessions that have been inactive for more than STALE_SESSION_MINUTES.
    
    For each closed session, evaluate_session_quality is called to trigger
    quality assessment and potential manual corrections.
    
    Returns the number of sessions closed.
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=STALE_SESSION_MINUTES)
    
    # Subquery to find the latest message time for each active session
    latest_message_subquery = (
        select(
            QaMessage.session_id,
            func.max(QaMessage.created_at).label("last_message_at"),
        )
        .group_by(QaMessage.session_id)
        .subquery()
    )
    
    # Find active sessions with last message time > 30 minutes ago
    # Select both id and student_id for quality evaluation
    stale_sessions_query = (
        select(QaSession.id, QaSession.student_id)
        .outerjoin(
            latest_message_subquery,
            QaSession.id == latest_message_subquery.c.session_id,
        )
        .where(
            QaSession.status == "active",
            # Either no messages (use created_at) or last message is stale
            (
                (latest_message_subquery.c.last_message_at.is_(None) & (QaSession.created_at < cutoff_time))
                | (latest_message_subquery.c.last_message_at < cutoff_time)
            ),
        )
        .limit(MAX_SESSIONS_PER_CLEANUP)
    )
    
    result = await db.execute(stale_sessions_query)
    stale_sessions = result.fetchall()
    
    if not stale_sessions:
        return 0
    
    closed_count = 0
    for session_id, student_id in stale_sessions:
        # Update session status to closed
        update_stmt = (
            update(QaSession)
            .where(QaSession.id == session_id)
            .values(
                status="closed",
                closed_at=func.now(),
            )
        )
        await db.execute(update_stmt)
        await db.flush()
        
        # Trigger quality evaluation for the closed session
        try:
            await evaluate_session_quality(db, session_id, student_id)
        except Exception as exc:
            logger.warning(
                "Quality evaluation failed for session %d: %s",
                session_id,
                str(exc),
            )
        
        closed_count += 1
    
    return closed_count


async def run_session_cleanup() -> int:
    """Run the session cleanup task."""
    async with async_session_factory() as db:
        count = await _close_stale_sessions(db)
        await db.commit()
        return count


@celery.task
def close_stale_sessions() -> int:
    """Close QA sessions that have been inactive for more than 30 minutes.
    
    This task is scheduled to run every 5 minutes via Celery Beat.
    
    Returns the number of sessions closed.
    """
    try:
        count = asyncio.run(run_session_cleanup())
        if count > 0:
            logger.info("Session cleanup completed. closed_sessions=%d", count)
        return count
    except Exception as exc:
        logger.error("Session cleanup failed. error=%s", str(exc))
        raise
