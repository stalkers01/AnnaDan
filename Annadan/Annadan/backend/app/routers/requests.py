"""Food-request lifecycle and delivery-partner handover endpoints."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.db.session import get_db
from app.dependencies import get_current_user, require_roles
from app.models.entities import DeliveryLocation, Donation, FoodRequest, RequestEvent, User
from app.models.enums import DonationStatus, RequestStatus, SafetyStatus, UserRole
from app.services.notifications import notify_user
from app.schemas.contracts import (
    RequestCreate,
    RequestDecision,
    RequestRead,
    RequestStatusUpdate,
    TrackingRead,
    DeliveryLocationInput,
    DeliveryLocationRead,
)

router = APIRouter(prefix="/requests", tags=["Food requests and delivery"])


def record_event(
    db: Session,
    request_id: UUID,
    actor_id: UUID | None,
    request_status: RequestStatus,
    note: str = "",
) -> None:
    db.add(
        RequestEvent(
            request_id=request_id,
            actor_id=actor_id,
            status=request_status,
            note=note.strip(),
        )
    )


@router.post(
    "/donations/{donation_id}",
    response_model=RequestRead,
    status_code=status.HTTP_201_CREATED,
)
def request_food(
    donation_id: UUID,
    payload: RequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.RECEIVER)),
):
    donation = db.get(Donation, donation_id)
    if donation is None or donation.status != DonationStatus.AVAILABLE:
        raise HTTPException(status_code=404, detail="This donation is not available.")
    if settings.require_safety_review and donation.safety_status != SafetyStatus.APPROVED:
        raise HTTPException(status_code=404, detail="This donation is not available.")
    if donation.donor_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot request your own donation.")
    now = datetime.now(timezone.utc)
    if donation.pickup_deadline <= now:
        raise HTTPException(status_code=409, detail="The pickup deadline has passed.")
    if donation.expires_at is not None and donation.expires_at <= now:
        raise HTTPException(status_code=409, detail="The food expiry time has passed.")
    if payload.quantity > donation.quantity_available:
        raise HTTPException(status_code=422, detail="Requested quantity exceeds the currently available quantity.")

    food_request = FoodRequest(
        donation_id=donation.id,
        receiver_id=current_user.id,
        quantity=payload.quantity,
        delivery_address=payload.delivery_address.strip(),
        delivery_city=payload.delivery_city.strip(),
        message=payload.message.strip(),
        delivery_latitude=payload.delivery_latitude,
        delivery_longitude=payload.delivery_longitude,
        status=RequestStatus.PENDING,
    )
    db.add(food_request)
    db.flush()
    record_event(db, food_request.id, current_user.id, RequestStatus.PENDING, "Request submitted")
    db.commit()
    notify_user(donation.donor, "New Annadan food request", f"A receiver requested {payload.quantity} {donation.quantity_unit} of {donation.title}. Sign in to review the request.")
    return db.scalar(
        select(FoodRequest)
        .options(joinedload(FoodRequest.donation))
        .where(FoodRequest.id == food_request.id)
    )


@router.get("/mine", response_model=list[RequestRead])
def list_my_requests(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = select(FoodRequest).options(joinedload(FoodRequest.donation))

    if current_user.role == UserRole.RECEIVER:
        statement = statement.where(FoodRequest.receiver_id == current_user.id)
    elif current_user.role == UserRole.DONOR:
        statement = statement.join(Donation).where(Donation.donor_id == current_user.id)
    elif current_user.role == UserRole.DELIVERY_PARTNER:
        statement = statement.where(FoodRequest.delivery_partner_id == current_user.id)
    else:
        statement = statement

    statement = statement.order_by(FoodRequest.created_at.desc()).limit(limit)
    return list(db.scalars(statement).unique().all())


@router.get("/available-deliveries", response_model=list[RequestRead])
def list_available_deliveries(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.DELIVERY_PARTNER)),
):
    statement = (
        select(FoodRequest)
        .options(joinedload(FoodRequest.donation))
        .where(
            FoodRequest.status == RequestStatus.APPROVED,
            FoodRequest.delivery_partner_id.is_(None),
        )
        .order_by(FoodRequest.created_at.asc())
        .limit(limit)
    )
    return list(db.scalars(statement).unique().all())


@router.patch("/{request_id}/decision", response_model=RequestRead)
def decide_request(
    request_id: UUID,
    payload: RequestDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food_request = db.get(FoodRequest, request_id)
    if food_request is None:
        raise HTTPException(status_code=404, detail="Request not found.")
    donation = db.get(Donation, food_request.donation_id)
    if donation is None:
        raise HTTPException(status_code=404, detail="Donation not found.")
    if donation.donor_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only the donor can review this request.")
    if food_request.status != RequestStatus.PENDING:
        raise HTTPException(status_code=409, detail="This request has already been reviewed.")

    new_status = RequestStatus(payload.decision)
    if new_status == RequestStatus.APPROVED:
        reservation = db.execute(
            update(Donation)
            .where(
                Donation.id == donation.id,
                Donation.status == DonationStatus.AVAILABLE,
                Donation.quantity_available >= food_request.quantity,
            )
            .values(quantity_available=Donation.quantity_available - food_request.quantity)
        )
        if reservation.rowcount != 1:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="There is not enough food remaining to approve this request.",
            )

    changed = db.execute(
        update(FoodRequest)
        .where(FoodRequest.id == request_id, FoodRequest.status == RequestStatus.PENDING)
        .values(status=new_status, updated_at=datetime.now(timezone.utc))
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="This request has already been reviewed.")

    db.flush()
    refreshed_donation = db.get(Donation, donation.id)
    if (
        new_status == RequestStatus.APPROVED
        and refreshed_donation is not None
        and refreshed_donation.quantity_available == 0
    ):
        refreshed_donation.status = DonationStatus.RESERVED

    record_event(db, request_id, current_user.id, new_status, payload.note or f"Request {new_status.value}")
    db.commit()
    notify_user(food_request.receiver, "Annadan request update", f"Your request for {donation.title} was {new_status.value}.")
    return db.scalar(
        select(FoodRequest)
        .options(joinedload(FoodRequest.donation))
        .where(FoodRequest.id == request_id)
    )


@router.post("/{request_id}/claim", response_model=RequestRead)
def claim_delivery(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.DELIVERY_PARTNER)),
):
    claimed = db.execute(
        update(FoodRequest)
        .where(
            FoodRequest.id == request_id,
            FoodRequest.status == RequestStatus.APPROVED,
            FoodRequest.delivery_partner_id.is_(None),
        )
        .values(
            delivery_partner_id=current_user.id,
            status=RequestStatus.ASSIGNED,
            updated_at=datetime.now(timezone.utc),
        )
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="This delivery is no longer available to claim.")

    record_event(db, request_id, current_user.id, RequestStatus.ASSIGNED, "Delivery partner accepted the handover")
    db.commit()
    claimed_request = db.scalar(
        select(FoodRequest)
        .options(joinedload(FoodRequest.donation), joinedload(FoodRequest.receiver))
        .where(FoodRequest.id == request_id)
    )
    notify_user(claimed_request.receiver, "Annadan delivery assigned", "A delivery partner has accepted your food handover.")
    notify_user(claimed_request.donation.donor, "Annadan delivery assigned", "A delivery partner has accepted your donation handover.")
    return claimed_request


@router.patch("/{request_id}/status", response_model=RequestRead)
def update_delivery_status(
    request_id: UUID,
    payload: RequestStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food_request = db.get(FoodRequest, request_id)
    if food_request is None:
        raise HTTPException(status_code=404, detail="Request not found.")

    is_admin = current_user.role == UserRole.ADMIN
    if not is_admin and food_request.delivery_partner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the assigned delivery partner can update this handover.")

    allowed_transition = {
        RequestStatus.PICKED_UP: RequestStatus.ASSIGNED,
        RequestStatus.DELIVERED: RequestStatus.PICKED_UP,
    }
    new_status = RequestStatus(payload.status)
    if food_request.status != allowed_transition[new_status]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move this request from {food_request.status.value} to {new_status.value}.",
        )

    expected_status = allowed_transition[new_status]
    transition_conditions = [
        FoodRequest.id == request_id,
        FoodRequest.status == expected_status,
    ]
    if not is_admin:
        transition_conditions.append(FoodRequest.delivery_partner_id == current_user.id)

    changed = db.execute(
        update(FoodRequest)
        .where(*transition_conditions)
        .values(status=new_status, updated_at=datetime.now(timezone.utc))
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="The handover status changed. Refresh and try again.")

    record_event(db, request_id, current_user.id, new_status, payload.note)

    if new_status == RequestStatus.DELIVERED:
        db.query(DeliveryLocation).filter(DeliveryLocation.request_id == request_id).delete(synchronize_session=False)
        db.flush()
        donation = db.get(Donation, food_request.donation_id)
        outstanding = db.scalar(
            select(FoodRequest.id).where(
                FoodRequest.donation_id == food_request.donation_id,
                FoodRequest.status.in_(
                    [RequestStatus.APPROVED, RequestStatus.ASSIGNED, RequestStatus.PICKED_UP]
                ),
            ).limit(1)
        )
        if donation and donation.quantity_available == 0 and outstanding is None:
            donation.status = DonationStatus.COMPLETED

    db.commit()
    db.refresh(food_request)
    notify_user(food_request.receiver, "Annadan delivery update", f"Your food handover is now {new_status.value.replace('_', ' ')}.")
    notify_user(food_request.donation.donor, "Annadan delivery update", f"Your donation handover is now {new_status.value.replace('_', ' ')}.")
    return db.scalar(
        select(FoodRequest)
        .options(joinedload(FoodRequest.donation))
        .where(FoodRequest.id == request_id)
    )


@router.post("/{request_id}/location", response_model=DeliveryLocationRead)
def update_delivery_location(
    request_id: UUID,
    payload: DeliveryLocationInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.DELIVERY_PARTNER)),
):
    food_request = db.get(FoodRequest, request_id)
    if food_request is None:
        raise HTTPException(status_code=404, detail="Delivery request not found.")
    if food_request.delivery_partner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the assigned delivery partner can share this location.")
    if food_request.status not in {RequestStatus.ASSIGNED, RequestStatus.PICKED_UP}:
        raise HTTPException(status_code=409, detail="Live location sharing is available only during an active delivery.")

    location = db.scalar(select(DeliveryLocation).where(DeliveryLocation.request_id == request_id))
    if location is None:
        location = DeliveryLocation(request_id=request_id, partner_id=current_user.id,
                                    latitude=payload.latitude, longitude=payload.longitude,
                                    accuracy_m=payload.accuracy_m)
        db.add(location)
    else:
        location.partner_id = current_user.id
        location.latitude = payload.latitude
        location.longitude = payload.longitude
        location.accuracy_m = payload.accuracy_m
        location.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(location)
    return DeliveryLocationRead(
        request_id=location.request_id, latitude=location.latitude, longitude=location.longitude,
        accuracy_m=location.accuracy_m, updated_at=location.updated_at,
    )


@router.get("/{request_id}/location", response_model=DeliveryLocationRead)
def get_delivery_location(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food_request = db.get(FoodRequest, request_id)
    if food_request is None:
        raise HTTPException(status_code=404, detail="Delivery request not found.")
    is_participant = current_user.id in {
        food_request.receiver_id, food_request.delivery_partner_id,
    }
    donation = db.get(Donation, food_request.donation_id)
    is_donor = donation is not None and donation.donor_id == current_user.id
    if not (is_participant or is_donor or current_user.role == UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="You are not allowed to view this delivery location.")
    location = db.scalar(select(DeliveryLocation).where(DeliveryLocation.request_id == request_id))
    if location is None:
        raise HTTPException(status_code=404, detail="The delivery partner has not shared a location yet.")
    return DeliveryLocationRead(
        request_id=location.request_id, latitude=location.latitude, longitude=location.longitude,
        accuracy_m=location.accuracy_m, updated_at=location.updated_at,
    )


@router.get("/{request_id}/tracking", response_model=TrackingRead)
def track_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    food_request = db.scalar(
        select(FoodRequest)
        .options(joinedload(FoodRequest.donation), joinedload(FoodRequest.events))
        .where(FoodRequest.id == request_id)
    )
    if food_request is None:
        raise HTTPException(status_code=404, detail="Request not found.")

    is_participant = current_user.id in {
        food_request.receiver_id,
        food_request.donation.donor_id,
        food_request.delivery_partner_id,
    }
    if not is_participant and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="You are not allowed to view this tracking record.")

    return TrackingRead(
        request_id=food_request.id,
        status=food_request.status,
        donation_title=food_request.donation.title,
        delivery_latitude=food_request.delivery_latitude,
        delivery_longitude=food_request.delivery_longitude,
        timeline=food_request.events,
    )
