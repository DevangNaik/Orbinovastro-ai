"""Place name -> latitude/longitude/UTC offset lookup.

Two independent, well-established public building blocks, chained together:
  1. OpenStreetMap's Nominatim geocoding API -- free, no API key, for a
     place name -> (lat, lon). Subject to Nominatim's usage policy (a real
     User-Agent header, and callers are expected to keep request volume
     reasonable -- fine for this app's interactive, one-lookup-per-user
     pattern).
  2. timezonefinder + Python's stdlib zoneinfo -- (lat, lon) -> an IANA
     timezone name, then that name + the *birth* date/time -> the correct
     historical UTC offset (accounts for DST and historical zone changes,
     which a flat "always +5:30" assumption would get wrong for many
     countries/eras).

This is purely geographic/astronomical convenience plumbing -- no
astrology judgment involved, so it carries none of the "beta" caveats the
KP significators module does.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from timezonefinder import TimezoneFinder

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "orbinovastro-ai-app/0.1 (astrology chart tool; contact: client-provided)"

_tf = TimezoneFinder()


class GeocodeError(Exception):
    pass


@dataclass
class GeocodeResult:
    place: str
    latitude: float
    longitude: float
    timezone_name: str | None
    utc_offset_hours: float | None


def geocode_place(place: str) -> tuple[float, float, str]:
    """place name -> (latitude, longitude, display_name). Raises
    GeocodeError if nothing is found or the request fails."""
    if not place or not place.strip():
        raise GeocodeError("Place name is empty.")
    try:
        resp = requests.get(
            _NOMINATIM_URL,
            params={"q": place, "format": "json", "limit": 1},
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
    except requests.RequestException as exc:
        raise GeocodeError(f"Geocoding lookup failed: {exc}") from exc

    if not results:
        raise GeocodeError(f"No location found for '{place}'.")

    top = results[0]
    return float(top["lat"]), float(top["lon"]), top.get("display_name", place)


def timezone_for(latitude: float, longitude: float) -> str | None:
    """(lat, lon) -> IANA timezone name, e.g. 'Asia/Kolkata', or None if
    the point doesn't resolve to a known timezone (open ocean, etc.)."""
    return _tf.timezone_at(lat=latitude, lng=longitude)


def utc_offset_hours_for(
    timezone_name: str, year: int, month: int, day: int, hour: int = 12, minute: int = 0,
) -> float:
    """The UTC offset (hours, e.g. 5.5) that `timezone_name` actually used
    at this specific local date/time -- correct for historical DST and
    zone-boundary changes, not just today's offset."""
    dt = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(timezone_name))
    offset = dt.utcoffset()
    if offset is None:
        raise GeocodeError(f"Could not resolve a UTC offset for {timezone_name}.")
    return offset.total_seconds() / 3600.0


def geocode_and_resolve_offset(
    place: str, year: int, month: int, day: int, hour: int = 12, minute: int = 0,
) -> GeocodeResult:
    """Full pipeline: place name -> lat/lon -> timezone -> historical UTC
    offset for the given birth date/time. If a timezone can't be resolved
    (rare -- e.g. a point over open ocean), latitude/longitude are still
    returned with timezone_name/utc_offset_hours as None so the caller can
    ask the user to enter the offset manually."""
    lat, lon, display_name = geocode_place(place)
    tz_name = timezone_for(lat, lon)
    offset = None
    if tz_name:
        try:
            offset = utc_offset_hours_for(tz_name, year, month, day, hour, minute)
        except GeocodeError:
            offset = None
    return GeocodeResult(
        place=display_name, latitude=lat, longitude=lon,
        timezone_name=tz_name, utc_offset_hours=offset,
    )
