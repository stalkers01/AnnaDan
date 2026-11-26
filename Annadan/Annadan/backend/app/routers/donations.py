"""Public donation discovery and donor-owned donation management."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user, require_roles
from app.models.entities import Donation, User
from app.models.enums import DonationStatus, SafetyStatus, UserRole
from app.core.config import settings
from app.schemas.contracts import DonationCreate, DonationRead, DonationUpdate

router = APIRouter(prefix="/donations", tags=["Donations"])


@router.get("", response_model=list[DonationRead])
def list_donations(
    city: str | None = Query(default=None, max_length=100),
    food_type: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    statement = select(Donation).where(
        Donation.status == DonationStatus.AVAILABLE,
        Donation.quantity_available > 0,
        Donation.pickup_deadline > now,
        or_(Donation.expires_at.is_(None), Donation.expires_at > now),
    )
    if settings.require_safety_review:
        statement = statement.where(Donation.safety_status == SafetyStatus.APPROVED)
    if city:
        statement = statement.where(Donation.city.ilike(f"%{city.strip()}%"))
    if food_type:
        statement = statement.where(Donation.food_type == food_type)
    statement = statement.order_by(Donation.pickup_deadline.asc()).offset(offset).limit(limit)
    return list(db.scalars(statement).all())


@router.post("", response_model=DonationRead, status_code=status.HTTP_201_CREATED)
def create_donation(
    payload: DonationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.DONOR)),
):
    now = datetime.now(timezone.utc)
    if settings.require_safety_review:
        required_checks = {"sealed_packaging", "allergens_disclosed", "safe_handling", "pickup_window_valid"}
        if not all(payload.safety_checklist.get(key) is True for key in required_checks):
            raise HTTPException(status_code=422, detail="Complete every food-safety self-check before submitting for review.")
    now = datetime.now(timezone.utc)
    if payload.pickup_deadline <= now:
        raise HTTPException(status_code=422, detail="Pickup deadline must be in the future.")
    if payload.expires_at and payload.expires_at <= now:
        raise HTTPException(status_code=422, detail="Food expiry time must be in the future.")
    if payload.expires_at and payload.expires_at < payload.pickup_deadline:
        raise HTTPException(status_code=422, detail="Pickup deadline must be before the food expiry time.")

    donation = Donation(
        donor_id=current_user.id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        food_type=payload.food_type,
        quantity_total=payload.quantity_total,
        quantity_available=payload.quantity_total,
        quantity_unit=payload.quantity_unit,
        pickup_location=payload.pickup_location.strip(),
        city=payload.city.strip(),
        pickup_deadline=payload.pickup_deadline,
        prepared_at=payload.prepared_at,
        expires_at=payload.expires_at,
        allergens=payload.allergens,
        is_vegetarian=payload.is_vegetarian,
        image_url=payload.image_url,
        latitude=payload.latitude,
        longitude=payload.longitude,
        safety_checklist=payload.safety_checklist,
        safety_status=SafetyStatus.PENDING if settings.require_safety_review else SafetyStatus.APPROVED,
        safety_notes="Pending administrator review" if settings.require_safety_review else "",
        status=DonationStatus.AVAILABLE,
    )
    db.add(donation)
    db.commit()
    db.refresh(donation)
    return donation


@router.get("/{donation_id}", response_model=DonationRead)
def get_donation(donation_id: UUID, db: Session = Depends(get_db)):
    donation = db.get(Donation, donation_id)
    if (
        donation is None
        or donation.status != DonationStatus.AVAILABLE
        or donation.pickup_deadline <= datetime.now(timezone.utc)
        or (donation.expires_at is not None and donation.expires_at <= datetime.now(timezone.utc))
    ):
        raise HTTPException(status_code=404, detail="Available donation not found.")
    if settings.require_safety_review and donation.safety_status != SafetyStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Available donation not found.")
    return donation


@router.patch("/{donation_id}", response_model=DonationRead)
def update_donation(
    donation_id: UUID,
    payload: DonationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    donation = db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found.")
    if donation.donor_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="You do not own this donation.")
    if donation.status not in {DonationStatus.AVAILABLE, DonationStatus.RESERVED}:
        raise HTTPException(status_code=409, detail="This donation can no longer be edited.")

    changes = payload.model_dump(exclude_unset=True)
    if "pickup_deadline" in changes and changes["pickup_deadline"] <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Pickup deadline must be in the future.")
    for field, value in changes.items():
        setattr(donation, field, value.strip() if isinstance(value, str) else value)
    if settings.require_safety_review and changes:
        donation.safety_status = SafetyStatus.PENDING
        donation.safety_notes = "Updated donation; administrator review required again"

    db.commit()
    db.refresh(donation)
    return donation


@router.delete("/{donation_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_donation(
    donation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    donation = db.get(Donation, donation_id)
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found.")
    if donation.donor_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="You do not own this donation.")
    if donation.status != DonationStatus.AVAILABLE:
        raise HTTPException(status_code=409, detail="Only an available donation can be cancelled.")
    donation.status = DonationStatus.CANCELLED
    db.commit()
