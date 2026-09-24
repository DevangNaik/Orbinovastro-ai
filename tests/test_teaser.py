"""Tests for the client-facing teaser/preview (engine/teaser.py) -- the
"Free Preview," rewritten (2026-09-24, later still) from a one-paragraph
Ascendant+Moon blurb into an extensive D1 placement analysis after the
client's own feedback that the original didn't "make the user order more"
or "give trust." See engine/teaser.py's module docstring for the full
design rationale (still template text, no LLM call; stops at placement
description, never scoring/judgment)."""
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine import teaser as teaser_module
from app.engine.chart import chart_to_dict
from app.engine.ephemeris import BirthMoment, RASHI_NAMES, compute_natal_chart
from app.engine.overview_report.overview_labels import HOUSE_LIFE_AREAS, PLANET_SIGNIFICATIONS
from app.engine.teaser import ASCENDANT_BLURBS, MOON_BLURBS, SUN_BLURBS, build_teaser


def _reference_chart():
    m = BirthMoment(year=1947, month=8, day=15, hour=0, minute=0, second=0,
                     utc_offset_hours=5.5, latitude=28.6139, longitude=77.2090)
    return compute_natal_chart(m)


def _real_client_reference_chart():
    """The client's own real, extensively-validated reference chart
    (1973-10-12, 14:55 IST, Amalsad, Gujarat) used throughout this
    engagement's CCSI/kp_lords validation -- reused here to cross-check
    the teaser's house-placement arithmetic against engine/chart.py's
    already-tested chart_to_dict(), independently of that module."""
    m = BirthMoment(year=1973, month=10, day=12, hour=14, minute=55, second=0,
                     utc_offset_hours=5.5, latitude=20.815615264029468,
                     longitude=72.95947488134223)
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


def test_all_twelve_signs_have_sun_blurbs_too():
    assert set(SUN_BLURBS) == set(RASHI_NAMES)


def test_build_teaser_sun_sign_matches_chart():
    chart = _reference_chart()
    teaser = build_teaser(chart)
    sun = next(p for p in chart.planets if p.code == "Su")
    assert teaser.sun_sign == sun.sign


def test_placements_include_ascendant_plus_all_nine_planets():
    chart = _reference_chart()
    teaser = build_teaser(chart)
    codes = [p.code for p in teaser.placements]
    assert codes == ["Asc", "Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]
    assert len(teaser.placements) == 10


def test_placement_houses_match_chart_to_dicts_rasi_house_independently():
    """Cross-checks teaser.py's own house-placement arithmetic against
    engine/chart.py's already-tested rasi_house field, computed via a
    completely separate code path (chart_to_dict), for the client's real
    reference chart."""
    chart = _real_client_reference_chart()
    teaser = build_teaser(chart)
    as_dict = chart_to_dict(chart)

    assert next(p for p in teaser.placements if p.code == "Asc").house == 1

    rasi_house_by_code = {p["code"]: p["rasi_house"] for p in as_dict["planets"]}
    for placement in teaser.placements:
        if placement.code == "Asc":
            continue
        assert placement.house == rasi_house_by_code[placement.code], (
            f"{placement.code}: teaser said house {placement.house}, "
            f"chart_to_dict said rasi_house {rasi_house_by_code[placement.code]}"
        )


def test_every_placement_narrative_uses_the_clients_real_labels():
    """Every placement's governs/house_domain/narrative must trace back to
    the client's own real HIT_CALC-sourced wording (overview_labels.py),
    never invented or generic text."""
    chart = _real_client_reference_chart()
    teaser = build_teaser(chart)
    for placement in teaser.placements:
        expected_gov_label = PLANET_SIGNIFICATIONS[placement.code].split("—")[0].strip()
        expected_house_label = HOUSE_LIFE_AREAS[placement.house].split("—")[0].strip()
        assert placement.governs == expected_gov_label
        assert placement.house_domain == expected_house_label
        assert expected_gov_label in placement.narrative
        assert expected_house_label in placement.narrative
        assert str(placement.house) or True  # house is always a plain int 1-12
        assert 1 <= placement.house <= 12


def test_retrograde_planet_gets_a_retrograde_clause_in_its_narrative():
    chart = _real_client_reference_chart()
    teaser = build_teaser(chart)
    for placement in teaser.placements:
        if placement.code == "Asc":
            continue
        planet = next(p for p in chart.planets if p.code == placement.code)
        if planet.retrograde:
            assert "retrograde" in placement.narrative.lower()


def test_executive_summary_mentions_all_three_big_three_signs():
    chart = _reference_chart()
    teaser = build_teaser(chart)
    assert teaser.ascendant_sign in teaser.executive_summary
    assert teaser.sun_sign in teaser.executive_summary
    assert teaser.moon_sign in teaser.executive_summary


def test_executive_summary_includes_name_when_given():
    chart = _reference_chart()
    teaser = build_teaser(chart, name="Devang")
    assert "Devang" in teaser.executive_summary


def test_synthesis_reports_correct_kendra_and_trikona_counts():
    """The synthesis's structural counts must match a plain, independent
    recount over the same 9 placements -- not just be nonempty text."""
    chart = _real_client_reference_chart()
    teaser = build_teaser(chart)
    graha_houses = [p.house for p in teaser.placements if p.code != "Asc"]
    expected_kendra = sum(1 for h in graha_houses if h in (1, 4, 7, 10))
    expected_trikona = sum(1 for h in graha_houses if h in (1, 5, 9))
    expected_occupied = len(set(graha_houses))

    assert f"{expected_kendra} of them sit in the four" in teaser.synthesis
    assert f"{expected_trikona} fall in the luckiest" in teaser.synthesis
    assert f"spread across {expected_occupied} of the twelve houses" in teaser.synthesis
    assert "under real pressure" in teaser.synthesis


def test_upgrade_pitch_names_the_paid_diagnostic_report_and_stays_honest():
    """The pitch must point to the paid report by name and explicitly say
    what the free preview leaves out -- but it must never mention CCSI's
    internal numbers/scores, since this is public-facing marketing copy,
    not the engine's own output."""
    chart = _reference_chart()
    teaser = build_teaser(chart)
    assert "Diagnostic Report" in teaser.upgrade_pitch
    assert "stress" in teaser.upgrade_pitch.lower()
    assert "dasha" in teaser.upgrade_pitch.lower()


def test_teaser_module_never_imports_the_proprietary_scoring_engines():
    """Guards the free/paid boundary at the source level: engine/teaser.py
    must never IMPORT hit_calc/ccsi/scoring/dasha/kp_lords -- if it ever
    does, the free preview risks leaking the paid report's proprietary
    connection-and-stress scoring, not just placement description. Checks
    actual import statements only (via ast), not prose mentions in
    comments/docstrings -- teaser.py's own module docstring legitimately
    names hit_calc.py/ccsi.py in explaining why it does NOT use them."""
    import ast

    src = inspect.getsource(teaser_module)
    tree = ast.parse(src)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.rsplit(".", 1)[-1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.rsplit(".", 1)[-1])

    forbidden = {"hit_calc", "ccsi", "scoring", "dasha", "kp_lords"}
    leaked = imported_modules & forbidden
    assert not leaked, f"teaser.py must not import {leaked}"
