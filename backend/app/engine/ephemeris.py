"""
Mechanical-layer astrology engine: planetary positions, signs, nakshatras,
ascendant and house cusps, via Swiss Ephemeris (pyswisseph).

This module ports the *non-proprietary* part of the client's VBA engine
(originally JyotishFunctions.bas / Mod_SWE.bas in the ORBINOVASTRO workbook):
generic sidereal-astronomy math with no open validation questions attached
to it in the VBA audit (see project doc "ai-agent-app-roadmap.md").

Explicitly OUT of scope for this module (left for a later, validated port):
  - KP significators / Cuspal Sub Lord (CSL) analysis
  - Divisional (varga) charts beyond D1 (Rasi)
  - Connection-scoring / prediction logic (ConnSummaryCore, WTDSCORE, etc.)
  - Dasha/Bhukti/Antra period selection and "allowed" filtering
  - The client's exact ayanamsa ("Devarajayan" named cell in the workbook,
    whose source value is still unconfirmed -- see open question #1 in the
    roadmap doc). This module defaults to the standard Krishnamurti (KP)
    ayanamsa built into Swiss Ephemeris instead, which is the closest
    well-defined stand-in until that's resolved. Swap AYANAMSA_MODE below
    once the client confirms Devarajayan's actual source.

All positions are SIDEREAL (tropical minus ayanamsa), matching KP practice.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import swisseph as swe

# ---------------------------------------------------------------------------
# Ayanamsa
# ---------------------------------------------------------------------------
# Standard Krishnamurti ayanamsa (Swiss Ephemeris sidereal mode 5). The VBA
# engine instead diffs against a named cell "Devarajayan" whose source is
# still unconfirmed by the client (see roadmap doc open question #1) -- once
# confirmed, replace this with the client's actual ayanamsa value/formula.
AYANAMSA_MODE = swe.SIDM_KRISHNAMURTI

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

PLANET_IDS: dict[str, int] = {
    "Su": swe.SUN,
    "Mo": swe.MOON,
    "Ma": swe.MARS,
    "Me": swe.MERCURY,
    "Ju": swe.JUPITER,
    "Ve": swe.VENUS,
    "Sa": swe.SATURN,
    "Ra": swe.TRUE_NODE,  # Rahu = true lunar node
    # Ketu is always 180 deg from Rahu, handled specially below.
}

PLANET_FULL_NAME: dict[str, str] = {
    "Su": "Sun", "Mo": "Moon", "Ma": "Mars", "Me": "Mercury",
    "Ju": "Jupiter", "Ve": "Venus", "Sa": "Saturn", "Ra": "Rahu", "Ke": "Ketu",
}

RASHI_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

RASHI_LORD = [
    "Ma", "Ve", "Me", "Mo", "Su", "Me", "Ve", "Ma", "Ju", "Sa", "Sa", "Ju",
]

NAKSHATRA_NAMES = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

# Vimshottari dasha lord cycle (repeats every 9 nakshatras), standard order.
VIMSHOTTARI_ORDER = ["Ke", "Ve", "Su", "Mo", "Ma", "Ra", "Ju", "Sa", "Me"]
VIMSHOTTARI_YEARS = {"Ke": 7, "Ve": 20, "Su": 6, "Mo": 10, "Ma": 7,
                     "Ra": 18, "Ju": 16, "Sa": 19, "Me": 17}

NAKSHATRA_SPAN = 360.0 / 27.0   # 13 deg 20', exact -- the VBA audit flagged
                                 # a truncated 13.33 bug in the legacy code;
                                 # this port uses the exact fraction.
PADA_SPAN = NAKSHATRA_SPAN / 4.0


def normalize360(deg: float) -> float:
    d = math.fmod(deg, 360.0)
    return d + 360.0 if d < 0 else d


@dataclass
class BirthMoment:
    """Local civil birth date/time + place, already resolved to UT Julian day."""
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int = 0
    utc_offset_hours: float = 0.0  # e.g. +5.5 for IST
    latitude: float = 0.0
    longitude: float = 0.0

    def to_julian_day_ut(self) -> float:
        local_dt = datetime(self.year, self.month, self.day,
                             self.hour, self.minute, self.second)
        ut_dt = local_dt - timedelta(hours=self.utc_offset_hours)
        hour_decimal = ut_dt.hour + ut_dt.minute / 60.0 + ut_dt.second / 3600.0
        return swe.julday(ut_dt.year, ut_dt.month, ut_dt.day, hour_decimal)


@dataclass
class PlanetPosition:
    code: str
    name: str
    longitude: float          # sidereal, 0-360
    sign: str
    sign_lord: str
    degree_in_sign: float      # 0-30
    nakshatra: str
    nakshatra_lord: str
    pada: int                  # 1-4
    retrograde: bool = False


@dataclass
class HouseCusp:
    house: int                 # 1-12
    longitude: float
    sign: str
    sign_lord: str


@dataclass
class NatalChart:
    ayanamsa_deg: float
    ayanamsa_mode: str
    planets: list[PlanetPosition] = field(default_factory=list)
    ascendant: Optional[HouseCusp] = None
    houses: list[HouseCusp] = field(default_factory=list)


def sign_for_longitude(sid_long: float) -> tuple[str, str, float]:
    sid_long = normalize360(sid_long)
    sign_index = int(sid_long // 30)
    degree_in_sign = sid_long - sign_index * 30
    return RASHI_NAMES[sign_index], RASHI_LORD[sign_index], degree_in_sign


def nakshatra_for_longitude(sid_long: float) -> tuple[str, str, int]:
    sid_long = normalize360(sid_long)
    nak_index = int(sid_long // NAKSHATRA_SPAN)
    nak_index = min(nak_index, 26)
    offset_in_nak = sid_long - nak_index * NAKSHATRA_SPAN
    pada = int(offset_in_nak // PADA_SPAN) + 1
    lord = VIMSHOTTARI_ORDER[nak_index % 9]
    return NAKSHATRA_NAMES[nak_index], lord, pada


def set_ayanamsa(mode: int = AYANAMSA_MODE) -> None:
    swe.set_sid_mode(mode, 0, 0)


def get_ayanamsa_deg(jd_ut: float, mode: int = AYANAMSA_MODE) -> float:
    set_ayanamsa(mode)
    return swe.get_ayanamsa_ut(jd_ut)


def compute_planet(code: str, jd_ut: float, mode: int = AYANAMSA_MODE) -> PlanetPosition:
    """Sidereal longitude + sign/nakshatra breakdown for one planet.
    Rahu is the true lunar node; Ketu is always exactly 180 deg from Rahu."""
    set_ayanamsa(mode)
    if code == "Ke":
        rahu = compute_planet("Ra", jd_ut, mode)
        ke_long = normalize360(rahu.longitude + 180.0)
        sign, sign_lord, deg_in_sign = sign_for_longitude(ke_long)
        nak, nak_lord, pada = nakshatra_for_longitude(ke_long)
        return PlanetPosition("Ke", "Ketu", ke_long, sign, sign_lord,
                               deg_in_sign, nak, nak_lord, pada, retrograde=True)

    planet_id = PLANET_IDS[code]
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    result, _ret_flags = swe.calc_ut(jd_ut, planet_id, flags)
    longitude, _lat, _dist, speed_long = result[0], result[1], result[2], result[3]
    longitude = normalize360(longitude)
    sign, sign_lord, deg_in_sign = sign_for_longitude(longitude)
    nak, nak_lord, pada = nakshatra_for_longitude(longitude)
    retrograde = speed_long < 0 and code not in ("Ra", "Ke")
    return PlanetPosition(code, PLANET_FULL_NAME[code], longitude, sign,
                           sign_lord, deg_in_sign, nak, nak_lord, pada, retrograde)


def compute_houses(jd_ut: float, lat: float, lon: float,
                    mode: int = AYANAMSA_MODE) -> tuple[HouseCusp, list[HouseCusp]]:
    """Ascendant + 12 Placidus house cusps, sidereal.

    NOTE: the VBA audit found the client's workbook has TWO different
    house-cusp implementations (one tropical, one sidereal -- see roadmap
    doc open question #2/#14), and it's unconfirmed which one feeds the
    client's actual chart display. This port uses sidereal cusps, the
    standard choice for KP-style house-based analysis; revisit once the
    client confirms which convention their production charts use.
    """
    set_ayanamsa(mode)
    cusps, ascmc = swe.houses_ex(jd_ut, lat, lon, b"P", flags=swe.FLG_SIDEREAL)
    asc_long = normalize360(ascmc[0])
    asc_sign, asc_lord, _ = sign_for_longitude(asc_long)
    ascendant = HouseCusp(1, asc_long, asc_sign, asc_lord)

    houses: list[HouseCusp] = []
    for house_num in range(1, 13):
        cusp_long = normalize360(cusps[house_num - 1])
        sign, lord, _ = sign_for_longitude(cusp_long)
        houses.append(HouseCusp(house_num, cusp_long, sign, lord))
    return ascendant, houses


def compute_natal_chart(moment: BirthMoment, mode: int = AYANAMSA_MODE) -> NatalChart:
    jd_ut = moment.to_julian_day_ut()
    ayanamsa_deg = get_ayanamsa_deg(jd_ut, mode)
    planets = [compute_planet(code, jd_ut, mode) for code in
               ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]]
    ascendant, houses = compute_houses(jd_ut, moment.latitude, moment.longitude, mode)
    mode_name = {5: "Krishnamurti (KP)"}.get(mode, str(mode))
    return NatalChart(ayanamsa_deg=ayanamsa_deg, ayanamsa_mode=mode_name,
                       planets=planets, ascendant=ascendant, houses=houses)
