"""BETA: standard KP (Krishnamurti Paddhati) Sub Lord + significators.

This is deliberately kept separate from ephemeris.py (the validated
mechanical layer). Everything here implements the *classical, publicly
documented* KP technique -- Sub Lord via proportional Vimshottari
subdivision of each nakshatra, and the standard 4-level significator
method (occupants / owner / star-lords-of-occupants / star-lord-of-owner).

It is explicitly NOT a port of the client's proprietary workbook logic:
  - It does NOT use ScoringModule.bas's Score_Additive weighting, or the
    ConnSummaryCore/BatchAnalyze_MD_Combinations_* ranking formulas --
    those depend on the client's own PlTblCl weight tables and
    hand-tuned coefficients, which live in worksheet cells we don't have
    (see roadmap doc open questions #3, #8).
  - It has NOT been cross-checked against the client's actual
    ConnSummaryCore output for real charts.

Treat every result from this module as "standard KP theory, unvalidated
against this client's specific practice" until spot-checked against the
production workbook. Surfaced in the UI/chat as clearly labeled beta.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ephemeris import (
    NAKSHATRA_NAMES,
    NAKSHATRA_SPAN,
    VIMSHOTTARI_ORDER,
    VIMSHOTTARI_YEARS,
    NatalChart,
    normalize360,
)


@dataclass
class SubLordInfo:
    nakshatra: str
    nakshatra_lord: str
    sub_lord: str


def sub_lord_for_longitude(sid_long: float) -> SubLordInfo:
    """Classic KP Sub Lord: each 13d20' nakshatra is split into 9 unequal
    parts, one per Vimshottari-order planet, sized proportional to that
    planet's dasha years out of 120, with the cycle starting at the
    nakshatra's own lord (not always Ketu)."""
    sid_long = normalize360(sid_long)
    nak_index = min(int(sid_long // NAKSHATRA_SPAN), 26)
    nak_start = nak_index * NAKSHATRA_SPAN
    offset = sid_long - nak_start
    nak_lord = VIMSHOTTARI_ORDER[nak_index % 9]

    start_pos = VIMSHOTTARI_ORDER.index(nak_lord)
    cumulative = 0.0
    sub_lord = VIMSHOTTARI_ORDER[start_pos]
    for step in range(9):
        lord = VIMSHOTTARI_ORDER[(start_pos + step) % 9]
        span = NAKSHATRA_SPAN * (VIMSHOTTARI_YEARS[lord] / 120.0)
        if offset < cumulative + span or step == 8:
            sub_lord = lord
            break
        cumulative += span

    return SubLordInfo(NAKSHATRA_NAMES[nak_index], nak_lord, sub_lord)


def house_of_longitude(sid_long: float, cusp_longitudes: list[float]) -> int:
    """Which of the 12 houses (1-12) a longitude falls in, given the 12
    cusp start-longitudes in house order, handling the 360-degree wrap."""
    sid_long = normalize360(sid_long)
    for h in range(12):
        start = cusp_longitudes[h]
        end = cusp_longitudes[(h + 1) % 12]
        if start <= end:
            if start <= sid_long < end:
                return h + 1
        else:  # wraps past 360
            if sid_long >= start or sid_long < end:
                return h + 1
    return 12  # fallback, should not normally hit


@dataclass
class HouseSignificators:
    house: int
    occupants: list[str] = field(default_factory=list)
    owner: str = ""
    star_lord_of_occupants: list[str] = field(default_factory=list)
    star_lord_of_owner: list[str] = field(default_factory=list)
    cuspal_sub_lord: str = ""


def compute_kp_beta(chart: NatalChart) -> dict:
    """Given an already-computed NatalChart, derive:
      - Sub Lord (and star/nakshatra lord) for every planet and every
        house cusp
      - the standard 4-level significators for each of the 12 houses

    Returns a plain dict, JSON-ready.
    """
    cusp_longs = [h.longitude for h in chart.houses]

    planet_sub: dict[str, SubLordInfo] = {
        p.code: sub_lord_for_longitude(p.longitude) for p in chart.planets
    }
    planet_house: dict[str, int] = {
        p.code: house_of_longitude(p.longitude, cusp_longs) for p in chart.planets
    }
    nakshatra_lord_of: dict[str, str] = {
        p.code: p.nakshatra_lord for p in chart.planets
    }

    houses_out: list[HouseSignificators] = []
    for house_num in range(1, 13):
        cusp = chart.houses[house_num - 1]
        occupants = [code for code, h in planet_house.items() if h == house_num]
        owner = cusp.sign_lord
        star_of_occupants = sorted(
            {code for code, nl in nakshatra_lord_of.items() if nl in occupants}
        )
        star_of_owner = sorted(
            {code for code, nl in nakshatra_lord_of.items() if nl == owner}
        )
        csl = sub_lord_for_longitude(cusp.longitude).sub_lord
        houses_out.append(HouseSignificators(
            house=house_num, occupants=occupants, owner=owner,
            star_lord_of_occupants=star_of_occupants,
            star_lord_of_owner=star_of_owner, cuspal_sub_lord=csl,
        ))

    return {
        "beta_disclaimer": (
            "BETA: standard KP Sub Lord + 4-level significator theory only. "
            "Does NOT use this client's proprietary ConnSummaryCore/"
            "Score_Additive scoring or ranking (those need workbook weight "
            "tables not yet available) and has not been cross-checked "
            "against the production workbook's own output. For reference "
            "only until validated."
        ),
        "planet_sub_lords": {
            code: {
                "nakshatra": info.nakshatra,
                "nakshatra_lord": info.nakshatra_lord,
                "sub_lord": info.sub_lord,
                "house": planet_house[code],
            }
            for code, info in planet_sub.items()
        },
        "house_significators": [
            {
                "house": h.house,
                "occupants": h.occupants,
                "owner": h.owner,
                "star_lord_of_occupants": h.star_lord_of_occupants,
                "star_lord_of_owner": h.star_lord_of_owner,
                "cuspal_sub_lord": h.cuspal_sub_lord,
            }
            for h in houses_out
        ],
    }
