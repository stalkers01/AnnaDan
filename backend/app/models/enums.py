"""Domain enums shared by models, schemas, and API routes."""

from enum import Enum


class UserRole(str, Enum):
    DONOR = "donor"
    RECEIVER = "receiver"
    DELIVERY_PARTNER = "delivery_partner"
    ADMIN = "admin"


class DonationStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class SafetyStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ASSIGNED = "assigned"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class OTPPurpose(str, Enum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


class PaymentStatus(str, Enum):
    CREATED = "created"
    PAID = "paid"
    FAILED = "failed"
