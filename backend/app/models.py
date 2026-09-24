"""Pydantic request/response models for the API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class BirthDetailsIn(BaseModel):
    name: str = Field("", description="Optional client name, for display only")
    year: int
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)
    second: int = Field(0, ge=0, le=59)
    utc_offset_hours: float = Field(
        5.5, description="Timezone offset from UTC at birth, e.g. 5.5 for IST"
    )
    latitude: float = Field(description="Decimal degrees, north positive")
    longitude: float = Field(description="Decimal degrees, east positive")
    place: str = Field("", description="Optional place name, for display only")


class PlanetConjunctionOut(BaseModel):
    code: str = Field(description="The other planet's code")
    orb_degrees: float = Field(description="Angular separation in degrees, always positive")


class PlanetAspectOut(BaseModel):
    code: str = Field(description="The other planet's code (or, for aspected_by only, could "
        "in principle be any graha -- never the Ascendant itself, which is never an aspect "
        "source, only ever a target)")
    aspect: str = Field(description="Which aspect this is, as a house-distance ordinal counted "
        "forward from the source planet's own D1 sign, e.g. '7th' for the universal "
        "opposition aspect every graha casts, or '4th'/'5th'/'8th'/'9th'/'3rd'/'10th' for "
        "Mars/Jupiter/Saturn's own special aspects. Not the same numbering as `house` or "
        "`rasi_house` -- this is always counted from the aspecting planet's sign, not the "
        "Ascendant's.")


class PlanetOut(BaseModel):
    code: str
    name: str
    longitude: float
    sign: str
    sign_lord: str
    degree_in_sign: float
    nakshatra: str
    nakshatra_lord: str
    pada: int
    retrograde: bool
    house: int = Field(description="Bhava Chalit house (Placidus cusp), used by KP practice")
    rasi_house: int = Field(description="Classical D1/Rasi house (whole-sign, from the ascendant's sign)")
    meaning: str = Field(
        description="One short sentence combining this placement's nakshatra theme and sign "
        "color, e.g. 'Sravana(4): listening, learning, and passing on what you know; Capricorn "
        "adds disciplined and patient.' Standard classical textbook material (see "
        "engine/chart_narrative.py), not the client's own proprietary Kundli-worksheet "
        "interpretation text."
    )
    conjunctions: list[PlanetConjunctionOut] = Field(
        default_factory=list,
        description="Every other planet sharing this one's D1 (Rasi) sign -- the same grouping "
        "a North Indian chart box visually shows -- with the angular separation in degrees, "
        "closest first. Empty if nothing else shares the sign.",
    )
    nature: str = Field(
        description="'Malefic' or 'Benefic' -- standard classical grouping (Sa/Ma/Ra/Ke vs. "
        "Su/Me/Mo/Ju/Ve), the same one this engine's CCSI weighting already uses internally."
    )
    flags: list[str] = Field(
        default_factory=list,
        description="Zero or more of 'Retrograde' / 'Combust' / 'Exalted' / 'Debilitated' / "
        "'Own Sign' / 'Vargottama', computed from standard classical rules -- the same "
        "engine/chart_narrative.py logic the Free Preview tab already used, now also here "
        "so every chart-wheel view (D1, Bhava Chalit, D9, Cuspal) shows them too.",
    )
    aspects: list[PlanetAspectOut] = Field(
        default_factory=list,
        description="Classical Parashari whole-sign graha drishti this planet casts on other "
        "planets -- the universal 7th/opposition aspect every graha casts, plus Mars/Jupiter/"
        "Saturn's own special aspects. NOT generally mutual (a special aspect isn't cast back), "
        "and NOT the same thing as `conjunctions` (same-sign proximity) or hit_calc.py's own "
        "Western-angle aspect classification used for CCSI stress scoring.",
    )
    aspected_by: list[PlanetAspectOut] = Field(
        default_factory=list,
        description="The reverse of `aspects`: which other planets cast a classical graha "
        "drishti onto this one.",
    )


class HouseOut(BaseModel):
    house: int
    longitude: float
    sign: str
    sign_lord: str


class AscendantOut(BaseModel):
    house: int
    longitude: float
    sign: str
    sign_lord: str
    degree_in_sign: float
    nakshatra: str
    nakshatra_lord: str
    pada: int
    meaning: str = Field(
        description="Same short nakshatra-theme + sign-color sentence every planet's `meaning` "
        "field carries, computed the same way from the Ascendant's own longitude."
    )
    flags: list[str] = Field(
        default_factory=list,
        description="Only ever 'Vargottama' or empty -- the Ascendant isn't a planet, so it has "
        "no retrograde/combust/dignity of its own.",
    )
    aspected_by: list[PlanetAspectOut] = Field(
        default_factory=list,
        description="Which planets cast a classical graha drishti onto the 1st house/Lagna. "
        "The Ascendant never casts an aspect of its own (it isn't a graha), so unlike a "
        "planet's entry there is no `aspects` field here.",
    )


class ChartOut(BaseModel):
    name: str = ""
    place: str = ""
    ayanamsa_deg: float
    ayanamsa_mode: str
    ascendant: AscendantOut
    houses: list[HouseOut]
    planets: list[PlanetOut]
    disclaimer: str = (
        "Mechanical-layer chart only, all positions Nirayana (sidereal): "
        "planetary/house positions computed via Swiss Ephemeris "
        "(Krishnamurti ayanamsa, standard stand-in pending client "
        "confirmation of the workbook's exact ayanamsa). Each planet's "
        "'house' is Bhava Chalit (Placidus cusp); 'rasi_house' is the "
        "classical D1 whole-sign house. Does NOT include KP significators "
        "(see /api/kp-beta), the D9 Navamsa divisional chart (see "
        "/api/navamsa, also beta), divisional charts beyond D1/D9, "
        "dasha/bhukti selection, or connection-scoring -- those parts of "
        "the engine are not yet ported/validated."
    )


class KPBetaOut(BaseModel):
    beta_disclaimer: str
    planet_sub_lords: dict
    house_significators: list


class NavamsaPlanetOut(BaseModel):
    code: str
    name: str
    navamsa_sign: str
    navamsa_sign_lord: str
    navamsa_house: int = Field(description="Whole-sign house within the D9 chart, from the D9 ascendant's own sign")


class NavamsaOut(BaseModel):
    ascendant_navamsa_sign: str
    ascendant_navamsa_sign_lord: str
    planets: list[NavamsaPlanetOut]
    beta_disclaimer: str


class TeaserPlacementOut(BaseModel):
    code: str = Field(description="Asc, or one of the 9 planet codes (Su/Mo/Ma/Me/Ju/Ve/Sa/Ra/Ke)")
    name: str
    sign: str
    house: int = Field(description="Cuspal (Bhava Chalit / Nirayana bhava) house (1-12) -- same "
        "convention as /api/chart's own `house` field and this engine's KP significators/paid "
        "scoring. `sign` is separately D1/Rasi-based; the two systems can legitimately differ, "
        "sometimes by a full house across the whole chart when the Ascendant sits close to a "
        "sign boundary")
    retrograde: bool
    governs: str = Field(description="Short signification label, from the client's own real HIT_CALC wording")
    house_domain: str = Field(description="Short house life-area label, from the client's own real HIT_CALC wording")
    narrative: str = Field(description="Full analytical sentence(s) for this specific placement")
    flags: list[str] = Field(
        default_factory=list,
        description="Zero or more of 'Retrograde' / 'Combust' / 'Exalted' / 'Debilitated' / "
        "'Own Sign' / 'Vargottama', computed from standard classical rules (not read from the "
        "client's own Kundli worksheet, which uses its own unported Excel formulas for these -- "
        "see engine/teaser.py's module docstring). 'Vargottama' depends on the D9 Navamsa chart, "
        "which is itself labeled beta elsewhere in this app.",
    )


class TeaserOut(BaseModel):
    ascendant_sign: str
    moon_sign: str
    sun_sign: str = ""
    headline: str
    blurb: str
    executive_summary: str = Field(
        "", description="Ascendant/Sun/Moon ('Big Three') synthesis paragraph"
    )
    placements: list[TeaserPlacementOut] = Field(
        default_factory=list,
        description="Ascendant + all 9 planets, each with its D1 house, real "
        "signification/house-domain labels, and a full analytical narrative",
    )
    synthesis: str = Field(
        "", description="Chart-wide structural synthesis (kendra/trikona counts, "
        "houses occupied) -- descriptive only, never a favorability judgment"
    )
    upgrade_pitch: str = Field(
        "", description="Explicit, honest statement of what this free preview "
        "does NOT include (stress/support scoring, dasha activation) and that "
        "the paid Diagnostic Report supplies it"
    )
    book_url: str
    disclaimer: str = (
        "A free preview only: which sign and house every planet occupies, "
        "and which of this practice's own real house/planet domains that "
        "activates. Sign (rashi) is your D1 (Rasi) birth chart placement. "
        "House (bhava) is cuspal (Bhava Chalit / Nirayana bhava), the same "
        "house convention this practice's KP significators and the paid "
        "Diagnostic Report's scoring use, so a planet's house can differ "
        "from a simple whole-sign count. Sometimes it's just one placement "
        "near a house cusp; when the Ascendant itself sits close to a sign "
        "boundary, every placement can shift by a full house at once. "
        "Neither number is wrong. They're two established, valid "
        "conventions that answer slightly different questions. Each "
        "placement's Retrograde/Exalted/Debilitated/Own Sign flags use "
        "standard classical rules; Combust uses standard classical orbs; "
        "Vargottama compares this chart's D1 sign against its D9 Navamsa "
        "sign, so it carries the same beta caveat as the D9 feature (a "
        "standard textbook formula, not yet checked against this "
        "practice's own workbook). None of these flags are read from this "
        "practice's own Kundli worksheet, which computes them with its own "
        "unported formulas. All positions are Nirayana (sidereal), from "
        "the validated mechanical layer. Deliberately does not include KP "
        "significators (see the beta significators feature), dasha/bhukti "
        "timing, or the proprietary connection-and-stress scoring (CCSI) "
        "the full paid Diagnostic Report is built on. It describes where "
        "each planet sits, not whether that placement is currently under "
        "astrological support or stress."
    )


class GeocodeRequestIn(BaseModel):
    place: str = Field(description="Free-text place name, e.g. 'New Delhi, India'")
    year: int = Field(description="Birth year, used to resolve the correct historical UTC offset")
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    hour: int = Field(12, ge=0, le=23, description="Local hour, only affects DST edge cases")
    minute: int = Field(0, ge=0, le=59)


class GeocodeOut(BaseModel):
    place: str
    latitude: float
    longitude: float
    timezone_name: str | None = None
    utc_offset_hours: float | None = None
    note: str = ""


class TransitDetailsIn(BaseModel):
    year: int | None = None
    month: int | None = Field(None, ge=1, le=12)
    day: int | None = Field(None, ge=1, le=31)
    hour: int | None = Field(None, ge=0, le=23)
    minute: int | None = Field(None, ge=0, le=59)
    utc_offset_hours: float = 0.0


class TransitRequestIn(BaseModel):
    birth: BirthDetailsIn
    transit: TransitDetailsIn | None = None  # None/omitted = right now, in UTC


class TransitPlanetOut(BaseModel):
    code: str
    name: str
    longitude: float
    sign: str
    sign_lord: str
    degree_in_sign: float
    nakshatra: str
    nakshatra_lord: str
    retrograde: bool
    natal_house: int
    conjuncts_natal: list[str] = Field(
        default_factory=list,
        description="Natal planet codes within a small orb of this transiting planet",
    )


class TransitOut(BaseModel):
    transit_time_utc: str
    transit_time_source: str
    planets: list[TransitPlanetOut]
    disclaimer: str = (
        "Mechanical-layer transit only: current sidereal planetary positions "
        "and which natal house each falls in, plus simple conjunction flags "
        "(same sign/nakshatra proximity, default 3-degree orb). Does NOT "
        "include transit-to-natal aspect analysis (trine/square/opposition), "
        "dasha/bhukti overlay, or the client's own event-timing scoring -- "
        "those are not yet ported/validated."
    )


class ChatMessageIn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequestIn(BaseModel):
    messages: list[ChatMessageIn]
    birth_details: BirthDetailsIn | None = None


class ChatResponseOut(BaseModel):
    reply: str
    used_chart_tool: bool = False


class CcsiTransitDetailsIn(BaseModel):
    year: int | None = None
    month: int | None = Field(None, ge=1, le=12)
    day: int | None = Field(None, ge=1, le=31)
    hour: int | None = Field(None, ge=0, le=23)
    minute: int | None = Field(None, ge=0, le=59)
    utc_offset_hours: float = Field(
        0.0,
        description=(
            "Timezone offset of the hour/minute/year/month/day fields "
            "above -- i.e. these fields are already LOCAL time at this "
            "offset, not UTC. Only meaningful when year is supplied "
            "(a custom transit moment); ignored otherwise."
        ),
    )
    latitude: float | None = Field(
        None,
        description=(
            "Location the transit cusps are computed for. Omitted = same "
            "location as the natal birth details -- the client's own "
            "convention for which location their 'current' transit "
            "snapshot uses is still unconfirmed (see the project roadmap "
            "doc), so this is a documented assumption, not a confirmed one."
        ),
    )
    longitude: float | None = None
    place: str = Field(
        "",
        description=(
            "Optional display name for the transit location (e.g. "
            "'Duluth, GA'), used only in report/PDF display -- 2026-09-24: "
            "added after the Overview Report PDF's Transit Information "
            "table showed 'Not available' for a defaulted-to-birth-location "
            "transit. If omitted and no custom transit is given, the "
            "birth's own place name is shown instead (since that's the "
            "actual location being used); if omitted with a custom "
            "lat/long, the coordinates are shown instead of leaving this "
            "blank."
        ),
    )


class CcsiRequestIn(BaseModel):
    birth: BirthDetailsIn
    transit: CcsiTransitDetailsIn | None = None  # None/omitted = right now, at the birth location


class CcsiRowOut(BaseModel):
    houses: dict[str, float] = Field(description='House number "1".."12" -> hit count')
    columns: dict[str, float] = Field(description='"Asc","Su",...,"Ke" -> hit count')


class CcsiOut(BaseModel):
    l_net: CcsiRowOut = Field(description="Natal Lagna: natal cusps/planets vs. natal planets")
    l_negative: CcsiRowOut
    lt_net: CcsiRowOut = Field(description="Transit-to-Lagna: natal cusps/planets vs. transiting planets")
    lt_negative: CcsiRowOut
    tt_net: CcsiRowOut = Field(description="Transit-to-Transit: transit cusps/planets vs. transiting planets")
    tt_negative: CcsiRowOut
    transit_time_utc: str
    transit_time_source: str
    disclaimer: str


class OverviewReportRequestIn(BaseModel):
    """POST /api/overview-report. Same birth/transit shape as CcsiRequestIn
    (the two engines share the exact same live CCSI computation), plus the
    client name shown on the report's cover/Client Information front
    matter. See engine/overview_report_builder.py's module docstring for
    what this Stage-1 endpoint does and doesn't produce yet."""
    client_name: str = Field(description="Client name shown on the report cover and Client Information page")
    birth: BirthDetailsIn
    transit: CcsiTransitDetailsIn | None = None  # None/omitted = right now, at the birth location
