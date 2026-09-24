"""
KP lordship-chain engine -- faithful Python port of `GetNL_SL_SSL_FromDeg`
(`ModKP_BTR_STEP2.bas`) plus `RashiLord` (`modKP_Core.bas`), extended into
a full per-planet lordship table equivalent to the client's `PlTblCl`
Excel table.

Why this module exists: the client's CCSI connection-scoring engine reads
an 8-row x 6-column grid (`GG21:GL28` on the workbook's grid sheet) whose
formulas were NOT present in the exported VBA -- they live as Excel cell
formulas. Reading the VBA that *consumes* that grid
(`ConnectionAnalysisSummary_UPDATED_v4.bas`, rows ROW_PLANET..ROW_NLOFSL)
shows the grid is just, for each of 6 picked dasha-level lords, a lookup
of that planet's own Rasi Lord / Nakshatra Lord / Sub Lord / Sub-Sub Lord
and second-order "Nakshatra-Lord-of-X" chains. Every one of those values
is a pure function of the planet's own natal sidereal longitude via
STANDARD KP methodology -- and that methodology IS present in the VBA
export (`GetNL_SL_SSL_FromDeg`). So this table can be built here with
confidence, with no need to wait on client-supplied source for this piece
specifically.

What this module does NOT solve: the client's proprietary "Event
Settings"/"EventList" table (house-to-life-category weights/tags consumed
by `Score_Additive`/`Flag_Additive` in `scoring.py`) is genuine client
data, not derivable from astronomy -- that piece is still blocked pending
the client (see `scoring.py` docstring and the project roadmap doc).

VALIDATED (2026-09-23) against a real `PlTblCl` export from the client's
workbook, for the reference chart 1973-10-12, 14:55 IST (+5:30):
- Rasi Lord, Nakshatra Lord, and Sub Lord all matched 10/10 rows
  (Ascendant + 9 planets) on first try.
- Sub-Sub Lord did NOT match using `GetNL_SL_SSL_FromDeg`'s own
  convention (only 1/10) -- see `get_nl_sl_ssl_from_deg`'s docstring for
  the fix (SSL cycles from the SUB LORD's index, not the nakshatra
  lord's). Corrected and re-validated 10/10.
- The second-order NLOFNL/NLOFSL/NLOFSSL self-referential lookups in
  `build_planet_lord_table` matched 10/10 exactly as designed.
- Empirically back-solved and confirmed the production ayanamsa
  constants by comparing this module's raw ephemeris output (mode 45,
  no diff) against the client's actual longitudes for the same chart:
  `Ayanamsa_Diff = -0.0654213` degrees (was previously an unconfirmed
  0.0 default), applied identically to all 7 classical planets. Rahu
  (and therefore Ketu) did NOT match using the TRUE lunar node -- it
  matched exactly (to 6 decimal places) using the MEAN lunar node
  instead, with the SAME `Ayanamsa_Diff`. This is a real, confirmed
  difference from `ai_app/backend/app/engine/ephemeris.py`, which uses
  the true node for the free/live chart features -- whichever module
  ends up computing the 9 planets' longitudes to feed this table's
  `longitudes` argument for real client reports MUST use the mean node
  for Rahu, not the true node, or every downstream NL/SL/SSL for Rahu/Ketu
  will be wrong. Not yet reconciled with the free features -- that's a
  separate, deliberate decision for later (see roadmap doc).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .dasha import (
    VIMSHOTTARI_ORDER_DEFAULT,
    VIMSHOTTARI_YEARS,
    VIM_TOTAL_YEARS,
    NAKSHATRA_SPAN,
    proper_planet_name,
    vim_dasha_years,
)

# Rasi (sign) lords, 1-indexed by sign number (1=Aries .. 12=Pisces),
# port of `RashiLord` (modKP_Core.bas).
RASHI_LORD_BY_SIGN_NUM: dict[int, str] = {
    1: "Ma", 2: "Ve", 3: "Me", 4: "Mo", 5: "Su", 6: "Me",
    7: "Ve", 8: "Ma", 9: "Ju", 10: "Sa", 11: "Sa", 12: "Ju",
}


def rashi_lord(sign_num_1_to_12: int) -> str:
    """Port of `RashiLord`. `sign_num_1_to_12`: 1=Aries ... 12=Pisces."""
    return RASHI_LORD_BY_SIGN_NUM.get(sign_num_1_to_12, "")


def sign_num_for_longitude(sid_long: float) -> int:
    """1-indexed sign number (1=Aries..12=Pisces) for a sidereal longitude."""
    d = sid_long % 360.0
    if d < 0:
        d += 360.0
    return int(d // 30) + 1


def get_nl_sl_ssl_from_deg(
    deg: float,
    *,
    vim_order: Optional[list[str]] = None,
) -> tuple[str, str, str]:
    """Given a sidereal longitude, returns (nakshatra_lord, sub_lord,
    sub_sub_lord) using the standard KP proportional-subdivision method.

    IMPORTANT CORRECTION (2026-09-23, validated against a real client
    `PlTblCl` export for a known chart -- see kp_lords.py's module
    docstring and the project roadmap doc): the SL cycle starts from the
    NAKSHATRA LORD's own index (self-first), but the SSL cycle starts
    from the SUB LORD's own index -- NOT from the nakshatra lord's index
    for both, as `GetNL_SL_SSL_FromDeg` (`ModKP_BTR_STEP2.bas`) does.

    That VBA function was ported first and assumed to be the general-
    purpose version, but real production data proved its SSL convention
    wrong for this table: testing against 10 real rows (Ascendant + 9
    planets) from the client's actual `PlTblCl` export, the NL-starting
    convention matched RL/NL/SL perfectly but SSL matched only 1/10 rows,
    while the SL-starting convention matched SSL 10/10. Conclusion:
    `GetNL_SL_SSL_FromDeg` is specific to the Birth Time Rectification
    pipeline that calls it (a different, apparently non-standard
    convention for that specific narrowing use case) and is NOT the
    right reference for the master lordship table this module builds.
    This function now implements the SL-starting convention exclusively,
    since it's the one confirmed against real output.
    """
    order = vim_order or VIMSHOTTARI_ORDER_DEFAULT

    d = deg % 360.0
    if d < 0:
        d += 360.0

    nak_idx = int(d // NAKSHATRA_SPAN)
    idx_nl = nak_idx % 9
    nl = proper_planet_name(order[idx_nl])

    frac_nk = (d - nak_idx * NAKSHATRA_SPAN) / NAKSHATRA_SPAN

    total = 0.0
    prev_total = 0.0
    d_frac = 0.0
    sl = ""
    idx_sl = idx_nl
    for i in range(9):
        idx = (idx_nl + i) % 9
        planet = proper_planet_name(order[idx])
        d_frac = vim_dasha_years(planet) / VIM_TOTAL_YEARS
        total += d_frac
        if frac_nk <= total or i == 8:
            sl = planet
            idx_sl = idx
            prev_total = total - d_frac
            break

    frac_in_sl = (frac_nk - prev_total) / d_frac if d_frac > 0 else 0.0

    total = 0.0
    ssl = ""
    for i in range(9):
        idx = (idx_sl + i) % 9  # self-first from the SUB LORD, confirmed empirically
        planet = proper_planet_name(order[idx])
        d_frac = vim_dasha_years(planet) / VIM_TOTAL_YEARS
        total += d_frac
        if frac_in_sl <= total or i == 8:
            ssl = planet
            break

    return nl, sl, ssl


@dataclass
class PlanetLordRow:
    """One row of the PlTblCl-equivalent table: a planet's own full
    lordship chain, matching the 8-row GG21:GL28 layout
    (ROW_PLANET..ROW_NLOFSL) confirmed in
    ConnectionAnalysisSummary_UPDATED_v4.bas."""
    planet: str
    rasi_lord: str      # RL
    nakshatra_lord: str  # NL
    nl_of_nl: str        # NLOFNL -- the NL of this planet's own NL
    sub_lord: str        # SL
    nl_of_ssl: str       # NLOFSSL -- the NL of this planet's own SSL
    sub_sub_lord: str    # SSL
    nl_of_sl: str         # NLOFSL -- the NL of this planet's own SL


def build_planet_lord_table(
    longitudes: dict[str, float],
    *,
    vim_order: Optional[list[str]] = None,
) -> dict[str, PlanetLordRow]:
    """Builds the full PlTblCl-equivalent table for a set of planets.

    `longitudes`: mapping of 2-letter planet code -> sidereal longitude
    in degrees (0-360), e.g. from `dasha.calc_planet_degree` run once per
    planet at the birth moment (with the SAME ayanamsa_id/ayanamsa_diff
    used everywhere else in this port -- mixing ayanamsa settings between
    the dasha engine and this table would silently desync them).

    The second-order columns (NLOFNL / NLOFSSL / NLOFSL) are resolved by
    a SELF-REFERENTIAL lookup within this same table: e.g. NLOFNL for
    planet X is "whatever NL was computed for planet NL(X)" -- not a
    fresh degree-based computation. This matches how the GG21:GL28 grid
    is described consuming the picked lord's chain in the VBA (the picked
    lord IS one of the 9 planets, so its own row already has NL/SL/SSL
    computed).
    """
    order = vim_order or VIMSHOTTARI_ORDER_DEFAULT

    base: dict[str, tuple[str, str, str, str]] = {}  # planet -> (RL, NL, SL, SSL)
    for planet, lon in longitudes.items():
        p = proper_planet_name(planet)
        rl = rashi_lord(sign_num_for_longitude(lon))
        nl, sl, ssl = get_nl_sl_ssl_from_deg(lon, vim_order=order)
        base[p] = (rl, nl, sl, ssl)

    def nl_of(planet_code: str) -> str:
        """NL of whichever planet `planet_code` resolves to. If that
        target planet isn't in the supplied longitude set (e.g. it's a
        node/planet not passed in), returns "" rather than guessing."""
        target = proper_planet_name(planet_code)
        row = base.get(target)
        return row[1] if row else ""

    table: dict[str, PlanetLordRow] = {}
    for planet, (rl, nl, sl, ssl) in base.items():
        table[planet] = PlanetLordRow(
            planet=planet,
            rasi_lord=rl,
            nakshatra_lord=nl,
            nl_of_nl=nl_of(nl),
            sub_lord=sl,
            nl_of_ssl=nl_of(ssl),
            sub_sub_lord=ssl,
            nl_of_sl=nl_of(sl),
        )
    return table
