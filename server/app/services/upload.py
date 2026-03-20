import hashlib
import os

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.models.upload import StudyUpload
from app.tasks.ocr import process_ocr, run_ocr_pipeline_inline


async def handle_upload(
    db: AsyncSession,
    student_id: int,
    file: UploadFile,
    upload_type: str,
    subject_id: int | None,
) -> StudyUpload:
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    ext = os.path.splitext(file.filename or "file")[1] or ".bin"

    upload_dir = os.path.join(settings.UPLOAD_DIR, str(student_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{file_hash}{ext}")

    with open(file_path, "wb") as f:
        f.write(content)

    upload = StudyUpload(
        student_id=student_id,
        upload_type=upload_type,
        file_hash=file_hash,
        original_url=file_path,
        subject_id=subject_id,
        ocr_status="pending",
    )
    db.add(upload)
    await db.flush()

    await _dispatch_ocr_task(upload.id, db=db, upload=upload)

    return upload


async def list_uploads(
    db: AsyncSession, student_id: int, page: int, page_size: int
) -> tuple[list[StudyUpload], int]:
    conditions = [
        StudyUpload.student_id == student_id,
        StudyUpload.is_deleted == False,  # noqa: E712
    ]

    count_result = await db.execute(
        select(func.count(StudyUpload.id)).where(*conditions)
    )
    total = count_result.scalar() or 0

    base = select(StudyUpload).where(*conditions)

    result = await db.execute(
        base.order_by(StudyUpload.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return result.scalars().all(), total


async def get_ocr_status(
    db: AsyncSession, student_id: int, upload_id: int
) -> StudyUpload:
    result = await db.execute(
        select(StudyUpload).where(
            StudyUpload.id == upload_id,
            StudyUpload.student_id == student_id,
            StudyUpload.is_deleted == False,  # noqa: E712
        )
    )
    upload = result.scalar_one_or_none()
    if not upload:
        raise AppError("UPLOAD_NOT_FOUND", "上传记录不存在", status_code=404)
    return upload


async def retry_ocr(db: AsyncSession, student_id: int, upload_id: int) -> StudyUpload:
    upload = await get_ocr_status(db, student_id, upload_id)
    if upload.ocr_status != "failed":
        raise AppError(
            "UPLOAD_OCR_NOT_FAILED",
            f"当前 OCR 状态为 {upload.ocr_status}，无需重试",
            status_code=400,
            detail={"current_ocr_status": upload.ocr_status},
        )

    upload.ocr_status = "pending"
    upload.ocr_error = None
    await db.flush()

    await _dispatch_ocr_task(upload.id, db=db, upload=upload)
    return upload


async def _dispatch_ocr_task(
    upload_id: int,
    *,
    db: AsyncSession | None = None,
    upload: StudyUpload | None = None,
) -> None:
    try:
        if settings.OCR_SYNC_FALLBACK:
            if db is None or upload is None:
                raise RuntimeError("sync fallback requires live db session and upload record")
            await run_ocr_pipeline_inline(db, upload)
        else:
            process_ocr.delay(upload_id)
    except Exception:
        # Broker 不可用时保持 pending，由测试或后台任务显式触发 pipeline。
        return
