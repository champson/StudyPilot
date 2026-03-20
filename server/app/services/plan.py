from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.llm.agents.planning import generate_plan_payload
from app.models.error_book import ErrorBook
from app.models.plan import DailyPlan, PlanTask
from app.models.report import SubjectRiskState
from app.models.student_profile import ExamRecord, StudentProfile
from app.models.subject import Subject
from app.models.upload import StudyUpload
from app.services.knowledge import aggregate_knowledge_mastery_by_subject

TASK_STATUS_ORDER = {"pending": 0, "entered": 1, "executed": 2, "completed": 3}
TASK_NEXT_STEP = {"pending": "entered", "entered": "executed", "executed": "completed"}
WEEKDAY_MODE = "workday_follow"
WEEKEND_MODE = "weekend_review"


def validate_transition(current: str, target: str) -> bool:
    """Allow sequential step or direct jump to completed."""
    if current not in TASK_STATUS_ORDER or target not in TASK_STATUS_ORDER:
        return False
    if target == "completed" and current != "completed":
        return True
    return TASK_NEXT_STEP.get(current) == target


def _derive_mode(preferred: str | None, today: date) -> str:
    if preferred:
        return preferred
    return WEEKDAY_MODE if today.weekday() < 5 else WEEKEND_MODE


async def _get_subject_catalog(
    db: AsyncSession, profile: StudentProfile
) -> list[dict[str, Any]]:
    subject_result = await db.execute(
        select(Subject).where(Subject.is_active == True).order_by(Subject.display_order)  # noqa: E712
    )
    subjects = subject_result.scalars().all()
    if not profile.subject_combination:
        return [
            {"subject_id": subject.id, "subject_name": subject.name, "subject_code": subject.code}
            for subject in subjects
        ]

    allowed_refs = {str(item) for item in profile.subject_combination}
    filtered = [
        subject
        for subject in subjects
        if str(subject.id) in allowed_refs
        or subject.code in allowed_refs
        or subject.name in allowed_refs
    ]
    if not filtered:
        filtered = subjects
    return [
        {"subject_id": subject.id, "subject_name": subject.name, "subject_code": subject.code}
        for subject in filtered
    ]


async def collect_planning_context(
    db: AsyncSession, student_id: int, available_minutes: int, learning_mode: str | None
) -> dict[str, Any]:
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.id == student_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile or not profile.onboarding_completed:
        raise AppError(
            "ONBOARDING_NOT_COMPLETED",
            "请先完成入学问卷，才能生成个性化学习计划",
            status_code=400,
            detail={"redirect": "/onboarding"},
        )

    today = date.today()
    mode = _derive_mode(learning_mode, today)
    subjects = await _get_subject_catalog(db, profile)

    knowledge_mastery = await aggregate_knowledge_mastery_by_subject(db, student_id)

    risk_result = await db.execute(
        select(SubjectRiskState).where(SubjectRiskState.student_id == student_id)
    )
    latest_risks: dict[int, SubjectRiskState] = {}
    for risk in sorted(
        risk_result.scalars().all(),
        key=lambda item: item.effective_week,
        reverse=True,
    ):
        latest_risks.setdefault(risk.subject_id, risk)

    recent_errors: list[dict[str, Any]] = []
    error_result = await db.execute(
        select(ErrorBook).where(
            ErrorBook.student_id == student_id,
            ErrorBook.is_deleted == False,  # noqa: E712
            ErrorBook.created_at >= datetime.now(UTC) - timedelta(days=7),
        )
    )
    error_counter: dict[tuple[int, int | None], dict[str, Any]] = {}
    for item in error_result.scalars().all():
        knowledge_point_id = None
        if isinstance(item.knowledge_points, list) and item.knowledge_points:
            first = item.knowledge_points[0]
            if isinstance(first, dict):
                knowledge_point_id = first.get("id")
        key = (item.subject_id, knowledge_point_id)
        bucket = error_counter.setdefault(
            key,
            {
                "subject_id": item.subject_id,
                "knowledge_point_id": knowledge_point_id,
                "error_count": 0,
            },
        )
        bucket["error_count"] += 1
    recent_errors = list(error_counter.values())

    upload_result = await db.execute(
        select(StudyUpload).where(
            StudyUpload.student_id == student_id,
            StudyUpload.is_deleted == False,  # noqa: E712
            StudyUpload.ocr_status == "completed",
            StudyUpload.created_at >= datetime.combine(today, datetime.min.time(), tzinfo=UTC),
        )
    )
    recent_uploads = []
    for upload in upload_result.scalars().all():
        recent_uploads.append(
            {
                "subject_id": upload.subject_id,
                "upload_type": upload.upload_type,
                "extracted_topics": [
                    item.get("name")
                    for item in (upload.knowledge_points or [])
                    if isinstance(item, dict) and item.get("name")
                ],
            }
        )

    exam_result = await db.execute(
        select(ExamRecord).where(
            ExamRecord.student_id == student_id,
            ExamRecord.exam_date >= today,
            ExamRecord.exam_date <= today + timedelta(days=14),
        )
    )
    upcoming_exams = [
        {
            "subject_id": exam.subject_id,
            "exam_type": exam.exam_type,
            "exam_date": exam.exam_date.isoformat(),
        }
        for exam in exam_result.scalars().all()
    ]

    return {
        "profile": {
            "grade": profile.grade,
            "subject_combination": profile.subject_combination or [],
            "textbook_version": profile.textbook_version,
        },
        "subjects": subjects,
        "knowledge_mastery": knowledge_mastery,
        "subject_risks": [
            {
                "subject_id": risk.subject_id,
                "subject_name": next(
                    (
                        subject["subject_name"]
                        for subject in subjects
                        if subject["subject_id"] == risk.subject_id
                    ),
                    "",
                ),
                "risk_level": risk.risk_level,
            }
            for risk in latest_risks.values()
        ],
        "recent_errors": recent_errors,
        "recent_uploads": recent_uploads,
        "upcoming_exams": upcoming_exams,
        "available_minutes": available_minutes,
        "learning_mode": mode,
        "today_weekday": today.weekday() + 1,
    }


def _plan_source(context: dict[str, Any]) -> tuple[str, bool]:
    if context.get("recent_uploads"):
        return "upload_corrected", False
    if (
        context.get("recent_errors")
        or context.get("knowledge_mastery")
        or context.get("upcoming_exams")
    ):
        return "history_inferred", True
    return "generic_fallback", True


async def _enrich_plan(plan: DailyPlan, db: AsyncSession) -> DailyPlan:
    subject_ids = {task.subject_id for task in plan.tasks}
    if isinstance(plan.recommended_subjects, list):
        subject_ids.update(
            item.get("subject_id")
            for item in plan.recommended_subjects
            if isinstance(item, dict)
        )
    subject_ids = {subject_id for subject_id in subject_ids if subject_id is not None}
    if subject_ids:
        subject_result = await db.execute(
            select(Subject).where(Subject.id.in_(subject_ids))
        )
        subject_map = {subject.id: subject.name for subject in subject_result.scalars().all()}
    else:
        subject_map = {}

    recommended_subjects = plan.recommended_subjects
    if isinstance(recommended_subjects, dict) and recommended_subjects.get("subject_ids"):
        recommended_subjects = [
            {
                "subject_id": subject_id,
                "subject_name": subject_map.get(subject_id),
                "reasons": [],
            }
            for subject_id in recommended_subjects["subject_ids"]
        ]
    elif isinstance(recommended_subjects, list):
        for item in recommended_subjects:
            if isinstance(item, dict) and item.get("subject_id") is not None:
                item.setdefault("subject_name", subject_map.get(item["subject_id"]))
                item.setdefault("reasons", [])

    setattr(plan, "recommended_subjects", recommended_subjects or [])
    setattr(
        plan,
        "warning",
        "连续7天未上传新内容，建议补充上传以恢复个性化准确度"
        if plan.source == "generic_fallback"
        else None,
    )
    for task in plan.tasks:
        setattr(task, "subject_name", subject_map.get(task.subject_id))
    return plan


async def generate_plan(
    db: AsyncSession,
    student_id: int,
    available_minutes: int,
    learning_mode: str | None,
    force_regenerate: bool = False,
) -> DailyPlan:
    today = date.today()
    existing = await db.execute(
        select(DailyPlan).where(
            DailyPlan.student_id == student_id,
            DailyPlan.plan_date == today,
            DailyPlan.is_deleted == False,  # noqa: E712
        )
    )
    existing_plan = existing.scalar_one_or_none()
    if existing_plan and not force_regenerate:
        raise AppError("PLAN_EXISTS", "今日计划已存在", status_code=409)
    if existing_plan and force_regenerate:
        existing_plan.is_deleted = True

    context = await collect_planning_context(db, student_id, available_minutes, learning_mode)
    plan_payload = await generate_plan_payload(context, db=db, student_id=student_id)
    source, is_history_inferred = _plan_source(context)

    plan = DailyPlan(
        student_id=student_id,
        plan_date=today,
        learning_mode=context["learning_mode"],
        system_recommended_mode=context["learning_mode"],
        available_minutes=available_minutes,
        source=source,
        is_history_inferred=is_history_inferred,
        recommended_subjects=plan_payload.get("recommended_subjects", []),
        plan_content=plan_payload,
        status="generated",
    )
    db.add(plan)
    await db.flush()

    subject_ids = {
        item["subject_id"]
        for item in plan_payload.get("recommended_subjects", [])
        if isinstance(item, dict) and item.get("subject_id") is not None
    }
    default_subject_id = next(iter(subject_ids), None)

    for task_data in plan_payload.get("tasks", []):
        task = PlanTask(
            plan_id=plan.id,
            subject_id=int(task_data.get("subject_id") or default_subject_id or 1),
            task_type=task_data.get("task_type", "review"),
            task_content={
                "title": task_data.get("title"),
                "description": task_data.get("description"),
                "knowledge_point_ids": task_data.get("knowledge_points", []),
            },
            sequence=int(task_data.get("sequence", 1)),
            estimated_minutes=task_data.get("estimated_minutes"),
            status="pending",
        )
        db.add(task)
    await db.flush()

    result = await db.execute(
        select(DailyPlan)
        .options(selectinload(DailyPlan.tasks))
        .where(DailyPlan.id == plan.id)
    )
    created_plan = result.scalar_one()
    return await _enrich_plan(created_plan, db)


async def get_today_plan(db: AsyncSession, student_id: int) -> DailyPlan | None:
    today = date.today()
    result = await db.execute(
        select(DailyPlan)
        .options(selectinload(DailyPlan.tasks))
        .where(
            DailyPlan.student_id == student_id,
            DailyPlan.plan_date == today,
            DailyPlan.is_deleted == False,  # noqa: E712
        )
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        return None
    return await _enrich_plan(plan, db)


async def update_plan_mode(
    db: AsyncSession, student_id: int, learning_mode: str
) -> DailyPlan:
    plan = await get_today_plan(db, student_id)
    if not plan:
        raise AppError("PLAN_NOT_FOUND", "今日计划不存在", status_code=404)
    plan.learning_mode = learning_mode
    await db.flush()
    return await _enrich_plan(plan, db)


async def update_task_status(
    db: AsyncSession, student_id: int, task_id: int, target_status: str
) -> PlanTask:
    result = await db.execute(select(PlanTask).where(PlanTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise AppError("TASK_NOT_FOUND", "任务不存在", status_code=404)

    plan_result = await db.execute(select(DailyPlan).where(DailyPlan.id == task.plan_id))
    plan = plan_result.scalar_one_or_none()
    if not plan or plan.student_id != student_id:
        raise AppError("TASK_NOT_FOUND", "任务不存在", status_code=404)

    if not validate_transition(task.status, target_status):
        raise AppError(
            "INVALID_STATUS_TRANSITION",
            f"不允许从 {task.status} 转换到 {target_status}",
            status_code=400,
        )

    now = datetime.now(UTC)
    if task.status == "pending" and target_status != "pending":
        task.started_at = now

    if target_status == "completed":
        task.completed_at = now
        if task.started_at:
            task.duration_minutes = int((now - task.started_at).total_seconds() / 60)

    task.status = target_status
    subject_result = await db.execute(select(Subject).where(Subject.id == task.subject_id))
    subject = subject_result.scalar_one_or_none()
    setattr(task, "subject_name", subject.name if subject else None)
    await db.flush()
    return task
