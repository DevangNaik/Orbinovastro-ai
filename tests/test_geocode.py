"""Tests for place -> lat/lon -> UTC offset resolution.

geocode_place() itself makes a real HTTP call to Nominatim, so it's not
unit-tested here (that would make the suite flaky/network-dependent).
Instead: the deterministic parts (timezone lookup + historical UTC offset)
are tested directly, and geocode_and_resolve_offset()'s pipeline logic is
tested with geocode_place() mocked out.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.geocode import (
    GeocodeError,
    timezone_for,
    utc_offset_hours_for,
    geocode_and_resolve_offset,
)


def test_timezone_for_known_city():
    assert timezone_for(28.6139, 77.2090) == "Asia/Kolkata"


def test_utc_offset_matches_ist():
    offset = utc_offset_hours_for("Asia/Kolkata", 1973, 10, 12, 14, 55)
    assert offset == 5.5


def test_utc_offset_is_dst_aware():
    # New York: -4 in summer (EDT), -5 in winter (EST) -- a flat offset
    # would get one of these wrong.
    summer = utc_offset_hours_for("America/New_York", 2020, 7, 1, 12, 0)
    winter = utc_offset_hours_for("America/New_York", 2020, 1, 1, 12, 0)
    assert summer == -4.0
    assert winter == -5.0


def test_geocode_and_resolve_offset_pipeline():
    with patch(
        "app.engine.geocode.geocode_place",
        return_value=(28.6139, 77.2090, "New Delhi, India"),
    ):
        result = geocode_and_resolve_offset("New Delhi", 1973, 10, 12, 14, 55)
        assert result.latitude == 28.6139
        assert result.longitude == 77.2090
        assert result.timezone_name == "Asia/Kolkata"
        assert result.utc_offset_hours == 5.5


def test_geocode_place_empty_string_raises():
    from app.engine.geocode import geocode_place
    try:
        geocode_place("")
        assert False, "expected GeocodeError"
    except GeocodeError:
        pass
