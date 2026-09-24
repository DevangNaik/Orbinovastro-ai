"""Orchestration: turn API input (BirthDetailsIn) into a NatalChart and
back into plain dicts/JSON-friendly shapes. Kept separate from ephemeris.py
so the pure-astronomy code has no FastAPI/pydantic dependency.

Each planet carries TWO house numbers, both valid, answering different
questions:
  - "house": Bhava Chalit -- which Placidus cusp segment the planet's
    exact longitude falls in. This is what KP practice (kp.py's
    significators) uses.
  - "rasi_house": classical D1/Rasi -- whole-sign house counted from the
    ascendant's own sign. This is the traditional North Indian/South
    Indian diagram convention. The two usually agree but can differ for
    a planet near a house cusp -- showing both is intentional, not a bug.

UPDATE (2026-09-24, latest): the client asked for the chart views to carry
the same richer per-planet detail their own Excel Kundli chart shows --
each planet already had degree/nakshatra/pada; two new fields added this
round: `meaning` (a short, standard "nakshatra theme + sign color"
sentence, via the new chart_narrative.py, reused from teaser.py's own
phrase banks so the two features never diverge) and `conjunctions` (which
other planets share this one's D1 sign, and how many degrees apart --
plain angular geometry, not a scoring judgment). Both are attached here,
in the one shared `/api/chart` response every chart view (D1, Bhava
Chalit, D9, Cuspal) already draws its planet list from, so this single
change reaches all of them at once -- see chart_narrative.py's own
docstring."""
from __future__ import annotations

from .chart_narrative import natal_conjunctions, planet_nature, position_meaning
from .ephemeris import (
    BirthMoment, NatalChart, compute_natal_chart,
    sign_index_for_longitude, whole_sign_house,
)
from .kp import house_of_longitude


def build_chart_from_fields(
    year: int, month: int, day: int, hour: int, minute: int,
    second: int = 0, utc_offset_hours: float = 5.5,
    latitude: float = 0.0, longitude: float = 0.0,
) -> NatalChart:
    moment = BirthMoment(
        year=year, month=month, day=day, hour=hour, minute=minute,
        second=second, utc_offset_hours=utc_offset_hours,
        latitude=latitude, longitude=longitude,
    )
    return compute_natal_chart(moment)


def chart_to_dict(chart: NatalChart) -> dict:
    cusp_longitudes = [h.longitude for h in chart.houses]
    asc_sign_index = sign_index_for_longitude(chart.ascendant.longitude)
    conjunctions_by_code = natal_conjunctions(chart.planets)
    return {
        "ayanamsa_deg": round(chart.ayanamsa_deg, 4),
        "ayanamsa_mode": chart.ayanamsa_mode,
        "ascendant": {
            "house": chart.ascendant.house,
            "longitude": round(chart.ascendant.longitude, 3),
            "sign": chart.ascendant.sign,
            "sign_lord": chart.ascendant.sign_lord,
        },
        "houses": [
            {
                "house": h.house,
                "longitude": round(h.longitude, 3),
                "sign": h.sign,
                "sign_lord": h.sign_lord,
            }
            for h in chart.houses
        ],
        "planets": [
            {
                "code": p.code,
                "name": p.name,
                "longitude": round(p.longitude, 3),
                "sign": p.sign,
                "sign_lord": p.sign_lord,
                "degree_in_sign": round(p.degree_in_sign, 3),
                "nakshatra": p.nakshatra,
                "nakshatra_lord": p.nakshatra_lord,
                "pada": p.pada,
                "retrograde": p.retrograde,
                "house": house_of_longitude(p.longitude, cusp_longitudes),
                "rasi_house": whole_sign_house(
                    sign_index_for_longitude(p.longitude), asc_sign_index
                ),
                "meaning": position_meaning(p.sign, p.nakshatra, p.pada),
                "conjunctions": conjunctions_by_code[p.code],
                "nature": planet_nature(p.code),
            }
            for p in chart.planets
        ],
    }
