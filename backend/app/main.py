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
  POST /api/ccsi          -> CCSI (Cusp Conflict Stress Indicator) connection
                              scoring -- FULLY VALIDATED (2026-09-24, 132/132
                              real cells) against the client's own HIT_CALC
                              output. Feeds the paid Overview Report. See
                              engine/ccsi.py.
  POST /api/overview-report -> STAGE 1 (2026-09-24) of the paid Overview
                              Report PDF: the core 5-part Life Balance Index
                              report, computed live from /api/ccsi's own
                              engine + an OpenAI interpretation pass, using
                              the client's own real house/planet life-area
                              wording (see engine/overview_report/
                              overview_labels.py). Does NOT yet include the
                              Kundli chart/Troubles & Misfortune/South
                              Indian chart pages (Stage 2, not started).
  POST /api/teaser        -> free, ungated "Free Preview": a full D1 chart
                              placement analysis (Ascendant + all 9 planets,
                              each with its own house, the client's own real
                              signification/house-domain wording, and an
                              analytical narrative), plus an executive
                              summary, a structural synthesis, and an
                              explicit upgrade pitch describing what the
                              paid Diagnostic Report adds -- deliberately
                              template text, no LLM call (see engine/
                              teaser.py's module docstring for why); its
                              whole purpose is to attract visitors who
                              haven't paid yet, so it is NOT gated behind a
                              subscription even once auth is turned on
  POST /api/chat          -> chat with the OpenAI assistant (non-streaming)
  POST /api/chat/stream   -> same, but Server-Sent Events token streaming
  GET  /                  -> serves the frontend (frontend/index.html)

All of /api/geocode, /api/chart, /api/kp-beta, /api/navamsa, /api/transit,
/api/ccsi, /api/overview-report, /api/chat* are gated behind require_active_subscription (see
app/auth.py) -- a no-op today (AUTH_ENABLED=false by default) and enforced
once the client sets up Supabase Auth + Stripe Billing and flips that flag
on. /api/teaser is deliberately NOT gated, even once auth is on -- see its
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

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import billing
from .auth import AUTH_ENABLED, SUPABASE_ANON_KEY, SUPABASE_URL, require_active_subscription
from .engine.ccsi import CCSI_DISCLAIMER, CcsiReport, compute_ccsi_report
from .engine.chart import build_chart_from_fields, chart_to_dict
from .engine.geocode import GeocodeError, geocode_and_resolve_offset
from .engine.ephemeris import BirthMoment
from .engine.hit_calc import CcsiRow
from .engine.kp import compute_kp_beta
from .engine.teaser import build_teaser
from .engine.transit import compute_transit, now_as_birth_moment
from .engine.varga import compute_navamsa
from .models import (
    BirthDetailsIn, CcsiOut, CcsiRequestIn, CcsiRowOut,
    ChartOut, ChatRequestIn, ChatResponseOut,
    GeocodeOut, GeocodeRequestIn, KPBetaOut,
    NavamsaOut, NavamsaPlanetOut, OverviewReportRequestIn, TeaserOut, TeaserPlacementOut,
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
    """Free, ungated "Free Preview": a full D1 chart placement analysis.
    Deliberately NOT gated behind require_active_subscription -- see
    module docstring above and engine/teaser.py."""
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
        sun_sign=teaser.sun_sign, headline=teaser.headline, blurb=teaser.blurb,
        executive_summary=teaser.executive_summary,
        placements=[TeaserPlacementOut(**vars(p)) for p in teaser.placements],
        synthesis=teaser.synthesis, upgrade_pitch=teaser.upgrade_pitch,
        book_url=teaser.book_url,
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


def _transit_moment_to_iso_utc(moment: BirthMoment) -> str:
    """Local civil moment -> ISO-8601 UTC timestamp string, same
    conversion `engine/transit.py`'s `compute_transit` uses for its own
    `iso_ts` return value."""
    from datetime import datetime, timedelta, timezone as dt_timezone

    local_dt = datetime(moment.year, moment.month, moment.day,
                         moment.hour, moment.minute, moment.second)
    ut_dt = local_dt - timedelta(hours=moment.utc_offset_hours)
    return ut_dt.replace(tzinfo=dt_timezone.utc).isoformat()


def _ccsi_row_out(row: CcsiRow) -> CcsiRowOut:
    return CcsiRowOut(
        houses={str(h): v for h, v in row.houses.items()},
        columns=dict(row.columns),
    )


def _resolve_natal_and_transit_moments(birth: BirthDetailsIn, transit) -> tuple[BirthMoment, BirthMoment, str]:
    """Shared by /api/ccsi and /api/overview-report: both take the exact
    same birth+transit request shape and need the exact same "None/omitted
    transit = right now, at the birth location" resolution logic. Returns
    (natal_moment, transit_moment, source), where source is "now (UTC)" or
    "custom" (matching /api/ccsi's original wording)."""
    natal_moment = BirthMoment(
        year=birth.year, month=birth.month, day=birth.day,
        hour=birth.hour, minute=birth.minute, second=birth.second,
        utc_offset_hours=birth.utc_offset_hours,
        latitude=birth.latitude, longitude=birth.longitude,
    )

    t = transit
    transit_lat = birth.latitude if (t is None or t.latitude is None) else t.latitude
    transit_lon = birth.longitude if (t is None or t.longitude is None) else t.longitude

    if t is None or t.year is None:
        transit_moment = now_as_birth_moment(transit_lat, transit_lon)
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
            latitude=transit_lat, longitude=transit_lon,
        )
        source = "custom"

    return natal_moment, transit_moment, source


def _resolve_transit_display_info(
    birth: BirthDetailsIn, transit, transit_moment: BirthMoment,
) -> tuple[str, float]:
    """2026-09-24, later still: split out of the Overview Report endpoint
    after the client caught a real generated PDF showing "Transit Place:
    Not available" and an unlabeled, silently-UTC transit time/timezone.
    `transit_moment` itself is always stored at whatever offset it happened
    to be built with by `_resolve_natal_and_transit_moments` (0.0/UTC for
    the "now, at the birth location" default) -- that's correct for
    computing planetary positions, but wrong to show a human as-is with no
    explanation. Returns (display_place, display_offset_hours): the actual
    location's name (or, lacking one, its coordinates -- never blank) and
    the UTC offset that location's own LOCAL time should be shown at.

    - No custom transit given (defaults to "now" at the birth location):
      the birth's own place/offset, since that's the location actually
      used.
    - Custom transit given: that transit's own `place` if supplied,
      otherwise its coordinates as a readable fallback; its own
      `utc_offset_hours`, since that's what the caller intended as this
      transit's local time (see `CcsiTransitDetailsIn.utc_offset_hours`'s
      docstring)."""
    is_custom = transit is not None and transit.year is not None
    if is_custom:
        place = transit.place or f"{transit_moment.latitude:.4f}, {transit_moment.longitude:.4f}"
        offset = transit.utc_offset_hours
    else:
        place = birth.place or f"{transit_moment.latitude:.4f}, {transit_moment.longitude:.4f}"
        offset = birth.utc_offset_hours
    return place, offset


@app.post("/api/ccsi", response_model=CcsiOut)
def api_ccsi(body: CcsiRequestIn, _user=Depends(require_active_subscription)) -> CcsiOut:
    """CCSI (Cusp Conflict Stress Indicator): the connection-scoring block
    that feeds the paid Overview Report. FULLY VALIDATED (2026-09-24) --
    132/132 real cells matched the client's own HIT_CALC output exactly,
    across all three variants (L, LT, TT) and both net/negative-only rows.
    See engine/ccsi.py and engine/hit_calc.py module docstrings for the
    full validation history and the (separate, documented) ayanamsa/node
    convention this uses versus /api/chart's."""
    try:
        natal_moment, transit_moment, source = _resolve_natal_and_transit_moments(body.birth, body.transit)
        report: CcsiReport = compute_ccsi_report(natal_moment, transit_moment)
        iso_ts = _transit_moment_to_iso_utc(transit_moment)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not compute CCSI: {exc}") from exc

    return CcsiOut(
        l_net=_ccsi_row_out(report.l_net),
        l_negative=_ccsi_row_out(report.l_negative),
        lt_net=_ccsi_row_out(report.lt_net),
        lt_negative=_ccsi_row_out(report.lt_negative),
        tt_net=_ccsi_row_out(report.tt_net),
        tt_negative=_ccsi_row_out(report.tt_negative),
        transit_time_utc=iso_ts,
        transit_time_source=source,
        disclaimer=CCSI_DISCLAIMER,
    )


def _require_openai_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set. Copy .env.example to .env and add your key.",
        )


@app.post("/api/overview-report")
def api_overview_report(body: OverviewReportRequestIn, _user=Depends(require_active_subscription)) -> Response:
    """STAGE 1 (2026-09-24) of the paid Overview Report PDF: the core
    5-part Life Balance Index report (Executive Assessment, Table 1 Houses,
    Table 2 Planets, Table 3 Strategic Focus, Table 4 Scorecard, Conclusion
    + Core Message), computed live end-to-end from /api/ccsi's own
    132/132-validated engine plus an OpenAI interpretation/guidance pass --
    no caller-supplied hardcoded data anywhere in the chain.

    Deliberately does NOT yet include the Kundli chart tables, Troubles &
    Misfortune page, or South Indian divisional charts -- see the project
    roadmap doc's "Overview Report pipeline audited" entry (2026-09-24) for
    why those are a separate, much larger Stage 2 audit, not started yet.
    `overview_pdf_writer.build_pdf()` already degrades gracefully without
    them (its own existing test harness proves this), so Stage 1 renders a
    complete, correctly-structured report -- just without those extra
    pages.

    2026-09-24, later still: the house life-area / planet-signification
    wording is now the client's own real `HIT_CALC` "LIFE AREA" text, not a
    placeholder (see `overview_labels.py`) -- `X-Labels-Are-Placeholder`
    now reads "false" for a normal request. Also as of the same date, the
    Transit Information block shows the transit's actual location (never
    blank) plus BOTH its local time and UTC time, explicitly labeled --
    see `_resolve_transit_display_info()` above.

    Returns the finished PDF as the raw response body (not JSON) --
    Content-Disposition names it "<client name>_overview.pdf"."""
    _require_openai_key()
    from openai import OpenAI

    from .engine.overview_report_builder import build_overview_report_pdf, safe_filename

    try:
        natal_moment, transit_moment, _source = _resolve_natal_and_transit_moments(body.birth, body.transit)
        transit_place, transit_display_offset = _resolve_transit_display_info(
            body.birth, body.transit, transit_moment,
        )
        client = OpenAI()
        result = build_overview_report_pdf(
            client, body.client_name, natal_moment, transit_moment,
            birth_place=body.birth.place,
            transit_place=transit_place,
            transit_display_offset_hours=transit_display_offset,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Overview report generation failed: {exc}") from exc

    filename = f"{safe_filename(body.client_name)}_overview.pdf"
    return Response(
        content=result.pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Labels-Are-Placeholder": "true" if result.labels_are_placeholder else "false",
        },
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
