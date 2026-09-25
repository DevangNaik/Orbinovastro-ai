"""Tests for place -> lat/lon -> UTC offset resolution.

geocode_place() itself makes real HTTP calls (to whichever of the three
providers answers first), so the actual network calls aren't unit-tested
here (that would make the suite flaky/network-dependent). Instead: the
deterministic parts (timezone lookup + historical UTC offset) are tested
directly, geocode_and_resolve_offset()'s pipeline logic is tested with
geocode_place() mocked out, and geocode_place()'s own provider-fallback
logic (added 2026-09-25 after Nominatim started 429-ing in production) is
tested by mocking the individual _geocode_via_* provider functions instead.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import requests

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


def test_geocode_place_falls_back_to_nominatim_when_open_meteo_fails():
    """The real-world bug this covers: Open-Meteo (tried first) is down or
    erroring, but Nominatim (tried second) still works -- the lookup should
    still succeed, transparently, with no error surfaced to the caller."""
    from app.engine.geocode import geocode_place

    with patch(
        "app.engine.geocode._geocode_via_open_meteo",
        side_effect=requests.exceptions.HTTPError("429 Client Error: Too many requests"),
    ), patch(
        "app.engine.geocode._geocode_via_nominatim",
        return_value=(27.5530, 76.6346, "Alwar, Rajasthan, India"),
    ):
        lat, lon, display_name = geocode_place("Alwar")
    assert (lat, lon, display_name) == (27.5530, 76.6346, "Alwar, Rajasthan, India")


def test_geocode_place_falls_back_to_photon_when_first_two_fail():
    """Same idea, one provider further: both Open-Meteo and Nominatim fail
    (e.g. both rate-limited, or a shared-IP block hits both at once) --
    Photon, third and last, still resolves the place."""
    from app.engine.geocode import geocode_place

    with patch(
        "app.engine.geocode._geocode_via_open_meteo",
        side_effect=GeocodeError("No location found for 'Alwar' (Open-Meteo)."),
    ), patch(
        "app.engine.geocode._geocode_via_nominatim",
        side_effect=requests.exceptions.HTTPError("429 Client Error: Too many requests"),
    ), patch(
        "app.engine.geocode._geocode_via_photon",
        return_value=(27.5530, 76.6346, "Alwar, Rajasthan, India"),
    ):
        lat, lon, display_name = geocode_place("Alwar")
    assert (lat, lon, display_name) == (27.5530, 76.6346, "Alwar, Rajasthan, India")


def test_geocode_place_raises_with_all_reasons_when_every_provider_fails():
    """When all three free providers are genuinely unavailable, the caller
    still gets one clear GeocodeError -- not a crash -- and the message
    names all three failures so a real outage is diagnosable from a log
    line instead of just 'geocoding failed'."""
    from app.engine.geocode import geocode_place

    with patch(
        "app.engine.geocode._geocode_via_open_meteo",
        side_effect=requests.exceptions.Timeout("timed out"),
    ), patch(
        "app.engine.geocode._geocode_via_nominatim",
        side_effect=requests.exceptions.HTTPError("429 Client Error: Too many requests"),
    ), patch(
        "app.engine.geocode._geocode_via_photon",
        side_effect=GeocodeError("No location found for 'Nowhereville' (Photon)."),
    ):
        try:
            geocode_place("Nowhereville")
            assert False, "expected GeocodeError"
        except GeocodeError as exc:
            message = str(exc)
            assert "Open-Meteo" in message or "timed out" in message
            assert "429" in message
            assert "Nowhereville" in message


def test_geocode_place_first_provider_wins_without_trying_the_rest():
    """The common, healthy-day case: Open-Meteo just works -- Nominatim and
    Photon should never even be called."""
    from app.engine.geocode import geocode_place

    with patch(
        "app.engine.geocode._geocode_via_open_meteo",
        return_value=(28.6139, 77.2090, "New Delhi, Delhi, India"),
    ) as mock_open_meteo, patch(
        "app.engine.geocode._geocode_via_nominatim",
    ) as mock_nominatim, patch(
        "app.engine.geocode._geocode_via_photon",
    ) as mock_photon:
        result = geocode_place("New Delhi")
    assert result == (28.6139, 77.2090, "New Delhi, Delhi, India")
    mock_open_meteo.assert_called_once_with("New Delhi")
    mock_nominatim.assert_not_called()
    mock_photon.assert_not_called()
