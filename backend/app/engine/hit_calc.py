"""
CCSI (Cusp Conflict Stress Indicator) engine -- faithful Python port of the
`HIT_CALC!G184:AE204` Excel LET formulas.

Why this module exists: the paid Overview Report (`generate_overview_report.py`
/ `ccsi_parser.py`) reads a pre-computed block, `HIT_CALC!G185:AE204`, from
the live workbook -- it never computes it. This module is the first attempt
to compute that block natively, based on:

1. The client's own `ccsi_parser.py` (read, not modified), whose docstring
   confirms CCSI is EVENT-INDEPENDENT: it measures house/planet "hit"
   stress from three angles -- natal Lagna chart (D1), Transit-to-Lagna,
   and Transit-to-Transit -- and is a wholly separate system from
   `EventList`/`Score_Additive` (see `scoring.py`). Confirmed the row
   layout: row 1 = houses 1-12 + planet codes (Asc,Su,Mo,Ma,Me,Ju,Ve,Sa,
   Ra,Ke); row 2 = NET Lagna; row 4 = NET Transit-to-Lagna; row 6 = NET
   Transit-to-Transit; a second block (starting ~row 13) repeats the same
   three as "Negative Hits Only" variants.
2. The client's own "Show Formulas" paste of every cell in
   `HIT_CALC!G184:AE204` (2026-09-23) -- the actual LET-based Excel
   formula, which this module ports line-for-line in spirit:
   - For a given reference point (a house cusp, or a planet's own
     position), measure the angular separation to each of 9 grahas.
   - Classify that separation by which row of an aspect-range lookup
     table (`HITAspectRanges`) it falls into.
   - Convert the aspect type to a signed weight, multiply by whether the
     aspecting planet is malefic (x2) or benefic (x1), and sum across all
     9 planets.
   - Three "net" (positive+negative) variants differ only in which cusp/
     planet data feeds in: L = natal cusp vs natal planets; LT = natal
     cusp vs TRANSIT planets; TT = transit cusp vs TRANSIT planets.
   - The "Negative Hits Only" block reuses the same per-planet aspect
     weight (`wFull`) but keeps only the negative side:
     `aspectW = IF(wFull<0, -wFull, 0)` -- i.e. it reports the pure
     magnitude of Irritation/Enemy/Killer aspects only, zeroing out
     Cnj/Frn/BFrn/SoulM entirely.
   - Planet-column cells additionally exclude the planet's own
     self-aspect (the VBA/Excel references a row-186 planet label for
     this; here it's just an explicit `exclude` planet name).
3. The client's own `HITAspectRanges` table (2026-09-23, pasted twice --
   once with just No/Degree/Margin/Min/Max/HIT Name/HIT Type, once more
   with three extra columns: Default Margin, Only Bad aspects, Default
   Range sequence). CONFIRMED, not guessed:
   - `Min`/`Max` are just `Degree - Margin` / `Degree + Margin`, except
     Conjunction's Min is hard-floored at 0 rather than going negative
     (harmless in practice: the angular-separation formula below always
     produces `d` in [0, 180], so Min never needs to go below 0 anyway).
   - The 7 aspect types turn out to be ordinary WESTERN aspect angles
     (0/30/45/60/90/120/180 degrees) with astrology-flavored labels
     stapled on (Frn="friend", BFrn="best friend", SoulM="soulmate",
     "Irritation"/"Enemy"/"Killer" for the hard aspects) -- NOT a
     planet-pair friendship/enmity table as this module's author had
     speculated before this data arrived. The classification depends
     ONLY on the angular distance between the two points, never on which
     specific two planets/points are involved. This resolved what had
     been flagged as the single biggest remaining unknown.
   - The extra "Default Margin"/"Only Bad aspects"/"Default Range
     sequence" columns turned out to be legend/ranking metadata (e.g.
     "Only Bad aspects" ranks Killer=1/Enemy=2/Irritation=3 by severity,
     and flags the friendly aspects with -1 and Cnj with 0) -- NOT used
     by the scoring formula itself, which hardcodes its own
     `{"Cnj","Frn","BFrn","SoulM","Irritation","Enemy","Killer"} ->
     {1,1,2,3,-1,-2,-3}` weight lookup independently of this table's
     "Only Bad aspects" column. Kept here for completeness/traceability
     but not used in any calculation.

STATUS (2026-09-24): FULLY VALIDATED -- all three variants (L, LT, TT)
and both the "net" and "Negative Hits Only" rows for each now match the
client's real `HIT_CALC` output exactly. This is the strongest possible
confirmation for a ported proprietary formula: every number this module
produces for these six real-data rows is byte-for-byte identical to the
client's own live workbook output, not merely "internally consistent."

Full end-to-end validation history:
1. `Bhava_Deg` (real natal house cusps) received from the client and
   back-solved to find the birth coordinates (20.815615N, 72.959475E),
   which reproduce all 12 real cusps to ~4e-7 degrees using this
   engine's own sidereal Placidus computation -- see
   `tests/test_hit_calc_reference_chart.py`. This confirmed the natal
   cusp/ayanamsa wiring independently, BEFORE any `HIT_CALC` numbers
   were available to check against.
2. The client then sent the real `HIT_CALC!G184:AE204` values block.
   Their transit 9-planet table (`$A$44:$B$52`) was empty at the time,
   but the "L" (natal-cusp-vs-natal-planet) row and its negative-only
   counterpart use ONLY already-validated natal data. Computing both
   rows with this module and comparing cell-by-cell against the real
   `HIT_CALC` output matched **44/44 cells exactly** (12 houses + Asc +
   9 planets, x2 rows) -- see `tests/test_hit_calc_lagna_validated.py`.
3. The client then populated and sent the real transit 9-planet table
   (`$A$44:$B$52`) plus the real `Bhava_Degrees_Transit` transit cusps.
   Computing LT (natal cusp/planet columns vs transiting aspecting
   planets) and TT (transit cusp/planet columns vs transiting aspecting
   planets), net and negative-only, and comparing against the same real
   `HIT_CALC` paste's LT/TT rows: **TT matched 44/44 immediately**
   (both net and negative-only). **LT initially mismatched on 3 of 22
   net cells** (the Mo/Ra/Ke planet-column self-exclusion cases) --
   negative-only LT still matched 22/22, isolating the bug to the
   self-exclusion logic specifically, only visible on friendly aspects.
   Diagnosis: `compute_ccsi_row`'s planet-column self-exclusion
   (`exclude=planet`) is only correct when `reference_planet_degrees`
   and `comparison_planet_degrees` come from the SAME table (true for L
   and TT: a planet's own position can't aspect itself) -- for LT, the
   natal planet and the transiting planet of the same name are two
   DIFFERENT positions, and the transiting planet legitimately aspects
   its own natal placement (that's a real transit hit, not a
   self-aspect). Added an explicit `exclude_self` parameter (default
   `True`, matching L/TT; callers pass `exclude_self=False` for LT) --
   with that fix, **LT also matched 44/44**. Total: **132/132 real
   `HIT_CALC` cells confirmed exactly** across L, LT, and TT, net and
   negative-only. This is a second genuine bug that only real data could
   have caught (the first was `kp_lords.py`'s SSL-cycle convention).
   See `tests/test_hit_calc_lt_tt_validated.py`.

`Bhava_Degrees_Transit`'s earlier back-solving residual (a few tenths of
a degree, when trying to recover the transit snapshot's date/time/
location blind) remains unexplained, but is now moot for this module's
purposes: the client's real transit cusps and transit planet table are
used directly, not re-derived, so that discrepancy no longer blocks
anything here. It's noted in the project roadmap doc as a loose end for
whoever eventually needs to compute a *live* "current" CCSI reading
end-to-end without the client re-exporting the transit table each time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# HITAspectRanges -- confirmed verbatim from the client's own table
# (2026-09-23). Min/Max are the literal resolved values (Degree +/- Margin,
# with Conjunction's Min floored at 0 as the client's own sheet does).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AspectRange:
    no: int
    degree: float
    margin: float
    min: float
    max: float
    name: str
    type: str


ASPECT_RANGES: List[AspectRange] = [
    AspectRange(no=0, degree=0, margin=3, min=0, max=3, name="Conj", type="Cnj"),
    AspectRange(no=4, degree=30, margin=3, min=27, max=33, name="Sem-Sextile", type="Frn"),
    AspectRange(no=5, degree=60, margin=5, min=55, max=65, name="Sextile", type="BFrn"),
    AspectRange(no=6, degree=120, margin=8, min=112, max=128, name="Trine", type="SoulM"),
    AspectRange(no=3, degree=45, margin=3, min=42, max=48, name="Semi Square", type="Irritation"),
    AspectRange(no=2, degree=90, margin=5, min=85, max=95, name="Sqare", type="Enemy"),
    AspectRange(no=1, degree=180, margin=8, min=172, max=188, name="Opposition", type="Killer"),
]

# Confirmed from the client's own LET formula:
# XLOOKUP(type, {"Cnj","Frn","BFrn","SoulM","Irritation","Enemy","Killer"},
#               {1,1,2,3,-1,-2,-3}, 0)
ASPECT_TYPE_WEIGHTS: Dict[str, float] = {
    "Cnj": 1.0,
    "Frn": 1.0,
    "BFrn": 2.0,
    "SoulM": 3.0,
    "Irritation": -1.0,
    "Enemy": -2.0,
    "Killer": -3.0,
}

# Confirmed from the client's own LET formula:
# XLOOKUP(pn, {"Sa","Ma","Ra","Ke","Su","Me","Mo","Ju","Ve"},
#             {2,2,2,2,1,1,1,1,1}, 0)
MALEFIC_PLANETS = {"Sa", "Ma", "Ra", "Ke"}
BENEFIC_PLANETS = {"Su", "Me", "Mo", "Ju", "Ve"}
PLANET_TYPE_WEIGHTS: Dict[str, float] = {
    **{p: 2.0 for p in MALEFIC_PLANETS},
    **{p: 1.0 for p in BENEFIC_PLANETS},
}

NINE_PLANETS = ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]


def angular_separation(deg_a: float, deg_b: float) -> float:
    """Shortest angular distance between two zodiacal degrees, in [0, 180].

    Matches the client's `d = ABS(MOD(pAdj - zAdj + 180, 360) - 180)`. The
    formula subtracts the Ascendant degree from both points first
    ("zAdj"/"pAdj"), but that cancels out algebraically -- `(p - asc) -
    (z - asc) == p - z` -- so this function takes the two raw degrees
    directly and produces the same `d`.
    """
    diff = (deg_b - deg_a + 180.0) % 360.0 - 180.0
    return abs(diff)


def classify_aspect(d: float) -> Optional[str]:
    """Return the aspect TYPE code (e.g. "Cnj", "Killer") whose [min, max]
    window contains `d`, or None if `d` falls in a gap between ranges
    (which contributes zero weight, matching the Excel formula's XLOOKUP
    default of 0 when no type is found).
    """
    for rng in ASPECT_RANGES:
        if rng.min <= d <= rng.max:
            return rng.type
    return None


def _planet_weight(planet: str) -> float:
    try:
        return PLANET_TYPE_WEIGHTS[planet]
    except KeyError:
        raise ValueError(
            f"Unknown planet code {planet!r}; expected one of {NINE_PLANETS}"
        )


def net_hit_score(
    reference_deg: float,
    planet_degrees: Dict[str, float],
    exclude: Optional[str] = None,
) -> float:
    """The "net" (positive + negative) CCSI hit-count for one cell: sum,
    over the 9 planets in `planet_degrees` (optionally excluding one, for
    a planet-column cell's self-aspect), of aspect-type-weight x
    planet-type-weight.

    `planet_degrees` should have exactly the 9 classical/nodal planet
    codes as keys (`NINE_PLANETS`) -- callers are responsible for
    supplying the correct natal-vs-transit table for the L/LT/TT variant
    being computed.
    """
    total = 0.0
    for planet, planet_deg in planet_degrees.items():
        if planet == exclude:
            continue
        d = angular_separation(reference_deg, planet_deg)
        aspect_type = classify_aspect(d)
        if aspect_type is None:
            continue
        total += ASPECT_TYPE_WEIGHTS[aspect_type] * _planet_weight(planet)
    return total


def negative_only_hit_score(
    reference_deg: float,
    planet_degrees: Dict[str, float],
    exclude: Optional[str] = None,
) -> float:
    """The "Negative Hits Only" CCSI hit-count for one cell: same
    per-planet aspect classification as `net_hit_score`, but each
    planet's contribution is `IF(wFull<0, -wFull, 0)` before being
    multiplied by the planet-type weight -- i.e. friendly aspects
    (Cnj/Frn/BFrn/SoulM) contribute nothing, and hard aspects
    (Irritation/Enemy/Killer) contribute their positive magnitude.
    Always >= 0.
    """
    total = 0.0
    for planet, planet_deg in planet_degrees.items():
        if planet == exclude:
            continue
        d = angular_separation(reference_deg, planet_deg)
        aspect_type = classify_aspect(d)
        if aspect_type is None:
            continue
        w_full = ASPECT_TYPE_WEIGHTS[aspect_type]
        aspect_w = -w_full if w_full < 0 else 0.0
        total += aspect_w * _planet_weight(planet)
    return total


@dataclass(frozen=True)
class CcsiRow:
    """One "net" row's 12 house-cusp hit-counts plus 10 planet-column
    (Asc + 9 planets) hit-counts, matching one row of
    `HIT_CALC!G184:AE204` (12 house columns + Asc + 9 planet columns).
    """

    houses: Dict[int, float]  # 1..12 -> hit count
    columns: Dict[str, float]  # "Asc","Su",...,"Ke" -> hit count


def compute_ccsi_row(
    house_cusp_degrees: Dict[int, float],
    ascendant_deg: float,
    reference_planet_degrees: Dict[str, float],
    comparison_planet_degrees: Dict[str, float],
    *,
    negative_only: bool = False,
    exclude_self: bool = True,
) -> CcsiRow:
    """Compute one full CCSI "net" (or "Negative Hits Only") row.

    - `house_cusp_degrees`: the 12 house-cusp degrees for the chart side
      being SCORED (natal cusps for the L and LT rows; transit cusps for
      the TT row).
    - `ascendant_deg`: that same chart side's Ascendant degree (its own
      column, scored the same way a house cusp is).
    - `reference_planet_degrees`: the 9 planets' degrees for the chart
      side being SCORED, used as each planet-column's own reference
      degree (natal planets for L; natal planets for LT [LT still scores
      the NATAL planet's own column against transiting aspectors]; transit
      planets for TT). Only the entries for `NINE_PLANETS` are read.
    - `comparison_planet_degrees`: the 9 aspecting planets' degrees (the
      ones being measured FOR aspects) -- natal planets for L, TRANSIT
      planets for both LT and TT, per the client's confirmed L/LT/TT
      definitions.
    - `negative_only`: use `negative_only_hit_score` instead of
      `net_hit_score` for every cell (the "Negative Hits Only" block).
    - `exclude_self`: whether each planet's own column excludes that same
      planet from `comparison_planet_degrees` (the row-186 self-exclusion).
      CONFIRMED (2026-09-24, real `HIT_CALC` data) this only applies when
      `reference_planet_degrees` and `comparison_planet_degrees` are the
      SAME underlying table -- i.e. **True for L and TT** (natal-vs-natal,
      transit-vs-transit: a planet's own position can't aspect itself) but
      **False for LT** (natal-vs-transit: the natal planet and the
      transiting planet of the same name are two different positions, and
      the transiting planet DOES aspect its own natal placement -- that's
      not a self-aspect, it's a real transit hit). Callers must pass
      `exclude_self=False` when calling this for the LT row.
    """
    score_fn = negative_only_hit_score if negative_only else net_hit_score

    houses: Dict[int, float] = {}
    for house_num, cusp_deg in house_cusp_degrees.items():
        houses[house_num] = score_fn(cusp_deg, comparison_planet_degrees)

    columns: Dict[str, float] = {
        "Asc": score_fn(ascendant_deg, comparison_planet_degrees)
    }
    for planet in NINE_PLANETS:
        if planet not in reference_planet_degrees:
            continue
        ref_deg = reference_planet_degrees[planet]
        exclude = planet if exclude_self else None
        columns[planet] = score_fn(ref_deg, comparison_planet_degrees, exclude=exclude)

    return CcsiRow(houses=houses, columns=columns)
