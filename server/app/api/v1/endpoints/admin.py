import math

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_redis, require_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import (
    CorrectionDetailOut,
    CorrectionOut,
    CostTrendOut,
    ErrorStatsOut,
    FallbackStatsOut,
    HealthOut,
    KnowledgeCorrectionRequest,
    LatencyStatsOut,
    MetricsTodayOut,
    ModelCallsOut,
    OcrCorrectionRequest,
    PendingCountByTypeOut,
    PlanCorrectionRequest,
    ResolveCorrectionRequest,
    SystemModeOut,
    SystemModeUpdate,
)
from app.schemas.common import PaginatedData, PaginatedResponse, SuccessResponse
from app.services import admin as svc

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/system/mode", response_model=SuccessResponse[SystemModeOut])
async def get_system_mode(
    r: aioredis.Redis = Depends(get_redis),
    _user: User = Depends(require_admin),
):
    mode = await svc.get_system_mode(r)
    return SuccessResponse(data=SystemModeOut(mode=mode))


@router.post("/system/mode", response_model=SuccessResponse[SystemModeOut])
async def set_system_mode(
    body: SystemModeUpdate,
    r: aioredis.Redis = Depends(get_redis),
    _user: User = Depends(require_admin),
):
    mode = await svc.set_system_mode(r, body.mode)
    return SuccessResponse(data=SystemModeOut(mode=mode))


@router.get("/corrections/pending", response_model=PaginatedResponse[CorrectionOut])
async def get_pending_corrections(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    items, total = await svc.get_pending_corrections(db, page, page_size)
    return PaginatedResponse(
        data=PaginatedData(
            items=[CorrectionOut.model_validate(i) for i in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )
    )


@router.post("/corrections/ocr", response_model=SuccessResponse[CorrectionOut])
async def correct_ocr(
    body: OcrCorrectionRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    correction = await svc.correct_ocr(
        db, user.id, body.upload_id, body.corrected_content, body.reason
    )
    return SuccessResponse(data=CorrectionOut.model_validate(correction))


@router.post("/corrections/knowledge", response_model=SuccessResponse[CorrectionOut])
async def correct_knowledge(
    body: KnowledgeCorrectionRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    correction = await svc.correct_knowledge(
        db, user.id, body.student_id, body.knowledge_point_id, body.new_status, body.reason
    )
    return SuccessResponse(data=CorrectionOut.model_validate(correction))


@router.post("/corrections/{correction_id}/resolve", response_model=SuccessResponse[CorrectionOut])
async def resolve_correction(
    correction_id: int,
    body: ResolveCorrectionRequest | None = None,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    corrected_content = body.corrected_content if body else None
    reason = body.reason if body else None
    correction = await svc.resolve_correction(db, user.id, correction_id, corrected_content, reason)
    return SuccessResponse(data=CorrectionOut.model_validate(correction))


@router.get("/metrics/today", response_model=SuccessResponse[MetricsTodayOut])
async def get_today_metrics(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    metrics = await svc.get_today_metrics(db)
    return SuccessResponse(data=MetricsTodayOut(**metrics))


@router.get("/metrics/health", response_model=SuccessResponse[HealthOut])
async def get_health(
    r: aioredis.Redis = Depends(get_redis),
    _user: User = Depends(require_admin),
):
    health = await svc.get_health(r)
    return SuccessResponse(data=HealthOut(**health))


@router.get("/metrics/model-calls", response_model=SuccessResponse[ModelCallsOut])
async def get_model_calls(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    data = await svc.get_model_calls(db)
    return SuccessResponse(data=ModelCallsOut(**data))


# --- Phase 5: Metrics endpoints ---


@router.get("/metrics/costs", response_model=SuccessResponse[CostTrendOut])
async def get_cost_trend(
    period: str = "today",
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    data = await svc.get_cost_trend(db, period)
    return SuccessResponse(data=CostTrendOut(**data))


@router.get("/metrics/fallbacks", response_model=SuccessResponse[FallbackStatsOut])
async def get_fallback_stats(
    period: str = "today",
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    data = await svc.get_fallback_stats(db, period)
    return SuccessResponse(data=FallbackStatsOut(**data))


@router.get("/metrics/errors", response_model=SuccessResponse[ErrorStatsOut])
async def get_error_stats(
    period: str = "today",
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    data = await svc.get_error_stats(db, period)
    return SuccessResponse(data=ErrorStatsOut(**data))


@router.get("/metrics/latency", response_model=SuccessResponse[LatencyStatsOut])
async def get_latency_stats(
    period: str = "today",
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    data = await svc.get_latency_stats(db, period)
    return SuccessResponse(data=LatencyStatsOut(**data))


# --- Phase 5: Correction endpoints ---


@router.get("/corrections/pending/count", response_model=SuccessResponse[PendingCountByTypeOut])
async def get_pending_count(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    data = await svc.get_pending_count_by_type(db)
    return SuccessResponse(data=PendingCountByTypeOut(**data))


@router.get("/corrections/logs", response_model=PaginatedResponse[CorrectionOut])
async def get_correction_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    items, total = await svc.get_correction_logs(db, page, page_size)
    return PaginatedResponse(
        data=PaginatedData(
            items=[CorrectionOut.model_validate(i) for i in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if total else 0,
        )
    )


@router.post("/corrections/plan", response_model=SuccessResponse[CorrectionOut])
async def correct_plan(
    body: PlanCorrectionRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    correction = await svc.correct_plan(
        db, user.id, body.plan_id, body.corrected_tasks, body.reason
    )
    return SuccessResponse(data=CorrectionOut.model_validate(correction))


@router.get("/corrections/{correction_id}", response_model=SuccessResponse[CorrectionDetailOut])
async def get_correction_detail(
    correction_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_admin),
):
    data = await svc.get_correction_detail(db, correction_id)
    return SuccessResponse(data=CorrectionDetailOut(**data))
