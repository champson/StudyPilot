from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    config,
    error_book,
    health,
    knowledge,
    parent,
    plan,
    qa,
    report,
    share,
    student_profile,
    upload,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(config.router)
api_router.include_router(student_profile.router)
api_router.include_router(plan.router)
api_router.include_router(upload.router)
api_router.include_router(qa.router)
api_router.include_router(error_book.router)
api_router.include_router(knowledge.router)
api_router.include_router(report.router)
api_router.include_router(share.router)
api_router.include_router(parent.router)
api_router.include_router(admin.router)
