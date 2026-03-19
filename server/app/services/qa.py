import asyncio
import json
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
        tutoring_strategy="hint",
        knowledge_points=[{"id": 1, "name": "示例知识点"}],
    )
    db.add(assistant_msg)
    await db.flush()

    return session, user_msg, assistant_msg


async def save_user_message(
    db: AsyncSession,
    student_id: int,
    session_id: int | None,
    message: str,
    subject_id: int | None,
    task_id: int | None,
    attachments: list,
) -> tuple[QaSession, QaMessage]:
    """Save user message only (for streaming — assistant message built from SSE chunks)."""
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

    return session, user_msg


STUB_CHUNKS = ["这是一个", "流式 stub", "回复。", "Phase 3 将接入", "AI 模型。"]
STUB_KNOWLEDGE_POINTS = [{"id": 1, "name": "示例知识点"}]
STUB_STRATEGY = "hint"


async def chat_stream_stub() -> AsyncGenerator[str, None]:
    """Yield structured SSE events matching api-contract §6.4."""
    for chunk in STUB_CHUNKS:
        event = json.dumps({"type": "chunk", "content": chunk}, ensure_ascii=False)
        yield f"data: {event}\n\n"
        await asyncio.sleep(0.3)

    kp_event = json.dumps(
        {"type": "knowledge_points", "data": STUB_KNOWLEDGE_POINTS},
        ensure_ascii=False,
    )
    yield f"data: {kp_event}\n\n"

    strategy_event = json.dumps({"type": "strategy", "data": STUB_STRATEGY}, ensure_ascii=False)
    yield f"data: {strategy_event}\n\n"

    yield "data: [DONE]\n\n"


async def save_stream_assistant_message(
    db: AsyncSession, session_id: int
) -> QaMessage:
    """Persist the stub assistant message after SSE stream completes."""
    full_content = "".join(STUB_CHUNKS)
    assistant_msg = QaMessage(
        session_id=session_id,
        role="assistant",
        content=full_content,
        intent="stub",
        tutoring_strategy=STUB_STRATEGY,
        knowledge_points=STUB_KNOWLEDGE_POINTS,
    )
    db.add(assistant_msg)
    await db.flush()
    return assistant_msg


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
