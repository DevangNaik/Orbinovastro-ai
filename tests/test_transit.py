import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.ephemeris import BirthMoment, compute_natal_chart
from app.engine.transit import compute_transit, now_as_birth_moment


def _natal_chart():
    m = BirthMoment(year=1973, month=10, day=12, hour=14, minute=55, second=0,
                     utc_offset_hours=5.5, latitude=28.6139, longitude=77.2090)
    return compute_natal_chart(m)


def test_transit_returns_all_nine_planets():
    natal = _natal_chart()
    transit_moment = BirthMoment(year=2026, month=9, day=23, hour=12, minute=0,
                                  utc_offset_hours=0.0, latitude=28.6139, longitude=77.2090)
    planets, iso_ts = compute_transit(natal, transit_moment)
    codes = {p.code for p in planets}
    assert codes == {"Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"}
    assert iso_ts.startswith("2026-09-23")


def test_transit_planets_have_valid_natal_house():
    natal = _natal_chart()
    transit_moment = BirthMoment(year=2026, month=9, day=23, hour=12, minute=0,
                                  utc_offset_hours=0.0, latitude=28.6139, longitude=77.2090)
    planets, _ = compute_transit(natal, transit_moment)
    for p in planets:
        assert 1 <= p.natal_house <= 12


def test_transiting_planet_conjuncts_itself_at_birth_moment():
    # Using the natal moment as the "transit" moment too, every transiting
    # planet should end up within the conjunction orb of its own natal
    # position (it's the same position).
    natal = _natal_chart()
    same_moment = BirthMoment(year=1973, month=10, day=12, hour=14, minute=55,
                               utc_offset_hours=5.5, latitude=28.6139, longitude=77.2090)
    planets, _ = compute_transit(natal, same_moment)
    for p in planets:
        assert p.code in p.conjuncts_natal


def test_now_as_birth_moment_uses_utc_offset_zero():
    m = now_as_birth_moment(28.6139, 77.2090)
    assert m.utc_offset_hours == 0.0
