from datetime import datetime

from pydantic import BaseModel


class KnowledgeStatusItemOut(BaseModel):
    knowledge_point_id: int
    knowledge_point_name: str
    subject_id: int
    subject_name: str
    level: int
    status: str
    importance_score: float | None = None
    last_updated_at: datetime
    is_manual_corrected: bool


class KnowledgeStatusOut(BaseModel):
    total: int
    by_status: dict[str, int]
    items: list[KnowledgeStatusItemOut]
