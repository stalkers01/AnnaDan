"""Database models for accounts, food donations, handovers, and feedback."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime
from app.models.enums import DonationStatus, RequestStatus, SafetyStatus, UserRole


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def enum_values(enum_class):
    return [item.value for item in enum_class]


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, values_callable=enum_values, native_enum=False),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    donations: Mapped[list["Donation"]] = relationship(back_populates="donor")
    received_requests: Mapped[list["FoodRequest"]] = relationship(
        back_populates="receiver", foreign_keys="FoodRequest.receiver_id"
    )


class Donation(Base):
    __tablename__ = "donations"
    __table_args__ = (
        CheckConstraint("quantity_total > 0", name="ck_donation_quantity_total_positive"),
        CheckConstraint("quantity_available >= 0", name="ck_donation_quantity_available_nonnegative"),
        Index("ix_donations_public_search", "status", "city", "pickup_deadline"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    donor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    food_type: Mapped[str] = mapped_column(String(50), default="prepared_food", nullable=False)
    quantity_total: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(30), default="meal_boxes", nullable=False)
    pickup_location: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pickup_deadline: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    prepared_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    allergens: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_vegetarian: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    safety_checklist: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    safety_status: Mapped[SafetyStatus] = mapped_column(
        SqlEnum(SafetyStatus, values_callable=enum_values, native_enum=False),
        default=SafetyStatus.PENDING,
        nullable=False,
        index=True,
    )
    safety_notes: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    status: Mapped[DonationStatus] = mapped_column(
        SqlEnum(DonationStatus, values_callable=enum_values, native_enum=False),
        default=DonationStatus.AVAILABLE,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    donor: Mapped[User] = relationship(back_populates="donations")
    requests: Mapped[list["FoodRequest"]] = relationship(back_populates="donation")


class FoodRequest(Base):
    __tablename__ = "food_requests"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_request_quantity_positive"),
        Index("ix_requests_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    donation_id: Mapped[UUID] = mapped_column(ForeignKey("donations.id", ondelete="RESTRICT"), index=True)
    receiver_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    delivery_partner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_address: Mapped[str] = mapped_column(String(255), nullable=False)
    delivery_city: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    delivery_latitude: Mapped[float | None] = mapped_column(nullable=True)
    delivery_longitude: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[RequestStatus] = mapped_column(
        SqlEnum(RequestStatus, values_callable=enum_values, native_enum=False),
        default=RequestStatus.PENDING,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)

    donation: Mapped[Donation] = relationship(back_populates="requests")
    receiver: Mapped[User] = relationship(back_populates="received_requests", foreign_keys=[receiver_id])
    delivery_partner: Mapped[User | None] = relationship(foreign_keys=[delivery_partner_id])
    events: Mapped[list["RequestEvent"]] = relationship(
        back_populates="food_request", cascade="all, delete-orphan", order_by="RequestEvent.created_at"
    )


class RequestEvent(Base):
    __tablename__ = "request_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("food_requests.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[RequestStatus] = mapped_column(
        SqlEnum(RequestStatus, values_callable=enum_values, native_enum=False), nullable=False
    )
    note: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    food_request: Mapped[FoodRequest] = relationship(back_populates="events")


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        CheckConstraint("score >= 1 AND score <= 5", name="ck_rating_score_range"),
        UniqueConstraint("request_id", "user_id", name="uq_rating_request_user"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("food_requests.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    topic: Mapped[str] = mapped_column(String(60), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

class OTPChallenge(Base):
    """Single-use email OTP challenge; raw codes are never stored."""

    __tablename__ = "otp_challenges"
    __table_args__ = (Index("ix_otp_email_purpose_created", "email", "purpose", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)


class DeliveryLocation(Base):
    """Latest live location only; one row per delivery to limit location retention."""

    __tablename__ = "delivery_locations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("food_requests.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    partner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, onupdate=utc_now)


class PaymentContribution(Base):
    """Optional voluntary platform-support payment; never a payment for food."""

    __tablename__ = "payment_contributions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    provider_order_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="created", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
