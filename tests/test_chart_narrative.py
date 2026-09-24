"""Tests for engine/chart_narrative.py -- the shared sign/nakshatra phrase
banks (moved out of teaser.py this round so /api/chart can reuse them),
the `meaning` sentence builder, and `natal_conjunctions()`'s same-sign
angular-separation grouping. Also confirms `/api/chart`'s new `meaning`/
`conjunctions` fields are wired correctly end to end via chart_to_dict().

Run with:  python -m pytest tests/ -v   (from backend/)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.chart import chart_to_dict
from app.engine.chart_narrative import (
    BENEFIC_PLANETS, MALEFIC_PLANETS, NAKSHATRA_THEMES, SIGN_TRAITS,
    angular_separation, natal_conjunctions, planet_nature, position_meaning,
)
from app.engine.ephemeris import BirthMoment, compute_natal_chart


def _reference_chart():
    # Same real reference chart used throughout this engagement's tests
    # (1973-10-12, 14:55 IST, Amalsad -- the client's own real birth data).
    m = BirthMoment(year=1973, month=10, day=12, hour=14, minute=55, second=0,
                     utc_offset_hours=5.5, latitude=20.815615264029468, longitude=72.95947488134223)
    return compute_natal_chart(m)


def test_sign_traits_and_nakshatra_themes_cover_every_name():
    from app.engine.ephemeris import RASHI_NAMES
    assert set(SIGN_TRAITS) == set(RASHI_NAMES)
    assert len(NAKSHATRA_THEMES) == 27


def test_position_meaning_matches_the_expected_format():
    text = position_meaning("Capricorn", "Shravana", 4)
    assert text == "Shravana(4): listening, learning, and passing on what you know; Capricorn adds disciplined and patient."


def test_position_meaning_degrades_gracefully_for_an_unknown_name():
    # Never raises -- a data hiccup should shorten the sentence, not 500.
    text = position_meaning("Capricorn", "NotARealNakshatra", 1)
    assert "NotARealNakshatra(1)" in text
    assert "Capricorn adds disciplined and patient." in text


def test_angular_separation_matches_teaser_pys_own_copy():
    assert angular_separation(10.0, 10.0) == 0.0
    assert angular_separation(10.0, 20.0) == 10.0
    assert angular_separation(350.0, 10.0) == 20.0  # wraps past 360
    assert angular_separation(0.0, 180.0) == 180.0  # opposite points


def test_natal_conjunctions_groups_only_same_sign_planets():
    chart = _reference_chart()
    conj = natal_conjunctions(chart.planets)
    assert set(conj) == {p.code for p in chart.planets}
    by_code = {p.code: p for p in chart.planets}
    for code, hits in conj.items():
        p = by_code[code]
        for hit in hits:
            q = by_code[hit["code"]]
            assert q.sign == p.sign  # only same-sign planets are ever listed
            assert hit["orb_degrees"] >= 0.0


def test_natal_conjunctions_orb_is_symmetric_and_sorted_closest_first():
    chart = _reference_chart()
    conj = natal_conjunctions(chart.planets)
    for code, hits in conj.items():
        # sorted closest-first
        orbs = [h["orb_degrees"] for h in hits]
        assert orbs == sorted(orbs)
        # symmetric: if A lists B with orb X, B lists A with the same orb X
        for hit in hits:
            other_hits = {h["code"]: h["orb_degrees"] for h in conj[hit["code"]]}
            assert other_hits[code] == hit["orb_degrees"]


def test_chart_to_dict_wires_meaning_and_conjunctions_for_every_planet():
    chart = _reference_chart()
    data = chart_to_dict(chart)
    for p in data["planets"]:
        assert p["meaning"]  # never empty
        assert p["sign"] in p["meaning"]  # by construction, format check
        assert isinstance(p["conjunctions"], list)
        for hit in p["conjunctions"]:
            assert set(hit) == {"code", "orb_degrees"}


def test_planet_nature_matches_hit_calc_pys_own_classification():
    # Same grouping hit_calc.py's MALEFIC_PLANETS/BENEFIC_PLANETS already
    # uses internally for CCSI weighting -- duplicated, not imported (see
    # chart_narrative.py's own docstring for why), but must stay in sync.
    assert MALEFIC_PLANETS == {"Sa", "Ma", "Ra", "Ke"}
    assert BENEFIC_PLANETS == {"Su", "Me", "Mo", "Ju", "Ve"}
    for code in MALEFIC_PLANETS:
        assert planet_nature(code) == "Malefic"
    for code in BENEFIC_PLANETS:
        assert planet_nature(code) == "Benefic"
    assert planet_nature("Asc") == ""


def test_chart_to_dict_wires_nature_for_every_planet():
    chart = _reference_chart()
    data = chart_to_dict(chart)
    for p in data["planets"]:
        assert p["nature"] in ("Malefic", "Benefic")
