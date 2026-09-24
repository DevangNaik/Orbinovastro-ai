"""
Renders the ORBINOVASTRO(tm) Life Balance Index report directly as a PDF,
via ReportLab -- no Excel COM involved anywhere in this path.

2026-09-08: this replaces overview_excel_writer.py's Excel-writing step.
Five separate attempts to make Excel's win32com Range.Characters() rich-
text API behave reliably on the client's machine all failed in different
ways (full history in this project's production log) -- the client asked
to drop the Excel-writing step entirely and just produce the PDF directly.
This module rebuilds the exact same 5-part report structure (Executive
Assessment + Legend, Table 1 Houses, Table 2 Planets, Table 3 Strategic
Focus Areas, Table 4 Scorecard, Conclusion + Core Message) as a PDF using
ReportLab -- a pure Python library with no COM/dispatch-mode ambiguity of
any kind, and (unlike the old Excel-COM path) fully testable end-to-end on
this project's own Linux test environment, not just reasoned about.

2026-09-24: vendored into the AI App's backend (`engine/overview_report/`)
unchanged except for converting its three sibling-module imports
(`ccsi_parser`/`kundli_chart`/`lbi_legend`) to relative package imports --
no rendering logic touched. This lets `build_pdf()` be called directly
from a live FastAPI request instead of only from the original xlwings/
Excel-COM script (see `engine/overview_report_builder.py`).
"""

from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from pypdf import PdfReader, PdfWriter

from .ccsi_parser import split_karaka, split_life_area
from .kundli_chart import (
    build_kundli_chart_section,
    build_planetary_characteristics_section,
    build_south_indian_charts_section,
    build_troubles_misfortune_section,
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .lbi_legend import (
    ACRONYM_LEGEND_ROWS,
    ASSESSMENT_LAYERS_ROWS,
    SCORE_LEGEND_ROWS,
    TIER_CIRCLES,
    score_bracket,
)

# ---------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------
# DejaVu Sans is embedded (looked up next to the script -- never via a
# system font path) specifically because it carries the U+25CF "BLACK
# CIRCLE" glyph (chr(0x25CF)) used for every score/tier indicator.
# ReportLab's built-in Helvetica/Times fonts do NOT include this glyph --
# the same class of problem this project's `pdf` skill warns about for
# Unicode super/subscripts on base-14 fonts (renders as a blank box or
# nothing at all). Embedding the font makes the circles render correctly
# regardless of what's installed on the machine that opens the finished PDF.
#
# 2026-09-15: "There should not be any reference to KPStellar directory it
# should be now new structure" -- the client's new ORBINOVASTRO workspace
# keeps shared assets (these fonts, the cover/border artwork below) in a
# sibling `assets\` folder next to `scripts\` (where this file now lives),
# rather than alongside the .py files as before. Prefer that layout when
# present; fall back to this script's own directory otherwise, so a local
# dev/test checkout that still keeps assets alongside the script (as this
# project's own test scripts do) keeps working unchanged.
_SCRIPT_DIR = Path(__file__).resolve().parent
_ASSETS_DIR = _SCRIPT_DIR.parent / "assets"
if not _ASSETS_DIR.is_dir():
    _ASSETS_DIR = _SCRIPT_DIR

pdfmetrics.registerFont(TTFont("DejaVuSans", str(_ASSETS_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(_ASSETS_DIR / "DejaVuSans-Bold.ttf")))

CIRCLE = "●"  # ●

# ---------------------------------------------------------------------
# Front-matter artwork (cover page + Client Information page background)
# ---------------------------------------------------------------------
# 2026-09-08: the client asked for the same branded cover + client/birth
# details page used on ORBINOVASTRO's other reports (the reference PDF
# this project has used since the start, see overview_excel_writer.py's
# original docstring). Both images live in _ASSETS_DIR, same resolution
# rule as the fonts above.
_COVER_IMAGE_PATH = _ASSETS_DIR / "cover_page.png"
_BORDER_BG_IMAGE_PATH = _ASSETS_DIR / "page_border_bg.png"

# 2026-09-08: "All pages should have same golden borders" -- every page
# (including the report body) now carries the same gold border artwork.
#
# 2026-09-08 (later same day): "Use only portrait the border is designed
# for portrait" -- the client asked to drop landscape entirely rather than
# use a rotated version of the border artwork, so the WHOLE document (cover,
# Client Information, Kundli page, and the report body) is now portrait A4,
# and every page uses the one original portrait border image directly, with
# no rotation needed. (The rotated `page_border_bg_landscape.png` asset from
# the landscape-era version of this fix is no longer referenced here -- left
# in place alongside the other files rather than deleted, harmless either
# way.)


def _draw_page_border(canvas_obj, doc) -> None:
    """onFirstPage/onLaterPages callback: draws the gold border behind every
    page of a portrait document (the report body, and the Kundli page)."""
    if _BORDER_BG_IMAGE_PATH.exists():
        canvas_obj.saveState()
        canvas_obj.drawImage(str(_BORDER_BG_IMAGE_PATH), 0, 0,
                              width=doc.pagesize[0], height=doc.pagesize[1],
                              preserveAspectRatio=False, anchor="c")
        canvas_obj.restoreState()


def _build_bordered_kundli_page(excel_page, page_size) -> "PageObject":
    """Stamps this report's own gold border underneath one page that
    arrived as its own separate PDF (Excel's native Kundli chart export --
    see build_pdf()'s chart_pdf branch), and scales/centers that page onto
    page_size if it isn't already that exact size.

    2026-09-15: client: "border is not visible" -- the raw Excel export
    was being appended straight into the document, bypassing
    _draw_page_border() entirely (that callback only runs for pages built
    through this module's own SimpleDocTemplate flows), so the Kundli
    page(s) had no border at all. Separately (found while fixing this, not
    reported by the client): Excel's own default paper size on this
    client's machine exports at US Letter (612x792pt) while the rest of
    this report is A4 (595.28x841.89pt) -- so the Kundli page was also a
    visibly different size/shape from every other page. Both are fixed
    here: draw the border at this report's real page_size, then scale the
    Excel page to fit centered within it rather than pasting it in at its
    own native size."""
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=page_size)
    if _BORDER_BG_IMAGE_PATH.exists():
        c.drawImage(str(_BORDER_BG_IMAGE_PATH), 0, 0,
                    width=page_size[0], height=page_size[1],
                    preserveAspectRatio=False, anchor="c")
    c.showPage()
    c.save()
    buf.seek(0)
    bordered_page = PdfReader(buf).pages[0]

    excel_w = float(excel_page.mediabox.width)
    excel_h = float(excel_page.mediabox.height)
    scale = min(page_size[0] / excel_w, page_size[1] / excel_h)
    tx = (page_size[0] - excel_w * scale) / 2
    ty = (page_size[1] - excel_h * scale) / 2
    bordered_page.merge_transformed_page(
        excel_page, (scale, 0, 0, scale, tx, ty)
    )
    return bordered_page

# ---------------------------------------------------------------------
# Colors (plain RGB -- reportlab, unlike the old Excel writer, needs no
# BGR packing)
# ---------------------------------------------------------------------

def rgb(r, g, b):
    return colors.Color(r / 255, g / 255, b / 255)


TITLE_NAVY = rgb(21, 43, 82)
SUBHEAD_BLUE = rgb(31, 96, 156)
BLACK = colors.black
WHITE = colors.white
GREY_LINE = rgb(150, 150, 150)

GREEN = rgb(0, 140, 51)
YELLOW = rgb(191, 143, 0)
RED = rgb(192, 0, 0)
TIER_COLOR = {"green": GREEN, "yellow": YELLOW, "red": RED}

HILITE_GREEN = rgb(146, 255, 145)
HILITE_YELLOW = rgb(255, 255, 0)
HILITE = {"green": HILITE_GREEN, "yellow": HILITE_YELLOW}


# ---------------------------------------------------------------------
# Text markup helpers
# ---------------------------------------------------------------------

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

# 2026-09-16: "square blocks in the middle of the document text" -- the AI
# model occasionally generates typographic Unicode characters (most often
# U+2011 NON-BREAKING HYPHEN inside compound words like "self-presentation"
# or "high-risk") that aren't in the WinAnsiEncoding glyph table this
# report's fonts (Helvetica/DejaVuSans) actually render. ReportLab silently
# draws those as a missing-glyph box, and a later pdftotext extraction of
# that same broken glyph comes back as a literal "■" BLACK SQUARE --
# confirmed by extracting a real generated report and checking the exact
# codepoint at each corrupted spot. Unicode NFKC normalization folds a few
# of these down via their compatibility <noBreak> mappings (e.g. U+2011 ->
# U+2010), but the folded form (plain U+2010 HYPHEN) still isn't in
# WinAnsiEncoding either, so an explicit map to a plain ASCII "-" (or other
# safe equivalent) is needed after normalizing.
_UNICODE_SANITIZE_MAP = {
    "‐": "-",       # HYPHEN
    "‑": "-",       # NON-BREAKING HYPHEN
    "‒": "-",       # FIGURE DASH
    "―": "—",  # HORIZONTAL BAR -> em dash (WinAnsi has em dash)
    "−": "-",       # MINUS SIGN
    "­": "",        # SOFT HYPHEN (invisible; safe to drop)
    "​": "",        # ZERO WIDTH SPACE
    "‌": "",        # ZERO WIDTH NON-JOINER
    "‍": "",        # ZERO WIDTH JOINER
    "﻿": "",        # BOM / ZERO WIDTH NO-BREAK SPACE
}


def _sanitize_unicode(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for bad, good in _UNICODE_SANITIZE_MAP.items():
        if bad in text:
            text = text.replace(bad, good)
    return text


def escape(text, *args, **kwargs):
    """Shadows the plain xml.sax.saxutils.escape imported above (kept as
    _xml_escape) so every one of this module's ~15 escape() call sites --
    AI-generated interpretation/guidance text via _rich() below, and every
    other escaped field (client name, dates, parser-derived life-area/
    karaka text, etc.) -- gets the Unicode sanitization pass for free,
    without having to hunt down and edit each call site individually.
    See _UNICODE_SANITIZE_MAP's comment above for why this is needed."""
    text = "" if text is None else str(text)
    return _xml_escape(_sanitize_unicode(text), *args, **kwargs)


def _rich(text) -> str:
    """Escapes `text` for safe use inside a ReportLab Paragraph, then turns
    **double-asterisk** spans into <b> tags -- the PDF equivalent of what
    write_rich_text()'s Characters()-based bold runs did for Excel. Escaping
    BEFORE substituting the bold tags (rather than after) keeps the tags
    themselves from being escaped."""
    text = "" if text is None else str(text)
    escaped = escape(text)
    return _BOLD_RE.sub(r"<b>\1</b>", escaped)


def _circles_html(count: int, color_name: str) -> str:
    if count <= 0:
        return ""
    hexcolor = TIER_COLOR[color_name].hexval()
    return f'<font name="DejaVuSans" color="{hexcolor}">{CIRCLE * count}</font>'


def circles_for_score(score: float):
    count, color_name, _ = score_bracket(score)
    return count, color_name


def circles_for_tier(tier: str):
    if tier not in TIER_CIRCLES:
        # Never crash the whole report over one bad tier key from the AI --
        # fall back to neutral/yellow and let the label text still show,
        # same "degrade, don't crash" pattern used throughout this project.
        return TIER_CIRCLES["neutral"]
    return TIER_CIRCLES[tier]


# ---------------------------------------------------------------------
# Paragraph styles
# ---------------------------------------------------------------------

TITLE_STYLE = ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=18,
                              textColor=TITLE_NAVY, leading=22, spaceAfter=4)
SUBTITLE_STYLE = ParagraphStyle("Subtitle", fontName="Helvetica-Bold", fontSize=12,
                                 textColor=BLACK, leading=15)
SECTION_STYLE = ParagraphStyle("Section", fontName="Helvetica-Bold", fontSize=14,
                                textColor=TITLE_NAVY, leading=18, spaceBefore=10, spaceAfter=4)
SUBHEAD_STYLE = ParagraphStyle("Subhead", fontName="Helvetica-Bold", fontSize=11,
                                textColor=SUBHEAD_BLUE, leading=14, spaceBefore=6, spaceAfter=3)
BODY_STYLE = ParagraphStyle("Body", fontName="Helvetica", fontSize=9, leading=12)
BODY_BOLD_STYLE = ParagraphStyle("BodyBold", fontName="Helvetica-Bold", fontSize=9, leading=12)
BODY_CENTER_STYLE = ParagraphStyle("BodyCenter", parent=BODY_STYLE, alignment=TA_CENTER)
BODY_BOLD_CENTER_STYLE = ParagraphStyle("BodyBoldCenter", parent=BODY_BOLD_STYLE, alignment=TA_CENTER)
HEADER_CELL_STYLE = ParagraphStyle("HeaderCell", fontName="Helvetica-Bold", fontSize=9,
                                    leading=11, alignment=TA_CENTER)
ASSESS_STYLE = ParagraphStyle("Assess", fontName="Helvetica", fontSize=9, leading=12)
# 2026-09-15: "align table 3 around the area and assessment" -- a centered
# variant of ASSESS_STYLE used only by Table 3 (Strategic Focus Areas),
# whose Area/Assessment columns hold short, single-line values well suited
# to centering, unlike Table 1/2 where Assessment stays left-aligned next
# to much longer Interpretation/Guidance text.
ASSESS_CENTER_STYLE = ParagraphStyle("AssessCenter", parent=ASSESS_STYLE, alignment=TA_CENTER)

# 2026-09-09: "Try to keep Each Table in one Page" -- Table 1 (Houses) and
# Table 2 (Planets) are the two tables with the most text per row
# (Interpretation + Guidance paragraphs), and at portrait width they were
# running noticeably taller per row than everything else. A smaller,
# tighter style for just those two columns (paired with reduced cell
# padding in _base_table_style(padding=...) below) shrinks row heights
# without touching the rest of the report's type size -- doesn't guarantee
# a 12-row table always fits one page, but meaningfully improves the odds
# and keeps whatever page break does happen less wasteful.
# 2026-09-15: "reduce font and cover more ground" -- shrunk further from
# 8/9.5 to 7/8.5 (still comfortably legible in a printed/PDF report) so
# Table 1's now-5 prose columns (Description, Karaka, Interpretation,
# Guidance) pack more characters per line, on top of the column-width
# rebalancing and margin/padding reduction done alongside this.
COMPACT_BODY_STYLE = ParagraphStyle("CompactBody", fontName="Helvetica", fontSize=7, leading=8.5)


def P(text, style=BODY_STYLE):
    return Paragraph(text, style)


def rich_p(text, style=BODY_STYLE):
    return P(_rich(text), style)


def score_p(score) -> Paragraph:
    if score is None:
        return P("")
    count, color_name = circles_for_score(score)
    n = int(round(score))
    sign = "+" if n > 0 else ""
    circles_html = _circles_html(count, color_name)
    return P(f"{circles_html} {sign}{n}".strip(), BODY_CENTER_STYLE)


def assessment_p(tier, label, centered=False) -> Paragraph:
    count, color_name = circles_for_tier(tier)
    label = escape((label or "").strip())
    circles_html = _circles_html(count, color_name)
    style = ASSESS_CENTER_STYLE if centered else ASSESS_STYLE
    return P(f"{circles_html} {label}".strip(), style)


# ---------------------------------------------------------------------
# Table styling helpers
# ---------------------------------------------------------------------

def _base_table_style(n_header_rows=1, highlights=None, spans=None, padding=3, h_padding=4):
    """highlights: list of (row_index, col_index, color_name) to shade a
    single cell background -- the PDF equivalent of apply_fill(). `padding`
    (2026-09-09) lets the two busiest tables (Houses/Planets) use tighter
    cell padding to help each fit in fewer pages, without affecting every
    other table's default spacing. `h_padding` (2026-09-15, "reduce font
    and cover more ground") does the same for LEFT/RIGHTPADDING -- every
    point of horizontal padding removed from a 10-column table is a point
    every one of those columns doesn't have to wrap text into, so Table 1/2
    use a tighter h_padding too instead of leaving that space unclaimed."""
    cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, GREY_LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), h_padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), h_padding),
        ("TOPPADDING", (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
    ]
    if n_header_rows:
        cmds.append(("BACKGROUND", (0, 0), (-1, n_header_rows - 1), rgb(235, 238, 242)))
    for row, col, color_name in (highlights or []):
        cmds.append(("BACKGROUND", (col, row), (col, row), HILITE.get(color_name, WHITE)))
    for (c0, r0), (c1, r1) in (spans or []):
        cmds.append(("SPAN", (c0, r0), (c1, r1)))
    return TableStyle(cmds)


def two_col_table(pairs, value_width, label_width):
    """A Category|Assessment (or Category|Value) table -- pairs is a list
    of (label, flowable_or_builder). Mirrors overview_excel_writer.py's
    two_col_table(), one row per pair, label bold in the left column."""
    data = [["Category", "Assessment"]]
    data[0] = [P("Category", HEADER_CELL_STYLE), P("Assessment", HEADER_CELL_STYLE)]
    for label, value in pairs:
        data.append([P(escape(label), BODY_BOLD_STYLE), value])
    table = Table(data, colWidths=[label_width, value_width])
    table.setStyle(_base_table_style(n_header_rows=1))
    return table


# ---------------------------------------------------------------------
# Section builders -- each returns a list of flowables to extend `story`
# with, mirroring overview_excel_writer.py's section functions.
# ---------------------------------------------------------------------

def build_title(client_name: str, page_width: float) -> list:
    return [
        Paragraph("ORBINOVASTRO&trade; Life Balance Index (LBI)", TITLE_STYLE),
        Paragraph(f"Executive CCSI Assessment &mdash; {escape(client_name)}", SUBTITLE_STYLE),
        Spacer(1, 8),
    ]


def build_executive_assessment(executive: dict, page_width: float) -> list:
    story = [Paragraph("Executive CCSI Assessment", SECTION_STYLE),
             Paragraph("Overall Life Balance", SUBHEAD_STYLE)]

    pairs = [
        ("Overall Life Potential",
         assessment_p(executive.get("overall_life_potential", {}).get("tier"),
                      executive.get("overall_life_potential", {}).get("label"))),
        ("Current Activation",
         assessment_p(executive.get("current_activation", {}).get("tier"),
                      executive.get("current_activation", {}).get("label"))),
        ("Current Cosmic Environment",
         assessment_p(executive.get("current_cosmic_environment", {}).get("tier"),
                      executive.get("current_cosmic_environment", {}).get("label"))),
        ("Highest Opportunity", rich_p(executive.get("highest_opportunity", ""))),
        ("Highest Priority", rich_p(executive.get("highest_priority", ""))),
        ("Overall Life Phase", rich_p(executive.get("overall_life_phase", ""))),
    ]
    label_w = page_width * 0.22
    story.append(two_col_table(pairs, value_width=page_width - label_w, label_width=label_w))
    story.append(Spacer(1, 6))
    story.append(rich_p(executive.get("summary", ""), BODY_STYLE))
    story.append(Spacer(1, 10))
    return story


def build_legend(page_width: float) -> list:
    story = [Paragraph("ORBINOVASTRO&trade; Legend", SECTION_STYLE),
             Paragraph("Score Legend", SUBHEAD_STYLE)]

    header = [P("Score", HEADER_CELL_STYLE), P("Symbol", HEADER_CELL_STYLE),
              P("Meaning", HEADER_CELL_STYLE), P("Interpretation", HEADER_CELL_STYLE)]
    rows = [header]
    for low, high, count, color_name, meaning, interpretation in SCORE_LEGEND_ROWS:
        if low is None:
            score_text = f"{high} and below"
        elif high is None:
            score_text = f"+{low} and above"
        elif low == high == 0:
            score_text = "0"
        else:
            sign_low = "+" if low > 0 else ("−" if low < 0 else "")
            score_text = (f"{sign_low}{abs(low)} to {'+' if high > 0 else ''}{high}"
                          if high != 0 else f"{sign_low}{abs(low)} to 0")
        rows.append([
            P(score_text, BODY_CENTER_STYLE),
            P(_circles_html(count, color_name), BODY_CENTER_STYLE),
            P(escape(meaning), BODY_STYLE),
            P(escape(interpretation), BODY_STYLE),
        ])
    col_widths = [page_width * w for w in (0.12, 0.10, 0.28, 0.50)]
    table = Table(rows, colWidths=col_widths)
    table.setStyle(_base_table_style(n_header_rows=1))
    story.append(table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Assessment Layers", SUBHEAD_STYLE))
    header2 = [P("Code", HEADER_CELL_STYLE), P("Assessment Layer", HEADER_CELL_STYLE),
               P("Description", HEADER_CELL_STYLE)]
    rows2 = [header2]
    for code, layer, description in ASSESSMENT_LAYERS_ROWS:
        rows2.append([P(escape(code), BODY_BOLD_STYLE), P(escape(layer), BODY_STYLE),
                      P(escape(description), BODY_STYLE)])
    col_widths2 = [page_width * w for w in (0.08, 0.22, 0.70)]
    table2 = Table(rows2, colWidths=col_widths2)
    table2.setStyle(_base_table_style(n_header_rows=1))
    story.append(table2)
    story.append(Spacer(1, 8))

    # 2026-09-08: "write the legend of acronyms there are many" -- a single
    # glossary covering every abbreviation used anywhere in the report
    # (report/table-name acronyms, the L/LT/TT codes again for a one-stop
    # reference, and all ten planet codes from Table 2).
    story.append(Paragraph("Acronym Legend", SUBHEAD_STYLE))
    header3 = [P("Acronym", HEADER_CELL_STYLE), P("Meaning", HEADER_CELL_STYLE)]
    rows3 = [header3]
    for acronym, meaning in ACRONYM_LEGEND_ROWS:
        rows3.append([P(escape(acronym), BODY_BOLD_STYLE), P(escape(meaning), BODY_STYLE)])
    col_widths3 = [page_width * w for w in (0.15, 0.85)]
    table3 = Table(rows3, colWidths=col_widths3, repeatRows=1)
    table3.setStyle(_base_table_style(n_header_rows=1))
    story.append(table3)
    story.append(Spacer(1, 10))
    return story


def _table1_column_widths(page_width):
    # House, Life Area, Description, L, LT, TT, Assessment, Interpretation, Guidance
    # 2026-09-08: widened the House column slightly (0.05 -> 0.08) for the
    # portrait conversion -- at portrait's narrower page width, "House" was
    # wrapping mid-word onto two lines ("Ho"/"use") in the header cell.
    #
    # 2026-09-15: "Split the Life Area in two columns" first split the old
    # single "Life Area" column into Life Area (label) + Description. A
    # real client report (Nishil D. Naik) then showed rows were STILL too
    # tall, because that client's sheet appends a whole extra "Karaka:
    # Sun (soul, constitution)." planetary-ruler sentence after the facets
    # sentence -- content this project's earlier test data didn't have --
    # which was landing entirely inside Description and roughly doubling
    # its length back to where it started. Karaka briefly got its own
    # column for that.
    #
    # 2026-09-16: a second real client (Mehul) has NO "Karaka: ..." clause
    # anywhere in their sheet's life-area text -- unlike Nishil's data, it's
    # simply absent, not present-but-different. That left the Karaka column
    # sitting completely blank across all 12 house rows, while Description
    # (only 0.10 at the time) was squeezed tight enough to wrap its own
    # 11-character header, "Description", onto two lines. Client: "Remove
    # karaka from there." The Karaka column is now removed entirely --
    # split_karaka() (ccsi_parser.py) still strips any "Karaka: ..." clause
    # out of a house's description text before it reaches the PDF (so it
    # never leaks into the Description column for a client whose sheet does
    # include it), the clause just isn't given its own column anymore. Its
    # former 0.13 share is redistributed below: +0.06 to Description (the
    # column that was actually cramped), +0.04 to Interpretation, +0.03 to
    # Guidance.
    return [page_width * w for w in
            (0.08, 0.08, 0.16, 0.045, 0.045, 0.045, 0.13, 0.23, 0.185)]


def build_table1_houses(houses_ccsi: list, houses_ai: list, closing: dict, page_width: float) -> list:
    story = [Paragraph("Table 1. Life Balance Index (LBI)", SECTION_STYLE)]
    headers = ["House", "Life Area", "Description", "L", "LT", "TT",
               "Assessment", "Interpretation", "Guidance"]
    rows = [[P(h, HEADER_CELL_STYLE) for h in headers]]
    ai_by_house = {int(h.get("house")): h for h in houses_ai if h.get("house") is not None}
    highlights = []
    # Column order is House, Life Area, Description, L, LT, TT, Assessment,
    # Interpretation, Guidance.
    interp_col = 7
    guidance_col = 8
    for i, house in enumerate(houses_ccsi):
        r = i + 1  # +1 for header row
        hnum = house["house"]
        ai = ai_by_house.get(hnum, {})
        life_area_label, life_area_description = split_life_area(house["life_area"])
        # Still stripped out (not displayed) so a client whose sheet DOES
        # include a "Karaka: ..." clause doesn't get it glued onto the end
        # of the Description column -- see this function's comment above.
        life_area_description, _karaka_text = split_karaka(life_area_description)
        # These labels are conventionally slash-joined with no spaces (e.g.
        # "Transformation/Longevity"), which in a narrow column ReportLab
        # would otherwise force-break mid-syllable ("Transformati"/
        # "on/Longevity"). Spacing the slash out ("Transformation /
        # Longevity") gives it two clean word-break points instead, without
        # changing what the label actually says.
        life_area_label_wrapped = escape(life_area_label).replace("/", " / ")
        row = [
            P(str(hnum), BODY_CENTER_STYLE),
            P(life_area_label_wrapped, BODY_BOLD_STYLE),
            P(escape(life_area_description), COMPACT_BODY_STYLE),
            score_p(house["L"]),
            score_p(house["LT"]),
            score_p(house["TT"]),
            assessment_p(ai.get("assessment_tier", "neutral"), ai.get("assessment_label", "")),
            rich_p(ai.get("interpretation", ""), COMPACT_BODY_STYLE),
            rich_p(ai.get("guidance", ""), COMPACT_BODY_STYLE),
        ]
        rows.append(row)
        if ai.get("interpretation_highlight", "none") != "none":
            highlights.append((r, interp_col, ai["interpretation_highlight"]))
        if ai.get("guidance_highlight", "none") != "none":
            highlights.append((r, guidance_col, ai["guidance_highlight"]))

    table = Table(rows, colWidths=_table1_column_widths(page_width), repeatRows=1)
    table.setStyle(_base_table_style(n_header_rows=1, highlights=highlights, padding=1, h_padding=2))
    story.append(table)
    story.append(Spacer(1, 6))

    if closing:
        story.append(Paragraph(escape(closing.get("heading", "Dominant House Pathway")), SUBHEAD_STYLE))
        story.append(rich_p(closing.get("text", "")))
    story.append(Spacer(1, 10))
    return story


def build_table2_planets(planets_ccsi: list, planets_ai: list, closings: list, page_width: float) -> list:
    story = [Paragraph("Table 2. Planetary Influence Assessment (PII)", SECTION_STYLE)]
    headers = ["Planet", "", "L", "LT", "TT", "Assessment", "Interpretation", "Guidance"]
    rows = [[P(headers[0], HEADER_CELL_STYLE), P("", HEADER_CELL_STYLE)] +
            [P(h, HEADER_CELL_STYLE) for h in headers[2:]]]
    ai_by_code = {p.get("code"): p for p in planets_ai if p.get("code")}
    highlights = []
    spans = [((0, 0), (1, 0))]  # merge "Planet" header across first two cols
    for i, planet in enumerate(planets_ccsi):
        r = i + 1
        ai = ai_by_code.get(planet["code"], {})
        row = [
            P(escape(planet["name"]), BODY_BOLD_STYLE), P(""),
            score_p(planet["L"]), score_p(planet["LT"]), score_p(planet["TT"]),
            assessment_p(ai.get("assessment_tier", "neutral"), ai.get("assessment_label", "")),
            rich_p(ai.get("interpretation", ""), COMPACT_BODY_STYLE),
            rich_p(ai.get("guidance", ""), COMPACT_BODY_STYLE),
        ]
        rows.append(row)
        spans.append(((0, r), (1, r)))
        if ai.get("interpretation_highlight", "none") != "none":
            highlights.append((r, 6, ai["interpretation_highlight"]))
        if ai.get("guidance_highlight", "none") != "none":
            highlights.append((r, 7, ai["guidance_highlight"]))

    col_widths = [page_width * w for w in (0.09, 0.09, 0.05, 0.05, 0.05, 0.13, 0.27, 0.27)]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(_base_table_style(n_header_rows=1, highlights=highlights, spans=spans, padding=1, h_padding=2))
    story.append(table)
    story.append(Spacer(1, 6))

    for closing in closings or []:
        story.append(Paragraph(escape(closing.get("heading", "")), SUBHEAD_STYLE))
        story.append(rich_p(closing.get("text", "")))
        bullets = closing.get("bullets") or []
        for item in bullets:
            story.append(rich_p(f"•  {item}"))
        story.append(Spacer(1, 4))
    story.append(Spacer(1, 6))
    return story


def build_table3_strategic(areas_ai: list, page_width: float) -> list:
    story = [Paragraph("Table 3. Strategic Focus Areas", SECTION_STYLE)]
    header = [P("Area", HEADER_CELL_STYLE), P("Assessment", HEADER_CELL_STYLE), P("Guidance", HEADER_CELL_STYLE)]
    rows = [header]
    highlights = []
    for i, area in enumerate(areas_ai):
        r = i + 1
        highlight = area.get("row_highlight", "none")
        rows.append([
            P(escape(area.get("area", "")), BODY_BOLD_CENTER_STYLE),
            assessment_p(area.get("assessment_tier", "neutral"), area.get("assessment_label", ""), centered=True),
            rich_p(area.get("guidance", "")),
        ])
        if highlight != "none":
            highlights.append((r, 0, highlight))
            highlights.append((r, 2, highlight))

    col_widths = [page_width * w for w in (0.22, 0.18, 0.60)]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(_base_table_style(n_header_rows=1, highlights=highlights))
    story.append(table)
    story.append(Spacer(1, 10))
    return story


def build_table4_scorecard(scorecard_ai: list, page_width: float) -> list:
    story = [Paragraph("Table 4. Scorecard", SECTION_STYLE)]
    pairs = []
    for item in scorecard_ai:
        pairs.append((item.get("category", ""),
                      assessment_p(item.get("assessment_tier", "neutral"), item.get("assessment_label", ""))))
    label_w = page_width * 0.35
    story.append(two_col_table(pairs, value_width=page_width - label_w, label_width=label_w))
    story.append(Spacer(1, 10))
    return story


def build_conclusion(conclusion: dict, core_message: dict, page_width: float) -> list:
    story = [Paragraph("Conclusion", SECTION_STYLE)]
    overall = conclusion.get("overall_chart_strength", {})
    pairs = [
        ("Overall Chart Strength", assessment_p(overall.get("tier", "positive"), overall.get("text", ""))),
        ("Primary Strengths", rich_p(conclusion.get("primary_strengths", ""))),
        ("Highest Opportunities", rich_p(conclusion.get("highest_opportunities", ""))),
        ("Priority Areas", rich_p(conclusion.get("priority_areas", ""))),
        ("Current Life Theme", rich_p(conclusion.get("current_life_theme", ""))),
        ("Long-Term Direction", rich_p(conclusion.get("long_term_direction", ""))),
    ]
    label_w = page_width * 0.22
    story.append(two_col_table(pairs, value_width=page_width - label_w, label_width=label_w))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Core Message", SUBHEAD_STYLE))
    for paragraph in core_message.get("paragraphs", []):
        story.append(rich_p(paragraph))
        story.append(Spacer(1, 3))
    return story


BIRTH_DETAIL_FIELDS = [
    ("date_of_birth", "Date of Birth"),
    ("time_of_birth", "Time of Birth"),
    ("place_of_birth", "Place of Birth"),
    ("timezone", "Timezone"),
    ("latitude", "Latitude"),
    ("longitude", "Longitude"),
]

# 2026-09-08: "Also add the Transit Information along with Client info" --
# a second field group shown on the same Client Information page, below
# birth details. See generate_overview_report.py's TRANSIT_DETAIL_NAMED_RANGES
# for the (assumed, not yet client-confirmed) named-range convention.
#
# 2026-09-24, later still: "Update Transit information properly with the
# location, date and time. End user doesn't care about UTC show them
# Localtime and UTC time both" -- the client caught a real generated PDF
# showing "Transit Place: Not available" and an unlabeled UTC time/offset
# that looked like a bug (it was: the transit engine always computes in
# UTC internally, but that was being shown to the end user as-is with no
# explanation). Restructured this from one ambiguous Date/Time/Timezone
# trio into separate Local and UTC rows, both explicitly labeled, plus a
# Transit Location row that's never left blank (see
# `overview_report_builder._transit_details_dict` for how these are
# computed -- this list only says WHICH fields to render, not how).
#
# 2026-09-24, later still again: "Add which Transit is taken if the Transit
# is taken Local/birthtime or other?" -- the client sent screenshots of a
# real generated PDF and pointed out the table never said whether the shown
# transit was the current moment (defaulted) or a custom date/time picked in
# the Transit tab, nor whose "local" the Local rows meant. Added a first
# "Transit Basis" row spelling both out in one plain-language sentence (see
# `overview_report_builder._transit_basis_text`); purely declarative like
# the rest of this list, so no rendering-code changes were needed.
TRANSIT_DETAIL_FIELDS = [
    ("transit_basis", "Transit Basis"),
    ("transit_date_local", "Transit Date (Local)"),
    ("transit_time_local", "Transit Time (Local)"),
    ("transit_place", "Transit Location"),
    ("transit_timezone_local", "Transit Timezone (Local)"),
    ("transit_date_utc", "Transit Date (UTC)"),
    ("transit_time_utc", "Transit Time (UTC)"),
]

CLIENT_INFO_TITLE_STYLE = ParagraphStyle("ClientInfoTitle", fontName="Helvetica-Bold", fontSize=20,
                                          textColor=TITLE_NAVY, leading=24, alignment=TA_CENTER)

# 2026-09-09: "Add the disclaimer page from template" -- the client's own
# reference report (ORBINOVASTRO_ASTROLOGY_REPORT_Sanjay_Gupta.pdf, the same
# template this whole engagement has matched cover/border/legend styling
# against) has a dedicated Disclaimer page as page 2, right after the cover
# and before Client Information.
#
# 2026-09-09 (same day, follow-up): "Revise make it professional and legal"
# -- the client asked for the template's own wording to be tightened up
# rather than reproduced as-is. This also resolves, by rewriting around it
# rather than guessing a single missing word, the "by s following a
# reading" gap flagged when the template text was first transcribed. Note:
# this rewrite is a professional-tone/grammar pass, NOT legal advice or an
# attorney-drafted release -- see the note sent to the client alongside
# this change recommending qualified legal counsel review the final wording
# before it goes into a real client-facing report.
DISCLAIMER_BODY_STYLE = ParagraphStyle("DisclaimerBody", fontName="Helvetica-Oblique",
                                        fontSize=9.5, leading=13, textColor=BLACK)

# Paragraph text is written as ready-made ReportLab paragraph XML (not run
# through _rich()/escape()) so the bold spans -- "Disclaimer:" and
# "Important Note:" plus its emphasized clause -- can be reproduced exactly
# via inline <font name="Helvetica-Bold"/"Helvetica-BoldOblique"> tags,
# matching the reference page's own bold-within-italic styling.
DISCLAIMER_PARAGRAPHS = [
    '<font name="Helvetica-Bold">Disclaimer:</font> By purchasing or requesting an '
    'astrological or Vastu reading, you acknowledge that you have read, understood, and '
    'agree to this disclaimer in its entirety; that you release the astrologer from all '
    'liability arising from any action taken or not taken as a result of this reading; and '
    'that you are at least eighteen (18) years of age. Astrology and Vastu are offered as '
    'tools for insight, guidance, exploration, and inspiration. All readings are provided '
    'strictly for educational and exploratory purposes.',

    'This report does not constitute, and is not a substitute for, financial, legal, '
    'medical, psychiatric, psychological, or other professional advice. If you require '
    'advice of that nature, please consult a licensed professional. The astrologer assumes '
    'no responsibility for any damage, consequence, or outcome resulting from any action '
    'taken or not taken by you in reliance on this reading. All personal information '
    'provided in connection with this reading is held in confidence and will not be '
    'disclosed to third parties.',

    '<font name="Helvetica-BoldOblique">Important Note:</font> All scores and probabilities '
    'presented in this report are generated objectively by the ORBINOVASTRO&trade; Event '
    'Engine, based on your astrological data and predefined event rules. They are '
    '<font name="Helvetica-BoldOblique">calculated independently of personal expectations, '
    'emotions, relationships, or desired outcomes</font>. The analysis remains consistent '
    'regardless of whether a given result is favorable or unfavorable, ensuring an unbiased, '
    'evidence-based assessment.',
]

KUNDLI_TITLE_STYLE = ParagraphStyle("KundliTitle", fontName="Helvetica-Bold", fontSize=18,
                                     textColor=TITLE_NAVY, leading=22, alignment=TA_CENTER,
                                     spaceAfter=10)
KUNDLI_NOTE_STYLE = ParagraphStyle("KundliNote", fontName="Helvetica-Oblique", fontSize=9,
                                    textColor=GREY_LINE, alignment=TA_CENTER)


def _build_front_matter_pdf(client_name: str, birth_details: dict, transit_details: dict,
                             report_date: str) -> io.BytesIO:
    """Builds the 3-page portrait front matter (branded cover + Disclaimer +
    Client Information / birth details page) that the client asked to have
    added, matching the reference report's own cover/disclaimer/client-info
    page order. Returns an in-memory PDF (merged into the main report by
    build_pdf()) rather than a second file, since these pages use a
    different page size/orientation than the rest of the report."""
    birth_details = birth_details or {}
    transit_details = transit_details or {}
    buf = io.BytesIO()
    page_w, page_h = A4  # portrait, matching the reference report and its artwork
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    margin = 26 * mm  # stays clear of the decorative border artwork
    content_w = page_w - 2 * margin

    # ---- Page 1: branded cover ----
    if _COVER_IMAGE_PATH.exists():
        c.drawImage(str(_COVER_IMAGE_PATH), 0, 0, width=page_w, height=page_h,
                    preserveAspectRatio=False, anchor="c")
    c.showPage()

    # ---- Page 2: Disclaimer (2026-09-09: "Add the disclaimer page from
    # template") -- matches the reference template's own page order (cover,
    # then disclaimer, then Client Information). ----
    if _BORDER_BG_IMAGE_PATH.exists():
        c.drawImage(str(_BORDER_BG_IMAGE_PATH), 0, 0, width=page_w, height=page_h,
                    preserveAspectRatio=False, anchor="c")

    disc_title = Paragraph("DISCLAIMER", CLIENT_INFO_TITLE_STYLE)
    dtw, dth = disc_title.wrap(content_w, page_h)
    disc_y = page_h - margin - dth
    disc_title.drawOn(c, margin, disc_y)
    disc_y -= 18

    for para_text in DISCLAIMER_PARAGRAPHS:
        para = Paragraph(para_text, DISCLAIMER_BODY_STYLE)
        pw, ph = para.wrap(content_w, disc_y)
        disc_y -= ph
        para.drawOn(c, margin, disc_y)
        disc_y -= 12

    c.showPage()

    # ---- Page 3: Client Information ----
    if _BORDER_BG_IMAGE_PATH.exists():
        c.drawImage(str(_BORDER_BG_IMAGE_PATH), 0, 0, width=page_w, height=page_h,
                    preserveAspectRatio=False, anchor="c")

    title = Paragraph("CLIENT INFORMATION", CLIENT_INFO_TITLE_STYLE)
    tw, th = title.wrap(content_w, page_h)
    title_y = page_h - margin - th
    title.drawOn(c, margin, title_y)

    rows = [
        ["Report Date", escape(report_date)],
        ["Client Name", escape(client_name or "")],
    ]
    for key, label in BIRTH_DETAIL_FIELDS:
        value = birth_details.get(key)
        value = str(value).strip() if value not in (None, "") else "Not available"
        rows.append([label, escape(value)])

    data = [[P(label, BODY_BOLD_STYLE), P(value, BODY_STYLE)] for label, value in rows]
    table = Table(data, colWidths=[content_w * 0.35, content_w * 0.65])
    table.setStyle(_base_table_style(n_header_rows=0))
    tw2, th2 = table.wrapOn(c, content_w, page_h)
    table_y = title_y - 14 - th2
    table.drawOn(c, margin, table_y)

    # ---- Transit Information (2026-09-08: "Also add the Transit
    # Information along with Client info") -- a second labeled block
    # beneath birth details, on the same page. ----
    subhead = Paragraph("TRANSIT INFORMATION", SUBHEAD_STYLE)
    sw, sh = subhead.wrap(content_w, page_h)
    subhead_y = table_y - 16 - sh
    subhead.drawOn(c, margin, subhead_y)

    transit_rows = []
    for key, label in TRANSIT_DETAIL_FIELDS:
        value = transit_details.get(key)
        value = str(value).strip() if value not in (None, "") else "Not available"
        transit_rows.append([label, escape(value)])

    transit_data = [[P(label, BODY_BOLD_STYLE), P(value, BODY_STYLE)] for label, value in transit_rows]
    transit_table = Table(transit_data, colWidths=[content_w * 0.35, content_w * 0.65])
    transit_table.setStyle(_base_table_style(n_header_rows=0))
    tw3, th3 = transit_table.wrapOn(c, content_w, page_h)
    transit_table_y = subhead_y - 6 - th3
    transit_table.drawOn(c, margin, transit_table_y)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------
# Kundli chart page
# ---------------------------------------------------------------------
# 2026-09-15: "Just use A:U and till row 120. remove anything else from
# Kundli that is going in report" -- the client asked to drop the
# "KUNDLI TECHNICAL REFERENCE" six-card page entirely (previously read from
# a separate wide helper range, Kundli!AD1:FD16, via label-matching column
# detection) so the ONLY Kundli content in the report is the chart export
# covering Kundli!A1:U120 (see generate_overview_report.py's
# KUNDLI_CHART_RANGE). This also removes the source of a real crash found
# in that page (a nested mini-table cell rendering far taller than a page
# frame when a source column held long-form text instead of short
# numeric/label values) -- the whole feature is gone rather than patched,
# since it's no longer part of the report. The removed functions were
# KUNDLI_REFERENCE_TITLES, _format_kundli_value(), _clean_header(),
# _find_kundli_header_row(), _find_runs(), _mini_table(), and
# _kundli_table_flowables() -- see this project's production log for their
# history if this page is ever wanted back.


def _build_native_kundli_pdf(kundli_chart_data, page_size, left_margin, right_margin,
                              top_margin, bottom_margin) -> io.BytesIO:
    """2026-09-20: builds the Kundli pages natively (vector diamond chart +
    two data tables per divisional chart, via kundli_chart.py) instead of
    embedding Excel's own picture export of the same content -- see
    generate_overview_report.py's extract_kundli_charts(), which reads
    Kundli!A1:U120 as real data (same range export_kundli_chart_image()
    exports as a picture) and returns one kundli_chart.KundliChartData per
    divisional chart found. Each chart gets its own page; falls back to
    the old image/PDF path in build_pdf() below when extraction found
    nothing (see that function's branch order)."""
    page_width = page_size[0] - left_margin - right_margin
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=page_size,
        leftMargin=left_margin, rightMargin=right_margin,
        topMargin=top_margin, bottomMargin=bottom_margin,
        title="ORBINOVASTRO Kundli",
    )
    story = []
    for i, chart in enumerate(kundli_chart_data):
        if i > 0:
            story.append(PageBreak())
        story += build_kundli_chart_section(chart, page_width)
    doc.build(story, onFirstPage=_draw_page_border, onLaterPages=_draw_page_border)
    buf.seek(0)
    return buf


def _build_kundli_pdf(kundli_chart_image, page_size, left_margin, right_margin,
                       top_margin, bottom_margin) -> io.BytesIO:
    """Builds the Kundli chart page as its own small portrait PDF -- kept
    separate from the Client Information canvas page and the main report's
    flowable story so the image scales to the page cleanly via ReportLab's
    own Image flowable rather than being hand-positioned on a fixed canvas.

    2026-09-15: this used to also render a "KUNDLI TECHNICAL REFERENCE"
    six-card data table (from a separate helper range); the client asked to
    remove that entirely so the Kundli page is chart-image only (see the
    module-level comment above this function)."""
    page_width = page_size[0] - left_margin - right_margin
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=page_size,
        leftMargin=left_margin, rightMargin=right_margin,
        topMargin=top_margin, bottomMargin=bottom_margin,
        title="ORBINOVASTRO Kundli",
    )

    story = []

    image_paths = kundli_chart_image if isinstance(kundli_chart_image, (list, tuple)) else [kundli_chart_image]
    image_paths = [Path(path) for path in image_paths if path and Path(path).exists()]

    story.append(Paragraph("KUNDLI &mdash; BIRTH CHART", KUNDLI_TITLE_STYLE))
    if image_paths:
        # Multiple paths (if ever passed) share the page height evenly; the
        # current export path (generate_overview_report.py) always passes a
        # single PDF covering the whole Kundli!A1:U120 range as one image.
        max_h = page_size[1] - top_margin - bottom_margin - 28 * mm
        image_h = max_h / len(image_paths)
        for image_path in image_paths:
            story.append(Image(str(image_path), width=page_width, height=image_h,
                                kind="proportional", hAlign="CENTER"))
            story.append(Spacer(1, 2))
    else:
        story.append(Paragraph("Kundli chart image not available for this run.", KUNDLI_NOTE_STYLE))

    doc.build(story, onFirstPage=_draw_page_border, onLaterPages=_draw_page_border)
    buf.seek(0)
    return buf


def _build_south_indian_charts_pdf(south_indian_charts: list, page_size, left_margin,
                                    right_margin, top_margin, bottom_margin) -> io.BytesIO:
    """2026-09-21: "You can still print the charts from the D30NatalTransit
    worksheet" -- builds the "Divisional Charts -- South Indian Style" page
    (D1/D9/D3/D30, 2x2 grid, one page) as its own small PDF, mirroring
    _build_native_kundli_pdf() above. Source data comes from
    generate_overview_report.py's extract_all_south_indian_charts(), which
    reads the 4 mini-charts D30NatalTransit itself draws (columns Z:AK).
    Rendering is build_south_indian_charts_section() in kundli_chart.py."""
    page_width = page_size[0] - left_margin - right_margin
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=page_size,
        leftMargin=left_margin, rightMargin=right_margin,
        topMargin=top_margin, bottomMargin=bottom_margin,
        title="ORBINOVASTRO Divisional Charts (South Indian)",
    )
    story = build_south_indian_charts_section(south_indian_charts, page_width)
    doc.build(story, onFirstPage=_draw_page_border, onLaterPages=_draw_page_border)
    buf.seek(0)
    return buf


def _build_troubles_pdf(troubles_data: dict, page_size, left_margin, right_margin,
                         top_margin, bottom_margin) -> io.BytesIO:
    """2026-09-21: builds the "Troubles & Misfortune" page (D30 Panchatattva/
    Drekkana/Navamsa clues + current-Dasha disease-relevant periods + a
    concise KP verdict summary) as its own small PDF, mirroring
    _build_native_kundli_pdf() above. Source data comes from
    generate_overview_report.py's extract_troubles_misfortune(), which reads
    D30NatalTransit!BA1:BN130; rendering is build_troubles_misfortune_section()
    in kundli_chart.py. Always a single page -- see that function's docstring
    for how the raw worksheet detail (including the astrologer's own KP
    computational scaffolding) is distilled down to client-appropriate
    content."""
    page_width = page_size[0] - left_margin - right_margin
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=page_size,
        leftMargin=left_margin, rightMargin=right_margin,
        topMargin=top_margin, bottomMargin=bottom_margin,
        title="ORBINOVASTRO Troubles & Misfortune",
    )
    story = build_troubles_misfortune_section(troubles_data, page_width)
    doc.build(story, onFirstPage=_draw_page_border, onLaterPages=_draw_page_border)
    buf.seek(0)
    return buf


def _build_planetary_characteristics_pdf(planetary_characteristics, d30_chart_cells, page_size,
                                          left_margin, right_margin, top_margin, bottom_margin) -> io.BytesIO:
    """2026-09-21: "use whole worksheet and its table to generate report" --
    builds the "Planetary Characteristics & Remedies" page (one page, one row
    per planet + Ascendant, plus the D30 South Indian mini-chart on one side)
    as its own small PDF, mirroring _build_troubles_pdf() above. Source data
    comes from generate_overview_report.py's extract_planetary_characteristics()
    (D30NatalTransit's Chara Karaka table, columns AL:AU -- a separate table
    from the BA:BN range the Troubles & Misfortune page reads) and
    extract_d30_south_indian_chart() (the sheet's own on-sheet D-30 mini-chart,
    columns Z:AK). Rendering is build_planetary_characteristics_section() in
    kundli_chart.py."""
    page_width = page_size[0] - left_margin - right_margin
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=page_size,
        leftMargin=left_margin, rightMargin=right_margin,
        topMargin=top_margin, bottomMargin=bottom_margin,
        title="ORBINOVASTRO Planetary Characteristics",
    )
    story = build_planetary_characteristics_section(
        planetary_characteristics, page_width, d30_chart_cells=d30_chart_cells)
    doc.build(story, onFirstPage=_draw_page_border, onLaterPages=_draw_page_border)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------

def build_pdf(report_data: dict, parsed: dict, client_name: str, output_path,
              birth_details: dict | None = None, transit_details: dict | None = None,
              kundli_chart_image=None, kundli_chart_data=None, troubles_data=None,
              planetary_characteristics=None, d30_chart_cells=None,
              south_indian_charts=None,
              report_date: str | None = None) -> None:
    """Builds the full ORBINOVASTRO LBI report PDF at `output_path`.
    `report_data` is the AI-generated (and _validate_and_fill()-defended)
    payload from generate_overview_report.py; `parsed` is ccsi_parser's
    deterministic houses/planets numbers. `birth_details`/`transit_details`
    (optional) are dicts keyed by BIRTH_DETAIL_FIELDS/TRANSIT_DETAIL_FIELDS
    above -- a missing or None value shows as "Not available" rather than
    failing the report. `kundli_chart_image` (optional path, or list of
    paths) adds a Kundli chart page after Client Information -- covering
    Kundli!A1:U120 per generate_overview_report.py's KUNDLI_CHART_RANGE.

    2026-09-20: `kundli_chart_data` (optional list of kundli_chart.
    KundliChartData, from generate_overview_report.py's
    extract_kundli_charts()) is the new preferred source for the Kundli
    page(s) -- a native vector chart + two data tables per divisional
    chart, built with this report's own styling, in place of embedding
    Excel's own picture export of the same worksheet range. When given
    and non-empty it takes priority over `kundli_chart_image`, which
    stays as the fallback for a run where extraction couldn't recognize
    the sheet's layout (see _build_native_kundli_pdf / _find_house_table
    in generate_overview_report.py for how that degrades).

    2026-09-21: `troubles_data` (optional dict from generate_overview_report.
    py's extract_troubles_misfortune(), reading D30NatalTransit!BA1:BN130)
    adds a single "Troubles & Misfortune" page. Originally placed right
    after the Kundli chart pages; client then asked to "Move the Troubles
    and Misfortune at the End", so it's now the LAST page(s) in the PDF,
    after the whole main report body. Omitted or empty (sheet/anchors not
    found) simply skips the page -- see _build_troubles_pdf().

    2026-09-21: `planetary_characteristics` (optional list from
    generate_overview_report.py's extract_planetary_characteristics(),
    reading D30NatalTransit's separate Chara Karaka table) would add a
    "Planetary Characteristics & Remedies" page -- see
    _build_planetary_characteristics_pdf(). `d30_chart_cells` (optional dict
    from generate_overview_report.py's extract_d30_south_indian_chart())
    additionally draws that sheet's own D-30 South Indian mini-chart on one
    side of that same page; omitted, that page just runs without a chart.
    2026-09-21: client then asked to "remove the PLANETARY CHARACTERISTICS &
    REMEDIES page" -- generate_overview_report.py's main() no longer extracts
    or passes `planetary_characteristics`/`d30_chart_cells`, so in the normal
    run they're None and this page is simply never built; left wired here
    (not deleted) in case it's wanted back.

    2026-09-21: `south_indian_charts` (optional list from
    generate_overview_report.py's extract_all_south_indian_charts()) is what
    replaced the D30-only chart above -- client: "You can still print the
    charts from the D30NatalTransit worksheet", clarified to mean all 4 of
    that sheet's own mini-charts (D1/D9/D3/D30), not just D30. Adds a single
    "Divisional Charts -- South Indian Style" page (2x2 grid) right after
    the North Indian Kundli chart pages. Omitted or empty simply skips the
    page -- see _build_south_indian_charts_pdf().

    2026-09-15: this function used to also accept `kundli_table` (a data
    table rendered as a separate "KUNDLI TECHNICAL REFERENCE" page); the
    client asked to remove that entirely ("remove anything else from Kundli
    that is going in report") so the chart image/PDF is the only Kundli
    content in the report.

    2026-09-08: added a branded cover page + a Client Information/birth-
    details page in front of the report proper, at the client's request
    ("This doesn't have the cover info.. client info and birth detail"),
    matching ORBINOVASTRO's other reports' front matter.

    2026-09-08 (later same day): the client asked to use portrait
    exclusively ("Use only portrait the border is designed for portrait")
    rather than a rotated landscape version of the border artwork -- the
    whole document (cover, Client Information, the new Kundli page, and the
    report body) is now built as portrait A4 throughout, all sharing the
    one unrotated `page_border_bg.png`. The cover/Client-Information pages
    are still built as their own small canvas-based PDF (precise fixed
    layout), the new Kundli page as its own flowable PDF (so a long data
    table can paginate on its own), and the report body as its own flowable
    PDF -- all three now the same page size, concatenated in order with
    pypdf (front matter -> Kundli -> report body)."""
    from datetime import date

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_date = report_date or date.today().strftime("%d %B %Y")

    page_size = A4  # portrait throughout -- see docstring above
    # Margins were widened (from 14/12mm) to 18/16mm at one point to stay
    # clear of the gold border artwork's frame line, drawn on every page
    # (see _draw_page_border() above).
    #
    # 2026-09-15: "reduce font and cover more ground" -- measured the
    # actual border artwork in page_border_bg.png directly (pixel-scanned
    # both edges) rather than guess: the plain double gold line running
    # along the LEFT/RIGHT/BOTTOM edges sits only ~3-7mm in, so 13mm there
    # leaves a clear buffer past it. The TOP edge is different -- its
    # center lotus flourish hangs down much further (~21mm) than the plain
    # line elsewhere, so a first attempt at 13mm/13mm on every side had
    # this page's own title text overlapping straight through the lotus
    # graphic; caught by rendering and visually inspecting the actual page
    # (not just trusting the pixel measurement), and fixed by giving the
    # top back its own, taller margin while keeping the other three at
    # 13mm -- confirmed clear at both the top-center lotus and all four
    # corner flourishes afterward.
    left_margin = right_margin = 13 * mm
    top_margin = 20 * mm
    bottom_margin = 13 * mm
    page_width = page_size[0] - left_margin - right_margin

    main_buf = io.BytesIO()
    doc = SimpleDocTemplate(
        main_buf,
        pagesize=page_size,
        leftMargin=left_margin, rightMargin=right_margin,
        topMargin=top_margin, bottomMargin=bottom_margin,
        title=f"ORBINOVASTRO LBI Report - {client_name}",
    )

    # 2026-09-09: "Try to keep Each Table in one Page. start with new page
    # when new table." -- each major table-bearing section now starts on
    # its own fresh page via an explicit PageBreak(), rather than flowing
    # straight on from whatever space was left on the previous page. Title
    # + Executive Assessment stay together on the report's first page (that
    # pairing isn't itself labeled as a "Table" and reads naturally as one
    # opening section); every section from the Legend onward gets its own
    # page. Table 1 (12 rows) and Table 2 (10 rows) also got a tighter
    # COMPACT_BODY_STYLE + padding=1 (see above) to help each fit on one
    # page -- when a table's real content is too long to fit even with
    # that, ReportLab still just spills the extra rows onto a second page
    # (never truncating or dropping data, and never splitting a row's own
    # content mid-cell), which is the correct trade-off: shrink first,
    # overflow rather than lose data if it still doesn't fit.
    story = []
    story += build_title(client_name, page_width)
    story += build_executive_assessment(report_data.get("executive_assessment", {}), page_width)
    story.append(PageBreak())
    story += build_legend(page_width)
    story.append(PageBreak())
    story += build_table1_houses(parsed["houses"], report_data.get("houses", []),
                                  report_data.get("houses_closing", {}), page_width)
    story.append(PageBreak())
    story += build_table2_planets(parsed["planets"], report_data.get("planets", []),
                                   report_data.get("planets_closing", []), page_width)
    story.append(PageBreak())
    story += build_table3_strategic(report_data.get("strategic_focus_areas", []), page_width)
    story.append(PageBreak())
    story += build_table4_scorecard(report_data.get("scorecard", []), page_width)
    story.append(PageBreak())
    story += build_conclusion(report_data.get("conclusion", {}), report_data.get("core_message", {}), page_width)

    doc.build(story, onFirstPage=_draw_page_border, onLaterPages=_draw_page_border)
    main_buf.seek(0)

    front_buf = _build_front_matter_pdf(client_name, birth_details, transit_details, report_date)

    writer = PdfWriter()
    for page in PdfReader(front_buf).pages:
        writer.add_page(page)

    chart_pdf = None
    if kundli_chart_image and not isinstance(kundli_chart_image, (list, tuple)):
        candidate = Path(kundli_chart_image)
        if candidate.suffix.casefold() == ".pdf" and candidate.exists():
            chart_pdf = candidate

    if kundli_chart_data:
        # Native chart+tables take priority -- see docstring above and
        # _build_native_kundli_pdf().
        kundli_buf = _build_native_kundli_pdf(
            kundli_chart_data, page_size,
            left_margin, right_margin, top_margin, bottom_margin,
        )
        for page in PdfReader(kundli_buf).pages:
            writer.add_page(page)
    elif chart_pdf:
        # Excel's native PDF export preserves the worksheet's own shapes,
        # text and chart geometry without using the Windows clipboard --
        # but it arrives as its own separate PDF, so each page gets this
        # report's gold border stamped underneath (and is scaled onto this
        # report's actual page_size) rather than being appended verbatim;
        # see _build_bordered_kundli_page()'s docstring for why both of
        # those were needed.
        for excel_page in PdfReader(str(chart_pdf)).pages:
            writer.add_page(_build_bordered_kundli_page(excel_page, page_size))
    elif kundli_chart_image:
        kundli_buf = _build_kundli_pdf(
            kundli_chart_image, page_size,
            left_margin, right_margin, top_margin, bottom_margin,
        )
        for page in PdfReader(kundli_buf).pages:
            writer.add_page(page)

    if south_indian_charts:
        # "You can still print the charts from the D30NatalTransit
        # worksheet" -- right after the North Indian Kundli chart pages,
        # since it's a different chart drawing convention from a different
        # sheet/range, not a duplicate of those pages.
        south_indian_buf = _build_south_indian_charts_pdf(
            south_indian_charts, page_size,
            left_margin, right_margin, top_margin, bottom_margin,
        )
        for page in PdfReader(south_indian_buf).pages:
            writer.add_page(page)

    # 2026-09-21: "Move the Troubles and Misfortune at the End" -- moved from
    # right after the Kundli chart pages to after the whole main report body,
    # so it's now the LAST thing in the PDF. "remove the PLANETARY
    # CHARACTERISTICS & REMEDIES page" -- generate_overview_report.py's
    # main() no longer extracts planetary_characteristics/d30_chart_cells, so
    # they arrive here as None and this block below is simply never reached;
    # _build_planetary_characteristics_pdf() and its build_pdf() parameters
    # are left in place (not deleted) in case the page is wanted back.
    for page in PdfReader(main_buf).pages:
        writer.add_page(page)

    if troubles_data:
        troubles_buf = _build_troubles_pdf(
            troubles_data, page_size,
            left_margin, right_margin, top_margin, bottom_margin,
        )
        for page in PdfReader(troubles_buf).pages:
            writer.add_page(page)

    if planetary_characteristics:
        planetary_char_buf = _build_planetary_characteristics_pdf(
            planetary_characteristics, d30_chart_cells, page_size,
            left_margin, right_margin, top_margin, bottom_margin,
        )
        for page in PdfReader(planetary_char_buf).pages:
            writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)
