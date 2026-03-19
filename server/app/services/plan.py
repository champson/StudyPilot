from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.models.plan import DailyPlan, PlanTask
from app.models.student_profile import StudentProfile

TASK_STATUS_ORDER = {"pending": 0, "entered": 1, "executed": 2, "completed": 3}
# Sequential transitions: pending→entered→executed→completed
TASK_NEXT_STEP = {"pending": "entered", "entered": "executed", "executed": "completed"}
WEEKDAY_MODE = "workday_follow"
WEEKEND_MODE = "weekend_review"


def validate_transition(current: str, target: str) -> bool:
    """Allow sequential step OR skip directly to completed from any state."""
    if current not in TASK_STATUS_ORDER or target not in TASK_STATUS_ORDER:
        return False
    if target == "completed" and current != "completed":
        return True
    return TASK_NEXT_STEP.get(current) == target


async def generate_plan_stub(
    db: AsyncSession, student_id: int, available_minutes: int, learning_mode: str | None
) -> DailyPlan:
    # Check onboarding completed
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.id == student_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile or not profile.onboarding_completed:
        raise AppError(
            "ONBOARDING_NOT_COMPLETED",
            "请先完成入学问卷，才能生成个性化学习计划",
            status_code=400,
        )

    today = date.today()

    # Check for existing active plan
    existing = await db.execute(
        select(DailyPlan).where(
            DailyPlan.student_id == student_id,
            DailyPlan.plan_date == today,
            DailyPlan.is_deleted == False,  # noqa: E712
        )
    )
    if existing.scalar_one_or_none():
        raise AppError("PLAN_EXISTS", "今日计划已存在", status_code=409)

    mode = learning_mode or (
        WEEKDAY_MODE if today.weekday() < 5 else WEEKEND_MODE
    )

    plan = DailyPlan(
        student_id=student_id,
        plan_date=today,
        learning_mode=mode,
        system_recommended_mode=mode,
        available_minutes=available_minutes,
        source="generic_fallback",
        is_history_inferred=False,
        recommended_subjects={"subject_ids": [1, 2]},
        plan_content={"description": "Stub 计划，Phase 3 将替换为 AI 生成"},
        status="generated",
    )
    db.add(plan)
    await db.flush()

    # Create 2-3 mock tasks
    stub_tasks = [
        PlanTask(
            plan_id=plan.id,
            subject_id=1,
            task_type="review",
            task_content={"title": "复习语文课文", "detail": "Stub 任务"},
            sequence=1,
            estimated_minutes=30,
            status="pending",
        ),
        PlanTask(
            plan_id=plan.id,
            subject_id=2,
            task_type="exercise",
            task_content={"title": "数学练习题", "detail": "Stub 任务"},
            sequence=2,
            estimated_minutes=40,
            status="pending",
        ),
        PlanTask(
            plan_id=plan.id,
            subject_id=1,
            task_type="error_review",
            task_content={"title": "语文错题回顾", "detail": "Stub 任务"},
            sequence=3,
            estimated_minutes=20,
            status="pending",
        ),
    ]
    db.add_all(stub_tasks)
    await db.flush()

    # Reload with tasks
    result = await db.execute(
        select(DailyPlan)
        .options(selectinload(DailyPlan.tasks))
        .where(DailyPlan.id == plan.id)
    )
    return result.scalar_one()


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
    return result.scalar_one_or_none()


async def update_plan_mode(
    db: AsyncSession, student_id: int, learning_mode: str
) -> DailyPlan:
    plan = await get_today_plan(db, student_id)
    if not plan:
        raise AppError("PLAN_NOT_FOUND", "今日计划不存在", status_code=404)
    plan.learning_mode = learning_mode
    await db.flush()
    return plan


async def update_task_status(
    db: AsyncSession, student_id: int, task_id: int, target_status: str
) -> PlanTask:
    result = await db.execute(select(PlanTask).where(PlanTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise AppError("TASK_NOT_FOUND", "任务不存在", status_code=404)

    # Verify ownership
    plan_result = await db.execute(
        select(DailyPlan).where(DailyPlan.id == task.plan_id)
    )
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

    # Record timestamps on transitions
    if task.status == "pending" and target_status != "pending":
        task.started_at = now

    if target_status == "completed":
        task.completed_at = now
        if task.started_at:
            task.duration_minutes = int((now - task.started_at).total_seconds() / 60)

    task.status = target_status
    await db.flush()
    return task
