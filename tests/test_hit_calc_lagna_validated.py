"""
END-TO-END validation of `hit_calc.py` against REAL `HIT_CALC` output from
the client's workbook (2026-09-24), for the same reference chart already
locked in by `test_kp_lords_reference_chart.py` and
`test_hit_calc_reference_chart.py` (1973-10-12, 14:55 IST, +5:30).

The client sent the full `HIT_CALC!G184:AE204` values block. Their own
transit 9-planet table (`$A$44:$B$52`) is currently EMPTY in their sheet
(confirmed by the client), so the LT (Transit-to-Lagna) and TT
(Transit-to-Transit) rows can't be validated yet -- but the "L" (natal
Lagna) row and its "Negative Hits Only" counterpart use ONLY natal cusps
and natal planets, both already independently validated (see the two
reference-chart test files above). So this test computes those two rows
with `hit_calc.py`, using nothing but that already-validated natal data,
and checks every single cell against the client's real numbers.

RESULT: 44/44 cells match EXACTLY (12 houses + Asc + 9 planets, x2 rows:
net and negative-only). This is a complete, real-number confirmation of:
- the angular-separation formula,
- the `HITAspectRanges` classification and both weight lookups,
- the row-186 planet self-exclusion logic (every planet's own column
  excludes itself correctly),
- and the "Negative Hits Only" `IF(wFull<0, -wFull, 0)` transform.

`hit_calc.py` can now be considered VALIDATED (not beta) for the L (natal
Lagna) row and its negative-only counterpart. The LT/TT (transit) rows
remain unvalidated until the client's transit planet table is populated
and shared -- do not remove that caveat from `hit_calc.py`'s docstring
just because this test passes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.hit_calc import NINE_PLANETS, compute_ccsi_row

# Real natal data -- same reference chart as test_kp_lords_reference_chart.py
# and test_hit_calc_reference_chart.py.
HOUSE_CUSPS = {
    1: 292.8464321, 2: 330.4265729, 3: 4.959396399, 4: 33.8214756,
    5: 59.0696775, 6: 84.09119216, 7: 112.8464321, 8: 150.4265729,
    9: 184.9593964, 10: 213.8214756, 11: 239.0696775, 12: 264.0911922,
}
ASCENDANT = 292.8464321
NATAL_PLANETS = {
    "Su": 175.4319186, "Mo": 358.8084601, "Ma": 12.2328005, "Me": 199.1429507,
    "Ju": 279.1205518, "Ve": 219.9768558, "Sa": 71.2482669, "Ra": 248.7090551,
    "Ke": 68.7090551,
}

# Real `HIT_CALC!G184:AE204` values, 2026-09-24, "CCSI- Lagna Chart" row
# (the "net" natal-vs-natal row -- L in this port's naming).
REAL_NET_LAGNA_HOUSES = {1: -1, 2: 1, 3: 8, 4: 0, 5: 3, 6: -1, 7: 1, 8: 0,
                          9: 5, 10: 0, 11: 5, 12: -3}
REAL_NET_LAGNA_COLUMNS = {"Asc": -1, "Su": -4, "Mo": -3, "Ma": 9, "Me": 0,
                           "Ju": 0, "Ve": 3, "Sa": 3, "Ra": -4, "Ke": 0}

# Real `HIT_CALC` "Negative Hits Only" block, "CCSI Lagna" row (the
# natal-vs-natal negative-only row).
REAL_NEG_ONLY_LAGNA_HOUSES = {1: 4, 2: 0, 3: 2, 4: 3, 5: 2, 6: 4, 7: 4, 8: 0,
                               9: 11, 10: 0, 11: 0, 12: 5}
REAL_NEG_ONLY_LAGNA_COLUMNS = {"Asc": 4, "Su": 4, "Mo": 3, "Ma": 5, "Me": 6,
                                "Ju": 4, "Ve": 1, "Sa": 6, "Ra": 12, "Ke": 6}


def test_net_lagna_row_matches_real_hit_calc_exactly():
    row = compute_ccsi_row(HOUSE_CUSPS, ASCENDANT, NATAL_PLANETS, NATAL_PLANETS)

    for house_num, expected in REAL_NET_LAGNA_HOUSES.items():
        assert row.houses[house_num] == expected, (
            f"house {house_num}: {row.houses[house_num]} != {expected}"
        )
    for key, expected in REAL_NET_LAGNA_COLUMNS.items():
        assert row.columns[key] == expected, (
            f"{key}: {row.columns[key]} != {expected}"
        )


def test_negative_only_lagna_row_matches_real_hit_calc_exactly():
    row = compute_ccsi_row(
        HOUSE_CUSPS, ASCENDANT, NATAL_PLANETS, NATAL_PLANETS, negative_only=True
    )

    for house_num, expected in REAL_NEG_ONLY_LAGNA_HOUSES.items():
        assert row.houses[house_num] == expected, (
            f"house {house_num}: {row.houses[house_num]} != {expected}"
        )
    for key, expected in REAL_NEG_ONLY_LAGNA_COLUMNS.items():
        assert row.columns[key] == expected, (
            f"{key}: {row.columns[key]} != {expected}"
        )


def test_all_nine_planet_columns_present_in_both_real_rows():
    # Sanity check on the fixture data itself, not the engine.
    assert set(REAL_NET_LAGNA_COLUMNS) == {"Asc", *NINE_PLANETS}
    assert set(REAL_NEG_ONLY_LAGNA_COLUMNS) == {"Asc", *NINE_PLANETS}
