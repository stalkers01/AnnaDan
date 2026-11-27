"""FastAPI application entry point for the Annadan service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models import Donation, FoodRequest, Rating, RequestEvent, User  # noqa: F401
from app.routers import admin, auth, donations, impact, payments, requests, uploads, users


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # For local development, create missing tables automatically. Production uses Alembic.
    if settings.environment.lower() != "production":
        Base.metadata.create_all(bind=engine)
    yield


if settings.environment.lower() == "production" and settings.secret_key == "change-this-secret-before-deploying":
    raise RuntimeError("Set a unique SECRET_KEY before starting Annadan in production.")
if settings.environment.lower() == "production" and settings.require_email_verification:
    if not settings.resend_api_key:
        raise RuntimeError("REQUIRE_EMAIL_VERIFICATION needs RESEND_API_KEY in production.")
    if settings.email_from.lower().endswith("@resend.dev"):
        raise RuntimeError("Set EMAIL_FROM to a sender identity verified in your Resend account.")
if settings.environment.lower() == "production" and settings.require_phone_verification and not all([
    settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_verify_service_sid
]):
    raise RuntimeError("REQUIRE_PHONE_VERIFICATION needs Twilio Verify credentials in production.")

app = FastAPI(
    title=settings.app_name,
    description="Food donation, request, and delivery coordination API.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(donations.router, prefix=settings.api_prefix)
app.include_router(requests.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(impact.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(uploads.router, prefix=settings.api_prefix)
app.include_router(payments.router, prefix=settings.api_prefix)


@app.get("/health", tags=["Operations"])
def health_check():
    return {"status": "ok", "service": settings.app_name}


@app.get("/ready", tags=["Operations"])
def readiness_check():
    from sqlalchemy import text
    from app.db.session import SessionLocal
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}
