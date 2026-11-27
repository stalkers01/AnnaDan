"""Optional voluntary platform-contribution payments using Razorpay Checkout."""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.entities import PaymentContribution, User
from app.schemas.contracts import PaymentOrderInput, PaymentOrderRead, PaymentVerifyInput
from app.services.payments import razorpay_client

router = APIRouter(prefix="/payments", tags=["Voluntary contributions"])
logger = logging.getLogger(__name__)


@router.get("/config")
def payment_config():
    from app.core.config import settings
    return {"enabled": bool(settings.razorpay_key_id and settings.razorpay_key_secret),
            "key_id": settings.razorpay_key_id}


@router.post("/orders", response_model=PaymentOrderRead)
def create_contribution_order(
    payload: PaymentOrderInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    amount_paise = payload.amount_inr * 100
    try:
        provider_order = razorpay_client().order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"annadan-{current_user.id.hex[:10]}-{int(datetime.now(timezone.utc).timestamp())}",
            "notes": {"purpose": "voluntary_platform_contribution", "user_id": str(current_user.id)},
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Razorpay order creation failed")
        raise HTTPException(status_code=502, detail="The payment provider could not create an order.") from exc

    contribution = PaymentContribution(
        user_id=current_user.id,
        provider_order_id=provider_order["id"],
        amount_paise=amount_paise,
        currency="INR",
        status="created",
    )
    db.add(contribution)
    db.commit()
    db.refresh(contribution)
    from app.core.config import settings
    return PaymentOrderRead(
        contribution_id=contribution.id,
        order_id=contribution.provider_order_id,
        amount_paise=contribution.amount_paise,
        key_id=settings.razorpay_key_id,
    )


@router.post("/verify")
def verify_contribution_payment(
    payload: PaymentVerifyInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contribution = db.scalar(select(PaymentContribution).where(
        PaymentContribution.provider_order_id == payload.razorpay_order_id,
        PaymentContribution.user_id == current_user.id,
    ))
    if contribution is None:
        raise HTTPException(status_code=404, detail="Payment order not found.")
    if contribution.status == "paid":
        return {"message": "This contribution is already confirmed."}
    try:
        razorpay_client().utility.verify_payment_signature({
            "razorpay_order_id": payload.razorpay_order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "razorpay_signature": payload.razorpay_signature,
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Payment signature verification failed.") from exc
    try:
        payment_details = razorpay_client().payment.fetch(payload.razorpay_payment_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not confirm the payment capture status.") from exc
    if payment_details.get("order_id") != contribution.provider_order_id:
        raise HTTPException(status_code=400, detail="Payment does not belong to this order.")
    if payment_details.get("status") != "captured":
        return {"message": "Payment signature is valid; final confirmation is pending provider capture."}
    contribution.provider_payment_id = payload.razorpay_payment_id
    contribution.status = "paid"
    contribution.paid_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Thank you. Your contribution has been verified."}


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    from app.core.config import settings
    if not settings.razorpay_webhook_secret:
        raise HTTPException(status_code=503, detail="Payment webhook is not configured.")
    body = await request.body()
    try:
        client = razorpay_client()
        client.utility.verify_webhook_signature(body.decode("utf-8"), x_razorpay_signature or "", settings.razorpay_webhook_secret)
        event = json.loads(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid payment webhook signature or payload.") from exc

    if event.get("event") == "payment.captured":
        entity = event.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = entity.get("order_id")
        payment_id = entity.get("id")
        if order_id and payment_id:
            contribution = db.scalar(select(PaymentContribution).where(PaymentContribution.provider_order_id == order_id))
            if contribution and contribution.status != "paid":
                contribution.provider_payment_id = payment_id
                contribution.status = "paid"
                contribution.paid_at = datetime.now(timezone.utc)
                db.commit()
    return {"received": True}
