"""Place name -> latitude/longitude/UTC offset lookup.

UPDATE (2026-09-25): production started returning
"Geocoding lookup failed: 429 Client Error: Too many requests" -- Nominatim
enforces a strict 1-request/second policy and, more importantly, judges that
by IP address, not by app. Render (and most other free-tier hosts) puts many
unrelated apps behind a small pool of shared outbound IPs, so this app can
get rate-limited by a *different* app's traffic sharing the same IP, with
nothing wrong in our own request pattern. A single hard-coded provider means
any outage or rate-limit on that one free service takes down every location
lookup on the site (Birth Details, "Same as birth location" unchecked on
Transit, and the chat agent's geocode_place tool). Fixed by trying THREE
independent, well-established, keyless geocoding services in order, falling
through to the next one on any failure (HTTP error, timeout, or no results)
instead of failing the whole request:
  1. Open-Meteo's geocoding API -- free, no key, a generous published free
     quota (no per-second lockstep like Nominatim), and it happens to
     return an IANA timezone name directly. Tried first since it's the
     least likely of the three to be caught in someone else's rate limit.
  2. OpenStreetMap's Nominatim -- the original provider, kept as a real
     fallback (still free, no key, good place-name quality for South Asian
     places specifically, which matters for this client base). Subject to
     the usage policy above (real User-Agent header, kept as-is).
  3. Photon (komoot's public OSM-based geocoder) -- free, no key, different
     infrastructure/IP pool than both of the above, so it's very unlikely
     to be down or rate-limited at the exact same time as both others.

Whichever provider answers, the result still goes through the SAME
downstream pipeline below:
  timezonefinder + Python's stdlib zoneinfo -- (lat, lon) -> an IANA
  timezone name, then that name + the *birth* date/time -> the correct
  historical UTC offset (accounts for DST and historical zone changes,
  which a flat "always +5:30" assumption would get wrong for many
  countries/eras). This is recomputed locally even for the provider
  (Open-Meteo) that already includes a timezone in its response, so the
  offset logic has exactly one source of truth regardless of which
  provider happened to answer.

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
_OPEN_METEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
_PHOTON_URL = "https://photon.komoot.io/api/"
_USER_AGENT = "orbinovastro-ai-app/0.1 (astrology chart tool; contact: client-provided)"
_REQUEST_TIMEOUT_SECONDS = 7

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


def _geocode_via_open_meteo(place: str) -> tuple[float, float, str]:
    resp = requests.get(
        _OPEN_METEO_URL,
        params={"name": place, "count": 1, "language": "en", "format": "json"},
        headers={"User-Agent": _USER_AGENT},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    results = (resp.json() or {}).get("results") or []
    if not results:
        raise GeocodeError(f"No location found for '{place}' (Open-Meteo).")
    top = results[0]
    parts = [top.get("name"), top.get("admin1"), top.get("country")]
    display_name = ", ".join(p for p in parts if p) or place
    return float(top["latitude"]), float(top["longitude"]), display_name


def _geocode_via_nominatim(place: str) -> tuple[float, float, str]:
    resp = requests.get(
        _NOMINATIM_URL,
        params={"q": place, "format": "json", "limit": 1},
        headers={"User-Agent": _USER_AGENT},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise GeocodeError(f"No location found for '{place}' (Nominatim).")
    top = results[0]
    return float(top["lat"]), float(top["lon"]), top.get("display_name", place)


def _geocode_via_photon(place: str) -> tuple[float, float, str]:
    resp = requests.get(
        _PHOTON_URL,
        params={"q": place, "limit": 1},
        headers={"User-Agent": _USER_AGENT},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    features = (resp.json() or {}).get("features") or []
    if not features:
        raise GeocodeError(f"No location found for '{place}' (Photon).")
    top = features[0]
    lon, lat = top["geometry"]["coordinates"]
    props = top.get("properties") or {}
    parts = [props.get("name"), props.get("city"), props.get("state"), props.get("country")]
    seen: list[str] = []
    for p in parts:
        if p and p not in seen:
            seen.append(p)
    display_name = ", ".join(seen) or place
    return float(lat), float(lon), display_name


# Tried in this order; the first provider that returns a result wins. Every
# entry here is a genuinely free, keyless service -- if one of these starts
# requiring an API key or shutting down, replace it here rather than
# reaching for a paid/keyed provider without asking the client first.
#
# NOTE: this stores each provider by FUNCTION NAME (a string), not a direct
# function reference, and looks it up via globals() inside geocode_place()
# below -- on purpose. A tuple of direct references would capture the
# original function objects at import time, so tests patching
# "app.engine.geocode._geocode_via_open_meteo" (the normal, correct way to
# mock a module-level function) would silently have no effect: the loop
# would keep calling the old, un-mocked function object it captured before
# the patch ever ran. Looking the name up fresh on every call is what makes
# that patching actually take effect.
_PROVIDERS = (
    ("Open-Meteo", "_geocode_via_open_meteo"),
    ("Nominatim", "_geocode_via_nominatim"),
    ("Photon", "_geocode_via_photon"),
)


def geocode_place(place: str) -> tuple[float, float, str]:
    """place name -> (latitude, longitude, display_name). Tries each
    provider in _PROVIDERS in turn, falling through to the next on any
    failure (HTTP error, timeout, or no results). Raises GeocodeError,
    with all three providers' failure reasons included, only if every one
    of them failed."""
    if not place or not place.strip():
        raise GeocodeError("Place name is empty.")

    failures: list[str] = []
    for name, func_name in _PROVIDERS:
        provider = globals()[func_name]
        try:
            return provider(place)
        except requests.RequestException as exc:
            failures.append(f"{name}: {exc}")
        except GeocodeError as exc:
            failures.append(str(exc))
        except (KeyError, TypeError, ValueError) as exc:
            # A provider answered but its response shape wasn't what we
            # expected (e.g. a field renamed upstream) -- don't let that
            # crash the whole lookup, just move on to the next provider.
            failures.append(f"{name}: unexpected response ({exc})")

    raise GeocodeError(
        f"Geocoding lookup failed for '{place}' -- all providers unavailable: "
        + "; ".join(failures)
    )


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
