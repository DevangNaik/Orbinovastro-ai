"""Tests for the client-facing teaser/preview (engine/teaser.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.ephemeris import BirthMoment, RASHI_NAMES, compute_natal_chart
from app.engine.teaser import ASCENDANT_BLURBS, MOON_BLURBS, build_teaser


def _reference_chart():
    m = BirthMoment(year=1947, month=8, day=15, hour=0, minute=0, second=0,
                     utc_offset_hours=5.5, latitude=28.6139, longitude=77.2090)
    return compute_natal_chart(m)


def test_all_twelve_signs_have_ascendant_and_moon_blurbs():
    assert set(ASCENDANT_BLURBS) == set(RASHI_NAMES)
    assert set(MOON_BLURBS) == set(RASHI_NAMES)


def test_build_teaser_uses_real_ascendant_and_moon_sign():
    chart = _reference_chart()
    teaser = build_teaser(chart)
    assert teaser.ascendant_sign == chart.ascendant.sign
    moon = next(p for p in chart.planets if p.code == "Mo")
    assert teaser.moon_sign == moon.sign


def test_build_teaser_blurb_is_nonempty_and_matches_signs():
    chart = _reference_chart()
    teaser = build_teaser(chart)
    assert ASCENDANT_BLURBS[teaser.ascendant_sign] in teaser.blurb
    assert MOON_BLURBS[teaser.moon_sign] in teaser.blurb


def test_build_teaser_defaults_to_square_booking_link():
    chart = _reference_chart()
    teaser = build_teaser(chart)
    assert teaser.book_url.startswith("https://orbinovastro.square.site")


def test_build_teaser_respects_custom_book_url():
    chart = _reference_chart()
    teaser = build_teaser(chart, book_url="https://example.com/book")
    assert teaser.book_url == "https://example.com/book"


def test_build_teaser_headline_includes_name_when_given():
    chart = _reference_chart()
    teaser = build_teaser(chart, name="Devang")
    assert "Devang" in teaser.headline


def test_build_teaser_headline_falls_back_when_no_name():
    chart = _reference_chart()
    teaser = build_teaser(chart, name="")
    assert "You" in teaser.headline
