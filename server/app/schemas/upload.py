from datetime import datetime

from pydantic import BaseModel


class UploadOut(BaseModel):
    id: int
    student_id: int
    upload_type: str
    file_hash: str
    original_url: str
    thumbnail_url: str | None = None
    ocr_result: dict | None = None
    extracted_questions: list | None = []
    subject_id: int | None = None
    knowledge_points: list | None = []
    ocr_status: str
    ocr_error: str | None = None
    is_manual_corrected: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OcrStatusOut(BaseModel):
    upload_id: int
    ocr_status: str
    ocr_result: dict | None = None
    ocr_error: str | None = None
