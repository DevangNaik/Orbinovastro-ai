"""Client-facing "Free Preview" -- an unpaid, ungated D1 (Rasi) chart
placement analysis shown to visitors on the public site, ending with a
call to book the full paid Diagnostic (the Overview Report).

UPDATE (2026-09-24, later still): the client's own explicit feedback on
the live page was that the original one-paragraph Ascendant+Moon blurb
"doesn't make the user order more... and doesn't even give trust." This
module was rewritten to be a genuinely extensive D1 analysis -- every one
of the chart's 9 planets plus the Ascendant, each placed into its own
house and paired with the client's own real, proprietary house/planet
framing (`overview_report/overview_labels.py`'s `HOUSE_LIFE_AREAS`/
`PLANET_SIGNIFICATIONS` -- the same real text now used in the paid
Overview Report), written in a precise, analytical register rather than
mainstream horoscope-column prose.

Design choices, all deliberate:

1. STILL template text, not an LLM call -- same reasoning as before, now
   more important, not less: this endpoint is free and explicitly NOT
   gated behind require_active_subscription (see main.py), so it is
   reachable by anyone, including automated abuse. A live OpenAI call per
   request would put an unbounded, uncapped cost on the client's own API
   budget for a feature with no payment wall. Every sentence below is
   composed deterministically from already-validated mechanical-layer
   chart data (ephemeris.py) and the client's own already-real label
   text -- free, instant, and exactly reproducible for the same input.

2. Deliberately STOPS at placement description, never scoring or
   judgment. This preview states WHERE each planet sits and WHICH of the
   client's own real house/planet domains that activates -- structural
   fact, not interpretation. It does not compute or imply which
   placements are under astrological "stress" or "support" (that is
   exactly what CCSI -- ai_app/backend/app/engine/hit_calc.py + ccsi.py,
   132/132 validated against the client's real HIT_CALC output -- does,
   and CCSI is the paid Overview Report's core differentiator). Keeping
   that line bright is what makes the free/paid boundary a genuine,
   honest value gap rather than an arbitrary paywall -- and the closing
   `upgrade_pitch` says so explicitly, in the same precise register,
   rather than a generic "unlock your full reading" sales line.

3. Register: written for a professionally sophisticated reader, not a
   mass-market horoscope audience -- the client's own explicit
   instruction. Analytical vocabulary (signifies/governs/domain/
   structural/diagnostic), full sentences, no mystical filler, numbers
   stated as numbers. Classical structural facts used below (which
   houses are "kendra"/angular, which are "trikona"/trine) are standard,
   textbook Vedic terminology, not the client's own proprietary scoring
   -- used only descriptively (counts), never as a favorability verdict.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ephemeris import NatalChart, sign_index_for_longitude, whole_sign_house
from .overview_report.overview_labels import HOUSE_LIFE_AREAS, PLANET_SIGNIFICATIONS

DEFAULT_BOOKING_URL = "https://orbinovastro.square.site/s/appointments"

ORDINALS: dict[int, str] = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth",
    7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth",
}

# Standard classical (textbook) house groupings -- not proprietary, used only
# to state structural counts, never a favorability judgment. Houses 1/4/7/10
# are "kendra" (angular); 1/5/9 are "trikona" (trine).
KENDRA_HOUSES = (1, 4, 7, 10)
TRIKONA_HOUSES = (1, 5, 9)

# One verb phrase per planet (Su, Mo, Ma, Me, Ju, Ve, Sa, Ra, Ke, in that
# fixed order -- matching ephemeris.compute_natal_chart's own planet order),
# used to vary the "structural implication" sentence across the nine
# placements without resorting to a random choice (this module must stay
# fully deterministic -- see module docstring, point 1).
_PLACEMENT_VERBS = [
    "channels its core signification into",
    "concentrates its influence within",
    "directs its characteristic drive toward",
    "expresses its governing function through",
    "extends its structural influence over",
    "anchors its principal effect within",
    "exercises its disciplining influence upon",
    "routes its underlying pull into",
    "resolves its detaching influence within",
]

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

SUN_BLURBS: dict[str, str] = {
    "Aries": "A Sun in Aries anchors identity in initiative -- decisive, self-directed, energized by being first.",
    "Taurus": "A Sun in Taurus anchors identity in stability -- patient, resource-conscious, consistent under pressure.",
    "Gemini": "A Sun in Gemini anchors identity in versatility -- articulate, adaptive, driven by the exchange of ideas.",
    "Cancer": "A Sun in Cancer anchors identity in care -- protective of what it builds, loyal, guided by instinct.",
    "Leo": "A Sun in Leo anchors identity in leadership -- confident, visible, motivated by meaningful recognition.",
    "Virgo": "A Sun in Virgo anchors identity in competence -- methodical, detail-oriented, defined by the standard of its own work.",
    "Libra": "A Sun in Libra anchors identity in relationship and fairness -- diplomatic, collaborative, calibrated to context.",
    "Scorpio": "A Sun in Scorpio anchors identity in depth -- strategic, resilient, comfortable operating below the surface.",
    "Sagittarius": "A Sun in Sagittarius anchors identity in purpose and expansion -- principled, direct, oriented toward the larger picture.",
    "Capricorn": "A Sun in Capricorn anchors identity in achievement -- disciplined, long-horizon in its thinking, unmoved by short-term setbacks.",
    "Aquarius": "A Sun in Aquarius anchors identity in independent thinking -- systems-oriented, unconventional, future-facing.",
    "Pisces": "A Sun in Pisces anchors identity in intuition -- adaptive, compassionate, responsive to the wider context around it.",
}


def _split_label(text: str) -> tuple[str, str]:
    """Splits the client's own "<short label> — <facets sentence>" format
    (see overview_labels.py's own docstring re: this exact convention)
    into (short_label, facets), trimmed. Falls back gracefully if the em
    dash is missing rather than raising, since this feeds public-facing
    copy, not the validated internal parsers."""
    if "—" in text:
        label, _, facets = text.partition("—")
        return label.strip(), facets.strip().rstrip(".")
    return text.strip(), ""


@dataclass
class PlanetPlacement:
    code: str
    name: str
    sign: str
    house: int
    retrograde: bool
    governs: str        # short signification label, e.g. "Wisdom/Growth"
    house_domain: str    # short house life-area label, e.g. "Creativity/Children"
    narrative: str       # the full analytical sentence(s) for this placement


@dataclass
class TeaserResult:
    ascendant_sign: str
    moon_sign: str
    sun_sign: str
    headline: str
    blurb: str
    executive_summary: str
    placements: list[PlanetPlacement]
    synthesis: str
    upgrade_pitch: str
    book_url: str


def _ordinal(house: int) -> str:
    return ORDINALS.get(house, str(house))


def _placement_narrative(index: int, planet_name: str, sig_label: str, sig_desc: str,
                           house_num: int, house_label: str, house_desc: str,
                           sign: str, retrograde: bool) -> str:
    verb = _PLACEMENT_VERBS[index % len(_PLACEMENT_VERBS)]
    retro_clause = (
        f" This placement was retrograde at the time of birth -- classical "
        f"practice reads this as an internally processed, reassessed "
        f"expression of {sig_label.lower()} rather than a diminished one."
        if retrograde else ""
    )
    return (
        f"{planet_name} -- karaka (significator) for {sig_label} ({sig_desc}) -- "
        f"is positioned in {sign}, within the {_ordinal(house_num)} house: "
        f"{house_label} ({house_desc}).{retro_clause} In structural terms, "
        f"{planet_name} {verb} the domain of {house_label.lower()}, making "
        f"this house one of the principal channels through which "
        f"{sig_label.lower()} is expressed in this chart."
    )


def build_teaser(chart: NatalChart, name: str = "", book_url: str = DEFAULT_BOOKING_URL) -> TeaserResult:
    asc_sign = chart.ascendant.sign
    asc_sign_index = sign_index_for_longitude(chart.ascendant.longitude)

    sun = next((p for p in chart.planets if p.code == "Su"), None)
    moon = next((p for p in chart.planets if p.code == "Mo"), None)
    sun_sign = sun.sign if sun else "?"
    moon_sign = moon.sign if moon else "?"

    who = name.strip() or "You"
    headline = f"{who} rise{'s' if name.strip() else ''} in {asc_sign}, Moon in {moon_sign}."

    asc_blurb = ASCENDANT_BLURBS.get(asc_sign, "")
    moon_blurb = MOON_BLURBS.get(moon_sign, "")
    sun_blurb = SUN_BLURBS.get(sun_sign, "")
    blurb = f"{asc_blurb} {moon_blurb}".strip()

    possessive = f"{name.strip()}'s" if name.strip() else "This chart's"
    asc_label, _asc_desc = _split_label(HOUSE_LIFE_AREAS[1])
    executive_summary = (
        f"{possessive} Ascendant (Lagna) -- the structural frame through which "
        f"every other placement in this chart is expressed, and the significator "
        f"of {asc_label} -- falls in {asc_sign}. {asc_blurb} "
        f"The Sun, seat of core identity and executive will, is placed in "
        f"{sun_sign}: {sun_blurb} "
        f"The Moon, governing cognitive and emotional processing, is placed in "
        f"{moon_sign}: {moon_blurb} "
        f"Ascendant, Sun, and Moon together form the chart's baseline operating "
        f"profile -- the reference frame against which the full nine-planet, "
        f"twelve-house structure below is read."
    ).strip()

    # Ascendant itself, as the first row of the placement table (house 1 by
    # definition; uses the same real HOUSE_LIFE_AREAS/PLANET_SIGNIFICATIONS
    # text as every other row, for consistency).
    asc_gov_label, asc_gov_desc = _split_label(PLANET_SIGNIFICATIONS["Asc"])
    asc_house_label, asc_house_desc = _split_label(HOUSE_LIFE_AREAS[1])
    placements: list[PlanetPlacement] = [
        PlanetPlacement(
            code="Asc", name="Ascendant", sign=asc_sign, house=1, retrograde=False,
            governs=asc_gov_label, house_domain=asc_house_label,
            narrative=(
                f"The Ascendant -- karaka (significator) for {asc_gov_label} "
                f"({asc_gov_desc}) -- rises in {asc_sign}, defining the first "
                f"house: {asc_house_label} ({asc_house_desc}). Every other "
                f"placement in this chart is read relative to this one, making "
                f"it the fixed reference point of the entire structure."
            ),
        )
    ]

    for i, planet in enumerate(chart.planets):
        house_num = whole_sign_house(sign_index_for_longitude(planet.longitude), asc_sign_index)
        sig_label, sig_desc = _split_label(PLANET_SIGNIFICATIONS.get(planet.code, planet.name))
        house_label, house_desc = _split_label(HOUSE_LIFE_AREAS.get(house_num, f"House {house_num}"))
        narrative = _placement_narrative(
            i, planet.name, sig_label, sig_desc, house_num, house_label, house_desc,
            planet.sign, planet.retrograde,
        )
        placements.append(PlanetPlacement(
            code=planet.code, name=planet.name, sign=planet.sign, house=house_num,
            retrograde=planet.retrograde, governs=sig_label, house_domain=house_label,
            narrative=narrative,
        ))

    graha_houses = [p.house for p in placements if p.code != "Asc"]
    kendra_count = sum(1 for h in graha_houses if h in KENDRA_HOUSES)
    trikona_count = sum(1 for h in graha_houses if h in TRIKONA_HOUSES)
    occupied_houses = len(set(graha_houses))

    synthesis = (
        f"Viewed as a whole, this chart distributes its nine planetary "
        f"placements across {occupied_houses} of the twelve houses. "
        f"{kendra_count} of 9 placements fall in the angular (kendra) houses "
        f"-- the first, fourth, seventh, and tenth, the classical structural "
        f"axis of self, home, partnership, and career -- and {trikona_count} "
        f"of 9 fall in the trinal (trikona) houses -- the first, fifth, and "
        f"ninth, associated with fortune, creativity, and higher purpose. "
        f"These are structural counts, not a verdict of favorability: this "
        f"preview describes WHERE each planet sits, not whether that "
        f"placement is presently operating under supportive or adverse "
        f"astrological pressure."
    )

    upgrade_pitch = (
        f"This is precisely where the free preview stops, by design. "
        f"Placement -- which sign, which house, which of your twelve life "
        f"domains each planet activates -- is descriptive fact, "
        f"and it is shown above in full, across all nine planets and the "
        f"Ascendant. What it does not yet tell you is how those placements "
        f"interact: which houses are presently reinforced and which are "
        f"under measurable stress, both in this natal chart and under "
        f"today's transiting sky, and how your current planetary period "
        f"(dasha) is activating specific placements right now. That "
        f"quantified, house-by-house diagnostic -- built on this practice's "
        f"own proprietary connection-and-stress scoring methodology -- is "
        f"the core of the full Diagnostic Report, delivered as a complete "
        f"written assessment, not a set of raw numbers."
    )

    return TeaserResult(
        ascendant_sign=asc_sign, moon_sign=moon_sign, sun_sign=sun_sign,
        headline=headline, blurb=blurb, executive_summary=executive_summary,
        placements=placements, synthesis=synthesis, upgrade_pitch=upgrade_pitch,
        book_url=book_url,
    )
