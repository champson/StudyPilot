from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_student_id, require_student
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.student_profile import (
    OnboardingStatusOut,
    OnboardingSubmit,
    OnboardingSubmitOut,
    StudentProfileCreate,
    StudentProfileOut,
    StudentProfileUpdate,
)
from app.services import student_profile as svc

router = APIRouter(prefix="/student", tags=["student-profile"])


@router.get("/profile", response_model=SuccessResponse[StudentProfileOut])
async def get_profile(
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    profile = await svc.get_profile(db, student_id)
    return SuccessResponse(data=StudentProfileOut.model_validate(profile))


@router.post("/profile", response_model=SuccessResponse[StudentProfileOut])
async def create_profile(
    body: StudentProfileCreate,
    user: User = Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    profile = await svc.create_profile(db, user.id, body)
    return SuccessResponse(data=StudentProfileOut.model_validate(profile))


@router.patch("/profile", response_model=SuccessResponse[StudentProfileOut])
async def update_profile(
    body: StudentProfileUpdate,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    profile = await svc.update_profile(db, student_id, body)
    return SuccessResponse(data=StudentProfileOut.model_validate(profile))


@router.post("/onboarding/submit", response_model=SuccessResponse[OnboardingSubmitOut])
async def submit_onboarding(
    body: OnboardingSubmit,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    result = await svc.submit_onboarding(db, student_id, body)
    return SuccessResponse(data=OnboardingSubmitOut(**result))


@router.get("/onboarding/status", response_model=SuccessResponse[OnboardingStatusOut])
async def get_onboarding_status(
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    completed = await svc.get_onboarding_status(db, student_id)
    return SuccessResponse(data=OnboardingStatusOut(onboarding_completed=completed))
