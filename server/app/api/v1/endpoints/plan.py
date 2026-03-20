from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_student_id, require_student
from app.core.database import get_db
from app.core.exceptions import AppError
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.plan import (
    DailyPlanOut,
    PlanGenerateRequest,
    PlanModeUpdate,
    PlanTaskOut,
    TaskStatusUpdate,
)
from app.services import plan as svc

router = APIRouter(prefix="/student/plan", tags=["plan"])


@router.post("/generate", response_model=SuccessResponse[DailyPlanOut])
async def generate_plan(
    body: PlanGenerateRequest,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    plan = await svc.generate_plan(
        db,
        student_id,
        body.available_minutes,
        body.learning_mode,
        body.force_regenerate,
    )
    return SuccessResponse(data=DailyPlanOut.model_validate(plan))


@router.get("/today", response_model=SuccessResponse[DailyPlanOut | None])
async def get_today_plan(
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    plan = await svc.get_today_plan(db, student_id)
    data = DailyPlanOut.model_validate(plan) if plan else None
    return SuccessResponse(data=data)


@router.patch("/mode", response_model=SuccessResponse[DailyPlanOut])
async def update_mode(
    body: PlanModeUpdate,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    plan = await svc.update_plan_mode(db, student_id, body.learning_mode)
    return SuccessResponse(data=DailyPlanOut.model_validate(plan))


@router.patch("/tasks/{task_id}", response_model=SuccessResponse[PlanTaskOut])
async def update_task_status(
    task_id: int,
    body: TaskStatusUpdate,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    if body.status not in svc.TASK_STATUS_ORDER:
        raise AppError("INVALID_STATUS", f"无效状态: {body.status}", status_code=400)
    task = await svc.update_task_status(db, student_id, task_id, body.status)
    return SuccessResponse(data=PlanTaskOut.model_validate(task))
