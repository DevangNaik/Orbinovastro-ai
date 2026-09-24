"""Shared, non-proprietary chart-narrative helpers used by BOTH the free
Preview (teaser.py) and the plain mechanical-layer Chart endpoint
(chart.py) -- factored out here so the same sign/nakshatra phrase banks
aren't duplicated (and can't silently drift apart) between the two.

UPDATE (2026-09-24, latest): the client asked for the live D1/Bhava
Chalit/D9/Cuspal chart views to show the same richer per-planet detail
their own Excel Kundli chart does -- degree, nakshatra/pada, a short
"meaning of position" sentence, and which other planets it's in close
natal conjunction with (same D1 sign). `SIGN_TRAITS`/`NAKSHATRA_THEMES`
already existed in teaser.py for this exact purpose (building its
placement narratives); moved here unchanged so `/api/chart` can reuse
them for a new `meaning` field, and `teaser.py` now imports them from
here instead of defining its own copy. Standard, textbook classical
material throughout -- not the client's own proprietary Kundli-worksheet
interpretation text (see overview_report/kundli_chart.py's own docstring
for why that text isn't available to this port yet).

Also new this round: `natal_conjunctions()`, a plain angular-separation
check between planets sharing the same D1 (Rasi) sign -- matches what a
North Indian chart visually groups into one house box. This is generic
geometry (shortest angular distance), not a scoring judgment, so it's
safe to expose everywhere the chart data itself is shown."""
from __future__ import annotations

# Short, plain, sign-based color -- standard astrology, not proprietary,
# safe to author generically.
SIGN_TRAITS: dict[str, str] = {
    "Aries": "bold and quick to act",
    "Taurus": "steady and comfort-seeking",
    "Gemini": "curious and quick-thinking",
    "Cancer": "protective and deeply feeling",
    "Leo": "warm and hard to overlook",
    "Virgo": "careful and detail-driven",
    "Libra": "diplomatic and relationship-minded",
    "Scorpio": "intense and private",
    "Sagittarius": "adventurous and big-picture",
    "Capricorn": "disciplined and patient",
    "Aquarius": "independent and original",
    "Pisces": "sensitive and imaginative",
}

# Standard, textbook nakshatra (lunar mansion) themes -- generic, widely
# documented classical significations, not the client's proprietary data.
NAKSHATRA_THEMES: dict[str, str] = {
    "Ashwini": "quick starts, healing, and pioneering energy",
    "Bharani": "intensity, endurance, and carrying real responsibility",
    "Krittika": "sharp focus and cutting straight to what's true",
    "Rohini": "growth, beauty, and a pull toward what's genuinely pleasurable",
    "Mrigashira": "curiosity and a gentle, searching kind of exploration",
    "Ardra": "breakthroughs that tend to arrive through some upheaval first",
    "Punarvasu": "renewal, and a quiet resilience that keeps rebuilding",
    "Pushya": "nourishing others and steady, dependable care",
    "Ashlesha": "penetrating insight and a hard-to-read inner depth",
    "Magha": "legacy, lineage, and a natural claim to authority",
    "Purva Phalguni": "enjoyment, creativity, and a relaxed love of pleasure",
    "Uttara Phalguni": "steady partnership and quiet generosity",
    "Hasta": "practical skill and a knack for making things work",
    "Chitra": "craftsmanship and a natural sense of design or charisma",
    "Swati": "independence and a diplomatic, adaptable balance",
    "Vishakha": "focused, determined pursuit of a goal once it's chosen",
    "Anuradha": "devotion, loyalty, and strong, lasting friendships",
    "Jyeshtha": "seniority and a quiet sense of responsibility for others",
    "Mula": "getting to the root of things, even if it means uprooting first",
    "Purva Ashadha": "conviction and early, hard-won victories",
    "Uttara Ashadha": "lasting achievement built on principle, not luck",
    "Shravana": "listening, learning, and passing on what you know",
    "Dhanishta": "rhythm, recognition, and a pull toward group achievement",
    "Shatabhisha": "healing and an unconventional, independent approach",
    "Purva Bhadrapada": "intensity and a transformative kind of idealism",
    "Uttara Bhadrapada": "quiet depth and patient, long-view wisdom",
    "Revati": "gentle nurturing, compassion, and seeing things through",
}


# Standard classical benefic/malefic grouping for the 7 classical grahas
# plus the nodes -- universally taught, not a proprietary judgment. Matches
# the same grouping already used (for a different, scoring purpose) in
# hit_calc.py's own MALEFIC_PLANETS/BENEFIC_PLANETS -- duplicated here
# rather than imported, since teaser.py (which imports this module) must
# never import hit_calc.py, even transitively (see its own AST-guard test).
MALEFIC_PLANETS = {"Sa", "Ma", "Ra", "Ke"}
BENEFIC_PLANETS = {"Su", "Me", "Mo", "Ju", "Ve"}


def planet_nature(code: str) -> str:
    """"Malefic" / "Benefic" / "" (the Ascendant point, "Asc", has no
    classical nature of its own)."""
    if code in MALEFIC_PLANETS:
        return "Malefic"
    if code in BENEFIC_PLANETS:
        return "Benefic"
    return ""


def position_meaning(sign: str, nakshatra: str, pada: int) -> str:
    """One short sentence combining the nakshatra's theme and the sign's
    color -- e.g. "Sravana(4): listening, learning, and passing on what
    you know; Capricorn adds disciplined and patient." Matches the format
    of the client's own Excel Kundli chart's "Interpretation" column, built
    from the same two standard, textbook phrase banks above. Falls back
    gracefully (never raises) if a name isn't in either bank, so a data
    hiccup degrades to a shorter sentence rather than a 500 error."""
    nak_theme = NAKSHATRA_THEMES.get(nakshatra)
    sign_trait = SIGN_TRAITS.get(sign)
    nak_part = f"{nakshatra}({pada}): {nak_theme}" if nak_theme else f"{nakshatra}({pada})"
    sign_part = f"{sign} adds {sign_trait}" if sign_trait else sign
    return f"{nak_part}; {sign_part}."


def angular_separation(deg_a: float, deg_b: float) -> float:
    """Shortest angular distance between two zodiacal degrees, 0-180 --
    plain geometry, kept local (not imported from hit_calc.py) since
    teaser.py, which also uses this, must never import that module (see
    its own AST-level guard test)."""
    return abs((deg_a - deg_b + 180.0) % 360.0 - 180.0)


def natal_conjunctions(planets: list) -> dict:
    """For each planet (any object/dict-like with .code/.sign/.longitude
    attributes), lists every OTHER planet sharing its same D1 (Rasi) sign
    -- the same grouping a North Indian chart box visually shows -- along
    with the angular separation between them in degrees, closest first.
    A planet with nothing else in its sign gets an empty list, not an
    absent key. `planets` items need `.code`, `.sign`, `.longitude`
    attributes (matches ephemeris.py's PlanetInfo)."""
    result: dict[str, list[dict]] = {}
    for p in planets:
        same_sign = []
        for q in planets:
            if q.code == p.code or q.sign != p.sign:
                continue
            same_sign.append({
                "code": q.code,
                "orb_degrees": round(angular_separation(p.longitude, q.longitude), 2),
            })
        same_sign.sort(key=lambda item: item["orb_degrees"])
        result[p.code] = same_sign
    return result
