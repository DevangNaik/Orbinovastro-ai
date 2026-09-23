"""Mechanical-layer transit: where the planets are *right now* (or at any
given moment), placed against an already-computed natal chart.

Scope, deliberately: sidereal position + sign + nakshatra for each
transiting planet, which *natal* house it currently occupies, and a simple
same-longitude conjunction flag against natal planets (default 3-degree
orb). This is generic astronomy plus the same house-placement math already
used and tested elsewhere in this app (engine/kp.py's house_of_longitude)
-- no proprietary judgment involved, so it is NOT labeled beta.

Explicitly NOT included (the client's own workbook has much more under
"transit and other tables" that hasn't been scoped/audited yet):
  - Transit-to-natal aspects beyond conjunction (trine/square/opposition,
    with whatever orb rules the client's practice uses)
  - Dasha/Bhukti overlay ("what period is running during this transit")
  - Any event-timing/scoring judgment
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone

from .ephemeris import BirthMoment, NatalChart, compute_natal_chart, normalize360
from .kp import house_of_longitude

CONJUNCTION_ORB_DEG = 3.0


@dataclass
class TransitPlanet:
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
    conjuncts_natal: list[str]


def _angular_diff(a: float, b: float) -> float:
    d = abs(normalize360(a) - normalize360(b))
    return min(d, 360.0 - d)


def compute_transit(
    natal_chart: NatalChart,
    transit_moment: BirthMoment,
) -> tuple[list[TransitPlanet], str]:
    """Compute current planetary positions and place them against the
    already-computed natal_chart's houses and planets. Returns
    (transit_planets, iso_utc_timestamp_used)."""
    transit_chart = compute_natal_chart(transit_moment)
    natal_cusps = [h.longitude for h in natal_chart.houses]

    out: list[TransitPlanet] = []
    for tp in transit_chart.planets:
        conjuncts = [
            np.code for np in natal_chart.planets
            if _angular_diff(tp.longitude, np.longitude) <= CONJUNCTION_ORB_DEG
        ]
        out.append(TransitPlanet(
            code=tp.code, name=tp.name, longitude=round(tp.longitude, 3),
            sign=tp.sign, sign_lord=tp.sign_lord,
            degree_in_sign=round(tp.degree_in_sign, 3),
            nakshatra=tp.nakshatra, nakshatra_lord=tp.nakshatra_lord,
            retrograde=tp.retrograde,
            natal_house=house_of_longitude(tp.longitude, natal_cusps),
            conjuncts_natal=conjuncts,
        ))

    ut_dt = datetime(
        transit_moment.year, transit_moment.month, transit_moment.day,
        transit_moment.hour, transit_moment.minute, transit_moment.second,
    ) - _offset_delta(transit_moment.utc_offset_hours)
    iso_ts = ut_dt.replace(tzinfo=dt_timezone.utc).isoformat()
    return out, iso_ts


def _offset_delta(utc_offset_hours: float):
    from datetime import timedelta
    return timedelta(hours=utc_offset_hours)


def now_as_birth_moment(latitude: float, longitude: float) -> BirthMoment:
    """A BirthMoment representing the current instant, UTC (offset 0)."""
    now = datetime.now(dt_timezone.utc)
    return BirthMoment(
        year=now.year, month=now.month, day=now.day,
        hour=now.hour, minute=now.minute, second=now.second,
        utc_offset_hours=0.0, latitude=latitude, longitude=longitude,
    )
