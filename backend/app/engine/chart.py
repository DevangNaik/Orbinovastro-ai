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
   of its own, matching how teaser.py already treats the Ascendant row.

UPDATE (2026-09-24, later still again): added `aspects`/`aspected_by` to
every planet (classical Parashari whole-sign graha drishti -- the
universal 7th/opposition aspect for all 9 grahas plus Mars/Jupiter/
Saturn's own special aspects, via chart_narrative.natal_aspects()) and
`aspected_by` to the Ascendant (planets aspecting the 1st house/Lagna is
standard; Lagna itself never casts an aspect, so it has no `aspects` key
of its own -- consistent with how it already has no `conjunctions`/
`nature`). Deliberately distinct from `conjunctions` (same-sign proximity)
and from hit_calc.py's own Western-angle aspect classification used for
CCSI stress scoring -- see chart_narrative.py's own docstring.

UPDATE (2026-09-24, even later still): switched to the CCSI-confirmed
ayanamsa/node convention (see ephemeris.py's own docstring) and added
`functional_nature` to every planet -- a new, chart-specific (house-
lordship based) Benefic/Malefic classification, client-requested,
deliberately SEPARATE from the existing fixed `nature` field (which stays
untouched, since it's load-bearing for hit_calc.py's validated CCSI
scoring). None for Rahu/Ketu (the lunar nodes rule no sign, so this
lordship-based rule has nothing to apply to them -- see
chart_narrative.py's own comment for why this is a deliberate omission,
not an oversight). BETA: a standard classical textbook rule, validated
against the client's real Excel data for the 7 rasi-ruling grahas, not
yet confirmed as the client's own workbook formula.

UPDATE (2026-09-24, yet even later still): added Uranus/Neptune/Pluto to
the `planets` list -- client-requested, real Swiss Ephemeris positions
(via `ephemeris.compute_outer_planets`), validated against the client's
real Excel data (all 3 matched to within 0.0001 degrees, same nakshatra/
pada). They get `house`/`rasi_house`/`meaning`/`flags` computed exactly
like any classical graha, but empty `conjunctions`/`aspects`/
`aspected_by` and no `nature`/`functional_nature` -- classical Parashari
conjunctions and graha-drishti are a graha-only concept, and the outer
planets have no classical natural-benefic/malefic assignment and rule no
sign. Deliberately kept OUT of `ephemeris.compute_natal_chart`'s own
9-planet `chart.planets` list and out of a SEPARATE `chart.outer_planets`
field instead, so every classical-9-planet-only consumer of
`compute_natal_chart` (teaser.py, kp.py significators, varga.py D9,
ccsi.py/hit_calc.py CCSI scoring, dasha.py) is completely unaffected --
only this function merges them into the /api/chart response."""
from __future__ import annotations

from .chart_narrative import (
    aspected_by_for_point, functional_nature, is_vargottama, natal_aspects,
    natal_conjunctions, planet_flags, planet_nature, position_meaning,
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
    aspects_by_code = natal_aspects(chart.planets)
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
    asc_aspected_by = aspected_by_for_point(chart.ascendant.longitude, chart.planets)

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
            "aspected_by": asc_aspected_by,
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
                "functional_nature": functional_nature(p.code, asc_sign_index),
                "flags": planet_flags(
                    p.code, p.sign, p.longitude, p.retrograde, sun_longitude
                ),
                "aspects": aspects_by_code[p.code]["aspects"],
                "aspected_by": aspects_by_code[p.code]["aspected_by"],
            }
            for p in chart.planets
        ] + [
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
                # Uranus/Neptune/Pluto: no conjunctions/aspects (classical
                # Parashari drishti is a graha-only concept -- see
                # ephemeris.py's OUTER_PLANET_IDS comment) and no nature/
                # functional_nature (no classical natural-benefic/malefic
                # assignment for the outer planets, and they rule no sign
                # so there's no house-lordship to base a functional
                # reading on either).
                "conjunctions": [],
                "nature": "",
                "functional_nature": None,
                "flags": planet_flags(
                    p.code, p.sign, p.longitude, p.retrograde, sun_longitude
                ),
                "aspects": [],
                "aspected_by": [],
            }
            for p in chart.outer_planets
        ],
    }
