"""FastAPI app: the ORBINOVASTRO AI app.

Endpoints:
  GET  /api/auth-config   -> public: whether sign-in is turned on, + Supabase project info
  POST /api/billing/webhook -> Stripe subscription events (inert until configured)
  POST /api/geocode      -> place name -> lat/lon/UTC offset (no LLM call)
  POST /api/chart        -> mechanical-layer natal chart (no LLM call); each
                             planet includes both a Bhava Chalit house
                             ("house") and a classical D1/Rasi whole-sign
                             house ("rasi_house") -- see engine/chart.py
  POST /api/kp-beta       -> BETA: KP sub lords + significators (no LLM call)
  POST /api/navamsa       -> BETA: D9 Navamsa divisional chart (no LLM call)
  POST /api/transit       -> mechanical-layer transit vs natal chart (no LLM call)
  POST /api/teaser        -> free client-facing preview (ascendant/Moon sign
                              + blurb + booking link) -- NOT gated behind a
                              subscription; its whole purpose is to attract
                              visitors who haven't paid yet
  POST /api/chat          -> chat with the OpenAI assistant (non-streaming)
  POST /api/chat/stream   -> same, but Server-Sent Events token streaming
  GET  /                  -> serves the frontend (frontend/index.html)

All of /api/geocode, /api/chart, /api/kp-beta, /api/navamsa, /api/transit,
/api/chat* are gated behind require_active_subscription (see app/auth.py)
-- a no-op today (AUTH_ENABLED=false by default) and enforced once the
client sets up Supabase Auth + Stripe Billing and flips that flag on.
/api/teaser is deliberately NOT gated, even once auth is on -- see its
docstring below.

Run locally:
  uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env (OPENAI_API_KEY, OPENAI_MODEL) before anything reads
# os.environ. Must happen before the deferred `from .agent.chat import ...`
# imports below, since that module reads OPENAI_MODEL at import time.
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH if _ENV_PATH.exists() else None)

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import billing
from .auth import AUTH_ENABLED, SUPABASE_ANON_KEY, SUPABASE_URL, require_active_subscription
from .engine.chart import build_chart_from_fields, chart_to_dict
from .engine.geocode import GeocodeError, geocode_and_resolve_offset
from .engine.ephemeris import BirthMoment
from .engine.kp import compute_kp_beta
from .engine.teaser import build_teaser
from .engine.transit import compute_transit, now_as_birth_moment
from .engine.varga import compute_navamsa
from .models import (
    BirthDetailsIn, ChartOut, ChatRequestIn, ChatResponseOut,
    GeocodeOut, GeocodeRequestIn, KPBetaOut,
    NavamsaOut, NavamsaPlanetOut, TeaserOut,
    TransitOut, TransitPlanetOut, TransitRequestIn,
)

app = FastAPI(title="ORBINOVASTRO Basic AI App", version="0.1.0")

# ALLOWED_ORIGINS: comma-separated list of origins allowed to call this API
# from a browser (e.g. "https://orbinovastro.com,https://your-site.openai.site").
# Unset/empty defaults to "*" (any origin) for local development only -- set
# this env var in production so the API isn't wide open to every website.
_allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "").strip()
_allowed_origins = (
    [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
    if _allowed_origins_env
    else ["*"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


app.include_router(billing.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/auth-config")
def api_auth_config() -> dict:
    """Public config the frontend uses to decide whether to show a
    sign-in flow. supabase_anon_key is Supabase's public anonymous key --
    safe to expose to the browser by design (it has no privileged access
    on its own)."""
    return {
        "auth_enabled": AUTH_ENABLED,
        "supabase_url": SUPABASE_URL if AUTH_ENABLED else "",
        "supabase_anon_key": SUPABASE_ANON_KEY if AUTH_ENABLED else "",
    }


@app.post("/api/geocode", response_model=GeocodeOut)
def api_geocode(body: GeocodeRequestIn, _user=Depends(require_active_subscription)) -> GeocodeOut:
    """Place name -> latitude/longitude, plus the UTC offset that place's
    timezone actually used at the given date (DST/historical-zone aware).
    Pure lookup, no LLM call, no astrology judgment."""
    try:
        result = geocode_and_resolve_offset(
            body.place, body.year, body.month, body.day, body.hour, body.minute,
        )
    except GeocodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    note = ""
    if result.timezone_name is None:
        note = (
            "Could not resolve a timezone for this location (unusual -- "
            "double-check the place name, or enter the UTC offset manually)."
        )
    return GeocodeOut(
        place=result.place, latitude=result.latitude, longitude=result.longitude,
        timezone_name=result.timezone_name, utc_offset_hours=result.utc_offset_hours,
        note=note,
    )


@app.post("/api/chart", response_model=ChartOut)
def api_chart(body: BirthDetailsIn, _user=Depends(require_active_subscription)) -> ChartOut:
    try:
        chart = build_chart_from_fields(
            year=body.year, month=body.month, day=body.day,
            hour=body.hour, minute=body.minute, second=body.second,
            utc_offset_hours=body.utc_offset_hours,
            latitude=body.latitude, longitude=body.longitude,
        )
    except Exception as exc:  # noqa: BLE001 -- surface a clean 400 to the client
        raise HTTPException(status_code=400, detail=f"Could not compute chart: {exc}") from exc

    data = chart_to_dict(chart)
    return ChartOut(name=body.name, place=body.place, **data)


@app.post("/api/kp-beta", response_model=KPBetaOut)
def api_kp_beta(body: BirthDetailsIn, _user=Depends(require_active_subscription)) -> KPBetaOut:
    """BETA: standard KP Sub Lord + significator theory. See engine/kp.py
    module docstring for exactly what this is and isn't."""
    try:
        chart = build_chart_from_fields(
            year=body.year, month=body.month, day=body.day,
            hour=body.hour, minute=body.minute, second=body.second,
            utc_offset_hours=body.utc_offset_hours,
            latitude=body.latitude, longitude=body.longitude,
        )
        data = compute_kp_beta(chart)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not compute KP beta data: {exc}") from exc
    return KPBetaOut(**data)


@app.post("/api/navamsa", response_model=NavamsaOut)
def api_navamsa(body: BirthDetailsIn, _user=Depends(require_active_subscription)) -> NavamsaOut:
    """BETA: D9 Navamsa divisional chart, standard textbook formula. See
    engine/varga.py module docstring for exactly what this is and isn't."""
    try:
        chart = build_chart_from_fields(
            year=body.year, month=body.month, day=body.day,
            hour=body.hour, minute=body.minute, second=body.second,
            utc_offset_hours=body.utc_offset_hours,
            latitude=body.latitude, longitude=body.longitude,
        )
        nav = compute_navamsa(chart)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not compute Navamsa: {exc}") from exc
    return NavamsaOut(
        ascendant_navamsa_sign=nav.ascendant_navamsa_sign,
        ascendant_navamsa_sign_lord=nav.ascendant_navamsa_sign_lord,
        planets=[NavamsaPlanetOut(**vars(p)) for p in nav.planets],
        beta_disclaimer=nav.beta_disclaimer,
    )


@app.post("/api/teaser", response_model=TeaserOut)
def api_teaser(body: BirthDetailsIn) -> TeaserOut:
    """Free client-facing preview: ascendant + Moon sign (validated
    mechanical layer) paired with a short general-personality blurb and a
    link to book the full paid consultation. Deliberately NOT gated
    behind require_active_subscription -- see module docstring above and
    engine/teaser.py."""
    try:
        chart = build_chart_from_fields(
            year=body.year, month=body.month, day=body.day,
            hour=body.hour, minute=body.minute, second=body.second,
            utc_offset_hours=body.utc_offset_hours,
            latitude=body.latitude, longitude=body.longitude,
        )
        teaser = build_teaser(
            chart, name=body.name,
            book_url=os.environ.get("BOOKING_URL", "https://orbinovastro.square.site/s/appointments"),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not compute preview: {exc}") from exc
    return TeaserOut(
        ascendant_sign=teaser.ascendant_sign, moon_sign=teaser.moon_sign,
        headline=teaser.headline, blurb=teaser.blurb, book_url=teaser.book_url,
    )


@app.post("/api/transit", response_model=TransitOut)
def api_transit(body: TransitRequestIn, _user=Depends(require_active_subscription)) -> TransitOut:
    """Mechanical-layer transit: current (or given-moment) planetary
    positions placed against the natal chart's houses. See engine/transit.py
    module docstring for exactly what this is and isn't."""
    try:
        natal_chart = build_chart_from_fields(
            year=body.birth.year, month=body.birth.month, day=body.birth.day,
            hour=body.birth.hour, minute=body.birth.minute, second=body.birth.second,
            utc_offset_hours=body.birth.utc_offset_hours,
            latitude=body.birth.latitude, longitude=body.birth.longitude,
        )
        t = body.transit
        if t is None or t.year is None:
            transit_moment = now_as_birth_moment(body.birth.latitude, body.birth.longitude)
            source = "now (UTC)"
        else:
            if t.month is None or t.day is None or t.hour is None or t.minute is None:
                raise HTTPException(
                    status_code=400,
                    detail="Custom transit moment needs year, month, day, hour, and minute.",
                )
            transit_moment = BirthMoment(
                year=t.year, month=t.month, day=t.day, hour=t.hour, minute=t.minute,
                utc_offset_hours=t.utc_offset_hours,
                latitude=body.birth.latitude, longitude=body.birth.longitude,
            )
            source = "custom"
        planets, iso_ts = compute_transit(natal_chart, transit_moment)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not compute transit: {exc}") from exc

    return TransitOut(
        transit_time_utc=iso_ts, transit_time_source=source,
        planets=[TransitPlanetOut(**vars(p)) for p in planets],
    )


def _require_openai_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.",
        )


@app.post("/api/chat", response_model=ChatResponseOut)
def api_chat(body: ChatRequestIn, _user=Depends(require_active_subscription)) -> ChatResponseOut:
    _require_openai_key()
    from .agent.chat import run_chat  # deferred import: don't require openai key at boot

    try:
        reply, used_tool = run_chat(body.messages, body.birth_details)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Chat backend error: {exc}") from exc
    return ChatResponseOut(reply=reply, used_chart_tool=used_tool)


@app.post("/api/chat/stream")
def api_chat_stream(body: ChatRequestIn, _user=Depends(require_active_subscription)) -> StreamingResponse:
    """Server-Sent Events stream of the assistant's reply. Each event is a
    JSON object on one line, prefixed `data: `:
      {"type": "tool_used", "name": "..."}
      {"type": "token", "text": "..."}
      {"type": "done"} | {"type": "error", "detail": "..."}
    """
    _require_openai_key()
    from .agent.chat import run_chat_stream  # deferred import

    async def event_source():
        async for event in run_chat_stream(body.messages, body.birth_details):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(str(FRONTEND_DIR / "index.html"))
