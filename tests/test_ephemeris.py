"""Sanity checks for the mechanical-layer ephemeris engine.

Most of these just confirm the engine computes internally-consistent,
plausible sidereal positions and doesn't crash -- not a substitute for
validating against the client's actual production data. The
`test_confirmed_ayanamsa_convention_matches_real_excel_data` class below
IS that validation, for the ayanamsa/node convention specifically: it
locks in the switch (2026-09-24) to the same mode-45+diff/mean-node
convention ccsi.py already used, against the client's real Excel Kundli
worksheet values for the reference chart -- see
ayanamsa-and-nature-findings-2026-09-24.md (project doc) for the full
comparison this was derived from.

Run with:  python -m pytest tests/ -v   (from backend/)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.chart import chart_to_dict
from app.engine.ephemeris import (
    BirthMoment, compute_natal_chart, normalize360,
    sign_index_for_longitude, whole_sign_house,
)


def _reference_chart():
    # 1947-08-15 00:00 IST, New Delhi -- a commonly-used KP reference chart.
    m = BirthMoment(year=1947, month=8, day=15, hour=0, minute=0, second=0,
                     utc_offset_hours=5.5, latitude=28.6139, longitude=77.2090)
    return compute_natal_chart(m)


def test_ayanamsa_in_plausible_range():
    chart = _reference_chart()
    # Krishnamurti ayanamsa for 1947 should be roughly 23 degrees.
    assert 22.5 < chart.ayanamsa_deg < 23.5


def test_all_nine_grahas_present():
    chart = _reference_chart()
    codes = {p.code for p in chart.planets}
    assert codes == {"Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"}


def test_outer_planets_are_kept_separate_from_the_classical_nine():
    """Uranus/Neptune/Pluto (2026-09-24, yet even later still) live on
    `chart.outer_planets`, NOT `chart.planets` -- by design, so every
    classical-9-planet-only consumer of compute_natal_chart (teaser.py,
    kp.py significators, varga.py D9, ccsi.py/hit_calc.py CCSI scoring,
    dasha.py) stays completely unaffected. Only chart.py's
    `chart_to_dict()` merges them back in for the /api/chart response."""
    chart = _reference_chart()
    assert {p.code for p in chart.planets} == {
        "Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke",
    }
    assert {p.code for p in chart.outer_planets} == {"Ur", "Ne", "Pl"}


def test_rahu_ketu_are_exactly_opposite():
    chart = _reference_chart()
    rahu = next(p for p in chart.planets if p.code == "Ra")
    ketu = next(p for p in chart.planets if p.code == "Ke")
    diff = abs(normalize360(rahu.longitude - ketu.longitude) - 180.0)
    assert diff < 0.001


def test_rahu_and_ketu_are_both_marked_retrograde():
    """Regression test for a real bug the client caught by reading the
    Preview output: Ketu was always correctly hardcoded retrograde=True
    (lunar nodes are permanently retrograde by Vedic convention, not
    measured), but Rahu fell through to the general per-planet branch,
    whose old logic explicitly forced Rahu's retrograde flag to False
    regardless of Swiss Ephemeris' own reported speed. Fixed so both
    nodes are always retrograde, consistently, for every chart."""
    chart = _reference_chart()
    rahu = next(p for p in chart.planets if p.code == "Ra")
    ketu = next(p for p in chart.planets if p.code == "Ke")
    assert rahu.retrograde is True
    assert ketu.retrograde is True


def test_longitudes_are_normalized():
    chart = _reference_chart()
    for p in chart.planets:
        assert 0.0 <= p.longitude < 360.0
    for h in chart.houses:
        assert 0.0 <= h.longitude < 360.0


def test_house_cusps_increase_around_the_circle():
    chart = _reference_chart()
    # Cusps should be in ascending order allowing exactly one wrap past 360.
    longs = [h.longitude for h in chart.houses]
    wraps = sum(1 for i in range(1, 12) if longs[i] < longs[i - 1])
    assert wraps <= 1


def test_nakshatra_pada_in_range():
    chart = _reference_chart()
    for p in chart.planets:
        assert 1 <= p.pada <= 4


def test_whole_sign_house_ascendant_own_sign_is_house_one():
    # A planet in the same sign as the ascendant is always in the 1st
    # whole-sign house, regardless of which sign that actually is.
    for asc_idx in range(12):
        assert whole_sign_house(asc_idx, asc_idx) == 1


def test_whole_sign_house_counts_forward_and_wraps():
    # Ascendant in Aries (index 0): Taurus (1) -> house 2, ... Pisces (11) -> house 12.
    assert whole_sign_house(1, 0) == 2
    assert whole_sign_house(11, 0) == 12
    # Ascendant in Pisces (index 11): Aries (0) -> house 2 (wraps).
    assert whole_sign_house(0, 11) == 2


def test_sign_index_for_longitude_matches_sign_for_longitude():
    from app.engine.ephemeris import RASHI_NAMES, sign_for_longitude
    for lon in [0.0, 29.99, 30.0, 143.2, 359.9]:
        sign, _lord, _deg = sign_for_longitude(lon)
        assert RASHI_NAMES[sign_index_for_longitude(lon)] == sign


def test_rasi_house_of_ascendant_sign_planet_is_house_one():
    chart = _reference_chart()
    data = chart_to_dict(chart)
    asc_sign = data["ascendant"]["sign"]
    for p in data["planets"]:
        if p["sign"] == asc_sign:
            assert p["rasi_house"] == 1


def test_every_planet_has_valid_rasi_house():
    chart = _reference_chart()
    data = chart_to_dict(chart)
    for p in data["planets"]:
        assert 1 <= p["rasi_house"] <= 12


# --- Confirmed ayanamsa/node convention (2026-09-24, later still again) --
# The client's real Excel Kundli worksheet for the reference chart
# (1973-10-12, 14:55 IST, Amalsad: lat=20.815615264029468,
# lon=72.95947488134223). Degrees converted from the sheet's D°M'S" to
# decimal; nakshatra/pada and the R*/D flags are read straight off the
# sheet. This is the exact same comparison table from the project doc,
# now locked in as a permanent regression test.

_REAL_EXCEL_REFERENCE_CHART = BirthMoment(
    year=1973, month=10, day=12, hour=14, minute=55, second=0,
    utc_offset_hours=5.5, latitude=20.815615264029468, longitude=72.95947488134223,
)

# code -> (expected sign, expected degree_in_sign, expected nakshatra, expected pada)
_EXCEL_EXPECTED = {
    "Asc": ("Capricorn", 22.8464, "Shravana", 4),
    "Su":  ("Virgo", 25.4319, "Chitra", 1),
    "Mo":  ("Pisces", 28.8083, "Revati", 4),
    "Ma":  ("Aries", 12.2328, "Ashwini", 4),
    "Me":  ("Libra", 19.1431, "Swati", 4),
    "Ju":  ("Capricorn", 9.1206, "Uttara Ashadha", 4),
    "Ve":  ("Scorpio", 9.9769, "Anuradha", 2),
    "Sa":  ("Gemini", 11.2483, "Ardra", 2),
    "Ra":  ("Sagittarius", 8.7092, "Mula", 3),
    "Ke":  ("Gemini", 8.7092, "Ardra", 1),
    # Uranus/Neptune/Pluto (2026-09-24, yet even later still) -- same
    # Excel sheet, same reference chart.
    "Ur":  ("Virgo", 29.6694, "Chitra", 2),
    "Ne":  ("Scorpio", 12.0275, "Anuradha", 3),
    "Pl":  ("Virgo", 11.3725, "Hasta", 1),
}

# Excel's R* (retrograde) flag was present for exactly these three (the
# sheet showed no flag for Ur/Ne/Pl, matching this engine's own
# speed-based computation for them -- see the all-planets test below).
_EXCEL_RETROGRADE_CODES = {"Ma", "Ra", "Ke"}


def test_confirmed_ayanamsa_convention_matches_real_excel_data_ascendant():
    chart = compute_natal_chart(_REAL_EXCEL_REFERENCE_CHART)
    data = chart_to_dict(chart)
    asc = data["ascendant"]
    expected_sign, expected_deg, expected_nak, expected_pada = _EXCEL_EXPECTED["Asc"]
    assert asc["sign"] == expected_sign
    assert abs(asc["degree_in_sign"] - expected_deg) < 0.001
    assert asc["nakshatra"] == expected_nak
    assert asc["pada"] == expected_pada


def test_confirmed_ayanamsa_convention_matches_real_excel_data_all_planets():
    """Covers all 12 entries /api/chart's `chart_to_dict()` now returns:
    the 9 classical grahas plus Uranus/Neptune/Pluto (2026-09-24, yet even
    later still)."""
    chart = compute_natal_chart(_REAL_EXCEL_REFERENCE_CHART)
    data = chart_to_dict(chart)
    assert {p["code"] for p in data["planets"]} == {
        "Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke", "Ur", "Ne", "Pl",
    }
    for p in data["planets"]:
        expected_sign, expected_deg, expected_nak, expected_pada = _EXCEL_EXPECTED[p["code"]]
        assert p["sign"] == expected_sign, f"{p['code']}: sign"
        assert abs(p["degree_in_sign"] - expected_deg) < 0.001, f"{p['code']}: degree_in_sign"
        assert p["nakshatra"] == expected_nak, f"{p['code']}: nakshatra"
        assert p["pada"] == expected_pada, f"{p['code']}: pada"
        assert p["retrograde"] == (p["code"] in _EXCEL_RETROGRADE_CODES), f"{p['code']}: retrograde"
