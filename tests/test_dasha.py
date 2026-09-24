"""
Structural tests for the Vimshottari Dasha engine port (engine/dasha.py).

These confirm the port is INTERNALLY faithful to the VBA algorithm
(sequencing, durations, self-first sub-division, silent-fallback
behaviors) -- they do NOT confirm the output matches the client's real
production workbook for a real chart, since the real `Ayanamsa_Diff`/`TZ`
values and a validated reference chart are not available yet. That
validation is still outstanding (see roadmap doc).

Run with:  python -m pytest tests/ -v   (from backend/)
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.dasha import (
    VIMSHOTTARI_ORDER_DEFAULT,
    VIMSHOTTARI_YEARS,
    DAYS_PER_YEAR,
    DashaPeriod,
    build_md_list,
    build_sub_periods,
    get_active_index,
    get_active_period,
    get_active_planet,
    index_of_planet,
    proper_planet_name,
    resolve_exact,
    root_md_from_anchor,
    select_index_for_anchor,
    vim_dasha_years,
)


# ---------------------------------------------------------------------------
# proper_planet_name / vim_dasha_years / index_of_planet
# ---------------------------------------------------------------------------

def test_proper_planet_name_normalizes_case_and_whitespace():
    assert proper_planet_name("su") == "Su"
    assert proper_planet_name("MOON"[:2]) == "Mo"
    assert proper_planet_name("  ke ") == "Ke"
    assert proper_planet_name("RA") == "Ra"


def test_vim_dasha_years_matches_known_table():
    assert vim_dasha_years("Ke") == 7
    assert vim_dasha_years("Ve") == 20
    assert vim_dasha_years("Su") == 6
    assert vim_dasha_years("Mo") == 10
    assert vim_dasha_years("Ma") == 7
    assert vim_dasha_years("Ra") == 18
    assert vim_dasha_years("Ju") == 16
    assert vim_dasha_years("Sa") == 19
    assert vim_dasha_years("Me") == 17
    assert sum(VIMSHOTTARI_YEARS.values()) == 120


def test_index_of_planet_fallback_matches_vba():
    order = VIMSHOTTARI_ORDER_DEFAULT
    assert index_of_planet(order, "Su") == 2
    # Unknown planet -> -1 (caller is responsible for the 0-fallback,
    # matching IndexOfPlanet's own contract in the VBA)
    assert index_of_planet(order, "Xx") == -1


# ---------------------------------------------------------------------------
# build_md_list
# ---------------------------------------------------------------------------

def test_build_md_list_is_sequential_and_covers_120_years():
    root_start = datetime(2000, 1, 1)
    periods = build_md_list("Ve", root_start)
    assert len(periods) == 9
    assert periods[0].planet == "Ve"
    # self-first: order starts at Ve and cycles the standard sequence
    expected_order = ["Ve", "Su", "Mo", "Ma", "Ra", "Ju", "Sa", "Me", "Ke"]
    assert [p.planet for p in periods] == expected_order

    # sequential, no gaps/overlaps
    for i in range(8):
        assert periods[i].end == periods[i + 1].start

    total_days = (periods[-1].end - periods[0].start).total_seconds() / 86400.0
    assert abs(total_days - 120 * DAYS_PER_YEAR) < 1e-6

    # each MD duration uses the exact 365.2425 constant
    for p in periods:
        expected_days = vim_dasha_years(p.planet) * DAYS_PER_YEAR
        actual_days = (p.end - p.start).total_seconds() / 86400.0
        assert abs(actual_days - expected_days) < 1e-6


def test_build_md_list_unknown_root_falls_back_to_index_zero():
    root_start = datetime(2000, 1, 1)
    periods = build_md_list("ZZ", root_start)
    # index 0 of the default order is Ke
    assert periods[0].planet == "Ke"


# ---------------------------------------------------------------------------
# build_sub_periods
# ---------------------------------------------------------------------------

def test_build_sub_periods_self_first_and_proportional():
    p_start = datetime(2000, 1, 1)
    p_end = p_start + timedelta(days=17 * DAYS_PER_YEAR)  # a Me MD, for round proportions
    periods = build_sub_periods("Me", p_start, p_end)

    assert len(periods) == 9
    expected_order = ["Me", "Ke", "Ve", "Su", "Mo", "Ma", "Ra", "Ju", "Sa"]
    assert [p.planet for p in periods] == expected_order

    # sequential, no gaps
    for i in range(8):
        assert periods[i].end == periods[i + 1].start
    assert periods[0].start == p_start
    assert periods[-1].end == p_end

    # proportional: each segment's share of the total span matches
    # planet_years/120, NOT planet_years*365.2425 (that's the bug this
    # test guards against -- sub-periods must NOT re-apply the year
    # constant, they must split the PARENT's actual elapsed span)
    span_days = (p_end - p_start).total_seconds() / 86400.0
    for p in periods:
        seg_days = (p.end - p.start).total_seconds() / 86400.0
        expected_days = span_days * (vim_dasha_years(p.planet) / 120.0)
        assert abs(seg_days - expected_days) < 1e-6


def test_build_sub_periods_unknown_parent_falls_back_to_index_zero():
    p_start = datetime(2000, 1, 1)
    p_end = p_start + timedelta(days=365)
    periods = build_sub_periods("ZZ", p_start, p_end)
    assert periods[0].planet == "Ke"


# ---------------------------------------------------------------------------
# select_index_for_anchor / get_active_*
# ---------------------------------------------------------------------------

def _three_periods():
    t0 = datetime(2000, 1, 1)
    t1 = t0 + timedelta(days=10)
    t2 = t1 + timedelta(days=10)
    t3 = t2 + timedelta(days=10)
    return [
        DashaPeriod("A", t0, t1),
        DashaPeriod("B", t1, t2),
        DashaPeriod("C", t2, t3),
    ]


def test_select_index_for_anchor_normal_cases():
    periods = _three_periods()
    assert select_index_for_anchor(periods, periods[0].start) == 0
    assert select_index_for_anchor(periods, periods[1].start) == 1
    assert select_index_for_anchor(periods, periods[2].start + timedelta(days=1)) == 2


def test_select_index_for_anchor_clamps_out_of_range_to_last():
    """Faithful replication of a VBA quirk: an anchor AFTER all periods
    clamps to the last period (expected/normal), and an anchor BEFORE the
    first period ALSO resolves to the last period (a VBA quirk we
    replicate rather than silently 'fix' -- see dasha.py docstring)."""
    periods = _three_periods()
    after = periods[-1].end + timedelta(days=100)
    assert select_index_for_anchor(periods, after) == 2

    before = periods[0].start - timedelta(days=100)
    assert select_index_for_anchor(periods, before) == 2  # VBA quirk, replicated


def test_select_index_for_anchor_empty_list():
    assert select_index_for_anchor([], datetime(2000, 1, 1)) == -1


def test_get_active_helpers_agree_with_select_index():
    periods = _three_periods()
    anchor = periods[1].start + timedelta(days=1)
    idx = get_active_index(periods, anchor)
    assert idx == 1
    assert get_active_period(periods, anchor) == periods[1]
    assert get_active_planet(periods, anchor) == "B"


# ---------------------------------------------------------------------------
# End-to-end: root_md_from_anchor / resolve_exact structural checks
# ---------------------------------------------------------------------------

def test_root_md_from_anchor_returns_planet_from_order_and_start_before_anchor():
    anchor = datetime(1990, 6, 15, 14, 30, 0)
    planet, start = root_md_from_anchor(anchor, tz_hours=5.5)
    assert planet in VIMSHOTTARI_ORDER_DEFAULT
    # elapsed_days is always >= 0 (fraction of nakshatra already elapsed),
    # so the root MD start must be at or before the anchor
    assert start <= anchor


def test_resolve_exact_anchor_falls_within_every_level():
    anchor = datetime(1990, 6, 15, 14, 30, 0)
    chain = resolve_exact(anchor, tz_hours=5.5)

    assert chain.md and chain.ad and chain.pd and chain.su and chain.pr
    assert chain.md_period.start <= anchor < chain.md_period.end
    assert chain.ad_period.start <= anchor < chain.ad_period.end
    assert chain.pd_period.start <= anchor < chain.pd_period.end
    assert chain.su_period.start <= anchor < chain.su_period.end
    assert chain.pr_period.start <= anchor < chain.pr_period.end

    # each level is a genuine sub-period of its parent
    assert chain.ad_period.start >= chain.md_period.start
    assert chain.ad_period.end <= chain.md_period.end
    assert chain.pd_period.start >= chain.ad_period.start
    assert chain.pd_period.end <= chain.ad_period.end
    assert chain.su_period.start >= chain.pd_period.start
    assert chain.su_period.end <= chain.pd_period.end
    assert chain.pr_period.start >= chain.su_period.start
    assert chain.pr_period.end <= chain.su_period.end


def test_resolve_exact_is_deterministic():
    anchor = datetime(1985, 3, 21, 6, 0, 0)
    c1 = resolve_exact(anchor, tz_hours=0.0)
    c2 = resolve_exact(anchor, tz_hours=0.0)
    assert (c1.md, c1.ad, c1.pd, c1.su, c1.pr) == (c2.md, c2.ad, c2.pd, c2.su, c2.pr)


def test_resolve_exact_ayanamsa_diff_is_wired_in_modulo_360():
    """Confirms `ayanamsa_diff` is actually applied to the Moon longitude
    lookup (matching `mo360 = mo360_raw + ayDiff` in the VBA) rather than
    silently ignored the way `Ayanamsa_Offset` is: adding a full 360-degree
    multiple must be a no-op (since the result is wrapped mod 360), which
    only holds if the diff genuinely flows through the same wrap-around
    arithmetic as the VBA."""
    anchor = datetime(1990, 6, 15, 14, 30, 0)
    chain_a = resolve_exact(anchor, tz_hours=5.5, ayanamsa_diff=0.0)
    chain_b = resolve_exact(anchor, tz_hours=5.5, ayanamsa_diff=360.0)
    assert (chain_a.md, chain_a.ad, chain_a.pd, chain_a.su, chain_a.pr) == \
           (chain_b.md, chain_b.ad, chain_b.pd, chain_b.su, chain_b.pr)

    # A non-multiple-of-360 diff must be capable of changing the root
    # nakshatra lord for at least one of several probe anchors (i.e. the
    # parameter has real, non-inert effect on the computation).
    probes = [datetime(1990, 6, 15, h, 30, 0) for h in range(0, 24, 3)]
    any_changed = False
    for probe in probes:
        root_a, _ = root_md_from_anchor(probe, tz_hours=5.5, ayanamsa_diff=0.0)
        root_b, _ = root_md_from_anchor(probe, tz_hours=5.5, ayanamsa_diff=13.0)
        if root_a != root_b:
            any_changed = True
            break
    assert any_changed
