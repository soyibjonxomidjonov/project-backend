import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings
from app.db import async_session
from app.routers import admin as admin_router
from app.routers import ai as ai_router
from app.routers import auth as auth_router
from app.routers import entities as entities_router
from app.routers import knowledge as knowledge_router
from app.routers import users as users_router

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs",
    openapi_url="/openapi.json",
)


# --- Security Headers ---

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# --- CORS ---

extra_origins = [o.strip() for o in settings.EXTRA_CORS_ORIGINS.split(",") if o.strip()]
suffix_escaped = re.escape(settings.ALLOWED_FRONTEND_SUFFIX)
origin_regex = rf"^https://[a-zA-Z0-9\-]+{suffix_escaped}$"

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=origin_regex,
    allow_origins=extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Error Handlers ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": 422, "message": str(exc)}},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": 500, "message": "Internal server error"}},
    )


# --- Routers ---

app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(entities_router.router)
app.include_router(admin_router.router)
app.include_router(ai_router.router)
app.include_router(knowledge_router.router)


# --- Health ---

@app.get("/health", summary="Health check", tags=["system"])
async def health():
    db_status = "error"
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
            db_status = "ok"
    except Exception:
        pass
    status = "ok" if db_status == "ok" else "degraded"
    return {"status": status, "db": db_status, "version": settings.GIT_SHA}
