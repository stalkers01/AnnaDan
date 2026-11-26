"""Registration, authentication, account verification, and password recovery."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.dependencies import get_authenticated_user
from app.models.entities import User
from app.schemas.contracts import (
    AuthResponse, LoginInput, OTPVerifyInput, PasswordResetConfirm,
    PasswordResetRequest, PhoneOTPRequest, PhoneOTPVerify, RegisterInput,
)
from app.services.notifications import check_phone_verification, send_phone_verification
from app.services.otp import create_email_challenge, verify_email_challenge

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.access_token_minutes * 60,
        user=user,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterInput, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        phone=payload.phone.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        email_verified=not settings.require_email_verification,
        phone_verified=not settings.require_phone_verification,
        settings={
            "donation_updates": True,
            "request_updates": True,
            "email_updates": True,
            "sms_updates": False,
            "preferred_role": payload.role.value,
        },
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    db.refresh(user)

    if settings.require_email_verification:
        create_email_challenge(db, email, "email_verification")
    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginInput, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been disabled.")
    return _auth_response(user)


@router.get("/me")
def current_account(current_user: User = Depends(get_authenticated_user)):
    from app.schemas.contracts import UserPublic
    return UserPublic.model_validate(current_user)


@router.post("/otp/request")
def request_email_otp(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    if current_user.email_verified:
        return {"message": "Your email address is already verified."}
    debug_code = create_email_challenge(db, current_user.email, "email_verification")
    result = {"message": "A verification code has been sent to your email address."}
    if debug_code:
        result["development_code"] = debug_code
    return result


@router.post("/otp/verify")
def verify_email_otp(
    payload: OTPVerifyInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    if not verify_email_challenge(db, current_user.email, "email_verification", payload.code):
        raise HTTPException(status_code=400, detail="The code is invalid, expired, or has reached its attempt limit.")
    current_user.email_verified = True
    db.commit()
    return {"message": "Email address verified successfully."}


@router.post("/phone/otp/request")
def request_phone_otp(
    payload: PhoneOTPRequest,
    current_user: User = Depends(get_authenticated_user),
):
    if current_user.phone_verified:
        return {"message": "Your phone number is already verified."}
    if not send_phone_verification(current_user.phone, payload.channel):
        raise HTTPException(status_code=503, detail="Phone verification is not configured or the provider is unavailable.")
    return {"message": "A verification code has been sent to your phone."}


@router.post("/phone/otp/verify")
def verify_phone_otp(
    payload: PhoneOTPVerify,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    if not check_phone_verification(current_user.phone, payload.code):
        raise HTTPException(status_code=400, detail="The phone verification code is invalid or expired.")
    current_user.phone_verified = True
    db.commit()
    return {"message": "Phone number verified successfully."}


@router.post("/password/forgot")
def forgot_password(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    response = {"message": "If an active account exists for that email, a reset code has been sent."}
    if user:
        try:
            debug_code = create_email_challenge(db, email, "password_reset")
            if debug_code:
                response["development_code"] = debug_code
        except HTTPException:
            # Keep the public response identical for existing and unknown accounts.
            pass
    return response


@router.post("/password/reset")
def reset_password(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    if not verify_email_challenge(db, email, "password_reset", payload.code):
        raise HTTPException(status_code=400, detail="The code is invalid, expired, or has reached its attempt limit.")
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=400, detail="The reset request is no longer valid.")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password updated. Sign in with your new password."}
