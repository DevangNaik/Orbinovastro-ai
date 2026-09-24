"""
Orchestrates the live-computed Overview Report: takes a natal + transit
BirthMoment (the same shape `/api/ccsi` already takes), computes the CCSI
report live via `ccsi.compute_ccsi_report()`, reshapes it into the exact
`parsed` houses/planets structure `overview_report/ccsi_parser.py`'s
`parse_ccsi_matrix()` would have produced from a live Excel read, calls
OpenAI for the interpretation/guidance layer
(`overview_report.overview_narrative.generate_overview_data`), and renders
the finished PDF with the client's own, unmodified
`overview_report.overview_pdf_writer.build_pdf()`.

STAGE 1 of the Overview Report port (see the project roadmap doc's
"Overview Report pipeline audited" entry, 2026-09-24): produces the core
5-part Life Balance Index report (Executive Assessment, Table 1 Houses,
Table 2 Planets, Table 3 Strategic Focus, Table 4 Scorecard, Conclusion +
Core Message) plus the cover/Client Information front matter -- exactly
what `build_pdf()` renders when its optional `kundli_chart_data`/
`troubles_data`/`south_indian_charts` arguments are omitted, its own
already-proven degrade path (see `overview_pdf_writer.py`'s own
`test_merged_pipeline.py`, in the original `overview_report/` folder). The
Kundli chart tables, Troubles & Misfortune page, and South Indian
divisional charts (Stage 2) are a separate, much larger, not-yet-started
audit -- see the roadmap doc -- and are deliberately left out of this
function rather than guessed at.

UPDATE (2026-09-24, later still): the one remaining Stage 1 gap -- the
house life-area / planet-signification label TEXT this function feeds into
the report -- is now the client's own real `HIT_CALC` "LIFE AREA" wording
(`overview_labels.py`'s `LABELS_ARE_PLACEHOLDER` is now False). Every
`OverviewReportResult` this function returns now reports
`labels_are_placeholder=False` and the extra placeholder caveat below is
skipped -- no code change was needed here to pick that up, since this
function only ever reads `overview_labels.py`'s dicts/flag, never a
hardcoded copy of them.

UPDATE (2026-09-24, later still): fixed a real Client Information page bug
the client caught from a real generated PDF -- the Transit Information
block showed "Transit Place: Not available" and a "Transit Time"/"Transit
Timezone" that were silently UTC (e.g. "4:04 AM" / "UTC+00:00") even though
the transit had defaulted to the birth location. Root cause: when no custom
transit is given, `main._resolve_natal_and_transit_moments()` builds the
transit moment via `transit.now_as_birth_moment()`, which always stores the
current instant as a UTC wall-clock (utc_offset_hours=0.0) -- correct for
computing planetary positions, but wrong to display as-is, since an end
user does not think in UTC and was never told this was UTC. Two fixes,
both in `_transit_details_dict` below: (1) the transit's location is now
resolved by the caller (`main.py`) to the birth place when defaulted, or
the transit's own place/coordinates when a custom transit is given --
never blank; (2) the report now shows BOTH the local time (at the
resolved location's own UTC offset) and the UTC time explicitly labeled as
such, rather than showing one ambiguous, unlabeled offset. See
`TRANSIT_DETAIL_FIELDS` in `overview_report/overview_pdf_writer.py` for
the resulting field list -- that list is plain declarative (key, label)
pairs, so no PDF-rendering code needed to change.
"""
from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime as _datetime
from datetime import timedelta as _timedelta
from pathlib import Path

from openai import OpenAI

from .ccsi import CCSI_DISCLAIMER, compute_ccsi_report
from .ephemeris import BirthMoment
from .overview_report.ccsi_parser import PLANET_CODES, PLANET_NAMES
from .overview_report.overview_labels import (
    HOUSE_LIFE_AREAS,
    LABELS_ARE_PLACEHOLDER,
    PLANET_SIGNIFICATIONS,
)
from .overview_report.overview_narrative import generate_overview_data
from .overview_report.overview_pdf_writer import build_pdf

HOUSE_COUNT = 12


def safe_filename(value: str) -> str:
    """Creates a safe filename, same rule as the original generate_overview_
    report.py's own safe_filename()."""
    value = str(value or "Client").strip()
    value = re.sub(r'[<>:"/\\|?*]+', "_", value)
    value = re.sub(r"\s+", "_", value)
    return value[:100] or "Client"


def build_parsed_from_ccsi(report) -> dict:
    """Reshapes a `ccsi.CcsiReport` into the exact `parsed` structure
    `ccsi_parser.parse_ccsi_matrix()` would have produced from a live Excel
    read of `HIT_CALC!G185:AE204` -- same field names, same value
    semantics (every number is `hit_calc.py`'s already-132/132-validated
    output, not re-derived here), just assembled from live objects instead
    of parsed cell text. The `life_area`/`signification` label text comes
    from `overview_labels.py` (see its docstring re: real vs. placeholder
    status)."""
    houses = []
    for house_num in range(1, HOUSE_COUNT + 1):
        houses.append({
            "house": house_num,
            "life_area": HOUSE_LIFE_AREAS.get(house_num, f"House {house_num}"),
            "L": report.l_net.houses[house_num],
            "LT": report.lt_net.houses[house_num],
            "TT": report.tt_net.houses[house_num],
            "L_neg": report.l_negative.houses[house_num],
            "LT_neg": report.lt_negative.houses[house_num],
            "TT_neg": report.tt_negative.houses[house_num],
        })

    planets = []
    for code in PLANET_CODES:
        planets.append({
            "code": code,
            "name": PLANET_NAMES[code],
            "signification": PLANET_SIGNIFICATIONS.get(code, code),
            "L": report.l_net.columns[code],
            "LT": report.lt_net.columns[code],
            "TT": report.tt_net.columns[code],
            "L_neg": report.l_negative.columns[code],
            "LT_neg": report.lt_negative.columns[code],
            "TT_neg": report.tt_negative.columns[code],
        })

    return {"houses": houses, "planets": planets}


def _format_utc_offset(hours: float) -> str:
    sign = "+" if hours >= 0 else "-"
    total_minutes = int(round(abs(hours) * 60))
    return f"UTC{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _hour_12h(hour_24: int) -> tuple[int, str]:
    hour12 = hour_24 % 12 or 12
    ampm = "AM" if hour_24 < 12 else "PM"
    return hour12, ampm


def _birth_details_dict(moment: BirthMoment, place: str) -> dict:
    dt = _date(moment.year, moment.month, moment.day)
    hour12, ampm = _hour_12h(moment.hour)
    return {
        "date_of_birth": dt.strftime("%d %B %Y"),
        "time_of_birth": f"{hour12}:{moment.minute:02d} {ampm}",
        "place_of_birth": place or "",
        "timezone": _format_utc_offset(moment.utc_offset_hours),
        "latitude": f"{moment.latitude:.4f}",
        "longitude": f"{moment.longitude:.4f}",
    }


def _shift_wall_clock(moment: BirthMoment, delta_hours: float) -> _datetime:
    """Returns `moment`'s own wall-clock date/time shifted by `delta_hours`
    (handles day/month/year rollover via timedelta, e.g. a UTC evening
    moment shifting into the next day in a +12 offset). Used to convert
    between two UTC-offset representations of the SAME instant: shifting by
    (target_offset - moment.utc_offset_hours) gives that instant's wall
    clock at target_offset."""
    dt = _datetime(moment.year, moment.month, moment.day, moment.hour, moment.minute)
    return dt + _timedelta(hours=delta_hours)


def _transit_details_dict(moment: BirthMoment, place: str, display_offset_hours: float) -> dict:
    """Builds the Transit Information table's fields, showing BOTH the
    local time at `display_offset_hours` (the transit's actual location --
    the birth location when defaulted, or the custom transit's own location
    when one was given) and the UTC time, explicitly labeled as such --
    see this module's UPDATE (2026-09-24, later still) docstring note for
    why both are shown rather than one ambiguous, unlabeled time. `moment`
    itself may be stored at any offset (its own `utc_offset_hours`); both
    displayed times are derived from the same underlying instant."""
    local_dt = _shift_wall_clock(moment, display_offset_hours - moment.utc_offset_hours)
    utc_dt = _shift_wall_clock(moment, -moment.utc_offset_hours)

    local_hour12, local_ampm = _hour_12h(local_dt.hour)
    utc_hour12, utc_ampm = _hour_12h(utc_dt.hour)

    return {
        "transit_date_local": local_dt.strftime("%d %B %Y"),
        "transit_time_local": f"{local_hour12}:{local_dt.minute:02d} {local_ampm}",
        "transit_place": place or "",
        "transit_timezone_local": _format_utc_offset(display_offset_hours),
        "transit_date_utc": utc_dt.strftime("%d %B %Y"),
        "transit_time_utc": f"{utc_hour12}:{utc_dt.minute:02d} {utc_ampm} UTC",
    }


@dataclass(frozen=True)
class OverviewReportResult:
    pdf_bytes: bytes
    labels_are_placeholder: bool
    disclaimer: str


def build_overview_report_pdf(
    client: OpenAI,
    client_name: str,
    natal_moment: BirthMoment,
    transit_moment: BirthMoment,
    birth_place: str = "",
    transit_place: str = "",
    transit_display_offset_hours: float | None = None,
) -> OverviewReportResult:
    """Computes the CCSI report live, calls OpenAI for the interpretation/
    guidance layer, and renders the Stage-1 core Overview Report PDF (no
    Kundli chart/Troubles & Misfortune/South Indian chart pages -- see
    module docstring).

    `transit_display_offset_hours`: which UTC offset to show the transit's
    LOCAL time at (see `_transit_details_dict`) -- the caller (`main.py`)
    resolves this to the birth's own offset when the transit defaulted to
    the birth location, or the custom transit's own offset otherwise, since
    `transit_moment` itself is always stored at whatever offset it happened
    to be built with (0.0/UTC for the "now" default -- see this module's
    2026-09-24 UPDATE docstring note). Defaults to `transit_moment`'s own
    offset if not given, which reproduces the pre-fix behavior for any
    caller that hasn't been updated to pass this."""
    ccsi_report = compute_ccsi_report(natal_moment, transit_moment)
    parsed = build_parsed_from_ccsi(ccsi_report)
    report_data = generate_overview_data(client, client_name, parsed)

    if transit_display_offset_hours is None:
        transit_display_offset_hours = transit_moment.utc_offset_hours

    birth_details = _birth_details_dict(natal_moment, birth_place)
    transit_details = _transit_details_dict(transit_moment, transit_place, transit_display_offset_hours)

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "overview_report.pdf"
        build_pdf(
            report_data, parsed, client_name, output_path,
            birth_details=birth_details, transit_details=transit_details,
        )
        pdf_bytes = output_path.read_bytes()

    disclaimer = CCSI_DISCLAIMER
    if LABELS_ARE_PLACEHOLDER:
        disclaimer += (
            " NOTE: the house/planet life-area and signification wording "
            "used in this report is currently STANDARD textbook text, not "
            "yet the client's own HIT_CALC sheet wording (that exact text "
            "was never captured) -- see engine/overview_report/"
            "overview_labels.py. This report's numbers are real and "
            "validated; this specific wording is a placeholder pending "
            "the client's own text."
        )

    return OverviewReportResult(
        pdf_bytes=pdf_bytes,
        labels_are_placeholder=LABELS_ARE_PLACEHOLDER,
        disclaimer=disclaimer,
    )
