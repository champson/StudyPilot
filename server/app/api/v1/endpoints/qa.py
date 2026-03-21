import math

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_student_id, require_student
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import PaginatedData, PaginatedResponse, SuccessResponse
from app.schemas.qa import (
    ChatRequest,
    ChatResponse,
    QaMessageOut,
    QaSessionListItem,
    QaSessionOut,
)
from app.services import qa as svc

router = APIRouter(prefix="/student/qa", tags=["qa"])


@router.post("/chat", response_model=SuccessResponse[ChatResponse])
async def chat(
    body: ChatRequest,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    session, user_msg, assistant_msg = await svc.chat_sync(
        db,
        student_id,
        body.session_id,
        body.message,
        body.subject_id,
        body.task_id,
        body.attachments,
    )
    return SuccessResponse(
        data=ChatResponse(
            session_id=session.id,
            user_message=QaMessageOut.model_validate(user_msg),
            assistant_message=QaMessageOut.model_validate(assistant_msg),
        )
    )


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    _session, stream = await svc.chat_stream(
        db,
        student_id=student_id,
        session_id=body.session_id,
        message=body.message,
        subject_id=body.subject_id,
        task_id=body.task_id,
        attachments=body.attachments,
    )
    return StreamingResponse(stream, media_type="text/event-stream")


@router.get("/history", response_model=PaginatedResponse[QaSessionListItem])
async def list_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    items, total = await svc.list_sessions(db, student_id, page, page_size)
    return PaginatedResponse(
        data=PaginatedData(
            items=[QaSessionListItem.model_validate(i) for i in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )
    )


@router.get("/sessions/{session_id}", response_model=SuccessResponse[QaSessionOut])
async def get_session_detail(
    session_id: int,
    student_id: int = Depends(get_student_id),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_student),
):
    session = await svc.get_session_detail(db, student_id, session_id)
    return SuccessResponse(data=QaSessionOut.model_validate(session))
