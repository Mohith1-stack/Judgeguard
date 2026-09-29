from fastapi import APIRouter

from app.api.adaptive import router as adaptive_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.events import router as events_router
from app.api.integrity import router as integrity_router
from app.api.integrity_step11 import router as step11_integrity_router
from app.api.influence import router as influence_router
from app.api.judging import router as judging_router
from app.api.public import router as public_router
from app.api.submissions import router as submissions_router
from app.api.stability import router as stability_router
from app.api.t4 import router as t4_router
from app.api.teams import router as teams_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(events_router)
router.include_router(teams_router)
router.include_router(submissions_router)
router.include_router(stability_router)
router.include_router(adaptive_router)
router.include_router(judging_router)
router.include_router(integrity_router)
router.include_router(step11_integrity_router)
router.include_router(influence_router)
router.include_router(public_router)
router.include_router(admin_router)
router.include_router(t4_router)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/db")
def database_health():
    from sqlalchemy import text
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok"}
