"""
END-TO-END validation of `hit_calc.py`'s LT (Transit-to-Lagna) and TT
(Transit-to-Transit) rows against REAL `HIT_CALC` output from the client's
workbook (2026-09-24) -- the two rows `test_hit_calc_lagna_validated.py`
could not check yet, because the client's transit 9-planet table
(`$A$44:$B$52`) was empty when the L row was validated.

The client has since populated and shared that table, plus the real
`Bhava_Degrees_Transit` transit cusps (already independently used in
`test_hit_calc_reference_chart.py`'s natal-side validation). This test
locks in the resulting comparison against the same real
`HIT_CALC!G184:AE204` paste already used for the L row.

RESULT, first attempt: TT matched 44/44 (net + negative-only) immediately.
LT's negative-only row also matched 22/22, but LT's NET row mismatched on
exactly 3 of 22 cells -- the Mo/Ra/Ke planet-column self-exclusion cases.
This isolated a real bug in `compute_ccsi_row`'s self-exclusion logic:
excluding a same-named planet from the aspecting set is only correct when
the reference and comparison tables are the SAME chart (L: natal vs
natal; TT: transit vs transit) -- a planet's own position can't aspect
itself. For LT (natal reference vs TRANSIT comparison), the natal planet
and the transiting planet of the same name are two DIFFERENT positions;
the transiting planet legitimately aspects its own natal placement, and
excluding it was wrong. Fixed by adding an explicit `exclude_self`
parameter to `compute_ccsi_row` (default True, matching L/TT; LT must
pass `exclude_self=False`). With that fix, ALL FOUR rows below match
exactly -- 88 cells here, plus the 44 from the L-row test, is
**132/132 real `HIT_CALC` cells confirmed exactly** across L, LT, TT,
net and negative-only. `hit_calc.py` can now be considered fully
validated, not beta, for all three CCSI variants.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.hit_calc import compute_ccsi_row

# Real natal data -- same reference chart as the other hit_calc test files.
NATAL_HOUSE_CUSPS = {
    1: 292.8464321, 2: 330.4265729, 3: 4.959396399, 4: 33.8214756,
    5: 59.0696775, 6: 84.09119216, 7: 112.8464321, 8: 150.4265729,
    9: 184.9593964, 10: 213.8214756, 11: 239.0696775, 12: 264.0911922,
}
NATAL_ASCENDANT = 292.8464321
NATAL_PLANETS = {
    "Su": 175.4319186, "Mo": 358.8084601, "Ma": 12.2328005, "Me": 199.1429507,
    "Ju": 279.1205518, "Ve": 219.9768558, "Sa": 71.2482669, "Ra": 248.7090551,
    "Ke": 68.7090551,
}

# Real transit data, received 2026-09-24. Bhava_Degrees_Transit (already
# used, unchanged, in test_hit_calc_reference_chart.py's natal back-solve
# investigation) and the real transit 9-planet table (newly shared).
TRANSIT_HOUSE_CUSPS = {
    1: 271.9862688, 2: 313.0972525, 3: 351.4855163, 4: 21.43389554,
    5: 45.47101628, 6: 67.56251303, 7: 91.98626877, 8: 133.0972525,
    9: 171.4855163, 10: 201.4338955, 11: 225.4710163, 12: 247.562513,
}
TRANSIT_ASCENDANT = 271.9862688  # matches Bhava_Degrees_Transit house 1 exactly
TRANSIT_PLANETS = {
    "Su": 157.35, "Mo": 302.75, "Ma": 93.99, "Me": 177.24,
    "Ju": 114.80, "Ve": 193.38, "Sa": 348.65, "Ra": 304.61, "Ke": 124.61,
}

# Real `HIT_CALC!G184:AE204` values, 2026-09-24, LT ("CCSI-Transit to
# Lagna") and TT ("CCSI- Transit to to Transit") net rows.
REAL_LT_HOUSES = {1: 4, 2: 4, 3: 5, 4: -5, 5: 14, 6: -1, 7: 8, 8: 3,
                   9: 10, 10: -2, 11: 12, 12: -2}
REAL_LT_COLUMNS = {"Asc": 4, "Su": 0, "Mo": 8, "Ma": 3, "Me": 0, "Ju": -5,
                    "Ve": 7, "Sa": 6, "Ra": 10, "Ke": 13}

REAL_TT_HOUSES = {1: -2, 2: 3, 3: 0, 4: 0, 5: 4, 6: 13, 7: 2, 8: 1,
                   9: -6, 10: -3, 11: 7, 12: 10}
REAL_TT_COLUMNS = {"Asc": -2, "Su": 5, "Mo": -6, "Ma": 4, "Me": 11, "Ju": 4,
                    "Ve": 0, "Sa": 0, "Ra": -4, "Ke": -6}

# Real "Negative Hits Only" block, LT ("CCSI -Tr to Lag") and TT
# ("CCSK-Tr to Tr") rows.
REAL_LTNEG_HOUSES = {1: 3, 2: 3, 3: 7, 4: 12, 5: 0, 6: 2, 7: 1, 8: 1,
                      9: 4, 10: 10, 11: 1, 12: 2}
REAL_LTNEG_COLUMNS = {"Asc": 3, "Su": 6, "Mo": 3, "Ma": 3, "Me": 0, "Ju": 8,
                       "Ve": 1, "Sa": 3, "Ra": 2, "Ke": 3}

REAL_TTNEG_HOUSES = {1: 8, 2: 0, 3: 5, 4: 2, 5: 0, 6: 3, 7: 2, 8: 1,
                      9: 8, 10: 3, 11: 0, 12: 2}
REAL_TTNEG_COLUMNS = {"Asc": 8, "Su": 1, "Mo": 11, "Ma": 0, "Me": 0, "Ju": 4,
                       "Ve": 0, "Sa": 3, "Ra": 8, "Ke": 9}


def _assert_row_matches(row, real_houses, real_columns, label):
    for house_num, expected in real_houses.items():
        assert row.houses[house_num] == expected, (
            f"{label} house {house_num}: {row.houses[house_num]} != {expected}"
        )
    for key, expected in real_columns.items():
        assert row.columns[key] == expected, (
            f"{label} {key}: {row.columns[key]} != {expected}"
        )


def test_lt_net_row_matches_real_hit_calc_exactly():
    # LT: natal cusp/planet columns scored against TRANSITING aspecting
    # planets. exclude_self=False -- the transiting planet of the same
    # name as the reference DOES aspect its own natal placement; that is
    # a real transit hit, not a self-aspect (see module docstring).
    row = compute_ccsi_row(
        NATAL_HOUSE_CUSPS, NATAL_ASCENDANT, NATAL_PLANETS, TRANSIT_PLANETS,
        exclude_self=False,
    )
    _assert_row_matches(row, REAL_LT_HOUSES, REAL_LT_COLUMNS, "LT net")


def test_tt_net_row_matches_real_hit_calc_exactly():
    # TT: transit cusp/planet columns scored against transiting aspecting
    # planets -- same table on both sides, so exclude_self=True (the
    # default) is correct, same as the L row.
    row = compute_ccsi_row(
        TRANSIT_HOUSE_CUSPS, TRANSIT_ASCENDANT, TRANSIT_PLANETS, TRANSIT_PLANETS,
    )
    _assert_row_matches(row, REAL_TT_HOUSES, REAL_TT_COLUMNS, "TT net")


def test_lt_negative_only_row_matches_real_hit_calc_exactly():
    row = compute_ccsi_row(
        NATAL_HOUSE_CUSPS, NATAL_ASCENDANT, NATAL_PLANETS, TRANSIT_PLANETS,
        negative_only=True, exclude_self=False,
    )
    _assert_row_matches(row, REAL_LTNEG_HOUSES, REAL_LTNEG_COLUMNS, "LT neg-only")


def test_tt_negative_only_row_matches_real_hit_calc_exactly():
    row = compute_ccsi_row(
        TRANSIT_HOUSE_CUSPS, TRANSIT_ASCENDANT, TRANSIT_PLANETS, TRANSIT_PLANETS,
        negative_only=True,
    )
    _assert_row_matches(row, REAL_TTNEG_HOUSES, REAL_TTNEG_COLUMNS, "TT neg-only")


def test_lt_exclude_self_true_would_have_been_wrong():
    # Regression guard for the bug this test file caught: confirms
    # exclude_self=True (the L/TT-correct default) actually DOES diverge
    # from the real LT data for the Mo/Ra/Ke columns, so a future change
    # that silently reverts LT to exclude_self=True fails loudly here
    # instead of just losing quiet accuracy.
    wrong_row = compute_ccsi_row(
        NATAL_HOUSE_CUSPS, NATAL_ASCENDANT, NATAL_PLANETS, TRANSIT_PLANETS,
        exclude_self=True,
    )
    mismatches = {
        key for key, expected in REAL_LT_COLUMNS.items()
        if wrong_row.columns[key] != expected
    }
    assert mismatches == {"Mo", "Ra", "Ke"}
