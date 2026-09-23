"""Client-facing "teaser" overview -- a short, appealing, free preview
meant to be shown to visitors on the public site, ending with a call to
book the full paid consultation. Deliberately NOT a reading: no
predictions, no significators, no dasha/timing judgment -- just the
ascendant and Moon sign (both from the validated mechanical layer) paired
with a short, warm, general-personality blurb, the same kind of
sign-level framing common in mainstream astrology media.

Design choice: this is template text, not an LLM call. A marketing
teaser doesn't need interpretation of this specific chart's finer
detail (that's the paid reading) -- it needs a warm, accurate-at-the-
sign-level, instantly reproducible blurb, and templated text is
deterministic, free, and trivially testable, unlike an LLM call.

This endpoint is intentionally NOT gated behind require_active_subscription
even when auth is turned on -- its whole purpose is to attract visitors
who haven't paid yet.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ephemeris import NatalChart

DEFAULT_BOOKING_URL = "https://orbinovastro.square.site/s/appointments"

ASCENDANT_BLURBS: dict[str, str] = {
    "Aries": "An Aries ascendant meets the world head-on -- direct, quick to act, energized by a challenge.",
    "Taurus": "A Taurus ascendant moves at its own steady pace -- grounded, dependable, drawn to comfort and quality.",
    "Gemini": "A Gemini ascendant greets life with curiosity -- quick-witted, sociable, always following the next question.",
    "Cancer": "A Cancer ascendant leads with feeling -- protective, intuitive, attuned to the emotional undercurrent of a room.",
    "Leo": "A Leo ascendant carries natural warmth and presence -- generous, expressive, hard to overlook.",
    "Virgo": "A Virgo ascendant approaches life with care and precision -- observant, practical, quietly exacting.",
    "Libra": "A Libra ascendant seeks balance and connection -- diplomatic, charming, attentive to fairness.",
    "Scorpio": "A Scorpio ascendant meets the world with intensity -- perceptive, private, drawn beneath the surface of things.",
    "Sagittarius": "A Sagittarius ascendant approaches life as an open road -- optimistic, candid, restless for the bigger picture.",
    "Capricorn": "A Capricorn ascendant carries quiet discipline -- composed, ambitious, patient in the way it builds.",
    "Aquarius": "An Aquarius ascendant stands a little apart -- independent-minded, original, drawn to ideas ahead of their time.",
    "Pisces": "A Pisces ascendant moves through life with sensitivity -- imaginative, empathetic, attuned to what isn't said aloud.",
}

MOON_BLURBS: dict[str, str] = {
    "Aries": "Paired with a Moon that feels things fast and moves on just as quickly -- an emotional world built for momentum.",
    "Taurus": "Paired with a Moon that finds comfort in the steady and familiar -- an emotional world that values security.",
    "Gemini": "Paired with a Moon that processes feeling through words and ideas -- an emotional world that thinks out loud.",
    "Cancer": "Paired with a Moon fully at home in feeling -- an emotional world that is deep, protective, and rememberful.",
    "Leo": "Paired with a Moon that needs warmth and recognition -- an emotional world that shines brightest when seen.",
    "Virgo": "Paired with a Moon that finds calm in order -- an emotional world that steadies itself through care and routine.",
    "Libra": "Paired with a Moon that seeks harmony in its closest bonds -- an emotional world tuned to others.",
    "Scorpio": "Paired with a Moon that feels everything at full depth -- an emotional world that holds on tightly and privately.",
    "Sagittarius": "Paired with a Moon that needs room to roam -- an emotional world that finds comfort in freedom and meaning.",
    "Capricorn": "Paired with a Moon that steadies itself through responsibility -- an emotional world that quietly carries a lot.",
    "Aquarius": "Paired with a Moon that keeps a thoughtful distance -- an emotional world that processes feeling through perspective.",
    "Pisces": "Paired with a Moon that dissolves easily into feeling -- an emotional world that is porous, dreamy, compassionate.",
}


@dataclass
class TeaserResult:
    ascendant_sign: str
    moon_sign: str
    headline: str
    blurb: str
    book_url: str


def build_teaser(chart: NatalChart, name: str = "", book_url: str = DEFAULT_BOOKING_URL) -> TeaserResult:
    asc_sign = chart.ascendant.sign
    moon = next((p for p in chart.planets if p.code == "Mo"), None)
    moon_sign = moon.sign if moon else "?"

    who = name.strip() or "You"
    headline = f"{who} rise{'s' if name.strip() else ''} in {asc_sign}, Moon in {moon_sign}."

    asc_blurb = ASCENDANT_BLURBS.get(asc_sign, "")
    moon_blurb = MOON_BLURBS.get(moon_sign, "")
    blurb = f"{asc_blurb} {moon_blurb}".strip()

    return TeaserResult(
        ascendant_sign=asc_sign, moon_sign=moon_sign,
        headline=headline, blurb=blurb, book_url=book_url,
    )
