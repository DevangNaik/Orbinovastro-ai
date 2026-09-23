"""Orchestration: turn API input (BirthDetailsIn) into a NatalChart and
back into plain dicts/JSON-friendly shapes. Kept separate from ephemeris.py
so the pure-astronomy code has no FastAPI/pydantic dependency."""
from __future__ import annotations

from .ephemeris import BirthMoment, NatalChart, compute_natal_chart
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
            }
            for p in chart.planets
        ],
    }
