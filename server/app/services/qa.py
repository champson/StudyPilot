import json
from collections.abc import AsyncGenerator
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.llm.agents.assessment import assess_session
from app.llm.agents.routing import classify_intent
from app.llm.agents.tutoring import (
    build_fallback_tutoring_response,
    parse_tutoring_output,
    stream_fallback_tutoring_response,
)
from app.llm.model_router import get_model_router
from app.llm.prompts import TUTORING_SYSTEM_PROMPT
from app.models.knowledge import KnowledgeTree
from app.models.qa import QaMessage, QaSession
from app.services.knowledge import apply_assessment_results, resolve_knowledge_points_by_names


async def _load_or_create_session(
    db: AsyncSession,
    *,
    student_id: int,
    session_id: int | None,
    subject_id: int | None,
    task_id: int | None,
) -> QaSession:
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
        return session

    session = QaSession(
        student_id=student_id,
        session_date=date.today(),
        task_id=task_id,
        subject_id=subject_id,
        status="active",
    )
    db.add(session)
    await db.flush()
    return session


async def _load_messages(db: AsyncSession, session_id: int) -> list[dict[str, Any]]:
    result = await db.execute(
        select(QaMessage)
        .where(QaMessage.session_id == session_id)
        .order_by(QaMessage.created_at.asc(), QaMessage.id.asc())
    )
    return [
        {"role": message.role, "content": message.content}
        for message in result.scalars().all()
    ]


async def _default_knowledge_points(
    db: AsyncSession, subject_id: int | None
) -> list[dict[str, Any]]:
    if subject_id is None:
        return []
    result = await db.execute(
        select(KnowledgeTree)
        .where(KnowledgeTree.subject_id == subject_id)
        .order_by(KnowledgeTree.level.asc(), KnowledgeTree.id.asc())
        .limit(2)
    )
    return [{"id": point.id, "name": point.name} for point in result.scalars().all()]


async def _normalize_knowledge_points(
    db: AsyncSession,
    subject_id: int | None,
    raw_points: list[Any] | None,
) -> list[dict[str, Any]]:
    raw_points = raw_points or []
    normalized: list[dict[str, Any]] = []
    unresolved_names: list[str] = []
    for point in raw_points:
        if isinstance(point, dict) and point.get("id") is not None:
            normalized.append({"id": int(point["id"]), "name": point.get("name")})
        elif isinstance(point, dict) and point.get("name"):
            unresolved_names.append(str(point["name"]))
        elif isinstance(point, str):
            unresolved_names.append(point)

    if unresolved_names:
        resolved = await resolve_knowledge_points_by_names(
            db, unresolved_names, subject_id=subject_id
        )
        seen_ids = {item["id"] for item in normalized if item.get("id") is not None}
        for item in resolved:
            if item["id"] not in seen_ids:
                normalized.append(item)

    if not normalized:
        normalized = await _default_knowledge_points(db, subject_id)
    return normalized


def _serialize_sse_event(payload: str | dict[str, Any]) -> str:
    if isinstance(payload, str):
        return f"data: {payload}\n\n"
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _save_assistant_message(
    db: AsyncSession,
    *,
    session_id: int,
    content: str,
    intent: str,
    tutoring_strategy: str,
    knowledge_points: list[dict[str, Any]],
) -> QaMessage:
    assistant_msg = QaMessage(
        session_id=session_id,
        role="assistant",
        content=content,
        intent=intent,
        tutoring_strategy=tutoring_strategy,
        knowledge_points=knowledge_points,
    )
    db.add(assistant_msg)
    await db.flush()
    return assistant_msg


async def _assess_and_apply(
    db: AsyncSession,
    *,
    student_id: int,
    session: QaSession,
    subject_id: int | None,
    knowledge_points: list[dict[str, Any]],
) -> None:
    messages = await _load_messages(db, session.id)
    status_snapshot = {}
    if knowledge_points:
        result = await db.execute(
            select(KnowledgeTree.id, KnowledgeTree.name).where(
                KnowledgeTree.id.in_([item["id"] for item in knowledge_points if item.get("id")])
            )
        )
        name_map = {row[0]: row[1] for row in result.all()}
        status_snapshot = {
            item["id"]: item.get("name") or name_map.get(item["id"])
            for item in knowledge_points
            if item.get("id") is not None
        }
    involved = [
        {
            "id": item["id"],
            "name": status_snapshot.get(item["id"]) or item.get("name"),
            "current_status": "未观察",
        }
        for item in knowledge_points
        if item.get("id") is not None
    ]
    assessment = await assess_session(
        subject_id=subject_id,
        messages=messages,
        knowledge_points_involved=involved,
        db=db,
        student_id=student_id,
    )
    await apply_assessment_results(
        db,
        student_id=student_id,
        session=session,
        assessment=assessment,
    )


async def _build_tutoring_response(
    db: AsyncSession,
    *,
    student_id: int,
    subject_id: int | None,
    messages: list[dict[str, Any]],
    latest_message: str,
) -> tuple[str, dict[str, Any]]:
    router = get_model_router()
    try:
        content, _meta = await router.invoke(
            "tutoring",
            [{"role": "system", "content": TUTORING_SYSTEM_PROMPT}, *messages],
            db=db,
            student_id=student_id,
            max_tokens=1200,
        )
    except Exception:
        content = build_fallback_tutoring_response(
            latest_message,
            await _default_knowledge_points(db, subject_id),
        )

    answer, metadata = parse_tutoring_output(content)
    metadata["knowledge_points"] = await _normalize_knowledge_points(
        db, subject_id, metadata.get("knowledge_points")
    )
    metadata["strategy"] = metadata.get("strategy") or "hint"
    return answer, metadata


async def chat_sync(
    db: AsyncSession,
    student_id: int,
    session_id: int | None,
    message: str,
    subject_id: int | None,
    task_id: int | None,
    attachments: list,
) -> tuple[QaSession, QaMessage, QaMessage]:
    session = await _load_or_create_session(
        db,
        student_id=student_id,
        session_id=session_id,
        subject_id=subject_id,
        task_id=task_id,
    )

    user_msg = QaMessage(
        session_id=session.id,
        role="user",
        content=message,
        attachments=attachments,
    )
    db.add(user_msg)
    await db.flush()

    intent_result = await classify_intent(
        message=message,
        has_attachments=bool(attachments),
        session_context="已有会话追问" if session_id else "新会话",
        db=db,
        student_id=student_id,
    )
    intent = intent_result["intent"]

    if intent_result["route_to"] == "none":
        answer = "请尽量把问题聚焦到具体学科学习内容，我可以帮你拆题、找思路和定位知识点。"
        knowledge_points = await _default_knowledge_points(db, subject_id)
        strategy = "redirect"
    else:
        messages = await _load_messages(db, session.id)
        answer, metadata = await _build_tutoring_response(
            db,
            student_id=student_id,
            subject_id=subject_id,
            messages=messages,
            latest_message=message,
        )
        knowledge_points = metadata["knowledge_points"]
        strategy = metadata["strategy"]

    assistant_msg = await _save_assistant_message(
        db,
        session_id=session.id,
        content=answer,
        intent=intent,
        tutoring_strategy=strategy,
        knowledge_points=knowledge_points,
    )
    await _assess_and_apply(
        db,
        student_id=student_id,
        session=session,
        subject_id=subject_id,
        knowledge_points=knowledge_points,
    )
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
    session = await _load_or_create_session(
        db,
        student_id=student_id,
        session_id=session_id,
        subject_id=subject_id,
        task_id=task_id,
    )
    user_msg = QaMessage(
        session_id=session.id,
        role="user",
        content=message,
        attachments=attachments,
    )
    db.add(user_msg)
    await db.flush()
    return session, user_msg


async def chat_stream(
    db: AsyncSession,
    *,
    student_id: int,
    session_id: int | None,
    message: str,
    subject_id: int | None,
    task_id: int | None,
    attachments: list,
) -> tuple[QaSession, AsyncGenerator[str, None]]:
    session, _user_msg = await save_user_message(
        db,
        student_id,
        session_id,
        message,
        subject_id,
        task_id,
        attachments,
    )

    intent_result = await classify_intent(
        message=message,
        has_attachments=bool(attachments),
        session_context="已有会话追问" if session_id else "新会话",
        db=db,
        student_id=student_id,
    )
    intent = intent_result["intent"]

    async def event_stream() -> AsyncGenerator[str, None]:
        yield _serialize_sse_event({"type": "session_id", "data": session.id})
        if intent_result["route_to"] == "none":
            answer = "请尽量把问题聚焦到具体学科学习内容，我可以帮你拆题、找思路和定位知识点。"
            knowledge_points = await _default_knowledge_points(db, subject_id)
            yield _serialize_sse_event({"type": "chunk", "content": answer})
            yield _serialize_sse_event({"type": "knowledge_points", "data": knowledge_points})
            yield _serialize_sse_event({"type": "strategy", "data": "redirect"})
            await _save_assistant_message(
                db,
                session_id=session.id,
                content=answer,
                intent=intent,
                tutoring_strategy="redirect",
                knowledge_points=knowledge_points,
            )
            yield _serialize_sse_event("[DONE]")
            return

        messages = await _load_messages(db, session.id)
        router = get_model_router()
        raw_stream = None
        try:
            raw_stream = router.invoke_stream(
                "tutoring",
                [{"role": "system", "content": TUTORING_SYSTEM_PROMPT}, *messages],
                db=db,
                student_id=student_id,
                max_tokens=1200,
            )
        except Exception:
            raw_stream = None

        raw_content = ""
        visible_content = ""
        metadata_started = False
        emitted_visible_chunk = False
        default_points = await _default_knowledge_points(db, subject_id)

        async def consume(source):
            nonlocal raw_content, visible_content, metadata_started, emitted_visible_chunk
            async for chunk in source:
                raw_content += chunk
                if metadata_started:
                    continue

                next_visible = visible_content + chunk
                if "---METADATA---" in next_visible:
                    answer_part, _metadata_part = next_visible.split("---METADATA---", 1)
                    delta = answer_part[len(visible_content) :]
                    if delta:
                        visible_content += delta
                        emitted_visible_chunk = True
                        yield _serialize_sse_event({"type": "chunk", "content": delta})
                    metadata_started = True
                    continue

                visible_content += chunk
                emitted_visible_chunk = True
                yield _serialize_sse_event({"type": "chunk", "content": chunk})

        try:
            if raw_stream is None:
                raise RuntimeError("router stream unavailable")
            async for event in consume(raw_stream):
                yield event
        except Exception:
            if not emitted_visible_chunk:
                raw_content = ""
                visible_content = ""
                metadata_started = False
                async for event in consume(
                    stream_fallback_tutoring_response(message, default_points)
                ):
                    yield event

        answer, metadata = parse_tutoring_output(raw_content)
        if not answer:
            answer = visible_content
        knowledge_points = await _normalize_knowledge_points(
            db, subject_id, metadata.get("knowledge_points")
        )
        strategy = metadata.get("strategy") or "hint"

        await _save_assistant_message(
            db,
            session_id=session.id,
            content=answer,
            intent=intent,
            tutoring_strategy=strategy,
            knowledge_points=knowledge_points,
        )
        await _assess_and_apply(
            db,
            student_id=student_id,
            session=session,
            subject_id=subject_id,
            knowledge_points=knowledge_points,
        )

        yield _serialize_sse_event({"type": "knowledge_points", "data": knowledge_points})
        yield _serialize_sse_event({"type": "strategy", "data": strategy})
        yield _serialize_sse_event("[DONE]")

    return session, event_stream()


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
    for session in sessions:
        msg_count = await db.execute(
            select(func.count(QaMessage.id)).where(QaMessage.session_id == session.id)
        )
        items.append(
            {
                "id": session.id,
                "session_date": session.session_date,
                "subject_id": session.subject_id,
                "status": session.status,
                "created_at": session.created_at,
                "message_count": msg_count.scalar() or 0,
            }
        )
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
