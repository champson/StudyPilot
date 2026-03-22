import asyncio
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.llm.agents.extraction import extract_questions_from_upload
from app.models.subject import Subject
from app.models.system import ManualCorrection
from app.models.upload import StudyUpload
from app.models.user import User
from app.services.knowledge import resolve_knowledge_points_by_names
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)

# OCR task retry configuration
OCR_MAX_RETRIES = 3
OCR_BASE_RETRY_DELAY = 60  # seconds


async def _resolve_admin_user_id(db: AsyncSession | None = None) -> int | None:
    async def _query(session: AsyncSession) -> int | None:
        result = await session.execute(
            select(User).where(User.role == "admin").order_by(User.id.asc())
        )
        admin = result.scalar_one_or_none()
        return admin.id if admin else None

    if db is not None:
        return await _query(db)
    async with async_session_factory() as new_db:
        return await _query(new_db)


async def _mark_processing(upload_id: int) -> StudyUpload | None:
    async with async_session_factory() as db:
        result = await db.execute(select(StudyUpload).where(StudyUpload.id == upload_id))
        upload = result.scalar_one_or_none()
        if upload is None:
            return None
        upload.ocr_status = "processing"
        upload.ocr_error = None
        await db.commit()
        return upload


async def _resolve_subject(
    db: AsyncSession, extracted_payload: dict[str, Any], upload: StudyUpload
) -> tuple[int | None, str | None]:
    subject_id = extracted_payload.get("detected_subject_id") or upload.subject_id
    subject_name = extracted_payload.get("detected_subject")
    if subject_id and not subject_name:
        result = await db.execute(select(Subject).where(Subject.id == subject_id))
        subject = result.scalar_one_or_none()
        subject_name = subject.name if subject else None
    if subject_name and not subject_id:
        result = await db.execute(select(Subject).where(Subject.name == subject_name))
        subject = result.scalar_one_or_none()
        subject_id = subject.id if subject else None
    return subject_id, subject_name


async def _complete_upload(
    db: AsyncSession, upload: StudyUpload, extracted_payload: dict[str, Any]
) -> None:
    subject_id, subject_name = await _resolve_subject(db, extracted_payload, upload)
    knowledge_point_names = list(
        dict.fromkeys(
            name
            for question in extracted_payload.get("questions", [])
            for name in question.get("knowledge_points", [])
            if isinstance(name, str) and name
        )
    )
    knowledge_points = await resolve_knowledge_points_by_names(
        db, knowledge_point_names, subject_id=subject_id
    )
    ocr_result = {
        "extracted_questions": extracted_payload.get("questions", []),
        "subject_detected": subject_name,
        "knowledge_points": [
            {"id": item["id"], "name": item["name"], "confidence": 1.0}
            for item in knowledge_points
        ],
        "raw_text": extracted_payload.get("raw_text"),
    }

    upload.subject_id = subject_id
    upload.ocr_status = "completed"
    upload.ocr_error = None
    upload.ocr_result = ocr_result
    upload.extracted_questions = extracted_payload.get("questions", [])
    upload.knowledge_points = knowledge_points
    await db.flush()


async def _mark_failed(
    db: AsyncSession, upload: StudyUpload, error_message: str
) -> None:
    upload.ocr_status = "failed"
    upload.ocr_error = error_message

    admin_user_id = await _resolve_admin_user_id(db)
    if admin_user_id is not None:
        db.add(
            ManualCorrection(
                target_type="ocr",
                target_id=upload.id,
                original_content=upload.ocr_result,
                corrected_content={
                    "requires_manual_review": True,
                    "error": error_message,
                },
                correction_reason="ocr_failed",
                corrected_by=admin_user_id,
            )
        )
    await db.flush()


async def run_ocr_pipeline_inline(
    db: AsyncSession,
    upload: StudyUpload,
    *,
    raise_on_error: bool = False,
) -> None:
    upload.ocr_status = "processing"
    upload.ocr_error = None
    await db.flush()

    subject_name = None
    if upload.subject_id:
        subject_result = await db.execute(select(Subject).where(Subject.id == upload.subject_id))
        subject = subject_result.scalar_one_or_none()
        subject_name = subject.name if subject else None

    try:
        payload = await extract_questions_from_upload(
            file_path=upload.original_url,
            subject_id=upload.subject_id,
            subject_name=subject_name,
            db=db,
            student_id=upload.student_id,
        )
    except Exception as exc:
        if raise_on_error:
            raise
        await _mark_failed(db, upload, str(exc))
        return

    await _complete_upload(db, upload, payload)


async def run_ocr_pipeline(upload_id: int, *, raise_on_error: bool = False) -> None:
    async with async_session_factory() as db:
        result = await db.execute(select(StudyUpload).where(StudyUpload.id == upload_id))
        upload = result.scalar_one_or_none()
        if upload is None:
            return
        await run_ocr_pipeline_inline(db, upload, raise_on_error=raise_on_error)
        await db.commit()


@celery.task(bind=True, max_retries=OCR_MAX_RETRIES, default_retry_delay=OCR_BASE_RETRY_DELAY)
def process_ocr(self, upload_id: int):
    """Process OCR for an uploaded file.
    
    Retry configuration:
    - max_retries: 3
    - Exponential backoff: 60s * (2 ^ retry_count)
    - Final failure: Mark upload as 'ocr_failed'
    """
    try:
        asyncio.run(run_ocr_pipeline(upload_id, raise_on_error=True))
    except Exception as exc:
        retry_count = self.request.retries
        
        if retry_count < self.max_retries:
            # Exponential backoff: 60, 120, 240 seconds
            countdown = OCR_BASE_RETRY_DELAY * (2 ** retry_count)
            logger.warning(
                "OCR task failed, retrying. upload_id=%s, retry=%d/%d, "
                "next_retry_in=%ds, error=%s",
                upload_id,
                retry_count + 1,
                self.max_retries,
                countdown,
                str(exc),
            )
            raise self.retry(exc=exc, countdown=countdown)
        
        # Final failure after all retries exhausted
        error_message = str(exc)
        logger.error(
            "OCR task failed after all retries. upload_id=%s, error=%s",
            upload_id,
            error_message,
        )

        async def _finalize_failure():
            async with async_session_factory() as db:
                result = await db.execute(select(StudyUpload).where(StudyUpload.id == upload_id))
                upload = result.scalar_one_or_none()
                if upload is None:
                    return
                upload.ocr_status = "failed"
                upload.ocr_error = error_message

                admin_user_id = await _resolve_admin_user_id()
                if admin_user_id is not None:
                    db.add(
                        ManualCorrection(
                            target_type="ocr",
                            target_id=upload.id,
                            original_content=upload.ocr_result,
                            corrected_content={
                                "requires_manual_review": True,
                                "error": error_message,
                            },
                            correction_reason="ocr_failed_after_retries",
                            corrected_by=admin_user_id,
                        )
                    )
                await db.commit()

        asyncio.run(_finalize_failure())
