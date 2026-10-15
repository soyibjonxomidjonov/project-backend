import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.verification import VerificationCode
from app.schemas.user import UserResponse
from app.services.auth_service import (
    create_token_pair,
    decode_refresh_token,
    sign_state,
    unsign_state,
)
from app.services.email_service import generate_code, send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


# --- Schemas ---

class SendCodeRequest(BaseModel):
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


# --- Email + Code Login ---

@router.post("/email/send-code", summary="Send verification code to email")
async def send_code(body: SendCodeRequest, db: AsyncSession = Depends(get_db)):
    code = generate_code()
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)

    vc = VerificationCode(email=body.email, code=code, expires_at=expires)
    db.add(vc)
    await db.commit()

    try:
        await send_verification_email(body.email, code)
    except Exception:
        raise HTTPException(500, "Email yuborishda xatolik")

    return {"message": "Tasdiqlash kodi yuborildi", "email": body.email}


@router.post("/email/verify", summary="Verify code and login", response_model=TokenPairResponse)
async def verify_code(body: VerifyCodeRequest, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.email == body.email,
            VerificationCode.code == body.code,
            VerificationCode.is_used == False,
            VerificationCode.expires_at > now,
        )
        .order_by(VerificationCode.created_at.desc())
        .limit(1)
    )
    vc = result.scalar_one_or_none()
    if vc is None:
        raise HTTPException(400, "Kod noto'g'ri yoki muddati o'tgan")

    vc.is_used = True

    # Find or create user
    user_result = await db.execute(select(User).where(User.email == body.email))
    user = user_result.scalar_one_or_none()
    admin_emails = [e.strip() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]

    if user is None:
        user = User(
            email=body.email,
            name=body.email.split("@")[0],
            role="admin" if body.email in admin_emails else "user",
        )
        db.add(user)

    user.last_login_at = now
    await db.commit()
    await db.refresh(user)

    return create_token_pair(user.id, user.email, user.role)


# --- Refresh Token ---

@router.post("/refresh", summary="Refresh access token", response_model=TokenPairResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_refresh_token(body.refresh_token)
    except Exception:
        raise HTTPException(401, "Invalid or expired refresh token")

    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(401, "User not found or inactive")

    return create_token_pair(user.id, user.email, user.role)


# --- Demo Login ---

@router.post("/demo-login", summary="Demo login (development only)", response_model=TokenPairResponse)
async def demo_login(db: AsyncSession = Depends(get_db)):
    if not settings.DEMO_LOGIN_ENABLED:
        raise HTTPException(403, "Demo login is disabled")

    demo_email = f"demo@{settings.BASE_DOMAIN}"
    result = await db.execute(select(User).where(User.email == demo_email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(email=demo_email, name="Demo User", role="user")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return create_token_pair(user.id, user.email, user.role)


# --- Google OAuth ---

def _is_allowed_redirect(url: str) -> bool:
    extra = [o.strip() for o in settings.EXTRA_CORS_ORIGINS.split(",") if o.strip()]
    if any(url == o or url.startswith(o + "/") for o in extra):
        return True
    pattern = rf"^https://[a-zA-Z0-9\-]+{re.escape(settings.ALLOWED_FRONTEND_SUFFIX)}(/.*)?$"
    return bool(re.match(pattern, url))


@router.get("/google/login", summary="Start Google OAuth flow")
async def google_login(redirect: str = Query(...)):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(501, "Google OAuth is not configured")
    if not _is_allowed_redirect(redirect):
        raise HTTPException(400, "Redirect URL is not allowed")
    state = sign_state(redirect)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback", summary="Google OAuth callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        redirect_url = unsign_state(state)
    except Exception:
        raise HTTPException(400, "Invalid or expired state")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(400, "Failed to exchange code for token")
        tokens = token_resp.json()

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(400, "Failed to get user info")
        userinfo = userinfo_resp.json()

    email = userinfo["email"]
    name = userinfo.get("name", email)
    avatar_url = userinfo.get("picture")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    admin_emails = [e.strip() for e in settings.ADMIN_EMAILS.split(",") if e.strip()]

    if user is None:
        user = User(
            email=email,
            name=name,
            avatar_url=avatar_url,
            role="admin" if email in admin_emails else "user",
        )
        db.add(user)
    else:
        user.name = name
        user.avatar_url = avatar_url
        if email in admin_emails:
            user.role = "admin"

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    pair = create_token_pair(user.id, user.email, user.role)
    return RedirectResponse(
        f"{redirect_url}/auth/callback#access_token={pair['access_token']}&refresh_token={pair['refresh_token']}"
    )


# --- Current User ---

@router.get("/me", summary="Get current user info", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user, from_attributes=True)
