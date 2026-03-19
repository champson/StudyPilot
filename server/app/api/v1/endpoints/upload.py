import math

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.api.v1.deps import get_student_id, require_student
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import PaginatedData, PaginatedResponse, SuccessResponse
from app.schemas.upload import OcrStatusOut, UploadOut
from app.services import upload as svc

router = APIRouter(prefix="/student/material", tags=["upload"])


@router.post("/upload")
async def upload_material(
    file: UploadFile = File(...),
    upload_type: str = Form(...),
    subject_id: int | None = Form(None),
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    upload = await svc.handle_upload(db, student_id, file, upload_type, subject_id)
    return JSONResponse(
        status_code=202,
        content={
            "data": {
                "resource_id": upload.id,
                "status": upload.ocr_status,
                "poll_url": f"/api/v1/student/material/{upload.id}/ocr-status",
                "message": "文件已上传，正在识别中，请稍后查询结果",
            }
        },
    )


@router.get("/list", response_model=PaginatedResponse[UploadOut])
async def list_materials(
    page: int = 1,
    page_size: int = 20,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    items, total = await svc.list_uploads(db, student_id, page, page_size)
    return PaginatedResponse(
        data=PaginatedData(
            items=[UploadOut.model_validate(i) for i in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )
    )


@router.get("/{upload_id}/ocr-status", response_model=SuccessResponse[OcrStatusOut])
async def get_ocr_status(
    upload_id: int,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    upload = await svc.get_ocr_status(db, student_id, upload_id)
    return SuccessResponse(
        data=OcrStatusOut(
            upload_id=upload.id,
            ocr_status=upload.ocr_status,
            ocr_result=upload.ocr_result,
            ocr_error=upload.ocr_error,
        )
    )


@router.post("/{upload_id}/retry-ocr")
async def retry_ocr(
    upload_id: int,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    upload = await svc.retry_ocr(db, student_id, upload_id)
    return JSONResponse(
        status_code=202,
        content={
            "data": {
                "resource_id": upload.id,
                "status": upload.ocr_status,
                "poll_url": f"/api/v1/student/material/{upload.id}/ocr-status",
                "message": "已重新提交识别任务，请稍后查询结果",
            }
        },
    )
