from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.auth import LoginOut, LoginRequest, RegisterRequest, UserOut
from app.security.auth import create_session, current_session, current_user, hash_password, verify_password
from app.services.audit import record_audit
from app.services.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)) is not None:
        raise HTTPException(status_code=409, detail="An account with that email already exists")

    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=UserRole.PARTICIPANT,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=LoginOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> LoginOut:
    # Rate limiting is intentionally applied to the account key here; the caller's IP
    # is not trusted as a security identity because deployments may sit behind proxies.
    email = str(payload.email).strip().lower()
    settings = get_settings()
    allowed, retry_after = limiter.consume(
        f"login:{email}",
        limit=settings.login_rate_limit,
        window_seconds=settings.login_rate_window_seconds,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many login attempts", headers={"Retry-After": str(retry_after)})
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account inactive")

    token, session = create_session(db, user)
    record_audit(db, event_id=None, actor_user_id=user.id, action="AUTH_LOGIN", entity_type="session", entity_id=str(session.id))
    db.commit()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return LoginOut(user=user, token=token, expires_at=session.expires_at)


@router.post("/logout", status_code=204)
def logout(response: Response, session=Depends(current_session), db: Session = Depends(get_db)) -> None:
    session.revoked_at = session.last_seen_at
    db.commit()
    response.delete_cookie(get_settings().session_cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user
