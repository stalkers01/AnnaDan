"""Profile, notification preferences, personal statistics, and feedback."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.entities import Donation, FoodRequest, Rating, User
from app.models.enums import RequestStatus, UserRole
from app.schemas.contracts import (
    RatingCreate,
    SettingsUpdate,
    UserPublic,
    UserStats,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Users and profile"])


@router.get("/me", response_model=UserPublic)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserPublic)
def update_profile(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    changes = {
        key: value.strip()
        for key, value in payload.model_dump(exclude_unset=True).items()
        if value is not None
    }
    for key, value in changes.items():
        setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/settings")
def get_settings(current_user: User = Depends(get_current_user)):
    return current_user.settings or {}


@router.patch("/me/settings")
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = dict(current_user.settings or {})
    updated.update(
        {
            key: value
            for key, value in payload.model_dump(exclude_unset=True).items()
            if value is not None
        }
    )
    current_user.settings = updated
    db.commit()
    db.refresh(current_user)
    return current_user.settings


@router.get("/me/stats", response_model=UserStats)
def get_my_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    donations_shared = db.scalar(
        select(func.count(Donation.id)).where(Donation.donor_id == current_user.id)
    ) or 0
    requests_made = db.scalar(
        select(func.count(FoodRequest.id)).where(FoodRequest.receiver_id == current_user.id)
    ) or 0

    meal_quantity_query = (
        select(func.coalesce(func.sum(FoodRequest.quantity), 0))
        .join(Donation, Donation.id == FoodRequest.donation_id)
        .where(
            FoodRequest.status == RequestStatus.DELIVERED,
            Donation.quantity_unit.in_(["meal_boxes", "portions"]),
        )
    )
    if current_user.role == UserRole.DELIVERY_PARTNER:
        meal_quantity_query = meal_quantity_query.where(
            FoodRequest.delivery_partner_id == current_user.id
        )
    elif current_user.role == UserRole.DONOR:
        meal_quantity_query = meal_quantity_query.where(Donation.donor_id == current_user.id)
    else:
        meal_quantity_query = meal_quantity_query.where(FoodRequest.receiver_id == current_user.id)

    meals_helped = db.scalar(meal_quantity_query) or 0

    return UserStats(
        donations_shared=donations_shared,
        requests_made=requests_made,
        meals_helped=meals_helped,
    )


@router.post("/ratings", status_code=status.HTTP_201_CREATED)
def submit_rating(
    payload: RatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food_request = db.get(FoodRequest, payload.request_id)
    if food_request is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    is_participant = current_user.id in {
        food_request.receiver_id,
        food_request.donation.donor_id,
        food_request.delivery_partner_id,
    }
    if not is_participant and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only people involved in this handover can leave feedback.")
    if food_request.status != RequestStatus.DELIVERED:
        raise HTTPException(status_code=409, detail="Feedback is available after a delivery is completed.")
    existing = db.scalar(
        select(Rating).where(
            Rating.request_id == payload.request_id,
            Rating.user_id == current_user.id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="You have already rated this handover.")

    rating = Rating(
        request_id=payload.request_id,
        user_id=current_user.id,
        topic=payload.topic,
        score=payload.score,
        comment=payload.comment.strip(),
    )
    db.add(rating)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already rated this handover.")
    db.refresh(rating)
    return {"id": str(rating.id), "message": "Thank you for your feedback."}
