"""
Tests for `main._resolve_transit_display_info()` -- the fix for a real bug
the client caught from a generated Overview Report PDF's Client Information
page: the Transit Information block showed "Transit Place: Not available"
and an unlabeled, silently-UTC time/timezone even when the transit had
defaulted to the birth location. This file checks the three scenarios that
function has to resolve correctly: no custom transit (default to the birth
location's own place/offset), a custom transit WITH a place name, and a
custom transit WITHOUT one (falls back to coordinates, never blank).

Does not re-test the local/UTC time-conversion arithmetic itself -- see
test_overview_report.py's `_transit_details_dict`/`_shift_wall_clock` tests
for that; this file only checks which (place, offset) pair gets chosen.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.ephemeris import BirthMoment
from app.main import _resolve_transit_display_info
from app.models import BirthDetailsIn, CcsiTransitDetailsIn

BIRTH = BirthDetailsIn(
    name="Devang Naik", year=1973, month=10, day=12, hour=14, minute=55, second=0,
    utc_offset_hours=5.5, latitude=20.815615264029468, longitude=72.95947488134223,
    place="Amalsad, Gujarat, India",
)

# A stand-in "now" transit moment, as _resolve_natal_and_transit_moments
# would build it via now_as_birth_moment() -- always UTC offset 0.0 -- for
# the default (no custom transit) scenario.
DEFAULTED_TRANSIT_MOMENT = BirthMoment(
    year=2026, month=9, day=24, hour=4, minute=4, second=0,
    utc_offset_hours=0.0, latitude=BIRTH.latitude, longitude=BIRTH.longitude,
)


def test_defaulted_transit_uses_birth_place_and_offset():
    place, offset = _resolve_transit_display_info(BIRTH, None, DEFAULTED_TRANSIT_MOMENT)
    assert place == "Amalsad, Gujarat, India"
    assert offset == 5.5


def test_custom_transit_with_place_uses_its_own_place_and_offset():
    transit = CcsiTransitDetailsIn(
        year=2026, month=9, day=14, hour=23, minute=5,
        utc_offset_hours=-5.0, latitude=33.9566391, longitude=-83.989006,
        place="Duluth, GA",
    )
    transit_moment = BirthMoment(
        year=2026, month=9, day=14, hour=23, minute=5, second=0,
        utc_offset_hours=-5.0, latitude=33.9566391, longitude=-83.989006,
    )
    place, offset = _resolve_transit_display_info(BIRTH, transit, transit_moment)
    assert place == "Duluth, GA"
    assert offset == -5.0


def test_custom_transit_without_place_falls_back_to_coordinates_not_blank():
    transit = CcsiTransitDetailsIn(
        year=2026, month=9, day=14, hour=23, minute=5,
        utc_offset_hours=-5.0, latitude=33.9566391, longitude=-83.989006,
        # place omitted -- must not come back blank/"Not available"
    )
    transit_moment = BirthMoment(
        year=2026, month=9, day=14, hour=23, minute=5, second=0,
        utc_offset_hours=-5.0, latitude=33.9566391, longitude=-83.989006,
    )
    place, offset = _resolve_transit_display_info(BIRTH, transit, transit_moment)
    assert place != ""
    assert "33.9566" in place and "-83.9890" in place
    assert offset == -5.0


def test_defaulted_transit_without_birth_place_falls_back_to_coordinates():
    birth_no_place = BIRTH.model_copy(update={"place": ""})
    place, offset = _resolve_transit_display_info(birth_no_place, None, DEFAULTED_TRANSIT_MOMENT)
    assert place != ""
    assert "20.8156" in place
    assert offset == 5.5
