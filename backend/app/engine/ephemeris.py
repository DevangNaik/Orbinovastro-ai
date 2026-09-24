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

UPDATE (2026-09-24, later still again): this module now uses the SAME
ayanamsa/node convention as `ccsi.py`'s already-validated engine (mode 45
"Krishnamurti VP291" + `dasha.CONFIRMED_AYANAMSA_DIFF`, MEAN lunar node
for Rahu/Ketu) instead of the old mode-5/true-node stand-in. This was
previously a KNOWN, DELIBERATELY UNRECONCILED discrepancy between this
module (used by /api/chart, teaser.py, kp.py, varga.py, transit.py -- the
free-tier chart features) and ccsi.py (the paid CCSI engine) -- see
ccsi.py's own docstring, still accurate about the discrepancy's history
even though it's now resolved here.

It was reconciled by validating against the client's own real Excel Kundli
worksheet data for the reference chart (1973-10-12, 14:55 IST, Amalsad):
under this convention, all 9 planets AND the Ascendant match the client's
real degree-in-sign, nakshatra, and pada to within 0.0002 degrees (pure
rounding) -- see project doc `ayanamsa-and-nature-findings-2026-09-24.md`
for the full comparison table. The old mode-5/true-node convention was off
by a consistent ~0.08 degrees on every planet, and further off on Rahu/
Ketu specifically because of the true-node-vs-mean-node difference. The
client confirmed switching to this convention (2026-09-24).

`CONFIRMED_AYANAMSA_DIFF`, `DEFAULT_AYANAMSA_ID`, and `SWE_FLAGS` are
imported from `dasha.py` rather than redefined here, so there is exactly
one source of truth for these calibration constants -- `dasha.py` has no
imports of its own (confirmed no circular import), and these three names
are pure Swiss Ephemeris calibration values, not proprietary
scoring/weighting logic, so importing them here does not cross the free/
paid boundary the teaser.py AST-import-guard test protects (that test
only checks teaser.py's own direct imports, and teaser.py imports this
module, not dasha.py, directly).

All positions are SIDEREAL (tropical minus ayanamsa), matching KP practice.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import swisseph as swe

from .dasha import CONFIRMED_AYANAMSA_DIFF, DEFAULT_AYANAMSA_ID, SWE_FLAGS

# ---------------------------------------------------------------------------
# Ayanamsa
# ---------------------------------------------------------------------------
# Krishnamurti VP291 (Swiss Ephemeris sidereal mode 45) + the empirically
# confirmed diff -- the same convention `ccsi.py` already uses, now
# validated against the client's real Excel data for the free-tier chart
# features too (see module docstring UPDATE above). `AYANAMSA_MODE` is kept
# as a name for backward compatibility with anything reading it, but the
# diff correction below is what actually makes this match -- switching
# `mode` away from `DEFAULT_AYANAMSA_ID` without also revisiting the diff
# would NOT reproduce the confirmed convention (no caller does this today).
AYANAMSA_MODE = DEFAULT_AYANAMSA_ID

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
    "Ra": swe.MEAN_NODE,  # Rahu = MEAN lunar node (confirmed convention,
    # see module docstring UPDATE -- was swe.TRUE_NODE until 2026-09-24).
    # Ketu is always 180 deg from Rahu, handled specially below.
}

# Uranus/Neptune/Pluto -- NEW (2026-09-24, even later still), client-
# requested. Deliberately kept OUT of `PLANET_IDS`/the 9-code list
# `compute_natal_chart` loops over, so every classical-9-planet-only
# consumer (teaser.py, kp.py significators, varga.py D9, ccsi.py/
# hit_calc.py CCSI scoring, dasha.py) is completely unaffected -- KP
# practice and this engagement's validated proprietary engines don't use
# the outer planets at all. Instead, `compute_outer_planets()` below
# computes these three separately, and only chart.py's `chart_to_dict()`
# (the /api/chart response) merges them into its own `planets` list, with
# no `nature`/`functional_nature` (outer planets have no classical
# natural-benefic/malefic assignment, and rule no sign, so
# `functional_nature()` already returns None for them with no code
# change needed) and excluded from `conjunctions`/`aspects` (classical
# Parashari conjunctions/graha-drishti are a graha-only concept -- see
# chart.py's own docstring for exactly how they're merged in).
OUTER_PLANET_IDS: dict[str, int] = {
    "Ur": swe.URANUS,
    "Ne": swe.NEPTUNE,
    "Pl": swe.PLUTO,
}

PLANET_FULL_NAME: dict[str, str] = {
    "Su": "Sun", "Mo": "Moon", "Ma": "Mars", "Me": "Mercury",
    "Ju": "Jupiter", "Ve": "Venus", "Sa": "Saturn", "Ra": "Rahu", "Ke": "Ketu",
    "Ur": "Uranus", "Ne": "Neptune", "Pl": "Pluto",
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
    # Uranus/Neptune/Pluto -- kept SEPARATE from `planets` on purpose (see
    # the OUTER_PLANET_IDS comment above); most callers should keep
    # ignoring this field entirely, since it exists only for chart.py's
    # `chart_to_dict()` to merge into its own /api/chart response.
    outer_planets: list[PlanetPosition] = field(default_factory=list)


def sign_for_longitude(sid_long: float) -> tuple[str, str, float]:
    sid_long = normalize360(sid_long)
    sign_index = int(sid_long // 30)
    degree_in_sign = sid_long - sign_index * 30
    return RASHI_NAMES[sign_index], RASHI_LORD[sign_index], degree_in_sign


def sign_index_for_longitude(sid_long: float) -> int:
    """0-11 index into RASHI_NAMES/RASHI_LORD for a sidereal longitude."""
    return int(normalize360(sid_long) // 30) % 12


def whole_sign_house(occupant_sign_index: int, ascendant_sign_index: int) -> int:
    """Classical Rasi/D1 (and divisional-chart) house placement: houses
    counted by SIGN from the ascendant's own sign (house 1 = whichever
    sign the ascendant occupies), not by Placidus cusp degree. This is
    the traditional D1 diagram convention used across most Vedic
    software, and the standard convention for divisional (varga) charts.

    Distinct from the cuspal (Bhava Chalit) house placement used
    elsewhere in this engine for KP practice -- see kp.house_of_longitude
    for that one. The two can disagree for a planet near a house cusp;
    showing both side by side is intentional (see roadmap doc)."""
    return (occupant_sign_index - ascendant_sign_index) % 12 + 1


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


def _confirmed_sidereal_longitude_and_speed(jd_ut: float, planet_id: int) -> tuple[float, float]:
    """One body's sidereal longitude + daily motion (speed), under the
    SAME confirmed convention ccsi.py's own `_confirmed_sidereal_longitude`
    uses: ayanamsa mode 45 (`DEFAULT_AYANAMSA_ID`) + `CONFIRMED_AYANAMSA_DIFF`,
    with `dasha.SWE_FLAGS` (sidereal, true position, no nutation) plus
    `FLG_SPEED` added so retrograde can still be read off speed -- adding
    FLG_SPEED does not change the returned longitude, only whether a speed
    value is also computed, so this still reproduces ccsi.py's validated
    longitudes exactly."""
    swe.set_sid_mode(DEFAULT_AYANAMSA_ID, 0, 0)
    result, _flags = swe.calc_ut(jd_ut, planet_id, SWE_FLAGS | swe.FLG_SPEED)
    raw = result[0] % 360.0
    longitude = (raw + CONFIRMED_AYANAMSA_DIFF) % 360.0
    return longitude, result[3]


def compute_planet(code: str, jd_ut: float, mode: int = AYANAMSA_MODE) -> PlanetPosition:
    """Sidereal longitude + sign/nakshatra breakdown for one planet, under
    the confirmed ayanamsa/node convention (see module docstring UPDATE).
    Rahu is the MEAN lunar node; Ketu is always exactly 180 deg from Rahu.

    The `mode` parameter is kept for signature compatibility (nothing
    calls this with a non-default `mode` today), but the actual
    computation always applies `CONFIRMED_AYANAMSA_DIFF` on top of
    `DEFAULT_AYANAMSA_ID`, exactly mirroring ccsi.py -- see
    `_confirmed_sidereal_longitude_and_speed`.

    Rahu and Ketu are both hardcoded `retrograde=True` -- by convention,
    not measured, since the lunar nodes are computational points, not
    physical bodies, and Vedic practice treats them as permanently
    retrograde (this was a real bug fix in an earlier round: Rahu used to
    fall through to the general branch and read its own, usually-but-not-
    always-negative node speed instead)."""
    if code == "Ke":
        rahu = compute_planet("Ra", jd_ut, mode)
        ke_long = normalize360(rahu.longitude + 180.0)
        sign, sign_lord, deg_in_sign = sign_for_longitude(ke_long)
        nak, nak_lord, pada = nakshatra_for_longitude(ke_long)
        return PlanetPosition("Ke", "Ketu", ke_long, sign, sign_lord,
                               deg_in_sign, nak, nak_lord, pada, retrograde=True)

    # NOTE: swe.SUN == 0, so this must be an explicit `in` check, not
    # `PLANET_IDS.get(code) or ...` (0 is falsy and would wrongly fall
    # through to OUTER_PLANET_IDS and KeyError on "Su").
    planet_id = PLANET_IDS[code] if code in PLANET_IDS else OUTER_PLANET_IDS[code]
    longitude, speed_long = _confirmed_sidereal_longitude_and_speed(jd_ut, planet_id)
    sign, sign_lord, deg_in_sign = sign_for_longitude(longitude)
    nak, nak_lord, pada = nakshatra_for_longitude(longitude)
    retrograde = True if code == "Ra" else speed_long < 0
    return PlanetPosition(code, PLANET_FULL_NAME[code], longitude, sign,
                           sign_lord, deg_in_sign, nak, nak_lord, pada, retrograde)


def compute_outer_planets(jd_ut: float, mode: int = AYANAMSA_MODE) -> list[PlanetPosition]:
    """Uranus, Neptune, Pluto -- same computation as `compute_planet`
    (real physical bodies, so genuinely speed-based retrograde, not the
    Ra/Ke hardcoded convention), kept as a SEPARATE function rather than
    folded into `compute_natal_chart`'s own 9-planet loop so every
    classical-9-planet-only consumer stays unaffected. See the
    `OUTER_PLANET_IDS` comment above for the full reasoning."""
    return [compute_planet(code, jd_ut, mode) for code in OUTER_PLANET_IDS]


def compute_houses(jd_ut: float, lat: float, lon: float,
                    mode: int = AYANAMSA_MODE) -> tuple[HouseCusp, list[HouseCusp]]:
    """Ascendant + 12 Placidus house cusps, sidereal, under the confirmed
    ayanamsa convention (mode 45 + `CONFIRMED_AYANAMSA_DIFF`) -- exactly
    mirroring `ccsi.compute_ccsi_houses`, whose own docstring notes house 1
    is confirmed to equal the Ascendant exactly against real client data,
    which is why the Ascendant below is sourced from house 1 rather than
    computed separately from `ascmc[0]`.

    NOTE (unrelated to the ayanamsa fix above): the VBA audit found the
    client's workbook has TWO different house-cusp implementations (one
    tropical, one sidereal -- see roadmap doc open question #2/#14), and
    it's unconfirmed which one feeds the client's actual chart display.
    This port uses sidereal Placidus cusps, the standard choice for
    KP-style house-based analysis; revisit once the client confirms which
    convention their production charts use.
    """
    swe.set_sid_mode(DEFAULT_AYANAMSA_ID, 0, 0)
    cusps, _ascmc = swe.houses_ex(jd_ut, lat, lon, b"P", flags=swe.FLG_SIDEREAL)

    houses: list[HouseCusp] = []
    for house_num in range(1, 13):
        cusp_long = normalize360(cusps[house_num - 1] + CONFIRMED_AYANAMSA_DIFF)
        sign, lord, _ = sign_for_longitude(cusp_long)
        houses.append(HouseCusp(house_num, cusp_long, sign, lord))

    asc = houses[0]
    ascendant = HouseCusp(1, asc.longitude, asc.sign, asc.sign_lord)
    return ascendant, houses


def compute_natal_chart(moment: BirthMoment, mode: int = AYANAMSA_MODE) -> NatalChart:
    jd_ut = moment.to_julian_day_ut()
    ayanamsa_deg = get_ayanamsa_deg(jd_ut, mode)
    planets = [compute_planet(code, jd_ut, mode) for code in
               ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]]
    outer_planets = compute_outer_planets(jd_ut, mode)
    ascendant, houses = compute_houses(jd_ut, moment.latitude, moment.longitude, mode)
    mode_name = {45: "Krishnamurti VP291 + confirmed diff"}.get(mode, str(mode))
    return NatalChart(ayanamsa_deg=ayanamsa_deg, ayanamsa_mode=mode_name,
                       planets=planets, ascendant=ascendant, houses=houses,
                       outer_planets=outer_planets)
