from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import SuccessResponse
from app.schemas.share import ShareContentOut, ShareValidateOut
from app.services import share as svc

router = APIRouter(prefix="/share", tags=["share"])


@router.get("/{token}", response_model=SuccessResponse[ShareContentOut])
async def get_share_content(token: str, db: AsyncSession = Depends(get_db)):
    content = await svc.get_share_content(db, token)
    return SuccessResponse(data=ShareContentOut(**content))


@router.get("/{token}/validate", response_model=SuccessResponse[ShareValidateOut])
async def validate_share(token: str):
    result = await svc.validate_share_token(token)
    return SuccessResponse(data=ShareValidateOut(**result))
