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
    house: int


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
        "Mechanical-layer chart only: planetary/house positions computed "
        "via Swiss Ephemeris (Krishnamurti ayanamsa, standard stand-in "
        "pending client confirmation of the workbook's exact ayanamsa). "
        "Does NOT include KP significators, divisional charts beyond D1, "
        "dasha/bhukti selection, or connection-scoring -- those parts of "
        "the engine are not yet ported/validated."
    )


class KPBetaOut(BaseModel):
    beta_disclaimer: str
    planet_sub_lords: dict
    house_significators: list


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
