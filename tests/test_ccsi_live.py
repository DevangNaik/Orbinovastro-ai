"""
Validates `ccsi.py` -- the LIVE computation wiring that pulls house cusps
and planet longitudes straight from Swiss Ephemeris (rather than the
hardcoded real-chart dictionaries `test_hit_calc_lagna_validated.py` and
`test_hit_calc_lt_tt_validated.py` use) and feeds them into the already
fully-validated `hit_calc.py` engine.

Two things are checked here, both against the SAME real reference chart
already locked in elsewhere in this suite (1973-10-12, 14:55 IST, +5:30,
back-solved birth coordinates 20.815615 N, 72.959475 E):

1. `compute_ccsi_positions` reproduces the real natal `Bhava_Deg` cusps
   and real `PlTblCl` planet longitudes to float precision, using the
   CCSI-confirmed ayanamsa (mode 45 + CONFIRMED_AYANAMSA_DIFF) and mean
   lunar node -- i.e. this module's live computation is wired to the
   SAME validated convention `hit_calc.py`'s own tests use, not to
   `ephemeris.py`'s different (mode 5, true node) convention.
2. `compute_ccsi_report`'s L (natal Lagna) net and negative-only rows,
   computed end-to-end from nothing but a `BirthMoment`, match the real
   `HIT_CALC` output exactly -- the same 22+22 real cells
   `test_hit_calc_lagna_validated.py` checks against hardcoded
   dictionaries, but here computed through the full live pipeline
   instead.

NOT validated here, and NOT claimed as validated: the LT/TT rows' TRANSIT
side specifically, since the real `HIT_CALC` LT/TT data was checked
against a hardcoded real transit planet table (`test_hit_calc_lt_tt_
validated.py`), not against a live computation for a confirmed transit
moment/location -- the client's own transit snapshot's exact date/time/
location remains unconfirmed (see the project roadmap doc's back-solving
discrepancy). The `exclude_self`/self-exclusion LOGIC for LT/TT is
already validated at the `hit_calc.py` level regardless of this gap.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.ccsi import compute_ccsi_positions, compute_ccsi_report
from app.engine.ephemeris import BirthMoment

# Same reference chart as test_kp_lords_reference_chart.py /
# test_hit_calc_reference_chart.py / test_hit_calc_lagna_validated.py.
NATAL_MOMENT = BirthMoment(
    year=1973, month=10, day=12, hour=14, minute=55, second=0,
    utc_offset_hours=5.5,
    latitude=20.815615264029468, longitude=72.95947488134223,
)

REAL_BHAVA_DEG = {
    1: 292.8464321, 2: 330.4265729, 3: 4.959396399, 4: 33.8214756,
    5: 59.0696775, 6: 84.09119216, 7: 112.8464321, 8: 150.4265729,
    9: 184.9593964, 10: 213.8214756, 11: 239.0696775, 12: 264.0911922,
}
REAL_PLANET_LONGITUDES = {
    "Su": 175.4319186, "Mo": 358.8084601, "Ma": 12.2328005, "Me": 199.1429507,
    "Ju": 279.1205518, "Ve": 219.9768558, "Sa": 71.2482669, "Ra": 248.7090551,
    "Ke": 68.7090551,
}

REAL_NET_LAGNA_HOUSES = {1: -1, 2: 1, 3: 8, 4: 0, 5: 3, 6: -1, 7: 1, 8: 0,
                          9: 5, 10: 0, 11: 5, 12: -3}
REAL_NET_LAGNA_COLUMNS = {"Asc": -1, "Su": -4, "Mo": -3, "Ma": 9, "Me": 0,
                           "Ju": 0, "Ve": 3, "Sa": 3, "Ra": -4, "Ke": 0}
REAL_NEG_ONLY_LAGNA_HOUSES = {1: 4, 2: 0, 3: 2, 4: 3, 5: 2, 6: 4, 7: 4, 8: 0,
                               9: 11, 10: 0, 11: 0, 12: 5}
REAL_NEG_ONLY_LAGNA_COLUMNS = {"Asc": 4, "Su": 4, "Mo": 3, "Ma": 5, "Me": 6,
                                "Ju": 4, "Ve": 1, "Sa": 6, "Ra": 12, "Ke": 6}


def test_live_positions_reproduce_real_natal_bhava_deg():
    positions = compute_ccsi_positions(NATAL_MOMENT)
    for house_num, expected in REAL_BHAVA_DEG.items():
        got = positions.house_cusps[house_num]
        diff = min(abs(got - expected), 360.0 - abs(got - expected))
        assert diff < 1e-4, f"house {house_num}: got {got}, real {expected}"
    assert positions.ascendant_deg == positions.house_cusps[1]


def test_live_positions_reproduce_real_planet_longitudes():
    positions = compute_ccsi_positions(NATAL_MOMENT)
    for planet, expected in REAL_PLANET_LONGITUDES.items():
        got = positions.planet_longitudes[planet]
        diff = min(abs(got - expected), 360.0 - abs(got - expected))
        assert diff < 1e-3, f"{planet}: got {got}, real {expected}"


def test_full_report_l_rows_match_real_hit_calc_end_to_end():
    # Transit moment is irrelevant to the L rows; pass the natal moment
    # again so compute_ccsi_report has something valid to compute LT/TT
    # from (not checked by this test).
    report = compute_ccsi_report(NATAL_MOMENT, NATAL_MOMENT)

    for house_num, expected in REAL_NET_LAGNA_HOUSES.items():
        assert report.l_net.houses[house_num] == expected
    for key, expected in REAL_NET_LAGNA_COLUMNS.items():
        assert report.l_net.columns[key] == expected

    for house_num, expected in REAL_NEG_ONLY_LAGNA_HOUSES.items():
        assert report.l_negative.houses[house_num] == expected
    for key, expected in REAL_NEG_ONLY_LAGNA_COLUMNS.items():
        assert report.l_negative.columns[key] == expected
