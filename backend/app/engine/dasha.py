"""
Vimshottari Dasha period engine -- faithful Python port of the client's
production VBA module `ModKP_Dasha_Final.bas` (workbook export,
`_production/workbook/bas/ModKP_Dasha_Final.bas`), cross-checked against
the sub-lord helper in `ModKP_BTR_STEP2.bas` and the planet-name/rashi-lord
helpers in `modKP_Core.bas`.

This is a *validated-by-source-read* port, not an inference: every formula
below is traceable to a specific VBA line. The MOON-LONGITUDE INPUT to
this engine (ayanamsa id, `Ayanamsa_Diff`, and the exact Swiss Ephemeris
call) is now VALIDATED against a real client data export -- see
`CONFIRMED_AYANAMSA_DIFF` below and `kp_lords.py`'s module docstring for
the full cross-check. The DASHA PERIOD ARITHMETIC ITSELF (MD/AD/PD/SU/PR
dates) is still NOT validated against real Excel dasha output for a known
chart -- that check is still outstanding (no real MD/AD/PD/SU/PR reference
values were available yet, only planetary longitudes). Treat dasha DATES
as BETA until that specific check happens; treat the Moon-longitude/
ayanamsa layer as validated.

--------------------------------------------------------------------------
Fidelity notes (deliberate, not bugs in this port):

1. Only 5 dasha levels are computed: MD, AD, PD, SU (Sookshma), PR (Prana).
   The VBA's own `ResolveExact` / `KP_VimFullChain` functions stop at PR --
   there is no 6th "Deha" level in the confirmed dasha engine itself.
   (A `dehLord` DOES appear elsewhere, in the connection-scoring module's
   candidate-combination loop -- that is a different, later-stage concern
   for the scoring engine, not this period builder. Do not conflate them.)

2. `Ayanamsa_Offset` is loaded but deliberately NEVER applied -- only
   `Ayanamsa_Diff` is added to the raw sidereal longitude. This matches
   the VBA exactly (see `RootMDFromAnchor`); it may be a latent bug in the
   original workbook, but faithful replication means keeping it as-is.

3. MD-level (and root-offset) durations use the exact constant
   365.2425 days/year. Sub-period (AD/PD/SU/PR) durations do NOT
   re-apply this constant -- they are pure day-proportion splits of the
   parent period's actual elapsed span. Mixing these up is the single
   easiest way to silently produce wrong dates; the tests guard against it.

4. Two silent-fallback behaviors are replicated on purpose:
     - An unrecognized planet code in `index_of_planet` falls back to
       index 0 (Ketu), matching `IndexOfPlanet` in the VBA.
     - `select_index_for_anchor` clamps an out-of-range anchor to the
       LAST period in the list, matching `SelectIndexForAnchor` in the
       VBA (including the edge case where an anchor BEFORE the first
       period also resolves to the last period -- this looks like a VBA
       quirk, but it is only ever reached with malformed input, since the
       root MD is always built to contain the anchor by construction).

5. `Ayanamsa_Diff` is now EMPIRICALLY CONFIRMED (2026-09-23): back-solved
   by comparing this module's raw ephemeris output against a real
   `PlTblCl` export from the client's workbook for the reference chart
   1973-10-12, 14:55 IST (+5:30) -- see `CONFIRMED_AYANAMSA_DIFF` below.
   The offset (`-0.0654213`) reconciled all 7 classical planets exactly
   (to 6 decimal places), and confirmed the client's Rahu/Ketu use the
   MEAN lunar node, not the true node used elsewhere in this codebase's
   free chart features (`ephemeris.py`) -- a real, now-documented
   discrepancy, not yet reconciled (see roadmap doc). `TZ` (birth-place
   UTC offset in hours) is not a fixed workbook constant -- it's supplied
   per birth record, same as it always has been; the reference chart
   above used TZ=5.5 (IST). Function defaults below still default
   `ayanamsa_diff` to 0.0 (the VBA's own fallback-on-missing-name
   behavior) so callers must explicitly opt in to the confirmed value
   until this is wired through the app's real birth-detail flow --
   passing `CONFIRMED_AYANAMSA_DIFF` explicitly is what's now
   recommended, not a guess.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import swisseph as swe

# ---------------------------------------------------------------------------
# Constants (all traceable to VBA source -- see module docstring)
# ---------------------------------------------------------------------------

# swe_set_sid_mode(45, 0, 0) in Mod_SWE.bas / LoadAyanamsaNum fallback in
# ModKP_Dasha_Final.bas -- "KP New" / Krishnamurti VP291 variant.
DEFAULT_AYANAMSA_ID = swe.SIDM_KRISHNAMURTI_VP291  # == 45

# swe_calc_ut flags in Mod_SWE.bas CalcPlanetDegree: exactly these three,
# no others (no FLG_SWIEPH added explicitly -- pyswisseph adds it by
# default when no ephemeris flag is given, matching the VBA's own default
# Swiss Ephemeris file mode).
SWE_FLAGS = swe.FLG_SIDEREAL | swe.FLG_TRUEPOS | swe.FLG_NONUT

# Excel serial-date epoch offset used by Mod_SWE.bas's CalcPlanetDegree:
#   timeJulian = theGMT + 2415018.5
# i.e. Excel day 0 (1899-12-30 00:00) == JD 2415018.5.
EXCEL_EPOCH_JD_OFFSET = 2415018.5

# Empirically confirmed (2026-09-23) against a real client PlTblCl export
# for the reference chart 1973-10-12, 14:55 IST (+5:30) -- see module
# docstring point 5 and kp_lords.py's docstring for the full cross-check.
# Reconciled all 7 classical planets to 6 decimal places once Rahu/Ketu
# were computed via the MEAN lunar node (see NODE_MODE_CONFIRMED below),
# not the true node. Not yet re-validated against a second chart.
CONFIRMED_AYANAMSA_DIFF = -0.0654213

# The client's production Rahu/Ketu use Swiss Ephemeris's MEAN node
# (swe.MEAN_NODE), confirmed by the same cross-check above -- NOT the
# true node (swe.TRUE_NODE) that ai_app/backend/app/engine/ephemeris.py
# uses for the free chart features. Whichever function ends up computing
# all 9 planets' longitudes to feed kp_lords.build_planet_lord_table for
# a real client report must use swe.MEAN_NODE for Rahu (Ketu = Rahu+180),
# or its NL/SL/SSL will be wrong even though the RL/NL/SL for the other
# 7 planets would look fine.
NODE_MODE_CONFIRMED = "mean"  # not "true" -- see above

VIMSHOTTARI_ORDER_DEFAULT = ["Ke", "Ve", "Su", "Mo", "Ma", "Ra", "Ju", "Sa", "Me"]

VIMSHOTTARI_YEARS: dict[str, float] = {
    "Ke": 7.0, "Ve": 20.0, "Su": 6.0, "Mo": 10.0, "Ma": 7.0,
    "Ra": 18.0, "Ju": 16.0, "Sa": 19.0, "Me": 17.0,
}

DAYS_PER_YEAR = 365.2425  # VBA literal -- MD-level and root-offset math only
NAKSHATRA_SPAN = 360.0 / 27.0  # 13 deg 20', exact
VIM_TOTAL_YEARS = 120.0

_TWO_LETTER_MAP = {
    "SU": "Su", "MO": "Mo", "MA": "Ma", "ME": "Me", "JU": "Ju",
    "VE": "Ve", "SA": "Sa", "RA": "Ra", "KE": "Ke",
}


def proper_planet_name(txt: str) -> str:
    """Port of `ProperPlanetName` (modKP_Core.bas). Normalizes any
    case/whitespace variant of a 2-letter planet code to the canonical
    "Xx" form. Unknown input falls through to the same odd
    first-upper/second-lower fallback as the VBA (never expected to
    trigger for the 9 known planets)."""
    s = txt.strip().upper()
    if not s:
        return ""
    head = s[:2]
    if head in _TWO_LETTER_MAP:
        return _TWO_LETTER_MAP[head]
    return s[0] + s[1:2].lower() if len(s) > 1 else s[0]


def vim_dasha_years(planet: str) -> float:
    """Port of `VimDashaYears`."""
    return VIMSHOTTARI_YEARS.get(proper_planet_name(planet), 0.0)


def index_of_planet(order: list[str], planet: str) -> int:
    """Port of `IndexOfPlanet`. Returns -1 if not found (caller then
    faithfully falls back to 0, matching the VBA call sites)."""
    p = proper_planet_name(planet)
    for i, candidate in enumerate(order):
        if proper_planet_name(candidate) == p:
            return i
    return -1


@dataclass
class DashaPeriod:
    """Port of the VBA `DashaPeriod` type. Dates are naive `datetime`
    values in the SAME clock as whatever `anchor` was passed in (local
    civil time, matching the VBA's own local-time bookkeeping -- see
    module docstring point 3 about GMT conversion happening only for the
    Moon-longitude lookup, never for period arithmetic)."""
    planet: str
    start: datetime
    end: datetime


def _add_days(dt: datetime, days: float) -> datetime:
    return dt + timedelta(days=days)


def _sub_days(dt: datetime, days: float) -> datetime:
    return dt - timedelta(days=days)


def select_index_for_anchor(periods: list[DashaPeriod], anchor: datetime) -> int:
    """Port of `SelectIndexForAnchor`. See module docstring point 4 for
    the deliberately-replicated clamp-to-last-period quirk."""
    if not periods:
        return -1
    n = len(periods)
    for i in range(n - 1):
        if periods[i].start <= anchor < periods[i + 1].start:
            return i
    return n - 1


def get_active_index(periods: list[DashaPeriod], anchor: datetime) -> int:
    return select_index_for_anchor(periods, anchor)


def get_active_period(periods: list[DashaPeriod], anchor: datetime) -> Optional[DashaPeriod]:
    idx = select_index_for_anchor(periods, anchor)
    if 0 <= idx < len(periods):
        return periods[idx]
    return None


def get_active_planet(periods: list[DashaPeriod], anchor: datetime) -> str:
    p = get_active_period(periods, anchor)
    return p.planet if p else ""


def calc_planet_degree(gmt_excel_serial: float, planet_id: int, ayanamsa_id: int) -> float:
    """Port of `CalcPlanetDegree` (Mod_SWE.bas). `gmt_excel_serial` is a
    GMT moment expressed as an Excel serial date/time (days since
    1899-12-30, fractional part = time of day) -- the same convention the
    VBA uses throughout. Returns raw sidereal longitude in degrees,
    BEFORE any Ayanamsa_Diff correction is applied (that happens in the
    caller, matching the VBA)."""
    swe.set_sid_mode(ayanamsa_id, 0, 0)
    jd_ut = gmt_excel_serial + EXCEL_EPOCH_JD_OFFSET
    result, _flags = swe.calc_ut(jd_ut, planet_id, SWE_FLAGS)
    return result[0]


def _excel_serial(dt: datetime) -> float:
    """Convert a naive Python datetime to an Excel serial date/time
    (days since 1899-12-30 00:00), matching how `anchor` is represented
    in the VBA (`anchor As Double`)."""
    excel_epoch = datetime(1899, 12, 30)
    delta = dt - excel_epoch
    return delta.days + delta.seconds / 86400.0 + delta.microseconds / 86_400_000_000.0


def root_md_from_anchor(
    anchor: datetime,
    *,
    tz_hours: float = 0.0,
    ayanamsa_id: int = DEFAULT_AYANAMSA_ID,
    ayanamsa_diff: float = 0.0,
    vim_order: Optional[list[str]] = None,
) -> tuple[str, datetime]:
    """Port of `RootMDFromAnchor`. `anchor` is LOCAL civil birth
    date/time; `tz_hours` is the UTC offset in hours (e.g. +5.5 for IST),
    matching the VBA's `TZ` named range. Returns (root_MD_planet,
    root_MD_start) where root_MD_start is in the SAME local clock as
    `anchor` (may be before `anchor` -- that's expected: it's the start
    of the nakshatra-derived MD, and the anchor normally falls partway
    through it).

    NOTE (see module docstring point 5): `ayanamsa_diff` defaults to 0.0,
    matching the VBA's own fallback, but the client's actual production
    value is not yet confirmed. Do not treat dates from the default as
    validated.
    """
    order = vim_order or VIMSHOTTARI_ORDER_DEFAULT

    anchor_serial = _excel_serial(anchor)
    gmt_serial = anchor_serial - (tz_hours / 24.0)

    moon_raw = calc_planet_degree(gmt_serial, swe.MOON, ayanamsa_id)
    moon_deg = moon_raw + ayanamsa_diff
    moon_deg = moon_deg % 360.0
    if moon_deg < 0:
        moon_deg += 360.0

    nak_index = int(moon_deg // NAKSHATRA_SPAN)
    idx_md = nak_index % 9
    root_planet = proper_planet_name(order[idx_md])

    frac_star = (moon_deg - nak_index * NAKSHATRA_SPAN) / NAKSHATRA_SPAN
    md_years = vim_dasha_years(root_planet)
    elapsed_years = frac_star * md_years
    elapsed_days = elapsed_years * DAYS_PER_YEAR

    root_start = _sub_days(anchor, elapsed_days)
    return root_planet, root_start


def build_md_list(
    root_lord: str,
    root_start: datetime,
    *,
    span_years: float = VIM_TOTAL_YEARS,
    vim_order: Optional[list[str]] = None,
) -> list[DashaPeriod]:
    """Port of `BuildMDList`. Builds the 9 Mahadasha periods (one full
    120-year Vimshottari cycle) starting from `root_lord`/`root_start`."""
    order = vim_order or VIMSHOTTARI_ORDER_DEFAULT
    i_root = index_of_planet(order, root_lord)
    if i_root < 0:
        i_root = 0  # faithful silent fallback -- see module docstring point 4

    periods: list[DashaPeriod] = []
    start = root_start
    for i in range(9):
        planet = proper_planet_name(order[(i_root + i) % 9])
        duration_days = vim_dasha_years(planet) * DAYS_PER_YEAR
        end = _add_days(start, duration_days)
        periods.append(DashaPeriod(planet, start, end))
        start = end
    return periods


def build_sub_periods(
    parent_lord: str,
    p_start: datetime,
    p_end: datetime,
    *,
    vim_order: Optional[list[str]] = None,
) -> list[DashaPeriod]:
    """Port of `BuildSubPeriods`. Subdivides [p_start, p_end) into 9
    proportional segments (by each planet's share of the 120-year cycle),
    starting with the parent's OWN lord first (self-first rule), cycling
    through the Vimshottari order. Uses the parent's ACTUAL elapsed span
    in days -- no re-application of the 365.2425 constant (see module
    docstring point 3)."""
    order = vim_order or VIMSHOTTARI_ORDER_DEFAULT
    parent = proper_planet_name(parent_lord)
    i_base = index_of_planet(order, parent)
    if i_base < 0:
        i_base = 0  # faithful silent fallback

    span_days = (p_end - p_start).total_seconds() / 86400.0

    periods: list[DashaPeriod] = []
    start = p_start
    for i in range(9):
        planet = proper_planet_name(order[(i_base + i) % 9])
        seg_days = span_days * (vim_dasha_years(planet) / VIM_TOTAL_YEARS)
        end = _add_days(start, seg_days)
        periods.append(DashaPeriod(planet, start, end))
        start = end
    return periods


@dataclass
class DashaChain:
    """MD -> AD -> PD -> SU -> PR at one anchor moment. Field names use
    the client's own abbreviations (SU = Sookshma, PR = Prana -- NOT Sun)."""
    md: str
    ad: str
    pd: str
    su: str
    pr: str
    md_period: Optional[DashaPeriod] = None
    ad_period: Optional[DashaPeriod] = None
    pd_period: Optional[DashaPeriod] = None
    su_period: Optional[DashaPeriod] = None
    pr_period: Optional[DashaPeriod] = None


def resolve_exact(
    anchor: datetime,
    *,
    tz_hours: float = 0.0,
    ayanamsa_id: int = DEFAULT_AYANAMSA_ID,
    ayanamsa_diff: float = 0.0,
    vim_order: Optional[list[str]] = None,
) -> DashaChain:
    """Port of `ResolveExact` / `KP_VimFullChain`. Full 5-level dasha
    chain (MD/AD/PD/SU/PR) active at `anchor` (local civil time)."""
    order = vim_order or VIMSHOTTARI_ORDER_DEFAULT

    root_lord, root_start = root_md_from_anchor(
        anchor, tz_hours=tz_hours, ayanamsa_id=ayanamsa_id,
        ayanamsa_diff=ayanamsa_diff, vim_order=order,
    )
    md_list = build_md_list(root_lord, root_start, vim_order=order)

    md_idx = get_active_index(md_list, anchor)
    if not (0 <= md_idx < len(md_list)):
        return DashaChain("", "", "", "", "")
    md_period = md_list[md_idx]

    ad_list = build_sub_periods(md_period.planet, md_period.start, md_period.end, vim_order=order)
    ad_idx = get_active_index(ad_list, anchor)
    if not (0 <= ad_idx < len(ad_list)):
        return DashaChain(md_period.planet, "", "", "", "", md_period=md_period)
    ad_period = ad_list[ad_idx]

    pd_list = build_sub_periods(ad_period.planet, ad_period.start, ad_period.end, vim_order=order)
    pd_idx = get_active_index(pd_list, anchor)
    if not (0 <= pd_idx < len(pd_list)):
        return DashaChain(md_period.planet, ad_period.planet, "", "", "",
                           md_period=md_period, ad_period=ad_period)
    pd_period = pd_list[pd_idx]

    su_list = build_sub_periods(pd_period.planet, pd_period.start, pd_period.end, vim_order=order)
    su_idx = get_active_index(su_list, anchor)
    if not (0 <= su_idx < len(su_list)):
        return DashaChain(md_period.planet, ad_period.planet, pd_period.planet, "", "",
                           md_period=md_period, ad_period=ad_period, pd_period=pd_period)
    su_period = su_list[su_idx]

    pr_list = build_sub_periods(su_period.planet, su_period.start, su_period.end, vim_order=order)
    pr_idx = get_active_index(pr_list, anchor)
    if not (0 <= pr_idx < len(pr_list)):
        return DashaChain(md_period.planet, ad_period.planet, pd_period.planet, su_period.planet, "",
                           md_period=md_period, ad_period=ad_period, pd_period=pd_period, su_period=su_period)
    pr_period = pr_list[pr_idx]

    return DashaChain(
        md_period.planet, ad_period.planet, pd_period.planet, su_period.planet, pr_period.planet,
        md_period=md_period, ad_period=ad_period, pd_period=pd_period,
        su_period=su_period, pr_period=pr_period,
    )
