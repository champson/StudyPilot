import asyncio
from collections.abc import AsyncGenerator
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.models.qa import QaMessage, QaSession


async def chat_sync(
    db: AsyncSession,
    student_id: int,
    session_id: int | None,
    message: str,
    subject_id: int | None,
    task_id: int | None,
    attachments: list,
) -> tuple[QaSession, QaMessage, QaMessage]:
    if session_id:
        result = await db.execute(
            select(QaSession).where(
                QaSession.id == session_id,
                QaSession.student_id == student_id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise AppError("SESSION_NOT_FOUND", "会话不存在", status_code=404)
    else:
        session = QaSession(
            student_id=student_id,
            session_date=date.today(),
            task_id=task_id,
            subject_id=subject_id,
            status="active",
        )
        db.add(session)
        await db.flush()

    user_msg = QaMessage(
        session_id=session.id,
        role="user",
        content=message,
        attachments=attachments,
    )
    db.add(user_msg)
    await db.flush()

    # Stub assistant response
    assistant_msg = QaMessage(
        session_id=session.id,
        role="assistant",
        content="这是一个 stub 回复。Phase 3 将接入 AI 模型生成真实答疑内容。",
        intent="stub",
        tutoring_strategy="stub",
    )
    db.add(assistant_msg)
    await db.flush()

    return session, user_msg, assistant_msg


async def chat_stream_stub() -> AsyncGenerator[str, None]:
    chunks = [
        "这是",
        "一个",
        "流式",
        "stub",
        "回复。",
        "Phase 3 将接入 AI 模型。",
    ]
    for chunk in chunks:
        yield f"data: {chunk}\n\n"
        await asyncio.sleep(0.3)
    yield "data: [DONE]\n\n"


async def list_sessions(
    db: AsyncSession, student_id: int, page: int, page_size: int
) -> tuple[list[dict], int]:
    count_result = await db.execute(
        select(func.count(QaSession.id)).where(QaSession.student_id == student_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(QaSession)
        .where(QaSession.student_id == student_id)
        .order_by(QaSession.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    sessions = result.scalars().all()

    items = []
    for s in sessions:
        msg_count = await db.execute(
            select(func.count(QaMessage.id)).where(QaMessage.session_id == s.id)
        )
        items.append({
            "id": s.id,
            "session_date": s.session_date,
            "subject_id": s.subject_id,
            "status": s.status,
            "created_at": s.created_at,
            "message_count": msg_count.scalar() or 0,
        })
    return items, total


async def get_session_detail(
    db: AsyncSession, student_id: int, session_id: int
) -> QaSession:
    result = await db.execute(
        select(QaSession)
        .options(selectinload(QaSession.messages))
        .where(
            QaSession.id == session_id,
            QaSession.student_id == student_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise AppError("SESSION_NOT_FOUND", "会话不存在", status_code=404)
    return session
