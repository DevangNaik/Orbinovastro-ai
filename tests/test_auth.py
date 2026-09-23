"""Tests for the auth/subscription scaffolding.

Two things matter here: (1) with AUTH_ENABLED unset/false (today's
default), every dependency is a true no-op -- nothing about existing
behavior changes; (2) once enabled, JWT verification and the subscriber
lookup actually work correctly against a locally-signed test token (no
real Supabase project needed to test the verification logic itself).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import app.auth as auth_module


@pytest.mark.anyio
async def test_get_current_user_is_noop_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(auth_module, "AUTH_ENABLED", False)
    result = await auth_module.get_current_user(authorization=None)
    assert result is None


@pytest.mark.anyio
async def test_require_active_subscription_is_noop_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(auth_module, "AUTH_ENABLED", False)
    result = await auth_module.require_active_subscription(user=None)
    assert result is None


@pytest.mark.anyio
async def test_get_current_user_requires_bearer_token_when_enabled(monkeypatch):
    monkeypatch.setattr(auth_module, "AUTH_ENABLED", True)
    with pytest.raises(Exception) as exc_info:
        await auth_module.get_current_user(authorization=None)
    assert "401" in str(exc_info.value) or "Sign in" in str(exc_info.value)


def test_verify_supabase_jwt_round_trip(monkeypatch):
    import jwt as pyjwt
    monkeypatch.setattr(auth_module, "SUPABASE_JWT_SECRET", "test-secret")
    token = pyjwt.encode(
        {"sub": "user-123", "email": "devang@example.com", "aud": "authenticated"},
        "test-secret", algorithm="HS256",
    )
    claims = auth_module.verify_supabase_jwt(token)
    assert claims["email"] == "devang@example.com"


def test_verify_supabase_jwt_rejects_wrong_secret(monkeypatch):
    import jwt as pyjwt
    monkeypatch.setattr(auth_module, "SUPABASE_JWT_SECRET", "real-secret")
    token = pyjwt.encode(
        {"sub": "user-123", "email": "attacker@example.com", "aud": "authenticated"},
        "wrong-secret", algorithm="HS256",
    )
    with pytest.raises(Exception):
        auth_module.verify_supabase_jwt(token)


def test_subscriber_upsert_and_lookup(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_module, "_DB_PATH", tmp_path / "subscribers_test.db")
    assert auth_module.subscriber_status("nobody@example.com") is None
    auth_module.upsert_subscriber("devang@example.com", "cus_123", "active")
    assert auth_module.subscriber_status("devang@example.com") == "active"
    # upsert again with a new status should overwrite, not duplicate
    auth_module.upsert_subscriber("devang@example.com", "cus_123", "canceled")
    assert auth_module.subscriber_status("devang@example.com") == "canceled"


@pytest.mark.anyio
async def test_require_active_subscription_blocks_without_active_status(monkeypatch, tmp_path):
    monkeypatch.setattr(auth_module, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_module, "_DB_PATH", tmp_path / "subscribers_test2.db")
    with pytest.raises(Exception) as exc_info:
        await auth_module.require_active_subscription(user={"email": "nosub@example.com"})
    assert "402" in str(exc_info.value) or "subscription" in str(exc_info.value)


@pytest.mark.anyio
async def test_require_active_subscription_allows_active_subscriber(monkeypatch, tmp_path):
    monkeypatch.setattr(auth_module, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_module, "_DB_PATH", tmp_path / "subscribers_test3.db")
    auth_module.upsert_subscriber("paid@example.com", "cus_456", "active")
    result = await auth_module.require_active_subscription(user={"email": "paid@example.com"})
    assert result == {"email": "paid@example.com"}


@pytest.fixture
def anyio_backend():
    return "asyncio"
