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
docstring.

UPDATE (2026-09-24, later still): two real bugs from the live Planet
Details Table, fixed here:

1. The Ascendant entry never carried `degree_in_sign` / `nakshatra` /
   `nakshatra_lord` / `pada` / `meaning` at all -- `chart.ascendant` is an
   `ephemeris.HouseCusp`, a different dataclass from `PlanetPosition`
   that was never given those fields, even though the Ascendant's degree
   was already shown (it's the same `longitude` the rest of the row is
   built from). Fixed by computing them here, the same way
   `ephemeris.compute_planet` does for a real planet, rather than adding
   unused fields to every house cusp (only the Ascendant/house 1 needs
   this treatment).
2. Every planet dict gained a new `flags` field -- the SAME Retrograde/
   Combust/Exalted/Debilitated/Own Sign/Vargottama flags the Free Preview
   (teaser.py) already computed, now also here via chart_narrative.py's
   `planet_flags()` (see that module's docstring for the full story: this
   endpoint previously only ever exposed the plain `retrograde` boolean,
   which is why, e.g., Jupiter sitting in its sign of debilitation never
   showed a "Debilitated" badge on the live chart-wheel views even though
   the Free Preview tab, a click away, already stated it correctly). The
   Ascendant also gets a `flags` list, though only ever `["Vargottama"]`
   or `[]` -- it isn't a planet, so it has no retrograde/combust/dignity
   of its own, matching how teaser.py already treats the Ascendant row."""
from __future__ import annotations

from .chart_narrative import (
    is_vargottama, natal_conjunctions, planet_flags, planet_nature,
    position_meaning,
)
from .ephemeris import (
    BirthMoment, NatalChart, compute_natal_chart, nakshatra_for_longitude,
    sign_for_longitude, sign_index_for_longitude, whole_sign_house,
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
    sun = next((p for p in chart.planets if p.code == "Su"), None)
    sun_longitude = sun.longitude if sun else None

    # Ascendant's own degree/nakshatra/pada -- same longitude the rest of
    # its row is already built from, just never broken down this way
    # before (see module docstring, this round's fix #1).
    _, _, asc_degree_in_sign = sign_for_longitude(chart.ascendant.longitude)
    asc_nakshatra, asc_nakshatra_lord, asc_pada = nakshatra_for_longitude(
        chart.ascendant.longitude
    )
    asc_flags = ["Vargottama"] if is_vargottama(chart.ascendant.longitude) else []

    return {
        "ayanamsa_deg": round(chart.ayanamsa_deg, 4),
        "ayanamsa_mode": chart.ayanamsa_mode,
        "ascendant": {
            "house": chart.ascendant.house,
            "longitude": round(chart.ascendant.longitude, 3),
            "sign": chart.ascendant.sign,
            "sign_lord": chart.ascendant.sign_lord,
            "degree_in_sign": round(asc_degree_in_sign, 3),
            "nakshatra": asc_nakshatra,
            "nakshatra_lord": asc_nakshatra_lord,
            "pada": asc_pada,
            "meaning": position_meaning(chart.ascendant.sign, asc_nakshatra, asc_pada),
            "flags": asc_flags,
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
                "flags": planet_flags(
                    p.code, p.sign, p.longitude, p.retrograde, sun_longitude
                ),
            }
            for p in chart.planets
        ],
    }
