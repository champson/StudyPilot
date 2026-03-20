from datetime import date

import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.knowledge import StudentKnowledgeStatus
from app.models.plan import DailyPlan
from app.models.qa import QaSession
from app.models.student_profile import StudentProfile
from app.models.system import ManualCorrection, ModelCallLog
from app.models.upload import StudyUpload

SYSTEM_MODE_KEY = "system:run_mode"


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
