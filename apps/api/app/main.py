from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api.router import router
from app.config import get_settings
from app.db.session import SessionLocal, engine
from app.models import Base, User, UserRole
from app.security.auth import hash_password


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    settings = get_settings()
    if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
        email = settings.bootstrap_admin_email.strip().lower()
        with SessionLocal() as db:
            existing = db.scalar(select(User).where(User.email == email))
            if existing is None:
                db.add(
                    User(
                        email=email,
                        display_name="Administrator",
                        password_hash=hash_password(settings.bootstrap_admin_password),
                        role=UserRole.ADMIN,
                        is_active=True,
                    )
                )
                db.commit()
    yield


settings = get_settings()
app = FastAPI(
    title="JudgeGuard",
    version="1.1.0",
    description=(
        "Self-hostable, API-first event judging portal with "
        "auditable public voting and judging-integrity analytics."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(_: Request, call_next):
    response = await call_next(_)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


app.include_router(router, prefix="/api/v1")
