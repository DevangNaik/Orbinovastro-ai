"""End-to-end tests for POST /api/transit -- through the REAL FastAPI route
and its `response_model=TransitOut` Pydantic serialization, same discipline
as test_api_chart.py (see that file's own docstring for why route-level
tests exist separately from testing engine/transit.py's functions directly).

UPDATE (2026-09-25): added alongside a real fix -- TransitDetailsIn never had
latitude/longitude/place fields, so a custom transit moment was always
computed at the BIRTH's own coordinates even if the visitor was somewhere
else entirely. api_transit() now shares the same
_resolve_natal_and_transit_moments/_resolve_transit_display_info helpers
/api/ccsi and /api/overview-report already used for exactly this problem.
These tests cover: the new location-override behavior, that omitting it is
still fully backward compatible (defaults to the birth location, matching
the endpoint's original-only behavior), and that transit_place/
transit_utc_offset_hours always resolve to something real, never blank.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Same real reference birth used throughout the other API-route test files.
_BIRTH = {
    "year": 1973, "month": 10, "day": 12, "hour": 14, "minute": 55, "second": 0,
    "utc_offset_hours": 5.5, "latitude": 20.815615264029468, "longitude": 72.95947488134223,
    "place": "Amalsad, Gujarat, India",
}


def _post_transit(body: dict) -> dict:
    response = client.post("/api/transit", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_no_transit_given_defaults_to_birth_location_backward_compatible():
    data = _post_transit({"birth": _BIRTH})
    assert data["transit_time_source"] == "now (UTC)"
    assert data["transit_place"] == "Amalsad, Gujarat, India"
    assert data["transit_utc_offset_hours"] == 5.5
    assert len(data["planets"]) == 9  # classical grahas only, same as before


def test_custom_transit_without_location_still_falls_back_to_birth_location():
    """Backward compatible: a custom date/time with no lat/long/place given
    (the only shape the old TransitDetailsIn could ever send) must compute
    exactly as before -- at the birth's own coordinates."""
    body = {
        "birth": _BIRTH,
        "transit": {
            "year": 2026, "month": 9, "day": 24, "hour": 19, "minute": 53,
            "utc_offset_hours": -4.0,
        },
    }
    data = _post_transit(body)
    assert data["transit_time_source"] == "custom"
    # No place given on a custom transit -> falls back to its own
    # coordinates as display text (never the birth's place, since the
    # visitor explicitly gave a different moment/offset).
    assert data["transit_place"] == f"{_BIRTH['latitude']:.4f}, {_BIRTH['longitude']:.4f}"
    assert data["transit_utc_offset_hours"] == -4.0


def test_custom_transit_with_its_own_location_overrides_birth_coordinates():
    body = {
        "birth": _BIRTH,
        "transit": {
            "year": 2026, "month": 9, "day": 24, "hour": 19, "minute": 53,
            "utc_offset_hours": -4.0,
            "latitude": 33.9566391, "longitude": -83.989006,
            "place": "Duluth, GA",
        },
    }
    data = _post_transit(body)
    assert data["transit_place"] == "Duluth, GA"
    assert data["transit_utc_offset_hours"] == -4.0
    # NOTE: this engine's planetary longitudes are geocentric (see
    # ephemeris.compute_planet -- takes only Julian day + ayanamsa mode, no
    # lat/long), so overriding the transit's location does NOT change any
    # planet's computed longitude/sign/nakshatra for the same UTC instant --
    # only the display fields above (transit_place/transit_utc_offset_hours)
    # and, if this endpoint ever exposes the transit's OWN ascendant/houses
    # in the future, that would change too. Not asserting a longitude
    # difference here on purpose -- there deliberately isn't one.


def test_custom_transit_missing_required_fields_returns_400():
    body = {"birth": _BIRTH, "transit": {"year": 2026}}  # month/day/hour/minute missing
    response = client.post("/api/transit", json=body)
    assert response.status_code == 400


def test_transit_place_never_blank_even_without_any_place_names():
    birth_no_place = dict(_BIRTH)
    birth_no_place["place"] = ""
    data = _post_transit({"birth": birth_no_place})
    assert data["transit_place"] != ""
    assert "20.8156" in data["transit_place"]
