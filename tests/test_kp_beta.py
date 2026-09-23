import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.ephemeris import BirthMoment, compute_natal_chart
from app.engine.kp import compute_kp_beta, sub_lord_for_longitude


def _reference_chart():
    m = BirthMoment(year=1947, month=8, day=15, hour=0, minute=0, second=0,
                     utc_offset_hours=5.5, latitude=28.6139, longitude=77.2090)
    return compute_natal_chart(m)


def test_sub_lord_returns_valid_planet_code():
    valid = {"Ke", "Ve", "Su", "Mo", "Ma", "Ra", "Ju", "Sa", "Me"}
    for deg in range(0, 360, 7):
        info = sub_lord_for_longitude(float(deg))
        assert info.sub_lord in valid
        assert info.nakshatra_lord in valid


def test_sub_lord_starts_at_nakshatra_lord():
    # At the very start of a nakshatra, the sub lord should equal the
    # nakshatra (star) lord itself.
    from app.engine.ephemeris import NAKSHATRA_SPAN
    for nak_index in range(27):
        info = sub_lord_for_longitude(nak_index * NAKSHATRA_SPAN + 0.0001)
        assert info.sub_lord == info.nakshatra_lord


def test_every_house_has_an_owner_and_csl():
    chart = _reference_chart()
    kp = compute_kp_beta(chart)
    assert len(kp["house_significators"]) == 12
    for h in kp["house_significators"]:
        assert h["owner"]
        assert h["cuspal_sub_lord"]


def test_every_planet_occupies_exactly_one_house_1_to_12():
    chart = _reference_chart()
    kp = compute_kp_beta(chart)
    for code, info in kp["planet_sub_lords"].items():
        assert 1 <= info["house"] <= 12


def test_occupants_are_mutually_exclusive_across_houses():
    chart = _reference_chart()
    kp = compute_kp_beta(chart)
    seen = set()
    for h in kp["house_significators"]:
        for p in h["occupants"]:
            assert p not in seen, f"{p} appears as occupant in two houses"
            seen.add(p)
    assert seen == {"Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"}
