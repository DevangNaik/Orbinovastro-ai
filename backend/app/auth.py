"""Optional auth + subscription gate, OFF by default.

Design (matches what the client chose): Supabase Auth handles user
registration, login, and MFA (TOTP authenticator-app codes) and issues a
JWT; this app verifies that JWT itself (Supabase JWTs are standard
HS256-signed with the project's own JWT secret -- no network call needed
to check one) and checks a local subscriber record, kept in sync by a
Stripe webhook, for an active subscription.

Why Supabase Auth + Stripe, and not a direct Squarespace/Square bridge:
orbinovastro.com's existing commerce (Squarespace + built-in Square
Payments) is built to gate Squarespace's own pages -- it has no supported
way to gate a separate app running elsewhere. Stripe Billing is the
standard, well-documented way to add subscription gating to an app like
this one, and can run alongside Squarespace/Square without touching the
main site's existing checkout at all. Full reasoning + setup steps are in
the "User accounts, MFA & subscription gating" section of the roadmap doc.

This is disabled (AUTH_ENABLED=false, the default) until the client:
  1. Creates a Supabase project (free tier is enough) and turns on
     email+password sign-up and TOTP MFA under Authentication settings.
  2. Creates a Stripe account and a subscription Product/Price for this
     app, and points a webhook at POST /api/billing/webhook.
  3. Puts SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET,
     STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, and AUTH_ENABLED=true into
     backend/.env.
Account creation and billing setup are the client's own to do -- Claude
can't sign up for Supabase/Stripe or enter payment details on their
behalf. Everything here is the code side, ready to switch on once those
accounts exist.

While AUTH_ENABLED is false, every dependency below is a no-op
passthrough, so nothing about the app's current (open) behavior changes.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import jwt
from fastapi import Depends, Header, HTTPException

AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").strip().lower() == "true"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")

_DB_PATH = Path(__file__).resolve().parent.parent / "subscribers.db"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS subscribers ("
        "email TEXT PRIMARY KEY, stripe_customer_id TEXT, status TEXT, updated_at TEXT)"
    )
    return conn


def upsert_subscriber(email: str, stripe_customer_id: str, status: str, updated_at: str | None = None) -> None:
    """Record (or update) one customer's subscription status. Called by
    the Stripe webhook handler in billing.py -- not meant to be called
    directly except from tests."""
    updated_at = updated_at or datetime.now(timezone.utc).isoformat()
    conn = _db()
    with conn:
        conn.execute(
            "INSERT INTO subscribers (email, stripe_customer_id, status, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(email) DO UPDATE SET stripe_customer_id=excluded.stripe_customer_id, "
            "status=excluded.status, updated_at=excluded.updated_at",
            (email, stripe_customer_id, status, updated_at),
        )
    conn.close()


def subscriber_status(email: str) -> str | None:
    conn = _db()
    row = conn.execute("SELECT status FROM subscribers WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row[0] if row else None


def verify_supabase_jwt(token: str) -> dict:
    """Verify a Supabase-issued JWT locally against the project's JWT
    secret. Raises a jwt.PyJWTError subclass on failure."""
    return jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"], audience="authenticated")


async def get_current_user(authorization: str | None = Header(None)) -> dict | None:
    """FastAPI dependency. While AUTH_ENABLED is false: always returns
    None (today's open-access behavior, unchanged). Once enabled: requires
    a valid 'Authorization: Bearer <supabase jwt>' header, returns the
    decoded claims, or raises 401."""
    if not AUTH_ENABLED:
        return None
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in required.")
    token = authorization[len("Bearer "):].strip()
    try:
        return verify_supabase_jwt(token)
    except Exception as exc:  # noqa: BLE001 -- any jwt failure -> clean 401
        raise HTTPException(status_code=401, detail=f"Invalid session: {exc}") from exc


async def require_active_subscription(user: dict | None = Depends(get_current_user)) -> dict | None:
    """FastAPI dependency for endpoints that should be gated behind a paid
    subscription. While AUTH_ENABLED is false: no-op (returns None,
    today's open-access behavior). Once enabled: requires get_current_user
    to have succeeded AND that user's email to have an 'active' status in
    the local subscriber table (populated by the Stripe webhook)."""
    if not AUTH_ENABLED:
        return None
    email = (user or {}).get("email")
    status = subscriber_status(email) if email else None
    if status != "active":
        raise HTTPException(
            status_code=402,
            detail="An active subscription is required to use this feature.",
        )
    return user
