from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.error_book import ErrorBook
from app.models.knowledge import StudentKnowledgeStatus
from app.models.qa import QaSession
from app.services.knowledge import (
    BASICALLY_MASTERED,
    NEEDS_CONSOLIDATION,
    apply_assessment_results,
    update_mastery_state,
)


@pytest.mark.asyncio
async def test_update_mastery_state_promotes_across_sessions(
    db_session: AsyncSession, seed_data: dict
):
    kp = seed_data["knowledge_points"][1]
    status = await update_mastery_state(
        db_session,
        student_id=seed_data["profile"].id,
        knowledge_point_id=kp.id,
        outcome="correct_first_try",
        session_id=101,
        reason="第一次答对",
    )
    assert status.status == NEEDS_CONSOLIDATION

    status = await update_mastery_state(
        db_session,
        student_id=seed_data["profile"].id,
        knowledge_point_id=kp.id,
        outcome="correct_first_try",
        session_id=102,
        reason="第二次不同会话答对",
    )
    assert status.status == BASICALLY_MASTERED


@pytest.mark.asyncio
async def test_apply_assessment_results_creates_error_book_and_summary(
    db_session: AsyncSession, seed_data: dict
):
    session = QaSession(
        student_id=seed_data["profile"].id,
        session_date=date.today(),
        subject_id=seed_data["subjects"][1].id,
        status="active",
    )
    db_session.add(session)
    await db_session.flush()

    kp = seed_data["knowledge_points"][0]
    await apply_assessment_results(
        db_session,
        student_id=seed_data["profile"].id,
        session=session,
        assessment={
            "knowledge_point_updates": [
                {
                    "knowledge_point_id": kp.id,
                    "knowledge_point_name": kp.name,
                    "previous_status": "未观察",
                    "new_status": "需要巩固",
                    "reason": "经提示后答对",
                    "confidence": 0.8,
                }
            ],
            "session_summary": {
                "total_questions": 1,
                "correct_first_try": 0,
                "correct_with_hint": 1,
                "incorrect": 0,
                "dominant_error_type": None,
            },
            "error_book_entries": [
                {
                    "subject_id": seed_data["subjects"][1].id,
                    "question_summary": "函数定义域理解错误",
                    "knowledge_point_ids": [kp.id],
                    "error_type": "概念不清",
                    "entry_reason": "wrong",
                }
            ],
            "suggested_followup": "明天复习定义域",
        },
    )

    status_result = await db_session.execute(
        select(StudentKnowledgeStatus).where(
            StudentKnowledgeStatus.student_id == seed_data["profile"].id,
            StudentKnowledgeStatus.knowledge_point_id == kp.id,
        )
    )
    status = status_result.scalar_one()
    assert status.status == NEEDS_CONSOLIDATION

    error_result = await db_session.execute(
        select(ErrorBook).where(ErrorBook.student_id == seed_data["profile"].id)
    )
    error = error_result.scalar_one()
    assert error.error_type == "概念不清"
    assert session.structured_summary["suggested_followup"] == "明天复习定义域"
