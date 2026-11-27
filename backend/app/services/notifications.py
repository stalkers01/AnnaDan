"""Best-effort email/SMS notifications. Provider failures never roll back a food handover."""

import html
import logging
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.models.entities import User

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, message: str) -> bool:
    if not settings.resend_api_key:
        logger.info("Email provider is not configured; skipped notification to %s", to_email)
        return False
    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}", "Content-Type": "application/json"},
            json={
                "from": settings.email_from,
                "to": [to_email],
                "subject": subject,
                "html": f"<div style='font-family:Arial,sans-serif;line-height:1.6'><h2>Annadan</h2><p>{html.escape(message)}</p></div>",
                "text": message,
            },
            timeout=12.0,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.exception("Email provider request failed")
        return False


def send_sms(to_number: str, message: str) -> bool:
    if not all([settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from_number]):
        logger.info("SMS provider is not configured; skipped notification")
        return False
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
        response = httpx.post(
            url,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            data={"From": settings.twilio_from_number, "To": to_number, "Body": message[:1500]},
            timeout=12.0,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.exception("SMS provider request failed")
        return False


def notify_user(user: User | None, subject: str, message: str, *, email: bool = True, sms: bool = True) -> None:
    if user is None:
        return
    preferences = user.settings or {}
    if email and user.email_verified and preferences.get("email_updates", True):
        send_email(user.email, subject, message)
    if sms and user.phone_verified and preferences.get("sms_updates", False) and user.phone:
        send_sms(user.phone, message)


def send_phone_verification(phone: str, channel: str = "sms") -> bool:
    if not all([settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_verify_service_sid]):
        return False
    try:
        url = f"https://verify.twilio.com/v2/Services/{settings.twilio_verify_service_sid}/Verifications"
        response = httpx.post(
            url,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            data={"To": phone, "Channel": channel},
            timeout=12.0,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.exception("Twilio Verify could not start a phone verification")
        return False


def check_phone_verification(phone: str, code: str) -> bool:
    if not all([settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_verify_service_sid]):
        return False
    try:
        url = f"https://verify.twilio.com/v2/Services/{settings.twilio_verify_service_sid}/VerificationCheck"
        response = httpx.post(
            url,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            data={"To": phone, "Code": code},
            timeout=12.0,
        )
        response.raise_for_status()
        return response.json().get("status") == "approved"
    except httpx.HTTPError:
        logger.exception("Twilio Verify code check failed")
        return False
