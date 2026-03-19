from datetime import datetime

from pydantic import BaseModel


class KnowledgeStatusOut(BaseModel):
    id: int
    student_id: int
    knowledge_point_id: int
    status: str
    last_update_reason: str | None = None
    last_updated_at: datetime
    is_manual_corrected: bool
    point_name: str | None = None
    subject_id: int | None = None

    model_config = {"from_attributes": True}
