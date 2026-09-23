"""Tests for the BETA D9 Navamsa engine (engine/varga.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.ephemeris import BirthMoment, RASHI_NAMES, compute_natal_chart
from app.engine.varga import compute_navamsa, navamsa_sign_index


def _reference_chart():
    m = BirthMoment(year=1947, month=8, day=15, hour=0, minute=0, second=0,
                     utc_offset_hours=5.5, latitude=28.6139, longitude=77.2090)
    return compute_natal_chart(m)


def test_navamsa_sign_index_first_part_of_aries_is_aries():
    assert navamsa_sign_index(0.0) == 0  # Aries 0d00' -> Navamsa Aries


def test_navamsa_sign_index_movable_sign_starts_from_itself():
    # Aries (movable): its own 9 navamsa parts start at Aries and end at
    # Sagittarius (index 8) just before 30 degrees.
    assert navamsa_sign_index(0.5) == 0
    assert navamsa_sign_index(29.9) == 8


def test_navamsa_sign_index_fixed_sign_starts_from_ninth_sign():
    # Taurus (fixed, index 1): navamsa parts start at Capricorn (index 9).
    assert navamsa_sign_index(30.5) == 9


def test_navamsa_sign_index_dual_sign_starts_from_fifth_sign():
    # Gemini (dual, index 2): navamsa parts start at Libra (index 6).
    assert navamsa_sign_index(60.5) == 6


def test_navamsa_sign_index_cycles_continuously_across_zodiac():
    # 108 equal parts of 3d20' across 360 degrees -- index at 359.9 should
    # be the last part, one before wrapping back to Aries at 360/0.
    assert navamsa_sign_index(359.9) == 11


def test_compute_navamsa_all_nine_planets_present():
    chart = _reference_chart()
    nav = compute_navamsa(chart)
    codes = {p.code for p in nav.planets}
    assert codes == {"Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"}


def test_compute_navamsa_signs_are_valid_rashi_names():
    chart = _reference_chart()
    nav = compute_navamsa(chart)
    assert nav.ascendant_navamsa_sign in RASHI_NAMES
    for p in nav.planets:
        assert p.navamsa_sign in RASHI_NAMES


def test_compute_navamsa_houses_in_range_one_to_twelve():
    chart = _reference_chart()
    nav = compute_navamsa(chart)
    for p in nav.planets:
        assert 1 <= p.navamsa_house <= 12


def test_compute_navamsa_planet_in_ascendant_navamsa_sign_is_house_one():
    chart = _reference_chart()
    nav = compute_navamsa(chart)
    for p in nav.planets:
        if p.navamsa_sign == nav.ascendant_navamsa_sign:
            assert p.navamsa_house == 1


def test_compute_navamsa_has_beta_disclaimer():
    chart = _reference_chart()
    nav = compute_navamsa(chart)
    assert "beta" in nav.beta_disclaimer.lower()
