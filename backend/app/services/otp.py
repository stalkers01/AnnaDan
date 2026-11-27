"""Email OTP creation, delivery, and single-use verification helpers."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import OTPChallenge
from app.services.notifications import send_email


def _digest(email: str, purpose: str, code: str) -> str:
    payload = f"{email.lower()}|{purpose}|{code}".encode()
    return hmac.new(settings.secret_key.encode(), payload, hashlib.sha256).hexdigest()


def create_email_challenge(db: Session, email: str, purpose: str) -> str | None:
    if not settings.resend_api_key and not (settings.environment.lower() == "development" and settings.expose_otp_in_development):
        raise HTTPException(status_code=503, detail="Email verification is not configured yet.")
    now = datetime.now(timezone.utc)
    latest = db.scalar(
        select(OTPChallenge)
        .where(OTPChallenge.email == email.lower(), OTPChallenge.purpose == purpose)
        .order_by(OTPChallenge.created_at.desc())
        .limit(1)
    )
    if latest and latest.created_at > now - timedelta(seconds=60):
        raise HTTPException(status_code=429, detail="A code was sent recently. Wait one minute before requesting another.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = OTPChallenge(
        email=email.lower(),
        purpose=purpose,
        code_hash=_digest(email, purpose, code),
        expires_at=now + timedelta(minutes=10),
    )
    db.add(challenge)
    db.commit()

    if not send_email(
        email,
        "Your Annadan verification code",
        f"Your Annadan verification code is {code}. It expires in 10 minutes. Do not share it with anyone.",
    ):
        if settings.environment.lower() == "development" and settings.expose_otp_in_development:
            return code
        db.delete(challenge)
        db.commit()
        raise HTTPException(status_code=503, detail="Email delivery is unavailable. Please try again later.")
    return None


def verify_email_challenge(db: Session, email: str, purpose: str, code: str) -> bool:
    now = datetime.now(timezone.utc)
    challenge = db.scalar(
        select(OTPChallenge)
        .where(
            OTPChallenge.email == email.lower(),
            OTPChallenge.purpose == purpose,
            OTPChallenge.consumed_at.is_(None),
        )
        .order_by(OTPChallenge.created_at.desc())
        .limit(1)
    )
    if challenge is None or challenge.expires_at <= now or challenge.attempts >= 5:
        return False
    challenge.attempts += 1
    valid = hmac.compare_digest(challenge.code_hash, _digest(email, purpose, code))
    if valid:
        challenge.consumed_at = now
    db.commit()
    return valid
