"""
CCSI (Cusp Conflict Stress Indicator) live computation -- wires the
fully-validated `hit_calc.py` engine to a real chart, instead of the
hardcoded reference-chart dictionaries the test files use.

Why this module exists on its own, rather than reusing `ephemeris.py`'s
`compute_natal_chart`: `ephemeris.py` uses ayanamsa mode 5
("Krishnamurti (KP)") and the TRUE lunar node for Rahu -- the stand-in
this app's free/live chart features (Chart, Transit, KP Significators
beta, D9 beta, Preview) use pending the client's confirmation of their
exact ayanamsa. The CCSI engine, however, has its OWN separately
confirmed convention -- ayanamsa mode 45 (Krishnamurti VP291) plus
`dasha.CONFIRMED_AYANAMSA_DIFF`, and the MEAN lunar node for Rahu/Ketu --
empirically back-solved and validated against real client data (see
`dasha.py`/`kp_lords.py`'s docstrings, and `hit_calc.py`'s own 132/132
real-cell validation, which used exactly this convention). Reusing
`ephemeris.py` here would silently feed `hit_calc.py` numbers computed
under the WRONG ayanamsa/node convention -- close, but not the one that
was actually validated. This module exists to keep that distinction
explicit rather than let it get blurred at a call site.

These two conventions are a known, documented discrepancy in this
engagement (see the project roadmap doc) -- not yet reconciled, because
reconciling them is the client's call, not a silent side effect of this
port. Until that happens, this module and `ephemeris.py` will keep
producing slightly different planetary degrees for the same birth data,
on purpose.

Scope: given a natal `BirthMoment` and a transit `BirthMoment` (typically
"now", at either the natal birthplace or wherever the client specifies --
see the project roadmap doc's still-open question about which location
the client's own "current" transit snapshot actually uses), computes all
three CCSI variants (L, LT, TT) in both their "net" and "Negative Hits
Only" forms -- the full `HIT_CALC!G184:AE204`-equivalent block.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import swisseph as swe

from .dasha import CONFIRMED_AYANAMSA_DIFF, DEFAULT_AYANAMSA_ID, SWE_FLAGS
from .ephemeris import BirthMoment
from .hit_calc import CcsiRow, compute_ccsi_row

# Planet -> Swiss Ephemeris body id, using the MEAN lunar node for Rahu
# (CONFIRMED, not the true node -- see dasha.NODE_MODE_CONFIRMED and this
# module's docstring). Ketu is always Rahu + 180 deg.
_PLANET_IDS: Dict[str, int] = {
    "Su": swe.SUN, "Mo": swe.MOON, "Ma": swe.MARS, "Me": swe.MERCURY,
    "Ju": swe.JUPITER, "Ve": swe.VENUS, "Sa": swe.SATURN, "Ra": swe.MEAN_NODE,
}


def _confirmed_sidereal_longitude(jd_ut: float, planet_id: int) -> float:
    """One planet's sidereal longitude under the CCSI-confirmed
    convention: ayanamsa mode 45 + CONFIRMED_AYANAMSA_DIFF. Mirrors
    exactly the method `test_kp_lords_reference_chart.py` and
    `test_hit_calc_reference_chart.py` used to validate this convention
    in the first place -- not a new computation path."""
    swe.set_sid_mode(DEFAULT_AYANAMSA_ID, 0, 0)
    result, _flags = swe.calc_ut(jd_ut, planet_id, SWE_FLAGS)
    raw = result[0] % 360.0
    return (raw + CONFIRMED_AYANAMSA_DIFF) % 360.0


def compute_ccsi_planet_longitudes(jd_ut: float) -> Dict[str, float]:
    """All 9 classical/nodal planets' sidereal longitudes at `jd_ut`,
    under the CCSI-confirmed ayanamsa/node convention."""
    longitudes: Dict[str, float] = {}
    for code, planet_id in _PLANET_IDS.items():
        longitudes[code] = _confirmed_sidereal_longitude(jd_ut, planet_id)
    longitudes["Ke"] = (longitudes["Ra"] + 180.0) % 360.0
    return longitudes


def compute_ccsi_houses(jd_ut: float, lat: float, lon: float) -> Dict[int, float]:
    """The 12 Placidus house-cusp degrees at `jd_ut`/`lat`/`lon`, under
    the CCSI-confirmed ayanamsa convention. House 1 equals the Ascendant
    exactly (confirmed against real `Bhava_Deg` data -- see
    `test_hit_calc_reference_chart.py`), so callers needing the
    Ascendant separately can just read `houses[1]`."""
    swe.set_sid_mode(DEFAULT_AYANAMSA_ID, 0, 0)
    cusps, _ascmc = swe.houses_ex(jd_ut, lat, lon, b"P", flags=swe.FLG_SIDEREAL)
    return {
        house_num: (cusp_deg + CONFIRMED_AYANAMSA_DIFF) % 360.0
        for house_num, cusp_deg in enumerate(cusps, start=1)
    }


@dataclass(frozen=True)
class CcsiChartPositions:
    """One chart side's worth of CCSI inputs -- either the natal side or
    the transit side, computed identically."""
    house_cusps: Dict[int, float]
    ascendant_deg: float
    planet_longitudes: Dict[str, float]


def compute_ccsi_positions(moment: BirthMoment) -> CcsiChartPositions:
    """Computes one chart side's house cusps + Ascendant + 9 planet
    longitudes, all under the CCSI-confirmed ayanamsa/node convention.
    Works identically whether `moment` is a natal birth moment or a
    transit ("now" or any other) moment -- CCSI's L/LT/TT variants only
    differ in which computed side feeds which role, not in how each side
    is computed."""
    jd_ut = moment.to_julian_day_ut()
    house_cusps = compute_ccsi_houses(jd_ut, moment.latitude, moment.longitude)
    planet_longitudes = compute_ccsi_planet_longitudes(jd_ut)
    return CcsiChartPositions(
        house_cusps=house_cusps,
        ascendant_deg=house_cusps[1],
        planet_longitudes=planet_longitudes,
    )


@dataclass(frozen=True)
class CcsiReport:
    """The full `HIT_CALC!G184:AE204`-equivalent block: all three CCSI
    variants (L, LT, TT), each as a net row and a Negative-Hits-Only row."""
    l_net: CcsiRow
    l_negative: CcsiRow
    lt_net: CcsiRow
    lt_negative: CcsiRow
    tt_net: CcsiRow
    tt_negative: CcsiRow


CCSI_DISCLAIMER = (
    "CCSI (Cusp Conflict Stress Indicator) hit-counts, computed live from "
    "this engine's own Swiss Ephemeris positions -- VALIDATED (2026-09-24) "
    "against the client's real HIT_CALC output: 132/132 real cells matched "
    "exactly across all three variants (L, LT, TT), net and Negative Hits "
    "Only. Uses a SEPARATE, independently-confirmed ayanamsa/node "
    "convention from this app's free chart features (mode 45 Krishnamurti "
    "VP291 + a confirmed correction, mean lunar node for Rahu/Ketu) -- "
    "planetary degrees here will differ slightly from /api/chart's for the "
    "same birth data; that discrepancy is real, documented, and not yet "
    "reconciled by the client. The transit side uses whatever moment/"
    "location the caller supplies; the client's own convention for which "
    "location their 'current' transit snapshot uses is still unconfirmed "
    "(see the project roadmap doc)."
)


def compute_ccsi_report(natal_moment: BirthMoment, transit_moment: BirthMoment) -> CcsiReport:
    """Computes the full CCSI report: L (natal cusp/planet vs. natal
    planets), LT (natal cusp/planet vs. TRANSIT planets), and TT (transit
    cusp/planet vs. TRANSIT planets), each net and Negative-Hits-Only.

    `exclude_self` is set per the confirmed rule (see `hit_calc.py`'s
    module docstring): True for L and TT (same table on both sides -- a
    planet's own position can't aspect itself), False for LT (the natal
    and transiting planet of the same name are different positions, and
    the transit DOES legitimately aspect its own natal placement).
    """
    natal = compute_ccsi_positions(natal_moment)
    transit = compute_ccsi_positions(transit_moment)

    l_net = compute_ccsi_row(
        natal.house_cusps, natal.ascendant_deg, natal.planet_longitudes,
        natal.planet_longitudes,
    )
    l_negative = compute_ccsi_row(
        natal.house_cusps, natal.ascendant_deg, natal.planet_longitudes,
        natal.planet_longitudes, negative_only=True,
    )
    lt_net = compute_ccsi_row(
        natal.house_cusps, natal.ascendant_deg, natal.planet_longitudes,
        transit.planet_longitudes, exclude_self=False,
    )
    lt_negative = compute_ccsi_row(
        natal.house_cusps, natal.ascendant_deg, natal.planet_longitudes,
        transit.planet_longitudes, negative_only=True, exclude_self=False,
    )
    tt_net = compute_ccsi_row(
        transit.house_cusps, transit.ascendant_deg, transit.planet_longitudes,
        transit.planet_longitudes,
    )
    tt_negative = compute_ccsi_row(
        transit.house_cusps, transit.ascendant_deg, transit.planet_longitudes,
        transit.planet_longitudes, negative_only=True,
    )

    return CcsiReport(
        l_net=l_net, l_negative=l_negative,
        lt_net=lt_net, lt_negative=lt_negative,
        tt_net=tt_net, tt_negative=tt_negative,
    )
