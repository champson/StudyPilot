import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_student_id, require_student
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import PaginatedData, PaginatedResponse, SuccessResponse
from app.schemas.error_book import (
    BatchRecallRequest,
    ErrorBookOut,
    ErrorSummaryOut,
    RecallResult,
)
from app.services import error_book as svc

router = APIRouter(prefix="/student/errors", tags=["error-book"])


@router.get("", response_model=PaginatedResponse[ErrorBookOut])
async def list_errors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    subject_id: int | None = None,
    is_recalled: bool | None = None,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    items, total = await svc.list_errors(
        db, student_id, page, page_size, subject_id, is_recalled
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=[ErrorBookOut.model_validate(i) for i in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )
    )


@router.get("/summary", response_model=SuccessResponse[ErrorSummaryOut])
async def get_summary(
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    summary = await svc.get_error_summary(db, student_id)
    return SuccessResponse(data=ErrorSummaryOut(**summary))


@router.get("/{error_id}", response_model=SuccessResponse[ErrorBookOut])
async def get_error_detail(
    error_id: int,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    error = await svc.get_error_detail(db, student_id, error_id)
    return SuccessResponse(data=ErrorBookOut.model_validate(error))


@router.post("/{error_id}/recall", response_model=SuccessResponse[ErrorBookOut])
async def recall_error(
    error_id: int,
    body: RecallResult,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    error = await svc.recall_error(db, student_id, error_id, body.result)
    return SuccessResponse(data=ErrorBookOut.model_validate(error))


@router.post("/batch-recall", response_model=SuccessResponse[list[ErrorBookOut]])
async def batch_recall(
    body: BatchRecallRequest,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    errors = await svc.batch_recall(db, student_id, body.items)
    return SuccessResponse(data=[ErrorBookOut.model_validate(e) for e in errors])
