from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_student_id, require_student
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.knowledge import KnowledgeStatusOut
from app.services import knowledge as svc

router = APIRouter(prefix="/student/knowledge", tags=["knowledge"])


@router.get("/status", response_model=SuccessResponse[KnowledgeStatusOut])
async def get_knowledge_status(
    subject_id: int | None = None,
    status: str | None = Query(default=None),
    min_importance: float | None = Query(default=None, ge=0, le=1),
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    data = await svc.get_knowledge_status(
        db,
        student_id,
        subject_id,
        status,
        min_importance,
    )
    return SuccessResponse(data=KnowledgeStatusOut(**data))
