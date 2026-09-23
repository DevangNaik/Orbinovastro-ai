"""D9 Navamsa (divisional/varga chart) engine -- BETA, standard textbook
formula only.

Every sign's 30 degrees is split into 9 equal Navamsa parts of 3d20' each.
The classical rule assigns each part a ruling sign based on whether the
occupied Rashi is movable/fixed/dual (chara/sthira/dwiswabhava), starting
the 9-part cycle at the Rashi itself (movable), the 9th sign from it
(fixed), or the 5th sign from it (dual). That rule is mathematically
identical to one continuous division of the whole 360-degree zodiac into
108 equal 3d20' parts, cycling Aries->Taurus->...->Pisces->Aries...
nine times over -- the simpler formula used here.

This is the classical, publicly documented D9 scheme -- there is far less
variation across schools for D9 specifically than for some of the other
~20 divisional-chart formulas in the client's DivPlanetLongitude (see
roadmap doc's mechanical-vs-proprietary breakdown), but it has NOT been
cross-checked against the client's own workbook output. Treat as beta,
same discipline as engine/kp.py: standard theory, unvalidated against
this client's specific practice, always clearly caveated in the UI.

House placement within the Navamsa chart itself uses the standard
divisional-chart convention: whole-sign houses counted from the D9
ascendant's own Navamsa sign (see ephemeris.whole_sign_house) -- Placidus
cusps are not recomputed for divisional charts.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ephemeris import NatalChart, RASHI_LORD, RASHI_NAMES, normalize360, whole_sign_house

NAVAMSA_SPAN = 30.0 / 9.0  # 3 deg 20'

BETA_DISCLAIMER = (
    "BETA: standard-textbook D9 Navamsa only (each sign's 30 degrees split "
    "into 9 equal 3d20' parts, cycling continuously Aries through Pisces "
    "across the whole zodiac). Houses are whole-sign, counted from the D9 "
    "ascendant's own Navamsa sign. NOT yet cross-checked against your "
    "workbook's own DivPlanetLongitude varga formula -- one of ~20 "
    "divisional-chart schemes flagged in the audit as needing your "
    "sign-off. Treat as a reference approximation, not production output."
)


def navamsa_sign_index(sid_long: float) -> int:
    """0-11 index into RASHI_NAMES/RASHI_LORD for a longitude's Navamsa
    (D9) sign."""
    return int(normalize360(sid_long) // NAVAMSA_SPAN) % 12


@dataclass
class NavamsaPlanet:
    code: str
    name: str
    navamsa_sign: str
    navamsa_sign_lord: str
    navamsa_house: int


@dataclass
class NavamsaChart:
    ascendant_navamsa_sign: str
    ascendant_navamsa_sign_lord: str
    planets: list[NavamsaPlanet] = field(default_factory=list)
    beta_disclaimer: str = BETA_DISCLAIMER


def compute_navamsa(chart: NatalChart) -> NavamsaChart:
    asc_idx = navamsa_sign_index(chart.ascendant.longitude)
    asc_sign, asc_lord = RASHI_NAMES[asc_idx], RASHI_LORD[asc_idx]

    planets: list[NavamsaPlanet] = []
    for p in chart.planets:
        idx = navamsa_sign_index(p.longitude)
        sign, lord = RASHI_NAMES[idx], RASHI_LORD[idx]
        house = whole_sign_house(idx, asc_idx)
        planets.append(NavamsaPlanet(p.code, p.name, sign, lord, house))

    return NavamsaChart(
        ascendant_navamsa_sign=asc_sign,
        ascendant_navamsa_sign_lord=asc_lord,
        planets=planets,
    )
