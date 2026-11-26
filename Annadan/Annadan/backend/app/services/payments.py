"""Razorpay adapter for voluntary Annadan platform contributions."""

from fastapi import HTTPException

from app.core.config import settings


def razorpay_client():
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(status_code=503, detail="Platform contributions are not configured yet.")
    import razorpay
    client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
    client.set_app_details({"title": "Annadan", "version": "1.0.0"})
    return client
