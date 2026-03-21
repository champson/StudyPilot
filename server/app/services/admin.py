from datetime import UTC, date, datetime, timedelta

import redis.asyncio as aioredis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.models.knowledge import KnowledgeTree, StudentKnowledgeStatus
from app.models.plan import DailyPlan
from app.models.qa import QaSession
from app.models.student_profile import StudentProfile
from app.models.subject import Subject
from app.models.system import ManualCorrection, ModelCallLog
from app.models.upload import StudyUpload

SYSTEM_MODE_KEY = "system:run_mode"

# Valid target types for manual corrections
VALID_TARGET_TYPES = {"ocr", "knowledge", "plan", "qa"}


async def validate_correction_target(
    db: AsyncSession,
    target_type: str,
    target_id: int,
) -> None:
    """
    Validate that the target_id exists for the given target_type.
    Raises HTTP 404 if target not found.
    """
    if target_type not in VALID_TARGET_TYPES:
        raise AppError(
            "INVALID_TARGET_TYPE",
            f"无效的 target_type: {target_type}，有效值为: {', '.join(sorted(VALID_TARGET_TYPES))}",
            status_code=400,
        )

    if target_type == "ocr":
        result = await db.execute(
            select(StudyUpload.id).where(StudyUpload.id == target_id)
        )
        if not result.scalar_one_or_none():
            raise AppError(
                "TARGET_NOT_FOUND",
                f"target_type='ocr' 的 target_id={target_id} 不存在（study_uploads 表中无此记录）",
                status_code=404,
            )
    elif target_type == "knowledge":
        result = await db.execute(
            select(StudentKnowledgeStatus.id).where(
                StudentKnowledgeStatus.id == target_id
            )
        )
        if not result.scalar_one_or_none():
            raise AppError(
                "TARGET_NOT_FOUND",
                f"target_type='knowledge' 的 target_id={target_id} 不存在（student_knowledge_status 表中无此记录）",
                status_code=404,
            )
    elif target_type == "plan":
        result = await db.execute(
            select(DailyPlan.id).where(
                DailyPlan.id == target_id,
                DailyPlan.is_deleted == False,  # noqa: E712
            )
        )
        if not result.scalar_one_or_none():
            raise AppError(
                "TARGET_NOT_FOUND",
                f"target_type='plan' 的 target_id={target_id} 不存在或已删除（daily_plans 表中无此记录）",
                status_code=404,
            )
    elif target_type == "qa":
        result = await db.execute(
            select(QaSession.id).where(QaSession.id == target_id)
        )
        if not result.scalar_one_or_none():
            raise AppError(
                "TARGET_NOT_FOUND",
                f"target_type='qa' 的 target_id={target_id} 不存在（qa_sessions 表中无此记录）",
                status_code=404,
            )


async def create_manual_correction(
    db: AsyncSession,
    target_type: str,
    target_id: int,
    corrected_content: dict,
    corrected_by: int,
    original_content: dict | None = None,
    correction_reason: str | None = None,
    status: str = "pending",
) -> ManualCorrection:
    """
    Create a manual correction record with validation.
    Validates that target_id exists for the given target_type before creating.
    """
    await validate_correction_target(db, target_type, target_id)

    correction = ManualCorrection(
        target_type=target_type,
        target_id=target_id,
        original_content=original_content,
        corrected_content=corrected_content,
        correction_reason=correction_reason,
        corrected_by=corrected_by,
        status=status,
    )
    db.add(correction)
    await db.flush()
    return correction


async def get_system_mode(r: aioredis.Redis) -> str:
    try:
        mode = await r.get(SYSTEM_MODE_KEY)
    except Exception:
        return "normal"
    return mode or "normal"


async def set_system_mode(r: aioredis.Redis, mode: str) -> str:
    if mode not in {"normal", "best"}:
        raise AppError("INVALID_MODE", "模式仅支持 normal 或 best", status_code=400)
    await r.set(SYSTEM_MODE_KEY, mode)
    return mode


async def get_pending_corrections(
    db: AsyncSession, page: int, page_size: int
) -> tuple[list[ManualCorrection], int]:
    pending_filter = ManualCorrection.status == "pending"
    count_result = await db.execute(
        select(func.count(ManualCorrection.id)).where(pending_filter)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ManualCorrection)
        .where(pending_filter)
        .order_by(ManualCorrection.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return result.scalars().all(), total


async def correct_ocr(
    db: AsyncSession,
    admin_user_id: int,
    upload_id: int,
    corrected_content: dict,
    reason: str | None,
) -> ManualCorrection:
    upload_result = await db.execute(
        select(StudyUpload).where(StudyUpload.id == upload_id)
    )
    upload = upload_result.scalar_one_or_none()
    if not upload:
        raise AppError("UPLOAD_NOT_FOUND", "上传记录不存在", status_code=404)

    correction = ManualCorrection(
        target_type="ocr",
        target_id=upload_id,
        original_content=upload.ocr_result,
        corrected_content=corrected_content,
        correction_reason=reason,
        corrected_by=admin_user_id,
        status="resolved",
    )
    db.add(correction)

    upload.ocr_result = corrected_content
    upload.ocr_status = "completed"
    upload.is_manual_corrected = True
    await db.flush()
    return correction


async def correct_knowledge(
    db: AsyncSession,
    admin_user_id: int,
    student_id: int,
    knowledge_point_id: int,
    new_status: str,
    reason: str | None,
) -> ManualCorrection:
    status_result = await db.execute(
        select(StudentKnowledgeStatus).where(
            StudentKnowledgeStatus.student_id == student_id,
            StudentKnowledgeStatus.knowledge_point_id == knowledge_point_id,
        )
    )
    status = status_result.scalar_one_or_none()
    if not status:
        raise AppError("KNOWLEDGE_STATUS_NOT_FOUND", "知识点状态不存在", status_code=404)

    correction = ManualCorrection(
        target_type="knowledge",
        target_id=status.id,
        original_content={
            "status": status.status,
            "student_id": student_id,
            "knowledge_point_id": knowledge_point_id,
        },
        corrected_content={"status": new_status},
        correction_reason=reason,
        corrected_by=admin_user_id,
        status="resolved",
    )
    db.add(correction)

    status.status = new_status
    status.is_manual_corrected = True
    status.last_update_reason = f"admin_correction: {reason or ''}"
    await db.flush()
    return correction


async def resolve_correction(
    db: AsyncSession,
    admin_user_id: int,
    correction_id: int,
    corrected_content: dict | None = None,
    reason: str | None = None,
) -> ManualCorrection:
    result = await db.execute(
        select(ManualCorrection).where(ManualCorrection.id == correction_id)
    )
    correction = result.scalar_one_or_none()
    if not correction:
        raise AppError("CORRECTION_NOT_FOUND", "纠偏记录不存在", status_code=404)
    if correction.status == "resolved":
        raise AppError("ALREADY_RESOLVED", "该纠偏已处理", status_code=409)

    if corrected_content is not None:
        correction.corrected_content = corrected_content
    if reason is not None:
        correction.correction_reason = reason

    if correction.target_type == "ocr":
        # OCR corrections require real text content to be resolved
        ocr_content = correction.corrected_content or {}
        has_real_content = bool(ocr_content.get("text"))
        if not has_real_content:
            raise AppError(
                "OCR_CONTENT_REQUIRED",
                "OCR 纠偏需要提供修正后的文本内容",
                status_code=400,
            )
        upload_result = await db.execute(
            select(StudyUpload).where(StudyUpload.id == correction.target_id)
        )
        upload = upload_result.scalar_one_or_none()
        if upload:
            upload.ocr_result = correction.corrected_content
            upload.ocr_status = "completed"
            upload.is_manual_corrected = True
    elif correction.target_type == "knowledge":
        original = correction.original_content or {}
        sid = original.get("student_id")
        kpid = original.get("knowledge_point_id")
        new_status = (correction.corrected_content or {}).get("status")
        if sid and kpid and new_status:
            status_result = await db.execute(
                select(StudentKnowledgeStatus).where(
                    StudentKnowledgeStatus.student_id == sid,
                    StudentKnowledgeStatus.knowledge_point_id == kpid,
                )
            )
            sk = status_result.scalar_one_or_none()
            if sk:
                sk.status = new_status
                sk.is_manual_corrected = True
                sk.last_update_reason = f"admin_correction: {correction.correction_reason or ''}"
    elif correction.target_type == "plan":
        corrected_tasks = (correction.corrected_content or {}).get("tasks", [])
        if not corrected_tasks:
            raise AppError(
                "PLAN_TASKS_REQUIRED",
                "计划纠偏需要提供修正后的任务列表",
                status_code=400,
            )
        plan_result = await db.execute(
            select(DailyPlan)
            .options(selectinload(DailyPlan.tasks))
            .where(DailyPlan.id == correction.target_id)
        )
        plan = plan_result.scalar_one_or_none()
        if not plan:
            raise AppError("PLAN_NOT_FOUND", "计划不存在", status_code=404)

        unmatched = []
        for ct in corrected_tasks:
            # Match by id first, then fall back to sequence
            existing = next(
                (t for t in plan.tasks if t.id == ct.get("id")),
                None,
            )
            if existing is None and "sequence" in ct:
                existing = next(
                    (t for t in plan.tasks if t.sequence == ct["sequence"]),
                    None,
                )
            if existing is None:
                unmatched.append(ct)
                continue
            if "task_type" in ct:
                existing.task_type = ct["task_type"]
            if "task_content" in ct:
                existing.task_content = ct["task_content"]
            if "subject_id" in ct:
                existing.subject_id = ct["subject_id"]
            if "sequence" in ct:
                existing.sequence = ct["sequence"]

        if unmatched:
            raise AppError(
                "PLAN_TASK_NOT_FOUND",
                f"无法匹配 {len(unmatched)} 个任务到现有计划",
                status_code=400,
            )

    correction.status = "resolved"
    await db.flush()
    return correction


async def get_today_metrics(db: AsyncSession) -> dict:
    today = date.today()

    students = await db.execute(select(func.count(StudentProfile.id)))
    plans = await db.execute(
        select(func.count(DailyPlan.id)).where(DailyPlan.plan_date == today)
    )
    uploads = await db.execute(
        select(func.count(StudyUpload.id)).where(
            func.date(StudyUpload.created_at) == today
        )
    )
    qa = await db.execute(
        select(func.count(QaSession.id)).where(QaSession.session_date == today)
    )

    return {
        "active_students": students.scalar() or 0,
        "plans_generated": plans.scalar() or 0,
        "uploads": uploads.scalar() or 0,
        "qa_sessions": qa.scalar() or 0,
    }


async def get_health(r: aioredis.Redis) -> dict:
    redis_ok = "ok"
    try:
        await r.ping()
    except Exception:
        redis_ok = "error"

    return {
        "database": "ok",
        "redis": redis_ok,
        "celery": "unknown",
    }


async def get_model_calls(db: AsyncSession) -> dict:
    total_result = await db.execute(select(func.count(ModelCallLog.id)))
    total = total_result.scalar() or 0

    by_agent_result = await db.execute(
        select(ModelCallLog.agent_name, func.count(ModelCallLog.id))
        .group_by(ModelCallLog.agent_name)
    )
    by_agent = [
        {"agent": row[0], "count": row[1]} for row in by_agent_result.all()
    ]

    by_provider_result = await db.execute(
        select(ModelCallLog.provider, func.count(ModelCallLog.id))
        .group_by(ModelCallLog.provider)
    )
    by_provider = [
        {"provider": row[0], "count": row[1]} for row in by_provider_result.all()
    ]

    return {"total": total, "by_agent": by_agent, "by_provider": by_provider}


# ---------------------------------------------------------------------------
# Phase 5 helpers
# ---------------------------------------------------------------------------


VALID_PERIODS = {"today", "week", "month"}


def _validate_period(period: str) -> str:
    if period not in VALID_PERIODS:
        raise AppError(
            "INVALID_PERIOD",
            f"period 必须为 {', '.join(sorted(VALID_PERIODS))}",
            status_code=400,
        )
    return period


def _period_start_date(period: str) -> datetime:
    today = date.today()
    if period == "week":
        start = today - timedelta(days=today.weekday())
    elif period == "month":
        start = today.replace(day=1)
    else:  # today
        start = today
    return datetime.combine(start, datetime.min.time(), tzinfo=UTC)


def _period_calendar_days(period: str) -> int:
    """Return number of calendar days elapsed in the period (at least 1)."""
    today = date.today()
    if period == "week":
        start = today - timedelta(days=today.weekday())
    elif period == "month":
        start = today.replace(day=1)
    else:
        return 1
    return max((today - start).days + 1, 1)


def _classify_fallback_reason(error_message: str | None) -> str:
    if not error_message:
        return "unknown"
    msg = error_message.lower()
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "rate" in msg or "429" in msg or "limit" in msg:
        return "rate_limit"
    if "500" in msg or "502" in msg or "503" in msg or "service" in msg:
        return "service_error"
    return "other"


def _classify_error_type(error_message: str | None) -> str:
    if not error_message:
        return "other"
    msg = error_message.lower()
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "parse" in msg or "json" in msg or "decode" in msg:
        return "parse_error"
    if "api" in msg or "401" in msg or "403" in msg:
        return "api_error"
    if "model" in msg or "generation" in msg:
        return "model_error"
    return "other"


# ---------------------------------------------------------------------------
# Phase 5: Metrics
# ---------------------------------------------------------------------------


async def get_cost_trend(db: AsyncSession, period: str = "today") -> dict:
    _validate_period(period)
    start_date = _period_start_date(period)

    total_result = await db.execute(
        select(func.coalesce(func.sum(ModelCallLog.estimated_cost), 0)).where(
            ModelCallLog.created_at >= start_date
        )
    )
    total_cost = float(total_result.scalar())

    by_model_result = await db.execute(
        select(ModelCallLog.model, func.sum(ModelCallLog.estimated_cost))
        .where(ModelCallLog.created_at >= start_date)
        .group_by(ModelCallLog.model)
        .order_by(func.sum(ModelCallLog.estimated_cost).desc())
    )
    by_model = [
        {"model": row[0], "cost": float(row[1] or 0)}
        for row in by_model_result.all()
    ]

    trend_result = await db.execute(
        select(
            func.date(ModelCallLog.created_at),
            func.sum(ModelCallLog.estimated_cost),
        )
        .where(ModelCallLog.created_at >= start_date)
        .group_by(func.date(ModelCallLog.created_at))
        .order_by(func.date(ModelCallLog.created_at))
    )
    trend = [
        {"date": str(row[0]), "cost": float(row[1] or 0)}
        for row in trend_result.all()
    ]

    days = _period_calendar_days(period)
    return {
        "period": period,
        "total_cost": round(total_cost, 2),
        "daily_avg_cost": round(total_cost / days, 2),
        "by_model": by_model,
        "trend": trend,
    }


async def get_fallback_stats(db: AsyncSession, period: str = "today") -> dict:
    _validate_period(period)
    start_date = _period_start_date(period)

    total_result = await db.execute(
        select(func.count(ModelCallLog.id)).where(
            ModelCallLog.created_at >= start_date
        )
    )
    total_calls = total_result.scalar() or 0

    fb_result = await db.execute(
        select(func.count(ModelCallLog.id)).where(
            ModelCallLog.created_at >= start_date,
            ModelCallLog.is_fallback.is_(True),
        )
    )
    fallback_count = fb_result.scalar() or 0

    fallback_rate = fallback_count / total_calls if total_calls else 0.0

    # Fetch fallback rows to classify reasons
    fb_rows = await db.execute(
        select(ModelCallLog.error_message).where(
            ModelCallLog.created_at >= start_date,
            ModelCallLog.is_fallback.is_(True),
        )
    )
    reason_counts: dict[str, int] = {}
    for (msg,) in fb_rows.all():
        reason = _classify_fallback_reason(msg)
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    by_reason = [
        {"reason": r, "count": c}
        for r, c in sorted(reason_counts.items(), key=lambda x: -x[1])
    ]

    # Daily trend
    trend_result = await db.execute(
        select(
            func.date(ModelCallLog.created_at),
            func.count(ModelCallLog.id),
            func.count(ModelCallLog.id).filter(ModelCallLog.is_fallback.is_(True)),
        )
        .where(ModelCallLog.created_at >= start_date)
        .group_by(func.date(ModelCallLog.created_at))
        .order_by(func.date(ModelCallLog.created_at))
    )
    trend = []
    for row in trend_result.all():
        day_total = row[1] or 1
        trend.append({
            "date": str(row[0]),
            "fallback_rate": round(row[2] / day_total, 4),
        })

    return {
        "period": period,
        "total_calls": total_calls,
        "fallback_count": fallback_count,
        "fallback_rate": round(fallback_rate, 4),
        "by_reason": by_reason,
        "trend": trend,
    }


async def get_error_stats(db: AsyncSession, period: str = "today") -> dict:
    _validate_period(period)
    start_date = _period_start_date(period)

    error_filter = (
        ModelCallLog.created_at >= start_date,
        ModelCallLog.success.is_(False),
    )

    total_result = await db.execute(
        select(func.count(ModelCallLog.id)).where(*error_filter)
    )
    total_errors = total_result.scalar() or 0

    # Classify by type
    err_rows = await db.execute(
        select(ModelCallLog.error_message).where(*error_filter)
    )
    type_counts: dict[str, int] = {}
    for (msg,) in err_rows.all():
        etype = _classify_error_type(msg)
        type_counts[etype] = type_counts.get(etype, 0) + 1
    by_type = [
        {"type": t, "count": c}
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
    ]

    # By agent
    by_agent_result = await db.execute(
        select(ModelCallLog.agent_name, func.count(ModelCallLog.id))
        .where(*error_filter)
        .group_by(ModelCallLog.agent_name)
        .order_by(func.count(ModelCallLog.id).desc())
    )
    by_agent = [
        {"agent": row[0], "error_count": row[1]}
        for row in by_agent_result.all()
    ]

    # Daily trend
    trend_result = await db.execute(
        select(
            func.date(ModelCallLog.created_at),
            func.count(ModelCallLog.id),
        )
        .where(*error_filter)
        .group_by(func.date(ModelCallLog.created_at))
        .order_by(func.date(ModelCallLog.created_at))
    )
    trend = [
        {"date": str(row[0]), "error_count": row[1]}
        for row in trend_result.all()
    ]

    return {
        "period": period,
        "total_errors": total_errors,
        "by_type": by_type,
        "by_agent": by_agent,
        "trend": trend,
    }


async def get_latency_stats(db: AsyncSession, period: str = "today") -> dict:
    _validate_period(period)
    start_date = _period_start_date(period)

    result = await db.execute(
        text("""
            SELECT
                COALESCE(AVG(latency_ms), 0)::int,
                COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0)::int,
                COALESCE(percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms), 0)::int
            FROM model_call_logs
            WHERE created_at >= :start_date AND success = true
        """),
        {"start_date": start_date},
    )
    row = result.one()

    by_agent_result = await db.execute(
        text("""
            SELECT
                agent_name,
                AVG(latency_ms)::int,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)::int
            FROM model_call_logs
            WHERE created_at >= :start_date AND success = true
            GROUP BY agent_name
        """),
        {"start_date": start_date},
    )

    return {
        "period": period,
        "avg_latency_ms": row[0],
        "p95_latency_ms": row[1],
        "p99_latency_ms": row[2],
        "by_agent": [
            {"agent": r[0], "avg_ms": r[1], "p95_ms": r[2]}
            for r in by_agent_result.all()
        ],
    }


# ---------------------------------------------------------------------------
# Phase 5: Corrections
# ---------------------------------------------------------------------------


async def get_correction_detail(db: AsyncSession, correction_id: int) -> dict:
    result = await db.execute(
        select(ManualCorrection).where(ManualCorrection.id == correction_id)
    )
    correction = result.scalar_one_or_none()
    if not correction:
        raise AppError("CORRECTION_NOT_FOUND", "纠偏记录不存在", status_code=404)

    context: dict = {}

    if correction.target_type == "ocr":
        upload_result = await db.execute(
            select(StudyUpload).where(StudyUpload.id == correction.target_id)
        )
        upload_obj = upload_result.scalar_one_or_none()
        if upload_obj:
            context = {
                "original_url": upload_obj.original_url,
                "thumbnail_url": upload_obj.thumbnail_url,
                "upload_type": upload_obj.upload_type,
                "ocr_result": upload_obj.ocr_result,
                "ocr_error": upload_obj.ocr_error,
            }
    elif correction.target_type == "knowledge":
        original = correction.original_content or {}
        sid = original.get("student_id")
        kpid = original.get("knowledge_point_id")
        if sid and kpid:
            kp_result = await db.execute(
                select(KnowledgeTree.name, Subject.name)
                .join(Subject, KnowledgeTree.subject_id == Subject.id)
                .where(KnowledgeTree.id == kpid)
            )
            kp_row = kp_result.one_or_none()
            if kp_row:
                context = {
                    "knowledge_point_name": kp_row[0],
                    "subject_name": kp_row[1],
                    "current_status": original.get("status"),
                }
    elif correction.target_type == "plan":
        plan_result = await db.execute(
            select(DailyPlan)
            .options(selectinload(DailyPlan.tasks))
            .where(DailyPlan.id == correction.target_id)
        )
        plan_obj = plan_result.scalar_one_or_none()
        if plan_obj:
            context = {
                "plan_date": str(plan_obj.plan_date),
                "learning_mode": plan_obj.learning_mode,
                "tasks": [
                    {
                        "id": t.id,
                        "subject_id": t.subject_id,
                        "task_type": t.task_type,
                        "task_content": t.task_content,
                        "sequence": t.sequence,
                    }
                    for t in plan_obj.tasks
                ],
            }

    from app.schemas.admin import CorrectionOut

    return {
        **CorrectionOut.model_validate(correction).model_dump(),
        "context": context,
    }


async def get_correction_logs(
    db: AsyncSession, page: int, page_size: int
) -> tuple[list[ManualCorrection], int]:
    resolved_filter = ManualCorrection.status == "resolved"
    count_result = await db.execute(
        select(func.count(ManualCorrection.id)).where(resolved_filter)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ManualCorrection)
        .where(resolved_filter)
        .order_by(ManualCorrection.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return result.scalars().all(), total


async def correct_plan(
    db: AsyncSession,
    admin_user_id: int,
    plan_id: int,
    corrected_tasks: list[dict],
    reason: str | None,
) -> ManualCorrection:
    plan_result = await db.execute(
        select(DailyPlan)
        .options(selectinload(DailyPlan.tasks))
        .where(DailyPlan.id == plan_id)
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise AppError("PLAN_NOT_FOUND", "计划不存在", status_code=404)

    original_tasks = [
        {
            "id": t.id,
            "subject_id": t.subject_id,
            "task_type": t.task_type,
            "task_content": t.task_content,
            "sequence": t.sequence,
        }
        for t in plan.tasks
    ]

    correction = ManualCorrection(
        target_type="plan",
        target_id=plan_id,
        original_content={"tasks": original_tasks},
        corrected_content={"tasks": corrected_tasks},
        correction_reason=reason,
        corrected_by=admin_user_id,
        status="pending",
    )
    db.add(correction)
    await db.flush()
    return correction


async def get_pending_count_by_type(db: AsyncSession) -> dict:
    result = await db.execute(
        select(ManualCorrection.target_type, func.count(ManualCorrection.id))
        .where(ManualCorrection.status == "pending")
        .group_by(ManualCorrection.target_type)
    )
    counts = {row[0]: row[1] for row in result.all()}
    return {
        "ocr": counts.get("ocr", 0),
        "knowledge": counts.get("knowledge", 0),
        "plan": counts.get("plan", 0),
        "total": sum(counts.values()),
    }
