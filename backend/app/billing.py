"""Stripe webhook receiver -- keeps the local subscriber table (checked by
auth.require_active_subscription) in sync with Stripe subscription state.

Inert (the route exists but always 503s) until STRIPE_WEBHOOK_SECRET is
configured. See app/auth.py's module docstring for the full setup this
depends on -- creating the Stripe account, product/price, and webhook is
the client's own action, not something done on their behalf here.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from .auth import upsert_subscriber

router = APIRouter()

STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

_ACTIVE_STATUSES = {"active", "trialing"}


def _email_from_event_object(obj: dict) -> str | None:
    """Stripe puts the customer's email in different places depending on
    the event type -- try the common spots before giving up."""
    return (
        obj.get("customer_email")
        or (obj.get("customer_details") or {}).get("email")
        or obj.get("email")
    )


@router.post("/api/billing/webhook")
async def stripe_webhook(request: Request) -> dict:
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Billing isn't configured yet (STRIPE_WEBHOOK_SECRET not set in .env).",
        )
    import stripe  # deferred: only needed once billing is actually configured

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {exc}") from exc

    obj = event["data"]["object"]
    now = datetime.now(timezone.utc).isoformat()
    event_type = event["type"]

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        email = _email_from_event_object(obj)
        status = "active" if obj.get("status") in _ACTIVE_STATUSES else obj.get("status", "inactive")
        if email:
            upsert_subscriber(email, obj.get("customer", ""), status, now)
    elif event_type == "customer.subscription.deleted":
        email = _email_from_event_object(obj)
        if email:
            upsert_subscriber(email, obj.get("customer", ""), "canceled", now)
    elif event_type == "checkout.session.completed":
        email = _email_from_event_object(obj)
        if email:
            upsert_subscriber(email, obj.get("customer", ""), "active", now)

    return {"received": True}
