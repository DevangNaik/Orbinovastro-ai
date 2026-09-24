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
    _shift_wall_clock,
    _transit_details_dict,
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


# 2026-09-24, later still: tests for the Transit Information display fix
# (see overview_report_builder.py's matching UPDATE docstring note) -- the
# client caught a real generated PDF showing "Transit Place: Not available"
# and an unlabeled, silently-UTC time. These check the local/UTC time-math
# itself; test_main_overview_transit_display.py checks the separate
# question of WHICH (place, offset) main.py resolves to feed in here.

def test_shift_wall_clock_same_offset_is_a_no_op():
    moment = BirthMoment(year=2026, month=9, day=24, hour=4, minute=4, second=0,
                          utc_offset_hours=0.0, latitude=0.0, longitude=0.0)
    same = _shift_wall_clock(moment, 0.0)
    assert (same.year, same.month, same.day, same.hour, same.minute) == (2026, 9, 24, 4, 4)


def test_shift_wall_clock_handles_day_rollover_forward():
    # A UTC evening moment, shifted +5.5h (IST) as _transit_details_dict's
    # "local" branch would when converting FROM UTC storage: 11:45 PM UTC
    # + 5:30 crosses midnight into the next day.
    moment = BirthMoment(year=2026, month=9, day=24, hour=23, minute=45, second=0,
                          utc_offset_hours=0.0, latitude=0.0, longitude=0.0)
    shifted = _shift_wall_clock(moment, 5.5)
    assert (shifted.year, shifted.month, shifted.day, shifted.hour, shifted.minute) == (2026, 9, 25, 5, 15)


def test_transit_details_dict_shows_both_local_and_utc_never_blank_place():
    # The exact bug from the client's screenshot: a "now"-defaulted transit
    # moment is always stored at UTC offset 0.0 internally (see
    # transit.now_as_birth_moment), e.g. 2026-09-24 04:04 UTC. Displaying it
    # for a birth location at +5:30 (IST) should show LOCAL as 09:34 AM the
    # same day, and UTC explicitly labeled as such -- not one unlabeled,
    # ambiguous time, and never "Not available" for the place.
    transit_moment = BirthMoment(year=2026, month=9, day=24, hour=4, minute=4, second=0,
                                  utc_offset_hours=0.0, latitude=20.8156, longitude=72.9595)
    details = _transit_details_dict(transit_moment, "Amalsad, Gujarat, India", 5.5)

    assert details["transit_place"] == "Amalsad, Gujarat, India"
    assert details["transit_date_local"] == "24 September 2026"
    assert details["transit_time_local"] == "9:34 AM"
    assert details["transit_timezone_local"] == "UTC+05:30"
    assert details["transit_date_utc"] == "24 September 2026"
    assert details["transit_time_utc"] == "4:04 AM UTC"


def test_transit_details_dict_custom_offset_needs_no_shift():
    # A custom transit already expressed in its own local offset (e.g. the
    # Duluth, GA screenshot elsewhere in this engagement, UTC-5): local
    # should reproduce the given wall clock unchanged, and UTC should be
    # correctly derived by subtracting that offset.
    transit_moment = BirthMoment(year=2026, month=9, day=14, hour=23, minute=5, second=0,
                                  utc_offset_hours=-5.0, latitude=33.9566391, longitude=-83.989006)
    details = _transit_details_dict(transit_moment, "Duluth, GA", -5.0)

    assert details["transit_time_local"] == "11:05 PM"
    assert details["transit_timezone_local"] == "UTC-05:00"
    assert details["transit_date_utc"] == "15 September 2026"
    assert details["transit_time_utc"] == "4:05 AM UTC"


def test_transit_details_dict_basis_defaults_to_now_at_birth_location():
    # 2026-09-24, later still again: the client sent screenshots of a real
    # generated PDF asking whether the shown transit was "Local/birthtime
    # or other" -- `source` defaults to "now" for any caller that hasn't
    # been updated to pass it (matches _resolve_natal_and_transit_moments'
    # own default), and the resulting sentence should name the birth
    # location explicitly rather than leaving "local" ambiguous.
    transit_moment = BirthMoment(year=2026, month=9, day=24, hour=4, minute=4, second=0,
                                  utc_offset_hours=0.0, latitude=20.8156, longitude=72.9595)
    details = _transit_details_dict(transit_moment, "Amalsad, Gujarat, India", 5.5)

    assert "transit_basis" in details
    assert "current moment" in details["transit_basis"].lower()
    assert "Amalsad, Gujarat, India" in details["transit_basis"]
    assert "birth location" in details["transit_basis"].lower()


def test_transit_details_dict_basis_names_a_custom_transit():
    transit_moment = BirthMoment(year=2026, month=9, day=14, hour=23, minute=5, second=0,
                                  utc_offset_hours=-5.0, latitude=33.9566391, longitude=-83.989006)
    details = _transit_details_dict(transit_moment, "Duluth, GA", -5.0, source="custom")

    assert "custom" in details["transit_basis"].lower()
    assert "Transit tab" in details["transit_basis"]
    assert "Duluth, GA" in details["transit_basis"]
    # A custom transit's basis sentence should not claim it's the "current
    # moment" -- that phrasing is reserved for the defaulted case.
    assert "current moment" not in details["transit_basis"].lower()


def test_transit_details_dict_basis_falls_back_when_place_is_blank():
    # Mirrors the existing "never blank place" discipline for transit_place
    # itself -- the basis sentence should still read sensibly rather than
    # naming an empty location.
    transit_moment = BirthMoment(year=2026, month=9, day=24, hour=4, minute=4, second=0,
                                  utc_offset_hours=0.0, latitude=20.8156, longitude=72.9595)
    details = _transit_details_dict(transit_moment, "", 5.5, source="custom")
    assert details["transit_basis"] != ""
    assert "the transit location shown below" in details["transit_basis"]


def test_house_and_planet_labels_are_complete_and_real():
    # 2026-09-24, later still: the client sent the real HIT_CALC "LIFE AREA"
    # row (12 house cells + 10 Asc/planet cells), so overview_labels.py now
    # ships that real text instead of the earlier standard-textbook
    # placeholder -- LABELS_ARE_PLACEHOLDER flipped to False. This test was
    # renamed from ..._flagged_placeholder to match; the completeness/
    # em-dash-format checks are unchanged since the real data follows the
    # exact same shape the placeholder data did.
    assert set(HOUSE_LIFE_AREAS.keys()) == set(range(1, 13))
    assert set(PLANET_SIGNIFICATIONS.keys()) == {
        "Asc", "Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"
    }
    for text in HOUSE_LIFE_AREAS.values():
        assert " — " in text, "expected an em-dash label/description split (ccsi_parser.split_life_area)"
    assert LABELS_ARE_PLACEHOLDER is False


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
    # 2026-09-24, later still: transit_place/transit_display_offset_hours
    # now passed explicitly, the way main.py's real endpoint does via
    # _resolve_transit_display_info() -- this is what main.py would resolve
    # for a defaulted (no custom transit) request, i.e. the birth's own
    # place/offset, since transit_moment here is just natal_moment reused.
    result = build_overview_report_pdf(
        _FakeOpenAIClient(), "Test Client", natal_moment, natal_moment,
        birth_place="Amalsad, Gujarat, India",
        transit_place="Amalsad, Gujarat, India",
        transit_display_offset_hours=5.5,
    )

    assert result.pdf_bytes.startswith(b"%PDF")
    assert len(result.pdf_bytes) > 5000  # a real multi-page report, not an empty/broken file
    # 2026-09-24, later still: real HIT_CALC label text is now in place (see
    # test_house_and_planet_labels_are_complete_and_real), so this no longer
    # carries the placeholder flag or the extra placeholder-caveat sentence.
    assert result.labels_are_placeholder is False
    assert "placeholder" not in result.disclaimer.lower()


def test_build_overview_report_pdf_end_to_end_with_custom_transit_source():
    # 2026-09-24, later still again: confirms transit_source threads all the
    # way through build_overview_report_pdf() -> _transit_details_dict()
    # without error for the "custom" case too, not just the default "now".
    natal_moment = BirthMoment(
        year=1973, month=10, day=12, hour=14, minute=55, second=0,
        utc_offset_hours=5.5,
        latitude=20.815615264029468, longitude=72.95947488134223,
    )
    transit_moment = BirthMoment(
        year=2026, month=9, day=14, hour=23, minute=5, second=0,
        utc_offset_hours=-5.0, latitude=33.9566391, longitude=-83.989006,
    )
    result = build_overview_report_pdf(
        _FakeOpenAIClient(), "Test Client", natal_moment, transit_moment,
        birth_place="Amalsad, Gujarat, India",
        transit_place="Duluth, GA",
        transit_display_offset_hours=-5.0,
        transit_source="custom",
    )
    assert result.pdf_bytes.startswith(b"%PDF")
    assert len(result.pdf_bytes) > 5000
