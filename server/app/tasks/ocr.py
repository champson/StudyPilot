import time

from app.tasks.celery_app import celery


@celery.task(bind=True, max_retries=2)
def process_ocr(self, upload_id: int):
    # Stub: simulate processing delay
    time.sleep(3)

    # In a real implementation, this would:
    # 1. Load the file from disk
    # 2. Call an OCR service
    # 3. Parse results and extract questions
    # For now, update DB synchronously via a new connection

    from sqlalchemy import create_engine, text

    from app.core.config import settings

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE study_uploads SET ocr_status = :status, ocr_result = :result "
                "WHERE id = :id"
            ),
            {
                "status": "completed",
                "result": '{"text": "Stub OCR 结果", "questions": []}',
                "id": upload_id,
            },
        )
        conn.commit()
    engine.dispose()
