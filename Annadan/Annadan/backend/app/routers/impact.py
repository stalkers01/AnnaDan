"""Public impact metrics calculated from completed deliveries."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.entities import Donation, FoodRequest
from app.models.enums import DonationStatus, RequestStatus, SafetyStatus
from app.schemas.contracts import ImpactRead

router = APIRouter(prefix="/impact", tags=["Community impact"])


@router.get("", response_model=ImpactRead)
def community_impact(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    active_donation_filters = [
        Donation.status == DonationStatus.AVAILABLE,
        Donation.quantity_available > 0,
        Donation.pickup_deadline > now,
        or_(Donation.expires_at.is_(None), Donation.expires_at > now),
    ]
    if settings.require_safety_review:
        active_donation_filters.append(Donation.safety_status == SafetyStatus.APPROVED)
    active_donations = db.scalar(
        select(func.count(Donation.id)).where(*active_donation_filters)
    ) or 0
    delivered_requests = db.scalar(
        select(func.count(FoodRequest.id)).where(FoodRequest.status == RequestStatus.DELIVERED)
    ) or 0

    units = db.execute(
        select(Donation.quantity_unit, func.sum(FoodRequest.quantity))
        .join(FoodRequest, FoodRequest.donation_id == Donation.id)
        .where(FoodRequest.status == RequestStatus.DELIVERED)
        .group_by(Donation.quantity_unit)
    ).all()
    totals = {unit: int(quantity or 0) for unit, quantity in units}
    meals_delivered = totals.get("meal_boxes", 0) + totals.get("portions", 0)

    return ImpactRead(
        active_donations=active_donations,
        delivered_requests=delivered_requests,
        meals_delivered=meals_delivered,
        food_units_by_type=totals,
    )
