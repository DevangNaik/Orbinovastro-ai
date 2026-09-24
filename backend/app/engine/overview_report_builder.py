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

One real gap even for Stage 1: the house life-area / planet-signification
label TEXT this function feeds into the report is currently
`overview_labels.py`'s STANDARD placeholder wording, not the client's own
sheet text (never captured during the CCSI validation rounds) -- see that
module's docstring. Every `OverviewReportResult` this function returns
therefore carries `labels_are_placeholder=True` until that module is
updated with the client's real data.
"""
from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from datetime import date as _date
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
    from `overview_labels.py` (see its docstring re: placeholder status)."""
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


def _transit_details_dict(moment: BirthMoment, place: str) -> dict:
    dt = _date(moment.year, moment.month, moment.day)
    hour12, ampm = _hour_12h(moment.hour)
    return {
        "transit_date": dt.strftime("%d %B %Y"),
        "transit_time": f"{hour12}:{moment.minute:02d} {ampm}",
        "transit_place": place or "",
        "transit_timezone": _format_utc_offset(moment.utc_offset_hours),
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
) -> OverviewReportResult:
    """Computes the CCSI report live, calls OpenAI for the interpretation/
    guidance layer, and renders the Stage-1 core Overview Report PDF (no
    Kundli chart/Troubles & Misfortune/South Indian chart pages -- see
    module docstring)."""
    ccsi_report = compute_ccsi_report(natal_moment, transit_moment)
    parsed = build_parsed_from_ccsi(ccsi_report)
    report_data = generate_overview_data(client, client_name, parsed)

    birth_details = _birth_details_dict(natal_moment, birth_place)
    transit_details = _transit_details_dict(transit_moment, transit_place)

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
