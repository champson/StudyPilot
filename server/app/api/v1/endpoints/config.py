from fastapi import APIRouter

from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/config", tags=["config"])

TEXTBOOK_VERSIONS = [
    {"id": "renjiaoA", "name": "人教版A"},
    {"id": "renjiaoB", "name": "人教版B"},
    {"id": "sujiaoban", "name": "苏教版"},
    {"id": "beishipan", "name": "北师版"},
    {"id": "hushipan", "name": "沪教版"},
]


@router.get("/textbook-versions", response_model=SuccessResponse[list[dict]])
async def get_textbook_versions():
    return SuccessResponse(data=TEXTBOOK_VERSIONS)
