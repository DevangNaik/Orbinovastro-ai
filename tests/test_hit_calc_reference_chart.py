"""
Validates `hit_calc.py`'s cusp-data assumption against a REAL `Bhava_Deg`
export from the client's workbook (2026-09-23), for the same reference
chart already locked in by `test_kp_lords_reference_chart.py`
(1973-10-12, 14:55 IST, +5:30).

METHOD: the client's `Bhava_Deg` export doesn't come with a birth
latitude/longitude attached, so this test first BACK-SOLVES it: house 10
(the Midheaven) depends only on time + longitude, not latitude, so a 1-D
search over longitude (holding the already-known birth date/time fixed)
finds the longitude that reproduces the real MC; a second 1-D search over
latitude then finds the latitude that reproduces the real Ascendant. Both
searches use the SAME sidereal convention already confirmed for
`kp_lords.py`/`dasha.py`: ayanamsa mode 45 (Krishnamurti VP291) plus
`CONFIRMED_AYANAMSA_DIFF`.

RESULT: lat=20.815615 N, lon=72.959475 E reproduce ALL 12 real cusps to
within ~4e-7 degrees (float noise) -- not just the two used to solve for
them. This is strong, independent confirmation that the workbook's
`Bhava_Deg` natal house cusps are plain sidereal Placidus cusps computed
with the exact same ayanamsa convention already validated for planets,
for a birth place at these coordinates (consistent with Amalsad,
Gujarat, India). `hit_calc.py` can therefore be wired to
`ephemeris.compute_houses`-equivalent natal cusps (using dasha.py's
ayanamsa constants, NOT ephemeris.py's own default mode) with confidence.

STILL OPEN (deliberately not asserted here): the client's own
`Bhava_Degrees_Transit` (transiting cusps "now") do NOT reproduce this
cleanly under the same method -- a joint (lat, lon, time) least-squares
fit leaves residuals of a few tenths of a degree across all 12 cusps,
noticeably worse than the ~1e-7 degree noise floor found for the natal
table. Possible explanations, not yet distinguished: the transit cusps
may be computed for a different (non-birth) location, or the
`CONFIRMED_AYANAMSA_DIFF` constant -- back-solved at the 1973 birth
epoch -- may not be perfectly time-invariant across the ~53-year gap to
"now". Flagged in the project roadmap doc as a follow-up question for
the client (the exact date/time/location the transit snapshot was taken
for) rather than guessed at here.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import swisseph as swe

from app.engine.dasha import CONFIRMED_AYANAMSA_DIFF, DEFAULT_AYANAMSA_ID, SWE_FLAGS
from datetime import datetime, timedelta

# Real natal Bhava_Deg export, 2026-09-23, for the reference chart
# 1973-10-12, 14:55 IST (+5:30). House 1 (Asc) matches the PlTblCl
# export's Asc longitude (292.8464321) exactly, confirming this is the
# SAME reference chart already locked in by test_kp_lords_reference_chart.py.
REFERENCE_BHAVA_DEG = [
    292.8464321, 330.4265729, 4.959396399, 33.8214756, 59.0696775,
    84.09119216, 112.8464321, 150.4265729, 184.9593964, 213.8214756,
    239.0696775, 264.0911922,
]

# Back-solved birth coordinates (see module docstring for method).
BACK_SOLVED_BIRTH_LAT = 20.815615264029468
BACK_SOLVED_BIRTH_LON = 72.95947488134223


def _jd_ut_for_reference_birth() -> float:
    local_dt = datetime(1973, 10, 12, 14, 55, 0)
    ut_dt = local_dt - timedelta(hours=5.5)
    return swe.julday(
        ut_dt.year, ut_dt.month, ut_dt.day,
        ut_dt.hour + ut_dt.minute / 60 + ut_dt.second / 3600,
    )


def _sidereal_cusps(jd_ut: float, lat: float, lon: float) -> list[float]:
    swe.set_sid_mode(DEFAULT_AYANAMSA_ID, 0, 0)
    cusps, _ascmc = swe.houses_ex(jd_ut, lat, lon, b"P", flags=swe.FLG_SIDEREAL)
    return [(c + CONFIRMED_AYANAMSA_DIFF) % 360 for c in cusps]


def test_back_solved_birth_coordinates_reproduce_all_12_natal_cusps():
    jd_ut = _jd_ut_for_reference_birth()
    computed = _sidereal_cusps(jd_ut, BACK_SOLVED_BIRTH_LAT, BACK_SOLVED_BIRTH_LON)

    for house_num, (computed_deg, real_deg) in enumerate(
        zip(computed, REFERENCE_BHAVA_DEG), start=1
    ):
        diff = abs((computed_deg - real_deg + 180) % 360 - 180)
        assert diff < 1e-4, (
            f"house {house_num}: computed={computed_deg} real={real_deg} diff={diff}"
        )


def test_back_solved_coordinates_are_plausible_for_a_gujarat_birthplace():
    # Sanity check only -- confirms the solve landed somewhere real
    # (coastal Gujarat, India), not a nonsense/degenerate solution.
    assert 18.0 < BACK_SOLVED_BIRTH_LAT < 24.0
    assert 68.0 < BACK_SOLVED_BIRTH_LON < 76.0
