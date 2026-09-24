"""Client-facing "Free Preview" -- an unpaid, ungated D1 (Rasi) chart
placement analysis shown to visitors on the public site, ending with a
call to book the full paid Diagnostic (the Overview Report).

UPDATE (2026-09-24, later still): the client's own explicit feedback on
the live page was that the original one-paragraph Ascendant+Moon blurb
"doesn't make the user order more... and doesn't even give trust." This
module was first rewritten to be a genuinely extensive D1 analysis -- every
one of the chart's 9 planets plus the Ascendant, each placed into its own
house and paired with the client's own real, proprietary house/planet
framing (`overview_report/overview_labels.py`'s `HOUSE_LIFE_AREAS`/
`PLANET_SIGNIFICATIONS` -- the same real text now used in the paid
Overview Report).

UPDATE (2026-09-24, later still again): that first rewrite used a dense,
academic register ("karaka," "significator," "structural terms," "principal
channels") per the client's own initial instruction to write it "in the
language of an MBA and higher learned person." Seeing it rendered, the
client corrected course: the actual AUDIENCE for this text is a site
VISITOR, not the client reviewing it -- and a visitor "does not know what
is structural position." Their words: give people what a placement MEANS
for them, in plain language, and build curiosity ("what's in it for me")
rather than academic precision. This module was rewritten again around
that instruction:

- Jargon removed: no "karaka," "significator," "structural terms,"
  "principal channels," or similar meta-commentary. Each placement is
  described as a plain-language, second-person statement of what it means
  for the visitor's life.
- The client's own real short labels (e.g. "Fortune/Dharma") are still
  surfaced -- this is real, proprietary, traceable content, not something
  to hide -- but woven in as "what this practice calls it" asides rather
  than the entire sentence's scaffolding.
- Curiosity/upsell framing is concentrated at the two bookends (the
  opening executive summary and the closing synthesis/upgrade_pitch)
  rather than repeated after every one of the ten placements, which would
  read as nagging rather than inviting.
- What a planet "represents" in each placement sentence is drawn ONLY from
  the client's own real `PLANET_SIGNIFICATIONS` facets (`sig_desc` below),
  never from a separately-authored generic-astrology description of that
  planet -- this client's own data does not always match textbook
  planetary meanings (e.g. their "Su" row reads as emotionally/nurturing
  rather than the more usual identity/authority framing), and inventing a
  separate generic description would silently contradict their own real
  data in the same paragraph. Sign-based color (`SIGN_TRAITS` below) is
  standard, non-proprietary, and safe to author generically.

Design choices carried over, both still deliberate:

1. STILL template text, not an LLM call -- this endpoint is free and
   explicitly NOT gated behind require_active_subscription (see main.py),
   so it is reachable by anyone, including automated abuse. A live OpenAI
   call per request would put an unbounded, uncapped cost on the client's
   own API budget for a feature with no payment wall. Every sentence below
   is composed deterministically from already-validated mechanical-layer
   chart data (ephemeris.py) and the client's own already-real label text
   -- free, instant, and exactly reproducible for the same input.

2. Deliberately STOPS at placement description, never scoring or
   judgment. This preview states WHERE each planet sits and WHAT part of
   the visitor's life that touches -- descriptive fact, not interpretation.
   It does not compute or imply which placements are under astrological
   "stress" or "support" (that is exactly what CCSI -- hit_calc.py +
   ccsi.py, 132/132 validated against the client's real HIT_CALC output --
   does, and CCSI is the paid Overview Report's core differentiator).
   Keeping that line bright is what makes the free/paid boundary a genuine,
   honest value gap rather than an arbitrary paywall -- the closing
   `upgrade_pitch` says so explicitly, in plain language, rather than a
   generic "unlock your full reading" sales line. Classical structural
   facts used in `synthesis` (which houses are "kendra"/angular, which are
   "trikona"/trine) are standard, textbook Vedic terminology, not the
   client's own proprietary scoring -- used only descriptively (counts),
   never as a favorability verdict.
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

# One plain-language closing clause per planet (Su, Mo, Ma, Me, Ju, Ve, Sa,
# Ra, Ke, in that fixed order -- matching ephemeris.compute_natal_chart's own
# planet order), so the ten placement sentences don't end on the exact same
# words nine times in a row. Deliberately plain, not jargon -- see module
# docstring re: dropping "structural terms"/"principal channels" language.
_PLACEMENT_CLOSERS = [
    "so this is one of the places in life where that side of you shows up most clearly",
    "so this house tends to be where that part of you gets tested and expressed",
    "so keep an eye here -- it's where that instinct plays out in real life",
    "so this is a natural outlet for that energy in your day-to-day",
    "so this house often becomes the stage where that trait takes center stage",
    "so that part of your nature tends to come out strongest right here",
    "so this is where you're likely to feel that pull most in practice",
    "so this house is a common home base for that side of your personality",
    "so this is one of the clearer windows into how that shows up for you",
]

# Short, plain, sign-based color -- standard astrology, not proprietary,
# safe to author generically. Used to keep each placement sentence from
# reading identically to the next, without touching the client's own real
# planet/house data.
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
    narrative: str       # the plain-language sentence(s) for this placement


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


def _retro_clause(retrograde: bool) -> str:
    if not retrograde:
        return ""
    return (
        " This one's retrograde in your chart, which in Vedic practice "
        "usually means the energy runs inward first -- more reflection "
        "and revisiting before action, not a weaker placement."
    )


def _placement_narrative(index: int, planet_name: str, sig_label: str, sig_desc: str,
                          house_num: int, house_label: str, house_desc: str,
                          sign: str, retrograde: bool) -> str:
    trait = SIGN_TRAITS.get(sign, "distinctly its own")
    closer = _PLACEMENT_CLOSERS[index % len(_PLACEMENT_CLOSERS)]
    return (
        f"Your {planet_name} sits in {sign} ({trait}), right in your "
        f"{_ordinal(house_num)} house -- what this practice calls your "
        f"{house_label} house, the part of life connected to {house_desc}. "
        f"{planet_name} itself represents {sig_desc} -- your {sig_label} -- "
        f"{closer}.{_retro_clause(retrograde)}"
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

    possessive = f"{name.strip()}'s" if name.strip() else "Your"
    executive_summary = (
        f"{possessive} chart opens with three placements that matter more "
        f"than any other: {asc_sign} rising, Sun in {sun_sign}, and Moon in "
        f"{moon_sign}. {asc_blurb} {sun_blurb} {moon_blurb} Together, these "
        f"three set the tone for everything else -- the nine planets and "
        f"twelve houses that follow are really this same story, told in "
        f"more detail."
    ).strip()

    # Ascendant itself, as the first row of the placement table (house 1 by
    # definition; uses the same real HOUSE_LIFE_AREAS/PLANET_SIGNIFICATIONS
    # text as every other row, for consistency).
    asc_gov_label, asc_gov_desc = _split_label(PLANET_SIGNIFICATIONS["Asc"])
    asc_house_label, asc_house_desc = _split_label(HOUSE_LIFE_AREAS[1])
    asc_trait = SIGN_TRAITS.get(asc_sign, "distinctly its own")
    placements: list[PlanetPlacement] = [
        PlanetPlacement(
            code="Asc", name="Ascendant", sign=asc_sign, house=1, retrograde=False,
            governs=asc_gov_label, house_domain=asc_house_label,
            narrative=(
                f"Your Ascendant -- what this practice calls your "
                f"{asc_gov_label} placement, covering {asc_gov_desc} -- "
                f"rises in {asc_sign} ({asc_trait}). It defines your first "
                f"house, the {asc_house_label} house: {asc_house_desc}. "
                f"Think of it as the filter everything else in your chart "
                f"passes through -- your natural approach to life, and the "
                f"first impression you make on anyone you meet."
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
        f"Step back and look at the whole chart: your nine planets are "
        f"spread across {occupied_houses} of the twelve houses in your "
        f"life. {kendra_count} of them sit in the four \"power houses\" -- "
        f"self, home, relationships, and career -- and {trikona_count} "
        f"fall in the luckiest, most fortune-linked houses in the chart. "
        f"That's the shape of it. What it doesn't tell you is which of "
        f"these areas are running smoothly for you right now and which "
        f"ones are under real pressure -- that's a completely different "
        f"question, tied to your current planetary period and today's sky, "
        f"and it's exactly what the full Diagnostic Report is built to "
        f"answer."
    )

    upgrade_pitch = (
        f"Here's the honest split between what's free and what's not. "
        f"Everything above tells you WHERE each planet sits and what part "
        f"of your life it touches -- that's placement, and you now have "
        f"all of it, for free. What it can't tell you is whether those "
        f"placements are currently working in your favor, running under "
        f"stress, or about to shift -- that's a moving picture, driven by "
        f"your current planetary period (dasha) and the sky right now, not "
        f"a fixed one. Mapping that out, house by house, planet by planet, "
        f"is exactly what the full Diagnostic Report does -- and if you've "
        f"read this far, you're probably already curious enough to want "
        f"that answer."
    )

    return TeaserResult(
        ascendant_sign=asc_sign, moon_sign=moon_sign, sun_sign=sun_sign,
        headline=headline, blurb=blurb, executive_summary=executive_summary,
        placements=placements, synthesis=synthesis, upgrade_pitch=upgrade_pitch,
        book_url=book_url,
    )
