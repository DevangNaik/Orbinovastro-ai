"""
Structural tests for the CCSI additive-scoring port (engine/scoring.py):
`core_score_and_flag` / `score_additive` / `flag_additive`, ported from
`Core_ScoreAndFlag` / `Score_Additive` / `Flag_Additive` (ScoringModule.bas).

The `EXAMPLE_EVENT_SETTINGS` table below is ENTIRELY MADE UP for testing
the arithmetic only -- it is NOT the client's real Event Settings table
(that's still pending from the client; see scoring.py's module docstring
and the project roadmap doc). Do not reuse this table, or any score
computed from it, anywhere client-facing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.scoring import (
    EventSettingsColumn,
    EventSettingsTable,
    core_score_and_flag,
    extract_houses_1_to_12,
    flag_additive,
    score_additive,
)

# FAKE example table, arithmetic-testing only -- see module docstring.
EXAMPLE_EVENT_SETTINGS = EventSettingsTable(columns=[
    EventSettingsColumn(header="A-Prime", houses=[2, 7, 11], weight=3.0),
    EventSettingsColumn(header="D-Worst", houses=[6, 8, 12], weight=-3.0),
    EventSettingsColumn(header="Good", houses=[1, 5, 9], weight=2.0),
    EventSettingsColumn(header="Weak Good", houses=[3, 4], weight=1.0, weak=True),
])


def test_extract_houses_1_to_12_filters_out_of_range_and_non_numeric():
    assert extract_houses_1_to_12("4, 6, 12") == ["4", "6", "12"]
    assert extract_houses_1_to_12("house 13 and 0 and 7") == ["7"]
    assert extract_houses_1_to_12("") == []
    assert extract_houses_1_to_12(None) == []


def test_unanimous_positive_houses_score_additively():
    # sig/nlof/slof all land in the "Good" bucket (weight +2, not prime)
    result = core_score_and_flag("1", "5", "9", EXAMPLE_EVENT_SETTINGS)
    # existence = 2+2+2 = 6; level = BONUS_SIG(0)+BONUS_NLOF(1)+BONUS_SLOF(2) = 3
    # (none of 1/5/9 are prime, so no x3/x-3 multiplier)
    # posHits: all three (S,E,R) hit the pos_set (everything not D-Worst-tagged) -> +3
    assert result.score == 6 + 3 + 3
    assert result.flag == ""


def test_non_unanimous_polarity_is_zeroed_out_by_default():
    # sig hits a positive house (2, A-Prime), nlof hits a negative house
    # (8, D-Worst) -- opposite polarities -> unanimity fails -> 0/"" per
    # Core_ScoreAndFlag's early-exit.
    result = core_score_and_flag("2", "8", "", EXAMPLE_EVENT_SETTINGS)
    assert result.score == 0.0
    assert result.flag == ""


def test_unanimity_can_be_disabled():
    result = core_score_and_flag("2", "8", "", EXAMPLE_EVENT_SETTINGS, enforce_unanimity=False)
    # existence = weight(2)=3 + weight(8)=-3 + 0 = 0
    # level: SIG bonus for house 2 (A-Prime, pos_prime) = 0*3=0;
    #        NLOF bonus for house 8 (D-Worst, neg_prime) = -(1*3) = -3
    # posHits/negHits: sig hits pos_set (1), nlof hits neg_set (1) -> adjust = 1-1=0
    assert result.score == 0 + (0 + -3) + 0
    assert "8-NEGPRIME-NLOF" in result.flag


def test_prime_house_gets_primary_factor_multiplier():
    # House 2 is in BOTH the "Good"-style weight map AND tagged A-Prime.
    # At the NLOF level (base bonus=1), a prime hit multiplies by 3.
    result = core_score_and_flag("", "2", "", EXAMPLE_EVENT_SETTINGS, enforce_unanimity=False)
    # existence = weight(2) = 3
    # level: NLOF bonus = BONUS_NLOF(1) * PRIMARY_FACTOR(3) = 3 (since 2 is posPrime)
    # posHits: nlof hits pos_set -> +1
    assert result.score == 3 + 3 + 1
    assert "2-POSPRIME-NLOF" in result.flag


def test_weak_prefix_reduces_weight_by_one():
    # House 3 is in the "Weak Good" column, weight 1 - 1 (weak) = 0
    result = core_score_and_flag("3", "", "", EXAMPLE_EVENT_SETTINGS, enforce_unanimity=False)
    # existence = 0 (weight is 0 after weak reduction)
    # level: SIG bonus = BONUS_SIG(0) since not prime -> 0
    # posHits: house 3 is in pos_set (not D-Worst-tagged) -> +1
    assert result.score == 0 + 0 + 1


def test_score_additive_and_flag_additive_agree_with_core():
    core = core_score_and_flag("1", "5", "9", EXAMPLE_EVENT_SETTINGS)
    assert score_additive("1", "5", "9", EXAMPLE_EVENT_SETTINGS) == core.score
    assert flag_additive("1", "5", "9", EXAMPLE_EVENT_SETTINGS) == "None"  # empty flag -> "None"


def test_flag_additive_returns_none_literal_when_no_flags():
    assert flag_additive("", "", "", EXAMPLE_EVENT_SETTINGS) == "None"


def test_no_matching_houses_at_all_is_zero_score_no_flags():
    result = core_score_and_flag("", "", "", EXAMPLE_EVENT_SETTINGS)
    assert result.score == 0.0
    assert result.flag == ""
