"""
Structural tests for `hit_calc.py`, the CCSI (Cusp Conflict Stress Indicator)
engine. Everything here is tested against the client's OWN confirmed
`HITAspectRanges` table and their own LET formula's lookup constants
(2026-09-23) -- not invented. See `hit_calc.py`'s module docstring for full
provenance.

NOT covered here (deliberately -- no real data for it yet): a real
`HIT_CALC` numeric row from the client's own workbook. These tests confirm
the arithmetic is internally consistent with the confirmed formula and
lookup table; end-to-end validation against real output is still pending.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.hit_calc import (
    ASPECT_RANGES,
    ASPECT_TYPE_WEIGHTS,
    NINE_PLANETS,
    PLANET_TYPE_WEIGHTS,
    angular_separation,
    classify_aspect,
    compute_ccsi_row,
    negative_only_hit_score,
    net_hit_score,
)


def test_aspect_ranges_match_clients_table_exactly():
    # No, Degree, Margin, Min, Max, Name, Type -- as the client pasted it.
    expected = [
        (0, 0, 3, 0, 3, "Conj", "Cnj"),
        (4, 30, 3, 27, 33, "Sem-Sextile", "Frn"),
        (5, 60, 5, 55, 65, "Sextile", "BFrn"),
        (6, 120, 8, 112, 128, "Trine", "SoulM"),
        (3, 45, 3, 42, 48, "Semi Square", "Irritation"),
        (2, 90, 5, 85, 95, "Sqare", "Enemy"),
        (1, 180, 8, 172, 188, "Opposition", "Killer"),
    ]
    actual = [
        (r.no, r.degree, r.margin, r.min, r.max, r.name, r.type) for r in ASPECT_RANGES
    ]
    assert actual == expected


def test_aspect_type_weights_match_clients_formula():
    assert ASPECT_TYPE_WEIGHTS == {
        "Cnj": 1.0,
        "Frn": 1.0,
        "BFrn": 2.0,
        "SoulM": 3.0,
        "Irritation": -1.0,
        "Enemy": -2.0,
        "Killer": -3.0,
    }


def test_planet_type_weights_match_clients_formula():
    assert PLANET_TYPE_WEIGHTS == {
        "Sa": 2.0, "Ma": 2.0, "Ra": 2.0, "Ke": 2.0,
        "Su": 1.0, "Me": 1.0, "Mo": 1.0, "Ju": 1.0, "Ve": 1.0,
    }


def test_angular_separation_is_symmetric_and_shortest_path():
    assert angular_separation(10, 20) == 10
    assert angular_separation(20, 10) == 10
    # wraps the short way around 0/360
    assert angular_separation(350, 10) == 20
    assert angular_separation(10, 350) == 20
    # antipodal
    assert abs(angular_separation(0, 180) - 180) < 1e-9
    # identical
    assert angular_separation(42, 42) == 0


def test_classify_aspect_boundaries():
    assert classify_aspect(0) == "Cnj"
    assert classify_aspect(3) == "Cnj"
    assert classify_aspect(3.01) is None  # gap between Cnj and Sem-Sextile
    assert classify_aspect(26.99) is None
    assert classify_aspect(27) == "Frn"
    assert classify_aspect(30) == "Frn"
    assert classify_aspect(33) == "Frn"
    assert classify_aspect(55) == "BFrn"
    assert classify_aspect(65) == "BFrn"
    assert classify_aspect(42) == "Irritation"
    assert classify_aspect(48) == "Irritation"
    assert classify_aspect(85) == "Enemy"
    assert classify_aspect(95) == "Enemy"
    assert classify_aspect(112) == "SoulM"
    assert classify_aspect(128) == "SoulM"
    assert classify_aspect(172) == "Killer"
    assert classify_aspect(180) == "Killer"
    assert classify_aspect(188) == "Killer"
    assert classify_aspect(100) is None  # gap between Enemy(95) and SoulM(112)


def test_net_hit_score_single_malefic_conjunction():
    # A malefic (Sa) exactly conjunct the reference point: Cnj weight (1)
    # x malefic weight (2) = 2.
    score = net_hit_score(0.0, {"Sa": 0.0})
    assert score == 2.0


def test_net_hit_score_single_benefic_opposition():
    # A benefic (Ju) exactly opposite the reference point: Killer weight
    # (-3) x benefic weight (1) = -3.
    score = net_hit_score(0.0, {"Ju": 180.0})
    assert score == -3.0


def test_net_hit_score_no_aspect_in_gap_contributes_zero():
    score = net_hit_score(0.0, {"Ve": 15.0})  # 15 degrees is in the gap
    assert score == 0.0


def test_net_hit_score_sums_across_multiple_planets():
    # Sa conjunct (malefic, Cnj=1 -> +2) and Ju opposite (benefic, Killer=-3 -> -3)
    score = net_hit_score(0.0, {"Sa": 0.0, "Ju": 180.0})
    assert score == 2.0 + (-3.0)


def test_net_hit_score_self_exclusion():
    # A planet exactly conjunct itself (d=0) must be excluded from its own
    # column's hit-count, matching the formula's row-186 self-exclusion.
    with_self = net_hit_score(0.0, {"Sa": 0.0, "Ju": 180.0}, exclude=None)
    without_self = net_hit_score(0.0, {"Sa": 0.0, "Ju": 180.0}, exclude="Sa")
    assert with_self == 2.0 - 3.0
    assert without_self == -3.0


def test_negative_only_hit_score_zeroes_friendly_aspects():
    # Conjunction (friendly) contributes nothing in the negative-only block.
    score = negative_only_hit_score(0.0, {"Sa": 0.0})
    assert score == 0.0


def test_negative_only_hit_score_keeps_hard_aspect_magnitude():
    # Opposition (Killer, weight -3) x benefic (1) -> wFull=-3 -> aspectW=3.
    score = negative_only_hit_score(0.0, {"Ju": 180.0})
    assert score == 3.0
    # Same aspect with a malefic planet doubles it.
    score_malefic = negative_only_hit_score(0.0, {"Ra": 180.0})
    assert score_malefic == 6.0


def test_negative_only_hit_score_always_non_negative():
    score = negative_only_hit_score(
        0.0, {"Sa": 0.0, "Ju": 180.0, "Ve": 15.0, "Ma": 90.0}
    )
    assert score >= 0.0
    # Sa conjunct contributes 0 (friendly), Ju opposite contributes +3,
    # Ve in the gap contributes 0, Ma square (Enemy=-2, malefic x2) -> +4.
    assert score == 0.0 + 3.0 + 0.0 + 4.0


def test_compute_ccsi_row_shape_and_self_exclusion():
    house_cusps = {h: float(h) * 10 for h in range(1, 13)}  # arbitrary, distinct
    ascendant = 5.0
    reference_planets = {p: float(i) * 7 for i, p in enumerate(NINE_PLANETS)}
    comparison_planets = dict(reference_planets)  # e.g. the "L" natal-vs-natal case

    row = compute_ccsi_row(
        house_cusps, ascendant, reference_planets, comparison_planets
    )

    assert set(row.houses.keys()) == set(range(1, 13))
    assert set(row.columns.keys()) == {"Asc", *NINE_PLANETS}

    # Every planet's own column must have excluded itself: recompute
    # directly and confirm they match the exclude= path, not the
    # non-excluded path (unless coincidentally equal).
    for planet in NINE_PLANETS:
        expected = net_hit_score(
            reference_planets[planet], comparison_planets, exclude=planet
        )
        assert row.columns[planet] == expected


def test_compute_ccsi_row_negative_only_variant():
    house_cusps = {h: float(h) * 10 for h in range(1, 13)}
    ascendant = 0.0
    reference_planets = {"Sa": 0.0}
    comparison_planets = {"Ju": 180.0}

    row = compute_ccsi_row(
        house_cusps,
        ascendant,
        reference_planets,
        comparison_planets,
        negative_only=True,
    )
    # Asc at 0 vs Ju at 180: Killer, benefic -> +3.
    assert row.columns["Asc"] == 3.0
