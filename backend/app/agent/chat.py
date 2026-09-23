"""OpenAI-powered chat agent for the ORBINOVASTRO app.

Design principle carried over from the rest of this engagement: the LLM
never does astrology math itself. It can call four tools:
  - compute_chart: validated mechanical layer (positions/signs/nakshatras/
    houses), via Swiss Ephemeris.
  - compute_kp_significators_beta: standard KP Sub Lord + significator
    theory, explicitly labeled beta/unvalidated against the client's own
    production scoring (see app/engine/kp.py's module docstring).
  - geocode_place: place name -> real lat/lon/UTC offset (via
    app/engine/geocode.py), so the model never has to guess coordinates.
  - compute_transit: current (or given-moment) planetary positions placed
    against the natal chart (see app/engine/transit.py).
The model's only job is to read those numbers and explain them in plain
language, honestly caveated, never inventing a position or a prediction.
"""
from __future__ import annotations

import json
import os
from typing import AsyncGenerator, Iterable

from openai import AsyncOpenAI, OpenAI

from ..engine.chart import build_chart_from_fields, chart_to_dict
from ..engine.ephemeris import BirthMoment
from ..engine.geocode import GeocodeError, geocode_and_resolve_offset
from ..engine.kp import compute_kp_beta
from ..engine.transit import compute_transit, now_as_birth_moment
from ..models import BirthDetailsIn, ChatMessageIn

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are the ORBINOVASTRO assistant, a Vedic/KP astrology helper.

Scope and honesty rules (do not break these):
- You may ONLY state planetary positions, signs, nakshatras, ascendant,
  house cusps, sub lords, or significators that came from a tool call in
  THIS conversation. Never invent or estimate an astronomical position or
  a significator yourself.
- compute_chart is the validated mechanical layer -- trust it fully.
- compute_kp_significators_beta is EXPLICITLY BETA: standard textbook KP
  Sub Lord and significator theory, not yet cross-checked against this
  client's own production workbook output, and it does NOT include the
  client's proprietary weighted scoring/ranking system. Whenever you use
  it, say plainly that it's a beta feature and results may not match the
  production workbook exactly.
- This build does NOT include divisional charts beyond D1, dasha/bhukti
  period selection/timing, or the client's connection-scoring/ranking
  engine. If asked for predictions, event timing, or a ranked judgment,
  say plainly that isn't included yet, and offer what compute_chart /
  compute_kp_significators_beta (both clearly labeled) can tell them
  instead.
- The ayanamsa used is the standard Krishnamurti (KP) ayanamsa built into
  Swiss Ephemeris -- a stand-in until the client confirms their workbook's
  exact ayanamsa ("Devarajayan"). Mention this if asked why numbers might
  differ slightly from their production reports.

Getting birth details:
- If you don't have complete birth details yet (date, time, and a place
  OR exact latitude/longitude), ask the user for what's missing in plain
  conversation -- don't call a tool with guessed values.
- If the user gives a place name instead of exact coordinates, call
  geocode_place FIRST to get real latitude/longitude/UTC offset -- never
  guess or approximate these yourself. Only fall back to asking the user
  for exact coordinates if geocode_place fails to find the place.

Transit:
- compute_transit needs the SAME birth details as compute_chart, plus an
  optional specific date/time (if omitted, it uses right now). It tells
  you where the planets currently are, which natal house each falls in,
  and simple conjunctions with natal planets -- it does NOT do
  transit-to-natal aspects (trine/square/opposition) or dasha/bhukti
  overlay, so say so plainly if asked for those.
"""

CHART_TOOL = {
    "type": "function",
    "function": {
        "name": "compute_chart",
        "description": (
            "Compute a basic sidereal (KP ayanamsa) natal chart: planetary "
            "positions, signs, nakshatras, ascendant, and house cusps. "
            "This is the ONLY source of truth for astronomical positions -- "
            "never state a position without calling this."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "year": {"type": "integer"},
                "month": {"type": "integer"},
                "day": {"type": "integer"},
                "hour": {"type": "integer", "description": "0-23, local birth time"},
                "minute": {"type": "integer", "description": "0-59"},
                "second": {"type": "integer", "default": 0},
                "utc_offset_hours": {
                    "type": "number",
                    "description": "Timezone offset from UTC at birth, e.g. 5.5 for IST",
                },
                "latitude": {"type": "number", "description": "Decimal degrees, north positive"},
                "longitude": {"type": "number", "description": "Decimal degrees, east positive"},
            },
            "required": ["year", "month", "day", "hour", "minute",
                         "utc_offset_hours", "latitude", "longitude"],
        },
    },
}

KP_BETA_TOOL = {
    "type": "function",
    "function": {
        "name": "compute_kp_significators_beta",
        "description": (
            "BETA. Compute standard KP Sub Lord (per planet and house cusp) "
            "and the classical 4-level house significators (occupants, "
            "owner, star-lord-of-occupants, star-lord-of-owner). Does NOT "
            "include the client's proprietary scoring/ranking system. "
            "Always tell the user this is a beta feature when you use it. "
            "Takes the same birth parameters as compute_chart."
        ),
        "parameters": CHART_TOOL["function"]["parameters"],
    },
}

GEOCODE_TOOL = {
    "type": "function",
    "function": {
        "name": "geocode_place",
        "description": (
            "Look up a place name's real latitude, longitude, and the UTC "
            "offset its timezone actually used on the given date (DST/"
            "historical-zone aware). Always call this instead of guessing "
            "coordinates when the user gives a place name."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "place": {"type": "string", "description": "Free-text place name, e.g. 'Mumbai, India'"},
                "year": {"type": "integer"},
                "month": {"type": "integer"},
                "day": {"type": "integer"},
                "hour": {"type": "integer", "default": 12},
                "minute": {"type": "integer", "default": 0},
            },
            "required": ["place", "year", "month", "day"],
        },
    },
}

TRANSIT_TOOL = {
    "type": "function",
    "function": {
        "name": "compute_transit",
        "description": (
            "Compute current (or given-moment) sidereal planetary positions "
            "placed against the natal chart: which natal house each "
            "transiting planet falls in, plus simple conjunctions with "
            "natal planets. Takes the same birth parameters as "
            "compute_chart, plus optional transit_year/month/day/hour/"
            "minute/utc_offset_hours -- omit those to mean 'right now'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                **CHART_TOOL["function"]["parameters"]["properties"],
                "transit_year": {"type": "integer", "description": "Omit for right now"},
                "transit_month": {"type": "integer"},
                "transit_day": {"type": "integer"},
                "transit_hour": {"type": "integer"},
                "transit_minute": {"type": "integer"},
                "transit_utc_offset_hours": {"type": "number", "default": 0},
            },
            "required": CHART_TOOL["function"]["parameters"]["required"],
        },
    },
}

TOOLS = [CHART_TOOL, KP_BETA_TOOL, GEOCODE_TOOL, TRANSIT_TOOL]


def _run_chart_tool(args: dict) -> dict:
    chart = build_chart_from_fields(
        year=args["year"], month=args["month"], day=args["day"],
        hour=args["hour"], minute=args["minute"], second=args.get("second", 0),
        utc_offset_hours=args["utc_offset_hours"],
        latitude=args["latitude"], longitude=args["longitude"],
    )
    return chart_to_dict(chart)


def _run_kp_beta_tool(args: dict) -> dict:
    chart = build_chart_from_fields(
        year=args["year"], month=args["month"], day=args["day"],
        hour=args["hour"], minute=args["minute"], second=args.get("second", 0),
        utc_offset_hours=args["utc_offset_hours"],
        latitude=args["latitude"], longitude=args["longitude"],
    )
    return compute_kp_beta(chart)


def _run_geocode_tool(args: dict) -> dict:
    try:
        result = geocode_and_resolve_offset(
            args["place"], args["year"], args["month"], args["day"],
            args.get("hour", 12), args.get("minute", 0),
        )
    except GeocodeError as exc:
        return {"error": str(exc)}
    return {
        "place": result.place, "latitude": result.latitude, "longitude": result.longitude,
        "timezone_name": result.timezone_name, "utc_offset_hours": result.utc_offset_hours,
    }


def _run_transit_tool(args: dict) -> dict:
    natal_chart = build_chart_from_fields(
        year=args["year"], month=args["month"], day=args["day"],
        hour=args["hour"], minute=args["minute"], second=args.get("second", 0),
        utc_offset_hours=args["utc_offset_hours"],
        latitude=args["latitude"], longitude=args["longitude"],
    )
    if args.get("transit_year") is None:
        transit_moment = now_as_birth_moment(args["latitude"], args["longitude"])
    else:
        transit_moment = BirthMoment(
            year=args["transit_year"], month=args["transit_month"], day=args["transit_day"],
            hour=args["transit_hour"], minute=args["transit_minute"],
            utc_offset_hours=args.get("transit_utc_offset_hours", 0.0),
            latitude=args["latitude"], longitude=args["longitude"],
        )
    planets, iso_ts = compute_transit(natal_chart, transit_moment)
    return {
        "transit_time_utc": iso_ts,
        "planets": [vars(p) for p in planets],
    }


def _execute_tool(name: str, args: dict) -> dict:
    if name == "compute_chart":
        return _run_chart_tool(args)
    if name == "compute_kp_significators_beta":
        return _run_kp_beta_tool(args)
    if name == "geocode_place":
        return _run_geocode_tool(args)
    if name == "compute_transit":
        return _run_transit_tool(args)
    return {"error": f"unknown tool {name}"}


def _build_convo(messages: Iterable[ChatMessageIn], birth_details: BirthDetailsIn | None) -> list[dict]:
    convo: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if birth_details is not None:
        convo.append({
            "role": "system",
            "content": (
                "Known birth details for this conversation (use these with "
                "the tools unless the user gives different ones): "
                + birth_details.model_dump_json()
            ),
        })
    for m in messages:
        convo.append({"role": m.role, "content": m.content})
    return convo


def run_chat(
    messages: list[ChatMessageIn],
    birth_details: BirthDetailsIn | None,
    client: OpenAI | None = None,
) -> tuple[str, bool]:
    """Non-streaming variant (kept for simple/non-browser callers).
    Returns (reply_text, used_a_tool)."""
    client = client or OpenAI()
    convo = _build_convo(messages, birth_details)

    used_tool = False
    first = client.chat.completions.create(
        model=OPENAI_MODEL, messages=convo, tools=TOOLS, tool_choice="auto",
    )
    choice = first.choices[0]

    if choice.message.tool_calls:
        used_tool = True
        convo.append(choice.message.model_dump(exclude_none=True))
        for call in choice.message.tool_calls:
            args = json.loads(call.function.arguments)
            result = _execute_tool(call.function.name, args)
            convo.append({
                "role": "tool", "tool_call_id": call.id, "content": json.dumps(result),
            })
        second = client.chat.completions.create(model=OPENAI_MODEL, messages=convo)
        return second.choices[0].message.content or "", used_tool

    return choice.message.content or "", used_tool


async def run_chat_stream(
    messages: list[ChatMessageIn],
    birth_details: BirthDetailsIn | None,
    client: AsyncOpenAI | None = None,
) -> AsyncGenerator[dict, None]:
    """Streaming variant. Yields event dicts:
      {"type": "tool_used", "name": ...}   -- once, if a tool was called
      {"type": "token", "text": ...}       -- many, as the reply streams in
      {"type": "done"}                     -- once, at the end
      {"type": "error", "detail": ...}     -- on failure

    Two-call design: an initial non-streaming call decides whether a tool
    is needed and executes it; the final, user-visible answer always comes
    from a second, streaming call, so token-by-token output is real OpenAI
    streaming in both the tool and no-tool cases.
    """
    client = client or AsyncOpenAI()
    convo = _build_convo(messages, birth_details)

    try:
        first = await client.chat.completions.create(
            model=OPENAI_MODEL, messages=convo, tools=TOOLS, tool_choice="auto",
        )
        choice = first.choices[0]

        if choice.message.tool_calls:
            convo.append(choice.message.model_dump(exclude_none=True))
            for call in choice.message.tool_calls:
                args = json.loads(call.function.arguments)
                result = _execute_tool(call.function.name, args)
                yield {"type": "tool_used", "name": call.function.name}
                convo.append({
                    "role": "tool", "tool_call_id": call.id, "content": json.dumps(result),
                })

        stream = await client.chat.completions.create(
            model=OPENAI_MODEL, messages=convo, stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield {"type": "token", "text": delta.content}
        yield {"type": "done"}
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "detail": str(exc)}
