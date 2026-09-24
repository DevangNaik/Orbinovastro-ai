"""
Regression test locking in a REAL validated reference chart.

On 2026-09-23 the client shared a real `PlTblCl` export (Ascendant + 9
planets, sidereal longitudes and their Rasi/Nakshatra/Sub/Sub-Sub Lords)
from the production workbook. This is the first real ground-truth data
this port has had access to, and it:

1. Confirmed `get_nl_sl_ssl_from_deg` and `rashi_lord` produce EXACTLY the
   right Rasi Lord / Nakshatra Lord / Sub Lord for all 10 rows.
2. Caught a real bug: the Sub-Sub Lord cycle must start from the SUB
   LORD's own index, not the nakshatra lord's -- see kp_lords.py's
   docstring for the full story. Fixed and re-validated 10/10.
3. Confirmed `build_planet_lord_table`'s self-referential NLOFNL/NLOFSL/
   NLOFSSL columns exactly.
4. Empirically back-solved `Ayanamsa_Diff = -0.0654213` and confirmed the
   client's Rahu/Ketu use the MEAN lunar node, not the true node --
   cross-checked against this module's own raw ephemeris output for the
   known reference birth moment (1973-10-12, 14:55 IST, +5:30).

This test file hardcodes that real data as a permanent regression guard:
if any future change to kp_lords.py or dasha.py's ayanamsa constants
breaks agreement with this real chart, this test will fail immediately.
Do NOT edit the expected values below to make a change pass -- if this
test starts failing, the change is wrong, not the test.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import swisseph as swe

from app.engine.dasha import (
    CONFIRMED_AYANAMSA_DIFF,
    DEFAULT_AYANAMSA_ID,
    SWE_FLAGS,
)
from app.engine.kp_lords import (
    build_planet_lord_table,
    get_nl_sl_ssl_from_deg,
    rashi_lord,
    sign_num_for_longitude,
)

# Real data from the client's PlTblCl export, 2026-09-23, for the
# reference chart 1973-10-12, 14:55 IST (+5:30). Longitude = Graha_Deg
# (already sidereal, ayanamsa mode 45 + Ayanamsa_Diff applied, mean node
# for Rahu/Ketu). RL/NL/SL/SSL = Ral/NL/Sbl/SSL columns as exported.
REFERENCE_ROWS = [
    # body, longitude,      RL,   NL,   SL,   SSL
    ("Asc", 292.8464321, "Sa", "Mo", "Su", "Ra"),
    ("Su",  175.4319186, "Me", "Ma", "Ra", "Ve"),
    ("Mo",  358.8084601, "Ju", "Me", "Sa", "Ve"),
    ("Ma",   12.2328005, "Ma", "Ke", "Me", "Mo"),
    ("Me",  199.1429507, "Ve", "Ra", "Mo", "Ve"),
    ("Ju",  279.1205518, "Sa", "Su", "Ve", "Ju"),
    ("Ve",  219.9768558, "Ma", "Sa", "Ve", "Me"),
    ("Sa",   71.2482669, "Me", "Ra", "Sa", "Ve"),
    ("Ra",  248.7090551, "Ju", "Ke", "Ju", "Ve"),
    ("Ke",   68.7090551, "Me", "Ra", "Ju", "Ju"),
]

# NLOFNL/NLOFSL/NLOFSSL from the same export (SGNLD/NL2/NLOFNL/SL/
# NLOFSL/SSL2/NLofSSL columns), keyed by body, for the second-order
# self-referential lookup check.
REFERENCE_SECOND_ORDER = {
    "Asc": {"nl_of_nl": "Me", "nl_of_sl": "Ma", "nl_of_ssl": "Ke"},
    "Su":  {"nl_of_nl": "Ke", "nl_of_sl": "Ke", "nl_of_ssl": "Sa"},
    "Mo":  {"nl_of_nl": "Ra", "nl_of_sl": "Ra", "nl_of_ssl": "Sa"},
    "Ma":  {"nl_of_nl": "Ra", "nl_of_sl": "Ra", "nl_of_ssl": "Me"},
    "Me":  {"nl_of_nl": "Ke", "nl_of_sl": "Me", "nl_of_ssl": "Sa"},
    "Ju":  {"nl_of_nl": "Ma", "nl_of_sl": "Sa", "nl_of_ssl": "Su"},
    "Ve":  {"nl_of_nl": "Ra", "nl_of_sl": "Sa", "nl_of_ssl": "Ra"},
    "Sa":  {"nl_of_nl": "Ke", "nl_of_sl": "Ra", "nl_of_ssl": "Sa"},
    "Ra":  {"nl_of_nl": "Ra", "nl_of_sl": "Su", "nl_of_ssl": "Sa"},
    "Ke":  {"nl_of_nl": "Ke", "nl_of_sl": "Su", "nl_of_ssl": "Su"},
}


def test_rl_nl_sl_ssl_match_real_client_export_exactly():
    for body, deg, expected_rl, expected_nl, expected_sl, expected_ssl in REFERENCE_ROWS:
        rl = rashi_lord(sign_num_for_longitude(deg))
        nl, sl, ssl = get_nl_sl_ssl_from_deg(deg)
        assert rl == expected_rl, f"{body}: RL {rl} != {expected_rl}"
        assert nl == expected_nl, f"{body}: NL {nl} != {expected_nl}"
        assert sl == expected_sl, f"{body}: SL {sl} != {expected_sl}"
        assert ssl == expected_ssl, f"{body}: SSL {ssl} != {expected_ssl}"


def test_second_order_columns_match_real_client_export():
    longitudes = {body: deg for body, deg, *_ in REFERENCE_ROWS if body != "Asc"}
    table = build_planet_lord_table(longitudes)
    for body, expected in REFERENCE_SECOND_ORDER.items():
        if body == "Asc":
            continue  # Ascendant isn't a planet in build_planet_lord_table's longitudes dict
        row = table[body]
        assert row.nl_of_nl == expected["nl_of_nl"], f"{body}: NLOFNL {row.nl_of_nl} != {expected['nl_of_nl']}"
        assert row.nl_of_sl == expected["nl_of_sl"], f"{body}: NLOFSL {row.nl_of_sl} != {expected['nl_of_sl']}"
        assert row.nl_of_ssl == expected["nl_of_ssl"], f"{body}: NLOFSSL {row.nl_of_ssl} != {expected['nl_of_ssl']}"


def test_confirmed_ayanamsa_diff_reconciles_seven_classical_planets():
    """Cross-checks this module's own raw ephemeris output (ayanamsa mode
    45, no diff) against the real client longitudes, confirming
    CONFIRMED_AYANAMSA_DIFF closes the gap to within ~1e-4 degrees for
    all 7 classical planets (small residual is float/rounding noise in
    the client's own exported value, not a real discrepancy)."""
    local_dt = datetime(1973, 10, 12, 14, 55, 0)
    ut_dt = local_dt - timedelta(hours=5.5)
    jd_ut = swe.julday(ut_dt.year, ut_dt.month, ut_dt.day,
                        ut_dt.hour + ut_dt.minute / 60 + ut_dt.second / 3600)
    swe.set_sid_mode(DEFAULT_AYANAMSA_ID, 0, 0)

    planet_ids = {
        "Su": swe.SUN, "Mo": swe.MOON, "Ma": swe.MARS, "Me": swe.MERCURY,
        "Ju": swe.JUPITER, "Ve": swe.VENUS, "Sa": swe.SATURN,
    }
    reference = {body: deg for body, deg, *_ in REFERENCE_ROWS}

    for code, pid in planet_ids.items():
        result, _ = swe.calc_ut(jd_ut, pid, SWE_FLAGS)
        raw = result[0] % 360
        corrected = (raw + CONFIRMED_AYANAMSA_DIFF) % 360
        expected = reference[code]
        diff = abs(corrected - expected)
        diff = min(diff, 360 - diff)
        assert diff < 1e-3, f"{code}: corrected={corrected} expected={expected} diff={diff}"


def test_rahu_matches_only_via_mean_node_not_true_node():
    """Confirms the client's production Rahu is the MEAN lunar node, not
    the true node -- a real, confirmed difference from ephemeris.py's
    free-chart features (see dasha.py's NODE_MODE_CONFIRMED constant)."""
    local_dt = datetime(1973, 10, 12, 14, 55, 0)
    ut_dt = local_dt - timedelta(hours=5.5)
    jd_ut = swe.julday(ut_dt.year, ut_dt.month, ut_dt.day,
                        ut_dt.hour + ut_dt.minute / 60 + ut_dt.second / 3600)
    swe.set_sid_mode(DEFAULT_AYANAMSA_ID, 0, 0)
    expected_ra = dict((b, d) for b, d, *_ in REFERENCE_ROWS)["Ra"]

    true_result, _ = swe.calc_ut(jd_ut, swe.TRUE_NODE, SWE_FLAGS)
    true_corrected = (true_result[0] % 360 + CONFIRMED_AYANAMSA_DIFF) % 360
    true_diff = abs(true_corrected - expected_ra)
    true_diff = min(true_diff, 360 - true_diff)

    mean_result, _ = swe.calc_ut(jd_ut, swe.MEAN_NODE, SWE_FLAGS)
    mean_corrected = (mean_result[0] % 360 + CONFIRMED_AYANAMSA_DIFF) % 360
    mean_diff = abs(mean_corrected - expected_ra)
    mean_diff = min(mean_diff, 360 - mean_diff)

    assert mean_diff < 1e-3, f"mean node should match closely, diff={mean_diff}"
    assert true_diff > 0.5, "true node should NOT match closely (confirms mean node is correct)"
