"""Sanity checks for the mechanical-layer ephemeris engine.

Not a substitute for validating against the client's actual production
workbook (that requires resolving the open ayanamsa/house-cusp questions
in the roadmap doc first) -- these just confirm the engine computes
internally-consistent, plausible sidereal positions and doesn't crash.

Run with:  python -m pytest tests/ -v   (from backend/)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.ephemeris import BirthMoment, compute_natal_chart, normalize360


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


def test_rahu_ketu_are_exactly_opposite():
    chart = _reference_chart()
    rahu = next(p for p in chart.planets if p.code == "Ra")
    ketu = next(p for p in chart.planets if p.code == "Ke")
    diff = abs(normalize360(rahu.longitude - ketu.longitude) - 180.0)
    assert diff < 0.001


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
