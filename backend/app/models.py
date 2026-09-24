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


class HouseOut(BaseModel):
    house: int
    longitude: float
    sign: str
    sign_lord: str


class ChartOut(BaseModel):
    name: str = ""
    place: str = ""
    ayanamsa_deg: float
    ayanamsa_mode: str
    ascendant: HouseOut
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


class TeaserOut(BaseModel):
    ascendant_sign: str
    moon_sign: str
    headline: str
    blurb: str
    book_url: str
    disclaimer: str = (
        "A free preview only -- ascendant and Moon sign from the "
        "validated mechanical layer, paired with general sign-level "
        "description. Not a personalized reading; book a consultation "
        "for that."
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
