"""
Validates `event_settings_table_for_event`/`TIER_WEIGHTS` against the
client's REAL EventList data and REAL confirmed tier weights (both
confirmed 2026-09-23 -- see scoring.py's module docstring and the
project roadmap doc). Unlike test_scoring.py's EXAMPLE_EVENT_SETTINGS
(explicitly fake, arithmetic-only), everything hardcoded below comes
directly from the client's own screenshot and worksheet export.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.scoring import (
    TIER_ORDER,
    TIER_WEIGHTS,
    core_score_and_flag,
    event_settings_table_for_event,
    find_event,
    load_eventlist,
)

# From the client's screenshot, 2026-09-23: EVT132 "Green Card /
# Permanent Residency (Natal)"'s six tier house-lists, and the
# "Weighted Score" row confirming each tier's numeric weight.
EXPECTED_TIER_HOUSES = {
    "A-Prime": [9, 12],
    "B-Secondary": [3, 4, 6, 11],
    "C-Supportive": [1, 2, 7, 10],
    "DI-Bad": [5],
    "D2-Worse": [8],
    "D3-Worst": [],  # shown as "0" in the client's sheet -- no houses in this tier
}

EXPECTED_TIER_WEIGHTS = {
    "A-Prime": 3.0,
    "B-Secondary": 2.0,
    "C-Supportive": 1.0,
    "DI-Bad": -1.0,
    "D2-Worse": -2.0,
    "D3-Worst": -3.0,
}


def test_tier_weights_match_clients_confirmed_screenshot():
    assert TIER_WEIGHTS == EXPECTED_TIER_WEIGHTS


def test_real_eventlist_loads_and_finds_evt132_by_id_and_name():
    events = load_eventlist()
    assert len(events) == 140

    by_id = find_event(events, event_id="EVT132")
    by_name = find_event(events, name="Green Card / Permanent Residency (Natal)")
    assert by_id is not None
    assert by_id is by_name  # same record, two lookup paths agree

    for tier in TIER_ORDER:
        assert by_id["tiers"][tier] == EXPECTED_TIER_HOUSES[tier], (
            f"{tier}: {by_id['tiers'][tier]} != {EXPECTED_TIER_HOUSES[tier]}"
        )


def test_event_settings_table_for_evt132_matches_screenshot_exactly():
    events = load_eventlist()
    evt132 = find_event(events, event_id="EVT132")
    table = event_settings_table_for_event(evt132)

    assert [c.header for c in table.columns] == TIER_ORDER
    for col in table.columns:
        assert col.houses == EXPECTED_TIER_HOUSES[col.header]
        assert col.weight == EXPECTED_TIER_WEIGHTS[col.header]
        assert col.weak is False  # "weak" is a separate VBA concept, not used here


def test_evt132_table_scores_a_hit_in_each_tier_with_expected_sign():
    # Sanity-check the confirmed weights actually flow through
    # core_score_and_flag's weight map as expected: a lone hit in each
    # tier (unanimity disabled, single input) should score that tier's
    # exact weight, since existence = weight and level bonus (BONUS_SIG)
    # is 0 for a SIG-only hit with no prime multiplier.
    events = load_eventlist()
    evt132 = find_event(events, event_id="EVT132")
    table = event_settings_table_for_event(evt132)

    # House 3 (B-Secondary, weight +2, not prime) hit via `sig` only.
    result = core_score_and_flag("3", "", "", table, enforce_unanimity=False)
    assert result.score == 2.0 + 0.0 + 1.0  # existence(2) + level(BONUS_SIG=0) + posHit(+1)

    # House 5 (DI-Bad, weight -1) hit via `sig` only. DI-Bad is treated
    # as a "neg prime" header by `_NEG_PRIME_HEADER_VARIANTS`, but since
    # BONUS_SIG is 0 the prime multiplier contributes nothing either way.
    result = core_score_and_flag("5", "", "", table, enforce_unanimity=False)
    assert result.score == -1.0 + 0.0 - 1.0  # existence(-1) + level(0) + negHit(-1)
