"""
Tests for the Stage-1 Overview Report port (engine/overview_report_builder.py
+ engine/overview_report/*): the live data-assembly logic
(build_parsed_from_ccsi), the ported-unchanged AI-response validation
(_validate_and_fill), and a full end-to-end PDF build with the OpenAI call
replaced by a fake client (no network call, no API key needed to run this
suite) -- mirrors this project's existing discipline of never letting a
real network dependency make the test suite flaky (see test_geocode.py's
own note on the same point for the Nominatim call).

Does NOT re-validate the CCSI numbers themselves -- those are already
132/132 real-cell validated in test_hit_calc_lagna_validated.py/
test_hit_calc_lt_tt_validated.py/test_ccsi_live.py. This file only checks
that build_parsed_from_ccsi() carries those already-correct numbers through
unchanged into the shape the PDF/AI-prompt layer expects, and that the
Stage-1 pipeline (data assembly -> AI call -> PDF render) runs end to end
without error.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.hit_calc import CcsiRow
from app.engine.overview_report_builder import (
    build_overview_report_pdf,
    build_parsed_from_ccsi,
    safe_filename,
)
from app.engine.overview_report.overview_labels import (
    HOUSE_LIFE_AREAS,
    LABELS_ARE_PLACEHOLDER,
    PLANET_SIGNIFICATIONS,
)
from app.engine.overview_report.overview_narrative import (
    _validate_and_fill,
    parse_json_response,
)
from app.engine.overview_report.lbi_legend import (
    CONCLUSION_ROWS,
    SCORECARD_CATEGORIES,
    STRATEGIC_FOCUS_AREAS,
    TIER_KEYS,
)
from app.engine.ephemeris import BirthMoment

# Same real reference chart used throughout the CCSI validation suite
# (1973-10-12, 14:55 IST, +5:30). The real, already-validated L-row values
# from test_hit_calc_lagna_validated.py -- reused here just to build a
# stand-in CcsiReport, not re-validated.
REAL_NET_LAGNA_HOUSES = {1: -1, 2: 1, 3: 8, 4: 0, 5: 3, 6: -1, 7: 1, 8: 0,
                          9: 5, 10: 0, 11: 5, 12: -3}
REAL_NET_LAGNA_COLUMNS = {"Asc": -1, "Su": -4, "Mo": -3, "Ma": 9, "Me": 0,
                           "Ju": 0, "Ve": 3, "Sa": 3, "Ra": -4, "Ke": 0}
REAL_NEG_ONLY_LAGNA_HOUSES = {1: 4, 2: 0, 3: 2, 4: 3, 5: 2, 6: 4, 7: 4, 8: 0,
                               9: 11, 10: 0, 11: 0, 12: 5}
REAL_NEG_ONLY_LAGNA_COLUMNS = {"Asc": 4, "Su": 4, "Mo": 3, "Ma": 5, "Me": 6,
                                "Ju": 4, "Ve": 1, "Sa": 6, "Ra": 12, "Ke": 6}


def _fake_ccsi_report():
    """A stand-in ccsi.CcsiReport built from the real, already-validated L
    row (reused for all three variants here -- LT/TT's own correctness is
    not what this test file is checking)."""
    l_net = CcsiRow(houses=dict(REAL_NET_LAGNA_HOUSES), columns=dict(REAL_NET_LAGNA_COLUMNS))
    l_negative = CcsiRow(houses=dict(REAL_NEG_ONLY_LAGNA_HOUSES), columns=dict(REAL_NEG_ONLY_LAGNA_COLUMNS))
    return SimpleNamespace(
        l_net=l_net, l_negative=l_negative,
        lt_net=l_net, lt_negative=l_negative,
        tt_net=l_net, tt_negative=l_negative,
    )


def test_house_and_planet_labels_are_complete_and_flagged_placeholder():
    assert set(HOUSE_LIFE_AREAS.keys()) == set(range(1, 13))
    assert set(PLANET_SIGNIFICATIONS.keys()) == {
        "Asc", "Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"
    }
    for text in HOUSE_LIFE_AREAS.values():
        assert " — " in text, "expected an em-dash label/description split (ccsi_parser.split_life_area)"
    assert LABELS_ARE_PLACEHOLDER is True


def test_build_parsed_from_ccsi_carries_real_validated_numbers_through_unchanged():
    parsed = build_parsed_from_ccsi(_fake_ccsi_report())

    assert len(parsed["houses"]) == 12
    assert len(parsed["planets"]) == 10

    for house in parsed["houses"]:
        n = house["house"]
        assert house["L"] == REAL_NET_LAGNA_HOUSES[n]
        assert house["L_neg"] == REAL_NEG_ONLY_LAGNA_HOUSES[n]
        # LT/TT reuse the same fake row on purpose (see _fake_ccsi_report).
        assert house["LT"] == REAL_NET_LAGNA_HOUSES[n]
        assert house["TT"] == REAL_NET_LAGNA_HOUSES[n]
        assert house["life_area"] == HOUSE_LIFE_AREAS[n]

    by_code = {p["code"]: p for p in parsed["planets"]}
    for code, expected in REAL_NET_LAGNA_COLUMNS.items():
        assert by_code[code]["L"] == expected
        assert by_code[code]["signification"] == PLANET_SIGNIFICATIONS[code]


def test_validate_and_fill_pads_missing_houses_planets_and_tables():
    parsed = build_parsed_from_ccsi(_fake_ccsi_report())

    # Deliberately sparse/malformed AI response: missing several houses,
    # missing a planet, wrong-length strategic focus areas, no scorecard,
    # malformed conclusion -- _validate_and_fill must not crash, and must
    # produce exactly the shapes build_pdf() expects.
    sparse = {
        "houses": [{"house": 1, "assessment_tier": "positive", "assessment_label": "Good"}],
        "planets": [{"code": "Su"}],
        "strategic_focus_areas": [{"area": STRATEGIC_FOCUS_AREAS[0]}],
    }

    fixed = _validate_and_fill(sparse, parsed)

    assert [h["house"] for h in fixed["houses"]] == list(range(1, 13))
    assert [p["code"] for p in fixed["planets"]] == [p["code"] for p in parsed["planets"]]
    assert [a["area"] for a in fixed["strategic_focus_areas"]] == STRATEGIC_FOCUS_AREAS
    assert [s["category"] for s in fixed["scorecard"]] == SCORECARD_CATEGORIES
    assert fixed["conclusion"]["overall_chart_strength"] == {"tier": "neutral", "text": ""}
    # Every padded/placeholder row uses a real tier key, never an invented one.
    for h in fixed["houses"]:
        assert h["assessment_tier"] in TIER_KEYS


def test_parse_json_response_strips_markdown_fences():
    fenced = "```json\n{\"a\": 1}\n```"
    assert parse_json_response(fenced) == {"a": 1}
    assert parse_json_response('{"a": 1}') == {"a": 1}


def test_safe_filename_strips_unsafe_characters():
    assert safe_filename('Devang "D" Naik/Test') == "Devang__D__Naik_Test"
    assert safe_filename("") == "Client"


def _fake_ai_report_json() -> str:
    """A minimal but fully-shaped fake AI response -- exercises the real
    build_pdf() rendering path end to end without a network call."""
    row = lambda **extra: {
        "assessment_tier": "positive", "assessment_label": "Steady",
        "interpretation": "Test interpretation.", "interpretation_highlight": "none",
        "guidance": "Test guidance.", "guidance_highlight": "none",
        **extra,
    }
    return json.dumps({
        "executive_assessment": {
            "overall_life_potential": {"tier": "positive", "label": "Steady"},
            "current_activation": {"tier": "neutral", "label": "Stable"},
            "current_cosmic_environment": {"tier": "positive", "label": "Favorable"},
            "highest_opportunity": "Test opportunity.",
            "highest_priority": "Test priority.",
            "overall_life_phase": "Test phase.",
            "summary": "Test summary.",
        },
        "houses": [row(house=i) for i in range(1, 13)],
        "houses_closing": {"heading": "Dominant House Pathway", "text": "Test."},
        "planets": [row(code=c) for c in ["Asc", "Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]],
        "planets_closing": [
            {"heading": "Strongest Planetary Combination", "text": "Test."},
            {"heading": "Planetary Priority", "text": "Test.", "bullets": ["a", "b", "c"]},
        ],
        "strategic_focus_areas": [
            {"area": a, "assessment_tier": "positive", "assessment_label": "Steady",
             "guidance": "Test.", "row_highlight": "none"}
            for a in STRATEGIC_FOCUS_AREAS
        ],
        "scorecard": [
            {"category": c, "assessment_tier": "positive", "assessment_label": "Steady"}
            for c in SCORECARD_CATEGORIES
        ],
        "conclusion": {
            "overall_chart_strength": {"tier": "positive", "text": "Test."},
            "primary_strengths": "Test.", "highest_opportunities": "Test.",
            "priority_areas": "Test.", "current_life_theme": "Test.",
            "long_term_direction": "Test.",
        },
        "core_message": {"paragraphs": ["Test.", "Test.", "Test.", "Test."]},
    })


class _FakeChoice:
    def __init__(self, content):
        self.message = SimpleNamespace(content=content)


class _FakeCompletionsResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def create(self, model, messages):  # noqa: ARG002 -- matches OpenAI's real signature
        return _FakeCompletionsResponse(_fake_ai_report_json())


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeOpenAIClient:
    """Stands in for openai.OpenAI() -- generate_overview_data() only ever
    calls client.chat.completions.create(model=..., messages=...), so
    anything with that shape works without a real network call or API key."""
    def __init__(self):
        self.chat = _FakeChat()


def test_build_overview_report_pdf_end_to_end_with_fake_openai_client():
    natal_moment = BirthMoment(
        year=1973, month=10, day=12, hour=14, minute=55, second=0,
        utc_offset_hours=5.5,
        latitude=20.815615264029468, longitude=72.95947488134223,
    )
    result = build_overview_report_pdf(
        _FakeOpenAIClient(), "Test Client", natal_moment, natal_moment,
        birth_place="Amalsad, Gujarat, India",
    )

    assert result.pdf_bytes.startswith(b"%PDF")
    assert len(result.pdf_bytes) > 5000  # a real multi-page report, not an empty/broken file
    assert result.labels_are_placeholder is True
    assert "placeholder" in result.disclaimer.lower() or "STANDARD" in result.disclaimer
