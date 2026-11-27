"""Validated request and response contracts exposed by the API."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import DonationStatus, RequestStatus, SafetyStatus, UserRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserPublic(ORMModel):
    id: UUID
    full_name: str
    email: EmailStr
    phone: str
    role: UserRole
    is_active: bool
    email_verified: bool
    phone_verified: bool
    created_at: datetime


class RegisterInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=30)
    password: str = Field(min_length=10, max_length=128)
    role: Literal[UserRole.DONOR, UserRole.RECEIVER, UserRole.DELIVERY_PARTNER]


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=7, max_length=30)


class SettingsUpdate(BaseModel):
    donation_updates: bool | None = None
    request_updates: bool | None = None
    email_updates: bool | None = None
    sms_updates: bool | None = None
    preferred_role: Literal["donor", "receiver", "delivery_partner"] | None = None


class DonationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=2000)
    food_type: str = Field(default="prepared_food", max_length=50)
    quantity_total: int = Field(gt=0, le=100000)
    quantity_unit: Literal["meal_boxes", "packets", "kg", "litres", "portions"] = "meal_boxes"
    pickup_location: str = Field(min_length=4, max_length=255)
    city: str = Field(min_length=2, max_length=100)
    pickup_deadline: datetime
    prepared_at: datetime | None = None
    expires_at: datetime | None = None
    allergens: list[str] = Field(default_factory=list, max_length=30)
    is_vegetarian: bool = False
    image_url: str | None = Field(default=None, max_length=1000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    safety_checklist: dict[str, bool] = Field(default_factory=dict)

    @field_validator("pickup_deadline", "prepared_at", "expires_at")
    @classmethod
    def normalize_datetimes(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @field_validator("allergens")
    @classmethod
    def clean_allergens(cls, values):
        cleaned = [item.strip()[:40] for item in values if item.strip()]
        return list(dict.fromkeys(cleaned))


class DonationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, min_length=10, max_length=2000)
    pickup_location: str | None = Field(default=None, min_length=4, max_length=255)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    pickup_deadline: datetime | None = None
    allergens: list[str] | None = Field(default=None, max_length=30)
    is_vegetarian: bool | None = None
    image_url: str | None = Field(default=None, max_length=1000)

    @field_validator("pickup_deadline")
    @classmethod
    def normalize_deadline(cls, value):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class DonationRead(ORMModel):
    id: UUID
    donor_id: UUID
    title: str
    description: str
    food_type: str
    quantity_total: int
    quantity_available: int
    quantity_unit: str
    pickup_location: str
    city: str
    pickup_deadline: datetime
    prepared_at: datetime | None
    expires_at: datetime | None
    allergens: list[str]
    is_vegetarian: bool
    image_url: str | None
    latitude: float | None
    longitude: float | None
    safety_checklist: dict[str, bool]
    safety_status: SafetyStatus
    safety_notes: str
    status: DonationStatus
    created_at: datetime


class RequestCreate(BaseModel):
    quantity: int = Field(gt=0, le=100000)
    delivery_address: str = Field(min_length=4, max_length=255)
    delivery_city: str = Field(min_length=2, max_length=100)
    message: str = Field(default="", max_length=500)
    delivery_latitude: float | None = Field(default=None, ge=-90, le=90)
    delivery_longitude: float | None = Field(default=None, ge=-180, le=180)


class RequestDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=300)


class RequestRead(ORMModel):
    id: UUID
    donation_id: UUID
    receiver_id: UUID
    delivery_partner_id: UUID | None
    quantity: int
    delivery_address: str
    delivery_city: str
    message: str
    delivery_latitude: float | None
    delivery_longitude: float | None
    status: RequestStatus
    created_at: datetime
    updated_at: datetime
    donation: DonationRead


class RequestStatusUpdate(BaseModel):
    status: Literal["picked_up", "delivered"]
    note: str = Field(default="", max_length=300)


class TrackingEventRead(ORMModel):
    status: RequestStatus
    note: str
    created_at: datetime


class TrackingRead(BaseModel):
    request_id: UUID
    status: RequestStatus
    donation_title: str
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None
    timeline: list[TrackingEventRead]


class RatingCreate(BaseModel):
    request_id: UUID
    topic: Literal["Food quality", "Pickup experience", "Overall experience"]
    score: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=300)


class ImpactRead(BaseModel):
    active_donations: int
    delivered_requests: int
    meals_delivered: int
    food_units_by_type: dict[str, int]


class AdminOverview(BaseModel):
    total_users: int
    active_users: int
    active_donations: int
    pending_requests: int
    delivered_requests: int


class AccountStatusUpdate(BaseModel):
    is_active: bool


class UserStats(BaseModel):
    donations_shared: int
    requests_made: int
    meals_helped: int


class EmailOTPRequest(BaseModel):
    purpose: Literal["email_verification", "password_reset"] = "email_verification"


class OTPVerifyInput(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=10, max_length=128)


class PhoneOTPRequest(BaseModel):
    channel: Literal["sms", "whatsapp"] = "sms"


class PhoneOTPVerify(BaseModel):
    code: str = Field(min_length=4, max_length=10)


class DeliveryLocationInput(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=10000)


class DeliveryLocationRead(BaseModel):
    request_id: UUID
    latitude: float
    longitude: float
    accuracy_m: float | None
    updated_at: datetime


class SafetyDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=500)


class PaymentOrderInput(BaseModel):
    amount_inr: int = Field(ge=50, le=5000)


class PaymentOrderRead(BaseModel):
    contribution_id: UUID
    order_id: str
    amount_paise: int
    currency: str = "INR"
    key_id: str

class PaymentVerifyInput(BaseModel):
    razorpay_order_id: str = Field(min_length=8, max_length=80)
    razorpay_payment_id: str = Field(min_length=8, max_length=80)
    razorpay_signature: str = Field(min_length=32, max_length=256)
