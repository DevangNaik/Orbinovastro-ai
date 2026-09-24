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
safe to expose everywhere the chart data itself is shown.

UPDATE (2026-09-24, later still): `_DIGNITY`, `_COMBUSTION_ORBS`,
`dignity_flag()`, and `is_vargottama()` moved here from `teaser.py`, and a
new `planet_flags()` added, for the same reason `SIGN_TRAITS`/
`NAKSHATRA_THEMES` moved here in the previous round -- so `/api/chart`
(chart.py) can compute the exact same Retrograde/Combust/Exalted/
Debilitated/Own Sign/Vargottama flags the Free Preview (teaser.py) already
did, off the SAME tables, instead of never computing them at all. That gap
was a real bug the client caught live: the Planet Details Table under the
chart-wheel views (built from `/api/chart`, not `/api/teaser`) only ever
had `/api/chart`'s plain `retrograde` boolean to show, so a planet like
Jupiter sitting in its sign of debilitation showed no "Debilitated" badge
there even though `teaser.py`'s own Free Preview text already stated it
correctly, a few tabs over, off the same underlying chart data.
`teaser.py` now imports `_COMBUSTION_ORBS`, `dignity_flag`, and
`is_vargottama` from here instead of keeping its own copies, so the two
features can no longer silently drift apart the way they just did."""
from __future__ import annotations

from .ephemeris import sign_index_for_longitude
from .varga import navamsa_sign_index

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


# Standard classical planetary dignity (Uccha/exaltation, Neecha/
# debilitation, Swakshetra/own sign) for the seven classical grahas --
# textbook astronomy-adjacent astrology, not proprietary. Deliberately
# excludes Rahu/Ketu: their dignity convention varies meaningfully across
# schools (KP vs. Parashari) with no single agreed answer, so asserting one
# here risks contradicting a visitor's own tradition rather than adding
# credibility. Moved here (2026-09-24, later still) from teaser.py -- see
# module docstring.
_DIGNITY: dict[str, dict[str, object]] = {
    "Su": {"exalted": "Aries", "debilitated": "Libra", "own": {"Leo"}},
    "Mo": {"exalted": "Taurus", "debilitated": "Scorpio", "own": {"Cancer"}},
    "Ma": {"exalted": "Capricorn", "debilitated": "Cancer", "own": {"Aries", "Scorpio"}},
    "Me": {"exalted": "Virgo", "debilitated": "Pisces", "own": {"Gemini", "Virgo"}},
    "Ju": {"exalted": "Cancer", "debilitated": "Capricorn", "own": {"Sagittarius", "Pisces"}},
    "Ve": {"exalted": "Pisces", "debilitated": "Virgo", "own": {"Taurus", "Libra"}},
    "Sa": {"exalted": "Libra", "debilitated": "Aries", "own": {"Capricorn", "Aquarius"}},
}

# Standard (Parashari) combustion orbs in degrees -- how close a planet has
# to sit to the Sun before classical practice treats it as "combust" (its
# own signification temporarily overshadowed by the Sun's glare). These are
# the commonly-cited classical values, NOT read from the client's own
# workbook (see module docstring). The Sun can't be combust with itself,
# and the lunar nodes are excluded -- classical combustion is specifically
# a Sun-proximity effect on a physical planet. Moved here (2026-09-24,
# later still) from teaser.py -- see module docstring.
_COMBUSTION_ORBS: dict[str, float] = {
    "Mo": 12.0, "Ma": 17.0, "Me": 14.0, "Ju": 11.0, "Ve": 10.0, "Sa": 15.0,
}


def dignity_flag(code: str, sign: str) -> str | None:
    """"Exalted" / "Debilitated" / "Own Sign" / None, for the 7 classical
    grahas. Moved here (2026-09-24, later still) from teaser.py so
    /api/chart (chart.py) can compute the exact same flag teaser.py's Free
    Preview already did, instead of never computing it at all."""
    info = _DIGNITY.get(code)
    if not info:
        return None
    if sign == info["exalted"]:
        return "Exalted"
    if sign == info["debilitated"]:
        return "Debilitated"
    if sign in info["own"]:
        return "Own Sign"
    return None


def is_vargottama(longitude: float) -> bool:
    """True when this longitude's D1 (Rasi) sign matches its D9 (Navamsa)
    sign -- reused by both teaser.py and chart.py (moved here 2026-09-24,
    later still) so the two can never disagree on which placements are
    Vargottama. Pure sign-index math via varga.py's already-built
    `navamsa_sign_index` (not a proprietary import -- see teaser.py's own
    AST-level guard test allowlist)."""
    return sign_index_for_longitude(longitude) == navamsa_sign_index(longitude)


def planet_flags(
    code: str, sign: str, longitude: float, retrograde: bool,
    sun_longitude: float | None,
) -> list[str]:
    """The full Retrograde / Combust / Exalted / Debilitated / Own Sign /
    Vargottama flag list for one planet, in that fixed order -- the SAME
    classical rules and tables teaser.py's Free Preview already used,
    centralized here (2026-09-24, later still) so /api/chart (chart.py)
    renders identical flags instead of only ever exposing the plain
    `retrograde` boolean. `sun_longitude=None` (no Sun in the planet list
    passed in, shouldn't normally happen) simply skips the Combust check
    rather than raising."""
    flags: list[str] = []
    if retrograde:
        flags.append("Retrograde")
    orb = _COMBUSTION_ORBS.get(code)
    if orb is not None and sun_longitude is not None:
        if angular_separation(longitude, sun_longitude) <= orb:
            flags.append("Combust")
    dflag = dignity_flag(code, sign)
    if dflag:
        flags.append(dflag)
    if is_vargottama(longitude):
        flags.append("Vargottama")
    return flags


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
