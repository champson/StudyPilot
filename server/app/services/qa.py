import json
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, timedelta
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
from app.models.system import ManualCorrection
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
            point_id = int(point["id"])
            if point_id > 0:
                normalized.append({"id": point_id, "name": point.get("name")})
            elif point.get("name"):
                unresolved_names.append(str(point["name"]))
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
        yield _serialize_sse_event({"type": "session_created", "session_id": session.id})
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


# ---------------------------------------------------------------------------
# 答疑质量评估与自动纠偏 - 参考 phase3-detailed-design.md §5.8
# ---------------------------------------------------------------------------

# 评估阈值配置
QA_QUALITY_LOW_FIRST_TRY_THRESHOLD = 0.2  # 低正确率阈值
QA_QUALITY_CONSECUTIVE_COUNT = 3  # 连续失败次数
QA_QUALITY_HIGH_FREQUENCY_HOURS = 24  # 高频答疑时间窗口（小时）
QA_QUALITY_HIGH_FREQUENCY_COUNT = 3  # 高频答疑次数阈值

# 纠偏类型
CORRECTION_TYPE_LOW_FIRST_TRY = "low_first_try_rate"
CORRECTION_TYPE_HIGH_FREQUENCY = "high_frequency_qa"
CORRECTION_TYPE_KNOWLEDGE_REGRESSION = "knowledge_regression"


def _extract_knowledge_point_ids(session: QaSession) -> set[int]:
    """从TQaSession的消息中提取知识点ID"""
    kp_ids: set[int] = set()
    if not session.messages:
        return kp_ids
    
    for msg in session.messages:
        if msg.knowledge_points:
            for kp in msg.knowledge_points:
                if isinstance(kp, dict) and kp.get("id"):
                    kp_ids.add(int(kp["id"]))
                elif isinstance(kp, int):
                    kp_ids.add(kp)
    return kp_ids


async def _count_sessions_for_kp_in_hours(
    db: AsyncSession,
    student_id: int,
    knowledge_point_id: int,
    hours: int = 24,
) -> int:
    """
    统计指定时间窗口内某知识点的答疑会话数量
    """
    cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
    
    # 查询包含该知识点的消息所属的会话
    # 使用 JSONB 查询匹配知识点
    session_ids_result = await db.execute(
        select(QaMessage.session_id)
        .distinct()
        .join(QaSession, QaMessage.session_id == QaSession.id)
        .where(
            QaSession.student_id == student_id,
            QaSession.created_at >= cutoff_time,
            QaMessage.knowledge_points.op('@>')(
                f'[{{"id": {knowledge_point_id}}}]'
            ),
        )
    )
    session_ids = session_ids_result.scalars().all()
    return len(session_ids)


async def _get_recent_sessions_for_kp(
    db: AsyncSession,
    student_id: int,
    knowledge_point_id: int,
    count: int = 3,
) -> list[QaSession]:
    """
    获取某知识点最近的 N 个答疑会话
    """
    # 查询包含该知识点的消息所属的会话
    session_ids_result = await db.execute(
        select(QaMessage.session_id)
        .distinct()
        .join(QaSession, QaMessage.session_id == QaSession.id)
        .where(
            QaSession.student_id == student_id,
            QaMessage.knowledge_points.op('@>')(
                f'[{{"id": {knowledge_point_id}}}]'
            ),
        )
        .order_by(QaSession.created_at.desc())
        .limit(count)
    )
    session_ids = session_ids_result.scalars().all()
    
    if not session_ids:
        return []
    
    result = await db.execute(
        select(QaSession)
        .options(selectinload(QaSession.messages))
        .where(QaSession.id.in_(session_ids))
        .order_by(QaSession.created_at.desc())
    )
    return list(result.scalars().all())


def _calculate_first_try_rate(session: QaSession) -> float:
    """
    计算会话的首次尝试正确率
    通过分析会话消息的 tutoring_strategy 判断
    - 'direct_answer' 或无策略认为是第一次正确
    - 'hint', 'scaffold' 等表示需要提示
    """
    if not session.messages:
        return 1.0  # 无消息默认正常
    
    assistant_messages = [m for m in session.messages if m.role == "assistant"]
    if not assistant_messages:
        return 1.0
    
    # 简化判断: 检查第一条助手消息的策略
    first_msg = assistant_messages[0]
    strategy = first_msg.tutoring_strategy or "direct_answer"
    
    # 如果第一次就使用了 hint/scaffold 策略，说明学生需要帮助
    if strategy in ("hint", "scaffold", "redirect"):
        return 0.0
    
    return 1.0


async def _create_qa_correction(
    db: AsyncSession,
    session_id: int,
    student_id: int,
    correction_type: str,
    reason: str,
    knowledge_point_id: int | None = None,
) -> ManualCorrection:
    """
    创建答疑纠偏记录
    """
    correction = ManualCorrection(
        target_type="qa",
        target_id=session_id,
        original_content={
            "alert_type": correction_type,
            "student_id": student_id,
            "knowledge_point_id": knowledge_point_id,
        },
        corrected_content={},  # 纠偏内容待管理员填写
        correction_reason=reason,
        corrected_by=0,  # 系统自动创建，使用 0 标识
        status="pending",
    )
    db.add(correction)
    await db.flush()
    return correction


async def evaluate_session_quality(
    db: AsyncSession,
    session_id: int,
    student_id: int,
) -> list[ManualCorrection]:
    """
    评估答疑会话质量，根据规则触发人工纠偏
    
    触发条件 (参考 phase3-detailed-design.md §5.8):
    1. 连续 3 次同知识点 first_try_correct=False
    2. 24h 内同知识点 ≥3 次答疑会话
    
    返回创建的纠偏记录列表
    """
    corrections: list[ManualCorrection] = []
    
    # 获取会话详情
    result = await db.execute(
        select(QaSession)
        .options(selectinload(QaSession.messages))
        .where(QaSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        return corrections
    
    # 提取会话涉及的知识点
    kp_ids = _extract_knowledge_point_ids(session)
    
    for kp_id in kp_ids:
        # 条件 1: 检查连续低正确率
        recent_sessions = await _get_recent_sessions_for_kp(
            db, student_id, kp_id, count=QA_QUALITY_CONSECUTIVE_COUNT
        )
        
        if len(recent_sessions) >= QA_QUALITY_CONSECUTIVE_COUNT:
            # 计算平均首次尝试正确率
            avg_rate = sum(
                _calculate_first_try_rate(s) for s in recent_sessions
            ) / len(recent_sessions)
            
            if avg_rate < QA_QUALITY_LOW_FIRST_TRY_THRESHOLD:
                # 检查是否已存在类似的待处理纠偏
                existing = await db.execute(
                    select(ManualCorrection.id).where(
                        ManualCorrection.target_type == "qa",
                        ManualCorrection.target_id == session_id,
                        ManualCorrection.status == "pending",
                    )
                )
                if not existing.scalar_one_or_none():
                    correction = await _create_qa_correction(
                        db,
                        session_id=session_id,
                        student_id=student_id,
                        correction_type=CORRECTION_TYPE_LOW_FIRST_TRY,
                        reason=f"知识点 {kp_id} 连续 {QA_QUALITY_CONSECUTIVE_COUNT} 次答疑正确率过低 ({avg_rate:.0%})，建议检查 Tutoring Agent 教学策略",
                        knowledge_point_id=kp_id,
                    )
                    corrections.append(correction)
        
        # 条件 2: 检查高频答疑
        recent_count = await _count_sessions_for_kp_in_hours(
            db, student_id, kp_id, hours=QA_QUALITY_HIGH_FREQUENCY_HOURS
        )
        
        if recent_count >= QA_QUALITY_HIGH_FREQUENCY_COUNT:
            # 检查是否已存在高频答疑纠偏
            existing = await db.execute(
                select(ManualCorrection.id).where(
                    ManualCorrection.target_type == "qa",
                    ManualCorrection.target_id == session_id,
                    ManualCorrection.original_content["alert_type"].astext == CORRECTION_TYPE_HIGH_FREQUENCY,
                    ManualCorrection.status == "pending",
                )
            )
            if not existing.scalar_one_or_none():
                correction = await _create_qa_correction(
                    db,
                    session_id=session_id,
                    student_id=student_id,
                    correction_type=CORRECTION_TYPE_HIGH_FREQUENCY,
                    reason=f"知识点 {kp_id} {QA_QUALITY_HIGH_FREQUENCY_HOURS}h 内答疑 {recent_count} 次，建议提高该知识点计划优先级",
                    knowledge_point_id=kp_id,
                )
                corrections.append(correction)
    
    return corrections


async def close_session(
    db: AsyncSession,
    student_id: int,
    session_id: int,
) -> QaSession:
    """
    关闭答疑会话并触发质量评估
    """
    result = await db.execute(
        select(QaSession).where(
            QaSession.id == session_id,
            QaSession.student_id == student_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise AppError("SESSION_NOT_FOUND", "会话不存在", status_code=404)
    
    # 更新会话状态
    session.status = "closed"
    session.closed_at = datetime.now(UTC)
    await db.flush()
    
    # 触发质量评估
    await evaluate_session_quality(db, session_id, student_id)
    
    return session
