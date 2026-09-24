"""Client-facing "Free Preview" -- an unpaid, ungated D1 (Rasi) sign +
cuspal (Bhava Chalit) house placement analysis shown to visitors on the
public site, ending with a call to book the full paid Diagnostic (the
Overview Report).

UPDATE (2026-09-24, latest): a batch of related fixes/additions, all from
the same round of client feedback on the live page:

1. Plain, human phrasing -- the previous draft's prose leaned hard on a
   single tic: stacking " -- " two and three times per sentence as a
   generic aside-connector, the same shape every time ("X -- what this
   practice calls Y -- Z"), which read as AI-generated rather than
   written by a person. Rewritten throughout: the em-dash habit is
   mostly gone (replaced with periods, commas, colons, parentheses, or
   just a different sentence shape), and -- since there are only 9
   planets, in a fixed, known order -- each of the 9 planet paragraphs
   below now has its own distinct sentence architecture (see
   `_PLACEMENT_TEMPLATES`) instead of one generic template reused nine
   times with only the closing clause varying.

2. New: Retrograde/Combust/Exalted/Debilitated/Own-Sign/Vargottama
   "flags", both as plain-language asides in the narrative AND as a new
   structured `PlanetPlacement.flags` list (so the frontend can render
   real badges, the same idea as the client's own Kundli worksheet's
   Flags column -- see overview_report/kundli_chart.py's FLAG_LEGEND --
   though this module does NOT read that worksheet; every flag here is
   computed fresh from already-validated ephemeris data using STANDARD
   classical rules, since the client's own exact Excel formulas for
   these flags live in the (unported, Stage-2, proprietary) Kundli sheet
   -- see kundli_chart.py's own module docstring: it only draws
   pre-computed flag strings, it doesn't compute them. Being explicit
   about this rather than silently claiming parity with the workbook:
   - Retrograde: real, exact -- straight from ephemeris.py (see its
     own docstring for a real bug fixed in this same round: Rahu was
     never marked retrograde, only Ketu was, an inconsistency the
     client caught by noticing Rahu never showed the marker).
   - Exalted / Debilitated / Own Sign: standard classical degrees for
     the 7 classical grahas (see `_DIGNITY`, unchanged from before this
     round) -- universally agreed across schools, so safe to state
     plainly. Deliberately excludes Rahu/Ketu (dignity convention for
     the nodes varies by school with no single agreed answer).
   - Combust: NEW this round. Standard (Parashari) combustion orbs --
     how close a planet sits to the Sun before classical practice
     treats its signification as "overshadowed." See `_COMBUSTION_ORBS`.
     Doesn't apply to the Sun itself or the nodes.
   - Vargottama: NEW this round. A planet landing in the exact same
     sign in both the D1 (Rasi) chart and the D9 (Navamsa) chart --
     computed by reusing `varga.py`'s already-built `navamsa_sign_index`
     (pure sign-index math, not a proprietary import -- see the
     AST-level guard test's allowlist). Because this depends on the D9
     Navamsa chart, which is itself labeled BETA elsewhere in this app
     (standard textbook D9 formula, not yet cross-checked against the
     client's own workbook), the Vargottama flag inherits that same
     beta caveat -- stated plainly in the disclaimer, not hidden.

House placement itself is unchanged from the previous round: cuspal
(Bhava Chalit / Nirayana bhava), matching /api/chart's own `house`
field, while sign (rashi) stays D1/Rasi. See the previous update note
below (kept for history) and the updated `disclaimer` default in
models.py's TeaserOut for the full reasoning.

UPDATE (2026-09-24, later still, history): house placement switched
from classical whole-sign (D1) counting to cuspal (Bhava Chalit /
Nirayana bhava) house placement -- the exact same `house_of_longitude`
cusp-segment function already used, and already validated, for
/api/chart's own `house` field and this engine's KP significators. Sign
(rashi) is unchanged: it was always, and remains, straight D1/Rasi
(`planet.sign`, from the mechanical layer). The client asked for this
explicitly, and that the distinction be visibly indicated to the visitor
rather than left implicit.

UPDATE (2026-09-24, earlier still, history): the client's own explicit
feedback on the live page was that the original one-paragraph
Ascendant+Moon blurb "doesn't make the user order more... and doesn't
even give trust." This module was first rewritten to be a genuinely
extensive D1 analysis -- every one of the chart's 9 planets plus the
Ascendant, each placed into its own house and paired with the client's
own real, proprietary house/planet framing
(`overview_report/overview_labels.py`'s `HOUSE_LIFE_AREAS`/
`PLANET_SIGNIFICATIONS` -- the same real text now used in the paid
Overview Report). A second pass then dropped an overly academic register
("karaka," "significator," "structural terms") in favor of plain,
second-person language, since the actual audience for this text is a
site visitor deciding whether to book, not the client reviewing it. What
a planet "represents" in each placement sentence is drawn ONLY from the
client's own real `PLANET_SIGNIFICATIONS` facets, never a
separately-authored generic-astrology description, since this client's
own data does not always match textbook planetary meanings and a
separately-authored line would risk silently contradicting it in the
same paragraph. Sign-based color (`SIGN_TRAITS` below) is standard,
non-proprietary, and safe to author generically.

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
   Classical structural facts used in `synthesis` (kendra/trikona house
   counts) and the new flags above (retrograde/combust/dignity/vargottama)
   are standard, textbook Vedic terminology, not the client's own
   proprietary scoring -- used only descriptively, never as a favorability
   verdict.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .chart_narrative import NAKSHATRA_THEMES, SIGN_TRAITS
from .ephemeris import NatalChart, nakshatra_for_longitude, sign_index_for_longitude
from .kp import house_of_longitude
from .overview_report.overview_labels import HOUSE_LIFE_AREAS, PLANET_SIGNIFICATIONS
from .varga import navamsa_sign_index

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

# One plain-language closing sentence per planet (Su, Mo, Ma, Me, Ju, Ve, Sa,
# Ra, Ke, in that fixed order -- matching ephemeris.compute_natal_chart's own
# planet order), so the ten placement paragraphs don't end on the exact same
# words nine times in a row. Full, standalone, capitalized sentences.
_PLACEMENT_CLOSERS = [
    "It's one of the places in life where that side of you tends to show up most clearly.",
    "This house is often where that part of you gets tested, and expressed.",
    "Keep an eye here: it's where that instinct tends to play out in real life.",
    "It's a natural outlet for that energy in your day-to-day.",
    "This house often becomes the stage where that trait takes center stage.",
    "That part of your nature tends to come out strongest right here.",
    "You're likely to feel that pull most in practice, right in this house.",
    "This house tends to be a home base for that side of your personality.",
    "It's one of the clearer windows into how that shows up for you.",
]

# SIGN_TRAITS / NAKSHATRA_THEMES moved to chart_narrative.py (2026-09-24,
# latest) so /api/chart can reuse the exact same standard phrase banks for
# its new `meaning` field -- imported above, not redefined here.

# Standard classical planetary dignity (Uccha/exaltation, Neecha/
# debilitation, Swakshetra/own sign) for the seven classical grahas --
# textbook astronomy-adjacent astrology, not proprietary. Deliberately
# excludes Rahu/Ketu: their dignity convention varies meaningfully across
# schools (KP vs. Parashari) with no single agreed answer, so asserting one
# here risks contradicting a visitor's own tradition rather than adding
# credibility.
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
# a Sun-proximity effect on a physical planet.
_COMBUSTION_ORBS: dict[str, float] = {
    "Mo": 12.0, "Ma": 17.0, "Me": 14.0, "Ju": 11.0, "Ve": 10.0, "Sa": 15.0,
}


def _angular_separation(deg_a: float, deg_b: float) -> float:
    """Shortest angular distance between two zodiacal degrees, 0-180.
    Plain geometry, not a scoring function -- deliberately kept local to
    this module rather than imported from hit_calc.py, which this module
    must never import from (see the AST-level guard test)."""
    return abs((deg_a - deg_b + 180.0) % 360.0 - 180.0)


def _dignity_flag(code: str, sign: str) -> str | None:
    """"Exalted" / "Debilitated" / "Own Sign" / None, for the 7 classical
    grahas -- the same `_DIGNITY` lookup `_dignity_note` below narrates in
    prose, exposed here as a short structured flag too."""
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


def _dignity_note(code: str, planet_name: str, sign: str) -> str:
    """A short, honest aside when a planet is exalted, debilitated, or in
    its own sign -- real classical structure, not the client's proprietary
    scoring. Returns "" for the ordinary, neutral case (most placements),
    so this never pads out a sentence with a "this placement is
    unremarkable" filler line."""
    flag = _dignity_flag(code, sign)
    if flag == "Exalted":
        return (
            f" This is also {planet_name}'s sign of exaltation, classically "
            f"its strongest and most confident expression."
        )
    if flag == "Debilitated":
        return (
            f" Worth being upfront about it: this is {planet_name}'s sign of "
            f"debilitation, its most classically challenged position. That "
            f"doesn't mean something is wrong, only that this placement "
            f"deserves a closer read rather than a quick label, which is "
            f"exactly what the full Diagnostic Report gives it."
        )
    if flag == "Own Sign":
        return (
            f" This also happens to be one of {planet_name}'s own signs, a "
            f"naturally comfortable and stable placement."
        )
    return ""


def _combust_note(planet_name: str, separation: float) -> str:
    return (
        f" It's also combust here, sitting only about {separation:.0f} "
        f"degrees from the Sun, close enough that classical practice treats "
        f"its own signification as temporarily overshadowed by the Sun's "
        f"glare rather than gone."
    )


def _vargottama_note(subject: str) -> str:
    return (
        f" One more thing worth flagging: {subject} is Vargottama here, "
        f"landing in the very same sign in both your D1 birth chart and "
        f"your D9 Navamsa chart. Classical practice treats that repetition "
        f"as real added strength."
    )


ASCENDANT_BLURBS: dict[str, str] = {
    "Aries": "An Aries ascendant meets the world head-on: direct, quick to act, and energized by a challenge.",
    "Taurus": "A Taurus ascendant moves at its own steady pace, grounded and dependable, drawn to comfort and quality.",
    "Gemini": "A Gemini ascendant greets life with curiosity, quick-witted and sociable, always chasing the next question.",
    "Cancer": "A Cancer ascendant leads with feeling: protective, intuitive, and attuned to the emotional undercurrent in a room.",
    "Leo": "A Leo ascendant carries natural warmth and presence, generous and expressive, hard to overlook.",
    "Virgo": "A Virgo ascendant approaches life with care and precision, observant and practical, quietly exacting.",
    "Libra": "A Libra ascendant seeks balance and connection, diplomatic and charming, attentive to fairness.",
    "Scorpio": "A Scorpio ascendant meets the world with intensity: perceptive, private, drawn beneath the surface of things.",
    "Sagittarius": "A Sagittarius ascendant treats life like an open road, optimistic and candid, restless for the bigger picture.",
    "Capricorn": "A Capricorn ascendant carries quiet discipline: composed and ambitious, patient in the way it builds.",
    "Aquarius": "An Aquarius ascendant stands a little apart, independent-minded and original, drawn to ideas ahead of their time.",
    "Pisces": "A Pisces ascendant moves through life with sensitivity, imaginative and empathetic, attuned to what isn't said aloud.",
}

MOON_BLURBS: dict[str, str] = {
    "Aries": "Paired with a Moon that feels things fast and moves on just as quickly, an emotional world built for momentum.",
    "Taurus": "Paired with a Moon that finds comfort in the steady and familiar, an emotional world that values security.",
    "Gemini": "Your Moon processes feeling through words and ideas, an emotional world that thinks out loud.",
    "Cancer": "Paired with a Moon fully at home in feeling, an emotional world that's deep, protective, and remembers everything.",
    "Leo": "Your Moon needs warmth and recognition, an emotional world that shines brightest when it's seen.",
    "Virgo": "Paired with a Moon that finds calm in order, an emotional world that steadies itself through care and routine.",
    "Libra": "Your Moon seeks harmony in its closest bonds, an emotional world tuned closely to others.",
    "Scorpio": "Paired with a Moon that feels everything at full depth, an emotional world that holds on tightly and privately.",
    "Sagittarius": "Your Moon needs room to roam, an emotional world that finds comfort in freedom and meaning.",
    "Capricorn": "Paired with a Moon that steadies itself through responsibility, an emotional world that quietly carries a lot.",
    "Aquarius": "Your Moon keeps a thoughtful distance, an emotional world that processes feeling through perspective.",
    "Pisces": "Paired with a Moon that dissolves easily into feeling, an emotional world that's porous, dreamy, and compassionate.",
}

SUN_BLURBS: dict[str, str] = {
    "Aries": "A Sun in Aries anchors identity in initiative: decisive and self-directed, energized by being first.",
    "Taurus": "A Sun in Taurus anchors identity in stability, patient and resource-conscious, consistent under pressure.",
    "Gemini": "A Sun in Gemini anchors identity in versatility, articulate and adaptive, driven by the exchange of ideas.",
    "Cancer": "A Sun in Cancer anchors identity in care, protective of what it builds and loyal, guided by instinct.",
    "Leo": "A Sun in Leo anchors identity in leadership: confident and visible, motivated by real recognition.",
    "Virgo": "A Sun in Virgo anchors identity in competence, methodical and detail-oriented, defined by the standard of its own work.",
    "Libra": "A Sun in Libra anchors identity in relationship and fairness, diplomatic and collaborative, calibrated to context.",
    "Scorpio": "A Sun in Scorpio anchors identity in depth: strategic and resilient, comfortable operating below the surface.",
    "Sagittarius": "A Sun in Sagittarius anchors identity in purpose and expansion, principled and direct, oriented toward the bigger picture.",
    "Capricorn": "A Sun in Capricorn anchors identity in achievement, disciplined and long-horizon in its thinking, unmoved by short-term setbacks.",
    "Aquarius": "A Sun in Aquarius anchors identity in independent thinking, systems-oriented and unconventional, future-facing.",
    "Pisces": "A Sun in Pisces anchors identity in intuition, adaptive and compassionate, responsive to the wider context around it.",
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
    flags: list[str] = field(default_factory=list)
    # Zero or more of "Retrograde" / "Combust" / "Exalted" / "Debilitated" /
    # "Own Sign" / "Vargottama" -- see module docstring for what each one
    # means and how it's computed (standard classical rules, not read from
    # the client's own Kundli worksheet).


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
        " This one is retrograde in your chart. In Vedic practice, that "
        "usually means the energy runs inward first, more reflection and "
        "revisiting before it shows up as action, not a weaker placement."
    )


# Nine distinct sentence shapes, one per planet in the fixed Su/Mo/Ma/Me/Ju/
# Ve/Sa/Ra/Ke order ephemeris.compute_natal_chart always returns. Each takes
# the same set of facts (sign, trait, ordinal house, house label/facets,
# planet's own significance label/facets) but built with a different word
# order and connector, so the ten placement paragraphs don't read like the
# same template with the nouns swapped.
_PLACEMENT_TEMPLATES = [
    # Su
    "Your Sun falls in {sign} ({trait}), placed in your {ordinal} house. "
    "This practice calls that the {house_label} house: the part of life "
    "built around {house_desc}. The Sun itself carries your {sig_label}, "
    "which is {sig_desc}.",
    # Mo
    "The Moon in your chart sits in {sign} ({trait}), right in your "
    "{ordinal} house, what this practice names the {house_label} house, "
    "the part of life tied to {house_desc}. That fits, since the Moon "
    "represents your {sig_label}: {sig_desc}.",
    # Ma
    "Mars sits in {sign} for you ({trait}), landing in your {ordinal} "
    "house. This practice calls it the {house_label} house, the part of "
    "life connected to {house_desc}, and Mars itself represents your "
    "{sig_label}: {sig_desc}.",
    # Me
    "Your Mercury is in {sign} ({trait}), in your {ordinal} house, the "
    "{house_label} house, tied to {house_desc}. Mercury represents your "
    "{sig_label}, meaning {sig_desc}.",
    # Ju
    "Jupiter falls in {sign} in your chart ({trait}), right in your "
    "{ordinal} house, the {house_label} house: the part of life shaped by "
    "{house_desc}. Jupiter itself stands for your {sig_label}, which is "
    "{sig_desc}.",
    # Ve
    "Venus sits in {sign} for you ({trait}), placed in your {ordinal} "
    "house. This practice calls that the {house_label} house, connected "
    "to {house_desc}, and Venus itself represents your {sig_label}: "
    "{sig_desc}.",
    # Sa
    "Your Saturn is in {sign} ({trait}), in your {ordinal} house, what "
    "this practice names the {house_label} house, the part of life tied "
    "to {house_desc}. Saturn represents your {sig_label}, which is "
    "{sig_desc}.",
    # Ra
    "Rahu falls in {sign} for you ({trait}), right in your {ordinal} "
    "house, the {house_label} house: the part of life connected to "
    "{house_desc}. Rahu itself carries your {sig_label}, meaning "
    "{sig_desc}.",
    # Ke
    "Ketu sits in {sign} in your chart ({trait}), placed in your "
    "{ordinal} house. This practice calls it the {house_label} house, "
    "tied to {house_desc}, and Ketu represents your {sig_label}: "
    "{sig_desc}.",
]


def _placement_narrative(index: int, code: str, planet_name: str, sig_label: str, sig_desc: str,
                          house_num: int, house_label: str, house_desc: str,
                          sign: str, retrograde: bool, combust: bool,
                          combust_separation: float, vargottama: bool) -> str:
    trait = SIGN_TRAITS.get(sign, "distinctly its own")
    template = _PLACEMENT_TEMPLATES[index % len(_PLACEMENT_TEMPLATES)]
    base = template.format(
        sign=sign, trait=trait, ordinal=_ordinal(house_num),
        house_label=house_label, house_desc=house_desc,
        sig_label=sig_label, sig_desc=sig_desc,
    )
    closer = _PLACEMENT_CLOSERS[index % len(_PLACEMENT_CLOSERS)]
    combust_text = _combust_note(planet_name, combust_separation) if combust else ""
    vargottama_text = _vargottama_note(f"your {planet_name}") if vargottama else ""
    return (
        f"{base} {closer}"
        f"{_dignity_note(code, planet_name, sign)}"
        f"{combust_text}{vargottama_text}{_retro_clause(retrograde)}"
    )


def build_teaser(chart: NatalChart, name: str = "", book_url: str = DEFAULT_BOOKING_URL) -> TeaserResult:
    asc_sign = chart.ascendant.sign
    # Cuspal (Bhava Chalit) house boundaries for this chart -- same 12
    # cusp longitudes /api/chart uses for its own `house` field. House 1's
    # cusp is the ascendant itself, so the Ascendant row below is always
    # house 1 under this system too (no separate case needed for it).
    cusp_longs = [h.longitude for h in chart.houses]

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

    # Nakshatra flavor for the Ascendant and Moon only -- real, specific,
    # already-computed astronomy.
    asc_nak_name, _asc_nak_lord, _asc_pada = nakshatra_for_longitude(chart.ascendant.longitude)
    asc_nak_theme = NAKSHATRA_THEMES.get(asc_nak_name, "")
    asc_nak_sentence = (
        f" With your Ascendant in {asc_nak_name}, {asc_nak_theme} tend to be "
        f"recurring themes in this chart."
        if asc_nak_theme else ""
    )
    moon_nak_theme = NAKSHATRA_THEMES.get(moon.nakshatra, "") if moon else ""
    moon_nak_clause = (
        f" {moon.nakshatra} adds a note of {moon_nak_theme}."
        if moon and moon_nak_theme else ""
    )

    possessive = f"{name.strip()}'s" if name.strip() else "Your"
    executive_summary = (
        f"{possessive} chart opens with three placements that matter more "
        f"than any other: {asc_sign} rising, Sun in {sun_sign}, and Moon in "
        f"{moon_sign}. {asc_blurb}{asc_nak_sentence} {sun_blurb} "
        f"{moon_blurb}{moon_nak_clause} Together, these three set the tone "
        f"for everything else. The nine planets and twelve houses that "
        f"follow are really the same story, told in more detail."
    ).strip()

    # Ascendant itself, as the first row of the placement table (house 1 by
    # definition; uses the same real HOUSE_LIFE_AREAS/PLANET_SIGNIFICATIONS
    # text as every other row, for consistency). No retrograde/combust
    # dignity for the Ascendant (it isn't a planet), but Vargottama is a
    # real classical concept for Lagna too -- checked the same way.
    asc_gov_label, asc_gov_desc = _split_label(PLANET_SIGNIFICATIONS["Asc"])
    asc_house_label, asc_house_desc = _split_label(HOUSE_LIFE_AREAS[1])
    asc_trait = SIGN_TRAITS.get(asc_sign, "distinctly its own")
    asc_vargottama = (
        sign_index_for_longitude(chart.ascendant.longitude)
        == navamsa_sign_index(chart.ascendant.longitude)
    )
    asc_flags = ["Vargottama"] if asc_vargottama else []
    asc_narrative = (
        f"Your Ascendant rises in {asc_sign} ({asc_trait}). This practice "
        f"calls it your {asc_gov_label} placement: it covers {asc_gov_desc}. "
        f"It also defines your first house, the {asc_house_label} house, the "
        f"part of life built around {asc_house_desc}. Think of it as the "
        f"filter everything else in your chart passes through, your natural "
        f"approach to life and the first impression you make on anyone you "
        f"meet.{_vargottama_note('your Ascendant') if asc_vargottama else ''}"
    )
    placements: list[PlanetPlacement] = [
        PlanetPlacement(
            code="Asc", name="Ascendant", sign=asc_sign, house=1, retrograde=False,
            governs=asc_gov_label, house_domain=asc_house_label,
            narrative=asc_narrative, flags=asc_flags,
        )
    ]

    for i, planet in enumerate(chart.planets):
        house_num = house_of_longitude(planet.longitude, cusp_longs)
        sig_label, sig_desc = _split_label(PLANET_SIGNIFICATIONS.get(planet.code, planet.name))
        house_label, house_desc = _split_label(HOUSE_LIFE_AREAS.get(house_num, f"House {house_num}"))

        dignity_flag = _dignity_flag(planet.code, planet.sign)
        orb = _COMBUSTION_ORBS.get(planet.code)
        separation = _angular_separation(planet.longitude, sun.longitude) if (orb and sun) else 0.0
        combust = bool(orb) and sun is not None and separation <= orb
        vargottama = (
            sign_index_for_longitude(planet.longitude) == navamsa_sign_index(planet.longitude)
        )

        flags: list[str] = []
        if planet.retrograde:
            flags.append("Retrograde")
        if combust:
            flags.append("Combust")
        if dignity_flag:
            flags.append(dignity_flag)
        if vargottama:
            flags.append("Vargottama")

        narrative = _placement_narrative(
            i, planet.code, planet.name, sig_label, sig_desc, house_num, house_label,
            house_desc, planet.sign, planet.retrograde, combust, separation, vargottama,
        )
        placements.append(PlanetPlacement(
            code=planet.code, name=planet.name, sign=planet.sign, house=house_num,
            retrograde=planet.retrograde, governs=sig_label, house_domain=house_label,
            narrative=narrative, flags=flags,
        ))

    graha_placements = [p for p in placements if p.code != "Asc"]
    graha_houses = [p.house for p in graha_placements]
    kendra_count = sum(1 for h in graha_houses if h in KENDRA_HOUSES)
    trikona_count = sum(1 for h in graha_houses if h in TRIKONA_HOUSES)
    occupied_houses = len(set(graha_houses))

    # Which houses have more than one planet -- a real, specific,
    # per-chart fact (a classical "stellium"), used to make the synthesis
    # feel grounded in THIS chart rather than a generic structural count.
    houses_to_names: dict[int, list[str]] = {}
    houses_to_domain: dict[int, str] = {}
    for p in graha_placements:
        houses_to_names.setdefault(p.house, []).append(p.name)
        houses_to_domain[p.house] = p.house_domain
    stellium_houses = sorted(h for h, names in houses_to_names.items() if len(names) >= 2)
    if stellium_houses:
        clauses = [
            f"your {_ordinal(h)} ({' and '.join(houses_to_names[h])}, "
            f"the {houses_to_domain[h]} house)"
            for h in stellium_houses
        ]
        stellium_sentence = (
            f" Worth noticing: more than one planet lands in "
            f"{'; '.join(clauses)}. Houses like that tend to carry extra "
            f"weight in a chart, simply because more is happening there at once."
        )
    else:
        stellium_sentence = ""

    synthesis = (
        f"Step back and look at the whole chart: your nine planets are "
        f"spread across {occupied_houses} of the twelve houses in your "
        f"life. {kendra_count} of them sit in the four \"power houses\" "
        f"(self, home, relationships, and career), and {trikona_count} "
        f"fall in the luckiest, most fortune-linked houses in the chart."
        f"{stellium_sentence} That's the shape of it. What it doesn't tell "
        f"you is which of these areas are running smoothly for you right "
        f"now and which ones are under real pressure. That's a "
        f"completely different question, tied to your current planetary "
        f"period and today's sky, and it's exactly what the full "
        f"Diagnostic Report is built to answer."
    )

    upgrade_pitch = (
        f"Here's the honest split between what's free and what's not. "
        f"Everything above tells you where each planet sits and what part "
        f"of your life it touches. That's placement, and you now have all "
        f"of it, for free. What it can't tell you is whether those "
        f"placements are currently working in your favor, running under "
        f"stress, or about to shift. That's a moving picture, driven by "
        f"your current planetary period (dasha) and the sky right now, not "
        f"a fixed one. Mapping that out, house by house and planet by "
        f"planet, is exactly what the full Diagnostic Report does. If "
        f"you've read this far, you're probably already curious enough to "
        f"want that answer."
    )

    return TeaserResult(
        ascendant_sign=asc_sign, moon_sign=moon_sign, sun_sign=sun_sign,
        headline=headline, blurb=blurb, executive_summary=executive_summary,
        placements=placements, synthesis=synthesis, upgrade_pitch=upgrade_pitch,
        book_url=book_url,
    )
