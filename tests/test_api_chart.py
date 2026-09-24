"""End-to-end tests for POST /api/chart -- through the REAL FastAPI route and
its `response_model=ChartOut` Pydantic serialization, not just chart_to_dict()
directly.

UPDATE (2026-09-24, later still again): added after a real production bug --
chart_to_dict() (engine/chart.py) was correctly extended this session with
the Ascendant's degree_in_sign/nakshatra/nakshatra_lord/pada/meaning/flags/
aspected_by and each planet's flags/aspects/aspected_by, and every unit test
in test_chart_narrative.py (which calls chart_to_dict() directly) passed.
But `/api/chart`'s route in main.py wraps that dict in `ChartOut(**data)`,
and ChartOut.ascendant was still typed as the OLD `HouseOut` model (no
Ascendant-specific fields at all) while `PlanetOut` had never been given
`flags`/`aspects`/`aspected_by` fields either. Pydantic's default behavior
on `SomeModel(**data)` is to silently ignore any keys in `data` that aren't
declared fields -- so the new data was computed correctly, sent into
`ChartOut(**data)`, and silently thrown away before ever reaching the
client. This shipped and was git-pushed and deployed to production with no
test catching it, because nothing in the test suite ever went through the
real HTTP route + response_model layer -- only through chart_to_dict()'s
raw dict return value, which was always correct.

These tests exist specifically to close that gap: assert on the actual JSON
the live route would send a client, not on the intermediate dict.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Same real reference chart used throughout test_chart_narrative.py.
_REFERENCE_BODY = {
    "year": 1973, "month": 10, "day": 12, "hour": 14, "minute": 55, "second": 0,
    "utc_offset_hours": 5.5, "latitude": 20.815615264029468, "longitude": 72.95947488134223,
}


def _post_chart(body: dict = _REFERENCE_BODY) -> dict:
    response = client.post("/api/chart", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_api_chart_ascendant_carries_degree_nakshatra_pada_and_meaning_over_http():
    data = _post_chart()
    asc = data["ascendant"]
    for key in ("degree_in_sign", "nakshatra", "nakshatra_lord", "pada", "meaning", "flags", "aspected_by"):
        assert key in asc, f"ascendant.{key} missing from the real /api/chart HTTP response"
    assert asc["nakshatra"] == "Shravana"
    assert asc["pada"] == 4


def test_api_chart_planets_carry_flags_aspects_and_aspected_by_over_http():
    data = _post_chart()
    for planet in data["planets"]:
        for key in ("flags", "aspects", "aspected_by"):
            assert key in planet, (
                f"{planet['code']}.{key} missing from the real /api/chart HTTP response "
                "-- likely stripped by ChartOut/PlanetOut's Pydantic schema"
            )


def test_api_chart_jupiter_is_flagged_debilitated_over_http():
    data = _post_chart()
    jupiter = next(p for p in data["planets"] if p["code"] == "Ju")
    assert "Debilitated" in jupiter["flags"]


def test_api_chart_mars_special_aspect_is_not_mutual_over_http():
    data = _post_chart()
    mars = next(p for p in data["planets"] if p["code"] == "Ma")
    venus = next(p for p in data["planets"] if p["code"] == "Ve")
    mars_aspects_venus = any(a["code"] == "Ve" for a in mars["aspects"])
    venus_aspects_mars = any(a["code"] == "Ma" for a in venus["aspects"])
    assert mars_aspects_venus
    assert not venus_aspects_mars


def test_api_chart_response_shape_matches_chart_to_dict_exactly():
    """The HTTP response, once parsed back to comparable primitives, should
    carry every key chart_to_dict() itself produces -- not a subset. This is
    the general form of the bug: any future field added to chart_to_dict()
    but not to models.py's ChartOut/PlanetOut/AscendantOut would silently
    vanish the same way, so this test enumerates the full key sets rather
    than just the specific fields from this round's bug."""
    from app.engine.chart import build_chart_from_fields, chart_to_dict

    chart = build_chart_from_fields(**_REFERENCE_BODY)
    expected = chart_to_dict(chart)
    actual = _post_chart()

    assert set(expected["ascendant"].keys()) <= set(actual["ascendant"].keys()), (
        "ascendant fields present in chart_to_dict() but missing from the live HTTP "
        f"response: {set(expected['ascendant'].keys()) - set(actual['ascendant'].keys())}"
    )
    expected_planet_keys = set(expected["planets"][0].keys())
    actual_planet_keys = set(actual["planets"][0].keys())
    assert expected_planet_keys <= actual_planet_keys, (
        "planet fields present in chart_to_dict() but missing from the live HTTP "
        f"response: {expected_planet_keys - actual_planet_keys}"
    )
