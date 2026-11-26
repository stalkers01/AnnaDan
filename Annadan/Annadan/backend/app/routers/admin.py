"""Administrative endpoints. Every route is restricted to admin accounts."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.dependencies import require_roles
from app.models.entities import Donation, FoodRequest, User
from app.models.enums import DonationStatus, RequestStatus, SafetyStatus, UserRole
from app.schemas.contracts import AccountStatusUpdate, AdminOverview, DonationRead, SafetyDecision, UserPublic
from app.services.notifications import notify_user

router = APIRouter(prefix="/admin", tags=["Administration"])
admin_only = require_roles(UserRole.ADMIN)


@router.get("/overview", response_model=AdminOverview)
def get_overview(
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    now = datetime.now(timezone.utc)
    active_donation_filters = [
        Donation.status == DonationStatus.AVAILABLE,
        Donation.quantity_available > 0,
        Donation.pickup_deadline > now,
        or_(Donation.expires_at.is_(None), Donation.expires_at > now),
    ]
    if settings.require_safety_review:
        active_donation_filters.append(Donation.safety_status == SafetyStatus.APPROVED)
    return AdminOverview(
        total_users=db.scalar(select(func.count(User.id))) or 0,
        active_users=db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0,
        active_donations=db.scalar(
            select(func.count(Donation.id)).where(*active_donation_filters)
        ) or 0,
        pending_requests=db.scalar(
            select(func.count(FoodRequest.id)).where(FoodRequest.status == RequestStatus.PENDING)
        ) or 0,
        delivered_requests=db.scalar(
            select(func.count(FoodRequest.id)).where(FoodRequest.status == RequestStatus.DELIVERED)
        ) or 0,
    )


@router.get("/users", response_model=list[UserPublic])
def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    statement = select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    return list(db.scalars(statement).all())


@router.patch("/users/{user_id}/status", response_model=UserPublic)
def update_user_status(
    user_id: UUID,
    payload: AccountStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(admin_only),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_admin.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="You cannot disable your own admin account.")
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@router.get("/safety/pending", response_model=list[DonationRead])
def list_pending_safety_reviews(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    statement = (
        select(Donation)
        .where(Donation.safety_status == SafetyStatus.PENDING)
        .order_by(Donation.created_at.asc())
        .limit(limit)
    )
    return list(db.scalars(statement).all())


@router.patch("/safety/{donation_id}", response_model=DonationRead)
def review_food_safety(
    donation_id: UUID,
    payload: SafetyDecision,
    db: Session = Depends(get_db),
    _admin: User = Depends(admin_only),
):
    donation = db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found.")
    if donation.safety_status != SafetyStatus.PENDING:
        raise HTTPException(status_code=409, detail="This donation has already received a safety decision.")
    donation.safety_status = SafetyStatus(payload.decision)
    donation.safety_notes = payload.note.strip()
    db.commit()
    db.refresh(donation)
    notify_user(
        donation.donor,
        "Annadan food-safety review",
        f"Your donation '{donation.title}' was {payload.decision} by the Annadan review team. {payload.note.strip()}".strip(),
    )
    return donation
