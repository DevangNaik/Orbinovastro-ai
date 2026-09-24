"""
Native (vector) rendering of the Kundli divisional charts (D1, D9, Bhava
Chalit, D30) -- chart diagram + the two accompanying data tables -- as
ReportLab flowables, replacing the old approach of exporting the Kundli
worksheet through Excel's native PDF renderer and merging the resulting
pages in as-is.

2026-09-19: client shared a real screenshot of a generated report's D1
chart page and said the raw Excel-exported look ("border is not visible"
was the earlier, separate complaint about this same page) wasn't
appealing next to the rest of the polished report, and asked how to fix
it "do not make any change in excel". Since the Excel worksheet itself is
off the table, the fix has to happen entirely on this side: redraw the
diamond chart natively instead of embedding Excel's own rendering of it,
and rebuild its two data tables with this report's own table styling
instead of Excel's default grid/font.

GEOMETRY -- do not "simplify" this without re-deriving it the same way:
the fixed 12-region layout and the house-to-position assignment were
derived empirically from that reference screenshot, by matching every
visible planet box's pixel position against that same chart's own
"House / Rasi / Planets" table (ground truth), NOT assumed from generic
"standard North Indian chart" recollection -- getting the rotation or
handedness wrong here would silently produce an astrologically WRONG
chart (right data, wrong house), which is a much worse failure than the
purely cosmetic problem this change sets out to fix.

What the matching showed: the small gray numbers printed in each of the
12 diamond regions are RASHI numbers (1=Aries ... 12=Pisces), fixed to
their positions regardless of any specific client's data. The reference
chart's ascendant is Scorpio (rashi 8), and its Ascendant box landed in
the TOP diamond point. Since a chart's houses always occupy consecutive
rashis starting from the ascendant's own rashi, and the reference chart's
rashi numbers decreased 8,7,6,5... going CLOCKWISE from the top, houses
1,2,3...12 must increase going COUNTER-CLOCKWISE from the top instead.
The four "kite" (diamond-point) positions -- top, left, bottom, right --
landed on houses 1, 4, 7, 10, which are exactly the four kendra/angular
houses in Vedic astrology. That fell out of the geometry rather than
being assumed going in, which is why this layout is trusted.

DATA SOURCE -- this module only draws from already-parsed data (see
KundliChartData/HouseData/PlanetBox below); it has no Excel/COM
dependency of its own. See generate_overview_report.py for how that data
gets extracted from the existing (unchanged) Excel export.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib import colors as rl_colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

RASHI_ABBR = ["Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi"]
RASHI_NUM = {abbr: i + 1 for i, abbr in enumerate(RASHI_ABBR)}

# 2026-09-19: dropped the old "Fire · Earth · Air · Water · Ether" prefix
# here now that the house shading itself carries a real, color-keyed
# legend (see _ELEMENT_LEGEND_SEGMENTS) -- keeping both would just repeat
# the same words twice in the footer.
# Leading "●" explains the corner badge drawn by _draw_special_badge.
#
# 2026-09-20: symbols corrected to match the client's own live workbook,
# discovered while wiring extract_kundli_charts() -- the Kundli sheet's
# own Flags column (and its own decorative footer text) uses E-up-arrow/
# D-down-arrow for Exalt/Debil, not the E+/D+ this was guessed as before
# any real flag data had been seen. The sheet's Vargottama symbol ("▫",
# U+25AB white small square) is NOT in ReportLab's Helvetica -- it silently
# draws as a corrupted-glyph black box (caught by this project's standard
# render + pdftotext-for-U+25A0 check) -- so extract_kundli_charts()
# rewrites it to "°" on the way in, and this legend uses that same "V°"
# rather than the sheet's own unrenderable "▫".
FLAG_LEGEND = "● = special condition  |  R* Retro  C^ Comb  E↑ Exalt  D↓ Debil  V° Varg"


@dataclass
class PlanetBox:
    """One planet's placement, as shown inside a chart's diamond box and
    as one row of the accompanying Planet/Position/Degree table."""
    code: str            # e.g. "Su", "Asc", "Ma"
    house: int           # 1..12 -- which house this planet occupies
    degree: str = ""     # e.g. "27°51'"
    retro: bool = False
    nak_abbr: str = ""   # first 3 letters of the nakshatra, e.g. "Kri"
    nak_full: str = ""   # e.g. "Krittika"
    pada: str = ""       # e.g. "1"
    flag: str = ""       # one of "", "R*", "V°", "C^", "E+", "D+"
    nature: str = ""     # "Benefic" / "Malefic" / "" (unclassified)
    interpretation: str = ""
    is_ascendant: bool = False

    def chart_label(self) -> str:
        code = f"{self.code}(R)" if self.retro and not self.is_ascendant else self.code
        parts = [code, self.degree]
        if self.nak_abbr:
            parts.append(f"{self.nak_abbr}{self.pada}")
        text = " ".join(p for p in parts if p)
        if self.flag:
            text += f" {self.flag}"
        return text


@dataclass
class KundliChartData:
    """Everything needed to draw one divisional chart (e.g. D1) and its
    two accompanying tables. `houses` maps house number (1-12) to that
    house's rashi number (1=Aries..12=Pisces); `planets` is every planet
    placement for this chart (Ascendant included, code "Asc")."""
    title: str                     # e.g. "Rashi (D1) · Mehul · Lagna Sc"
    houses: dict                   # {1: rashi_num, 2: rashi_num, ...}
    planets: list = field(default_factory=list)  # list[PlanetBox]

    def planets_by_house(self) -> dict:
        by_house = {}
        for p in self.planets:
            by_house.setdefault(p.house, []).append(p)
        return by_house


# ---------------------------------------------------------------------
# Diamond geometry (see module docstring for how this was derived)
# ---------------------------------------------------------------------

def _region_polygons(x0, y0, size):
    T = (x0 + size / 2, y0 + size)
    B = (x0 + size / 2, y0)
    L = (x0, y0 + size / 2)
    R = (x0 + size, y0 + size / 2)
    O = (x0 + size / 2, y0 + size / 2)
    TL, TR, BL, BR = (x0, y0 + size), (x0 + size, y0 + size), (x0, y0), (x0 + size, y0)

    def mid(p, q):
        return ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)

    X1, X2, X3, X4 = mid(T, L), mid(T, R), mid(R, B), mid(B, L)
    return [
        [T, X2, O, X1],   # House 1  -- top kite
        [TL, T, X1],      # House 2
        [TL, X1, L],      # House 3
        [L, X1, O, X4],   # House 4  -- left kite
        [BL, L, X4],      # House 5
        [BL, X4, B],      # House 6
        [B, X4, O, X3],   # House 7  -- bottom kite
        [BR, B, X3],      # House 8
        [BR, X3, R],      # House 9
        [R, X3, O, X2],   # House 10 -- right kite
        [TR, R, X2],      # House 11
        [TR, X2, T],      # House 12
    ]


_IS_KITE = [True, False, False, True, False, False, True, False, False, True, False, False]


def _centroid(poly):
    n = len(poly)
    return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)


# 2026-09-19, superseded same day: this used to hold a per-PLANET color
# table (Su=orange, Ma=red, etc., after the client asked for "color coding
# like planets like Horosoft"). Later the same day the client redefined
# the scheme again: "Benefic Dark Green Border, Malefic Dark Red border
# and the text background color matches with the Planet element" -- i.e.
# a planet's color is now its ELEMENT's fill + its NATURE's border (see
# _box_style / _nature_border_color / PLANET_TATTVA below) rather than a
# fixed per-planet hue, so that per-planet palette is gone. Kept only the
# neutral fallback fill for the 3 outer planets (no Tattva assigned) and
# the Ascendant's own fill/border, which are still used as-is.
_OUTER_FILL = "#e6e6ea"
_ASCENDANT_FILL, _ASCENDANT_BORDER = "#ffffff", "#1a1a2e"


# 2026-09-19: client redefined the box coloring scheme entirely: "Benefic
# Dark Green Border, Malefic Dark Red border and the text background
# color matches with the Planet element.. so we can see how it will react
# in the Rashi element on visuals" -- i.e. the box FILL now shows the
# planet's own Tattva/element (see PLANET_TATTVA further down), the box
# BORDER shows its Nature (Benefic/Malefic), and since the house region
# behind the box is already shaded by the RASHI's element (see
# _ELEMENT_BY_RASHI), a planet's box fill matching or clashing with its
# surrounding region's fill IS the visual "reaction" -- no separate
# indicator needed, the elemental relationship in element_reaction() is
# now literally visible as a color match/mismatch on the page itself.
_BENEFIC_BORDER = "#1e6b3a"
_MALEFIC_BORDER = "#8f2020"
_NEUTRAL_NATURE_BORDER = "#6b6f7a"   # no Nature classified (the 3 outer planets)
_ETHER_FILL = "#e3d6f0"              # Jupiter's Tattva -- doesn't correspond to
                                      # any of the 4 sign-elements, so it needs
                                      # its own color rather than borrowing one
                                      # of theirs (soft violet, the classical
                                      # Akasha/space association).


def _nature_border_color(planet: PlanetBox) -> str:
    if planet.is_ascendant:
        return _ASCENDANT_BORDER
    nature = (planet.nature or "").strip().lower()
    if nature == "benefic":
        return _BENEFIC_BORDER
    if nature == "malefic":
        return _MALEFIC_BORDER
    return _NEUTRAL_NATURE_BORDER


def _has_special_condition(planet: PlanetBox) -> bool:
    """True when this placement is Retrograde, Combust, Exalted,
    Debilitated, or Vargottama (see FLAG_LEGEND for the R*/C^/E↑/D↓/V▫
    codes). Checks both `retro` and `flag` because some data sets the R*
    flag text directly while others only set the boolean, and a placement
    can carry Combust/Exalted/Debilitated/Vargottama in `flag` without
    being retrograde at all (e.g. Jupiter Combust but direct)."""
    return bool(planet.retro or planet.flag)


# 2026-09-19: client feedback -- varying the border THICKNESS for a special
# condition on top of the same green/red Nature color read as
# "conflicting" (a thin green border and a thick green border look like a
# rendering inconsistency, not two intentional signals). Tried dropping
# the special-condition signal from the border entirely, but the client
# then asked to keep BOTH, "visually separated" -- so Nature stays on the
# border alone (constant width, see _box_style below), and the special
# condition gets its own small corner badge instead (_draw_special_badge),
# a completely different visual channel from color or line width.
_SPECIAL_BADGE_FILL = "#e8a317"
_SPECIAL_BADGE_BORDER = "#7a4a00"


SPECIAL_BADGE_PAD = 7  # extra box width reserved for the badge, see below


def _draw_special_badge(c, bx, by, box_w, box_h):
    """Draws a small filled dot against the box's right edge, vertically
    centered -- the marker that a placement is Retro/Combust/Exalted/
    Debilitated/Vargottama (which one is spelled out in the box's own
    label text and the table's Flags column; this badge only flags THAT
    something applies, at a glance, independent of the border's own
    color/width).

    2026-09-19: client feedback, twice -- v1 sat centered ON the top-right
    corner and covered the last character or two of tightly-fit label
    text; v2 moved outside the corner entirely but then risked overlapping
    the box stacked directly above it (stacked boxes are only ~1.4pt
    apart). This version stays fully INSIDE the box's own rectangle
    (never extends past by/by+box_h), in a strip of width SPECIAL_BADGE_PAD
    that the caller reserves in box_w specifically for it -- so it can
    neither cover the label (the label is centered in the remaining
    width) nor collide with a vertically stacked neighbor."""
    r = 2.0
    cx = bx + box_w - r - 1.2
    cy = by + box_h / 2
    c.setFillColor(HexColor(_SPECIAL_BADGE_FILL))
    c.setStrokeColor(HexColor(_SPECIAL_BADGE_BORDER))
    c.setLineWidth(0.5)
    c.circle(cx, cy, r, fill=1, stroke=1)


def _box_style(planet: PlanetBox):
    if planet.is_ascendant:
        return _ASCENDANT_FILL, _ASCENDANT_BORDER, 1.1
    tattva = PLANET_TATTVA.get(planet.code)
    fill = _ETHER_FILL if tattva == "ether" else _ELEMENT_FILL.get(tattva, _OUTER_FILL)
    border = _nature_border_color(planet)
    # Border now carries ONLY Nature (green/red/grey) at a constant width
    # -- see _draw_special_badge above for the separate special-condition
    # signal.
    return fill, border, 1.0


# 2026-09-19: client asked to also shade each of the 12 house regions by
# element (Fire/Earth/Air/Water) -- the standard grouping of the 12
# zodiac signs into 3-sign triplicities. Kept as very light washes (much
# paler than the planet-box colors above) so the shading reads as
# background texture, not competing with the planet boxes/text sitting
# on top of it.
_ELEMENT_BY_RASHI = {
    1: "fire", 5: "fire", 9: "fire",        # Aries, Leo, Sagittarius
    2: "earth", 6: "earth", 10: "earth",    # Taurus, Virgo, Capricorn
    3: "air", 7: "air", 11: "air",          # Gemini, Libra, Aquarius
    4: "water", 8: "water", 12: "water",    # Cancer, Scorpio, Pisces
}
# 2026-09-19: client specified the actual hue per element directly ("Fire
# is Red, Earth is brown, Airy white and watery blue shade") rather than
# the earlier generic pastel wash -- still softened toward pale/light so
# the planet boxes and rashi numbers sitting on top stay legible, but Fire
# and Water in particular are now a visibly warmer red / more saturated
# blue than before. Air stays plain white per that instruction (i.e.
# effectively unshaded), which also reads clearly against the other three.
# 2026-09-19: client feedback after the first pass -- "shades are very
# close to each other .. make it very easy to understand type of color
# shade" -- pushed noticeably more saturated/distinct than the earlier
# pale wash (which read as near-identical light pastels at a glance),
# while staying light enough that the small grey rashi numbers and planet
# boxes drawn on top of each region stay legible.
_ELEMENT_FILL = {
    "fire": "#f0a999",
    "earth": "#cfa96e",
    "air": "#ffffff",
    "water": "#9cc9e8",
}
# Darker, readable versions of the same 4 hues, used only for the footer
# legend text (not the region backgrounds themselves) -- "Air" gets a
# neutral grey label since white text would be invisible on the page.
_ELEMENT_LEGEND_SEGMENTS = [
    ("Fire ", "#a83224"),
    ("Earth ", "#7a5a2e"),
    ("Air ", "#888888"),
    ("Water", "#2f6690"),
]


# ---------------------------------------------------------------------
# Planet-element (Tattva) vs. sign-element "reaction" -- client, 2026-09-
# 19: "Need to identify the reaction based on vedic text how firy element
# will behave in different rashi."
#
# Classical basis (and where this is a reasoned extension, not a direct
# quotation -- flagged honestly rather than dressed up as scripture):
#   - Brihat Parashara Hora Shastra assigns a fixed Tattva to 5 of the 9
#     grahas: Mars=Agni(Fire), Mercury=Prithvi(Earth), Jupiter=Akasha
#     (Ether), Venus=Jala(Water), Saturn=Vayu(Air). That's a direct
#     classical citation, not a guess.
#   - BPHS's own 5-tattva list doesn't cover Sun, Moon, Rahu, Ketu.
#     Filled in here via the common secondary convention: Sun=Fire (it
#     rules Agni/vitality the way Mars does), Moon=Water (near-universal
#     across sources), Rahu=Air (paired with Saturn, whose behavior it
#     shadows), Ketu=Fire (paired with Mars). This pairing is the most
#     widely repeated convention, but -- unlike the BPHS 5 -- it is NOT
#     uniformly fixed across every source, so treat Su/Mo/Ra/Ke's Tattva
#     as "common convention" rather than "settled classical fact" if this
#     ever needs to be defended to a client who's read a different text.
#   - "A planet in a sign of its own element gains strength" and "Fire
#     and Water are mutual enemies" are both directly documented
#     classical statements (the latter is the same Fire/Water enmity
#     found throughout Indian elemental doctrine -- Fire is hot+dry,
#     Water is cold+moist, direct opposites). Earth/Air as the other
#     enemy pair, and Fire/Air + Earth/Water as the two friendly pairs,
#     follow the same hot-cold/dry-moist logic applied symmetrically
#     (Fire and Air share "hot"; Earth and Water share "moist"/"cold") --
#     this is the same elemental-dignity structure Tajik/Varshaphal
#     astrology's own sign relationships draw on, not an import from
#     Western astrology done for convenience.
#   - Ether (Jupiter, Ketu-by-pairing... though Ketu is placed under Fire
#     above, not Ether, per the more common convention) doesn't correspond
#     to any of the 12 signs' own element (only Fire/Earth/Air/Water
#     divide the 12 signs 3-each), so a planet whose Tattva is Ether is
#     treated as elementally neutral everywhere, rather than forced into
#     an always-mismatched reading purely because "ether" never equals
#     one of the 4 sign-elements.
PLANET_TATTVA = {
    "Su": "fire", "Ma": "fire", "Ke": "fire",
    "Me": "earth",
    "Sa": "air", "Ra": "air",
    "Mo": "water", "Ve": "water",
    "Ju": "ether",
}
_FRIENDLY_ELEMENT_PAIRS = {frozenset({"fire", "air"}), frozenset({"earth", "water"})}
_ENEMY_ELEMENT_PAIRS = {frozenset({"fire", "water"}), frozenset({"earth", "air"})}

# 2026-09-19: client sent a real screenshot of another chart program's own
# planet-label coloring ("Planet colors are here") -- colors below were
# sampled directly from that screenshot's pixels (not eyeballed), giving
# an actual reference instead of the earlier "no live screenshot was
# available" guess. Applied as the LABEL TEXT color -- both on the
# diamond-chart box and the Planet-column text in the two tables -- layered
# on top of (not replacing) the box fill=element / border=Benefic-Malefic
# scheme built just before this, so a box still shows its element (fill)
# and its Nature (border) while the code itself carries this reference's
# own planet identity color.
PLANET_TEXT_COLOR = {
    "Su": "#ff7000",
    # Darkened from the screenshot's own #42e6ff -- Moon's Tattva is Water,
    # so its box fill is the same light water-blue as a Water-sign region
    # (_ELEMENT_FILL["water"]); the screenshot's bright cyan nearly
    # disappeared against that fill/region combination. Deepened toward
    # teal just enough to stay legible everywhere while still reading as
    # "cyan" rather than drifting toward Saturn's indigo or the outer
    # planets' blue.
    "Mo": "#0b8fae",
    "Ma": "#e12623",
    "Me": "#00b000",
    "Ju": "#ff8800",
    "Ve": "#ff7bb9",
    "Sa": "#341ca1",
    "Ra": "#b319a6",
    "Ke": "#8b5f48",
    "Ur": "#0088ff",
    "Ne": "#0088ff",
    "Pl": "#0088ff",
}


def _planet_text_color(planet: PlanetBox) -> str:
    if planet.is_ascendant:
        return "#000000"
    return PLANET_TEXT_COLOR.get(planet.code, "#222222")

_ELEMENT_LABEL_COLOR = {
    "Own element": "#2f7d46",
    "Friendly element": "#5a9e6f",
    "Enemy element": "#c1554f",
    "Ether (neutral)": "#7a7a7a",
}


def element_reaction(planet_code: str, rashi_element):
    """Returns (label, description) for how planet_code's own Tattva
    relates to rashi_element (the element of the sign it currently
    occupies -- see _ELEMENT_BY_RASHI). Returns (None, None) for a planet
    with no Tattva assigned here (the 3 outer planets) or no rashi_element
    given (e.g. Bhava Chalit data that hasn't resolved a house's rashi)."""
    tattva = PLANET_TATTVA.get(planet_code)
    if not tattva or not rashi_element:
        return None, None
    if tattva == "ether":
        return "Ether (neutral)", ("Space (Akasha) transcends the 4 elements the 12 signs divide "
                                    "into -- no direct elemental clash or support here.")
    if tattva == rashi_element:
        return "Own element", ("Same element as the sign it occupies -- its natural strength "
                                "here is unobstructed (a planet in a sign of its own element "
                                "gains strength).")
    pair = frozenset({tattva, rashi_element})
    if pair in _FRIENDLY_ELEMENT_PAIRS:
        return "Friendly element", ("A supportive element pairing -- the sign's own quality "
                                     "reinforces rather than resists this planet's natural "
                                     "expression.")
    if pair in _ENEMY_ELEMENT_PAIRS:
        return "Enemy element", ("An opposing element pairing (Fire/Water and Earth/Air are "
                                  "classically mutual enemies) -- friction here, its natural "
                                  "expression is dampened or resisted by the sign it sits in.")
    return "Neutral element", "Neither a classically friendly nor enemy element pairing."


def _draw_legend_line(c, x, y, segments, font="Helvetica-Bold", size=5.6):
    """Draws `segments` (a list of (text, hex_color) pairs) left-to-right
    on one line starting at (x, y) -- lets one footer line color-key each
    word to match the region shading it explains, which a single plain
    canvas.drawString() call can't do (canvas text has no inline markup,
    unlike a Paragraph)."""
    cx = x
    for text, color in segments:
        c.setFillColor(HexColor(color))
        c.setFont(font, size)
        c.drawString(cx, y, text)
        cx += stringWidth(text, font, size)


def _draw_chart(c, x0, y0, size, title, houses: dict, planets_by_house: dict,
                 header_h=16, footer_h=20):
    chart_top = y0 + footer_h + size
    c.setFillColor(HexColor("#1a2744"))
    c.rect(x0, chart_top, size, header_h, fill=1, stroke=0)
    c.setFillColor(rl_colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(x0 + size / 2, chart_top + header_h / 2 - 3.1, title)

    # 2026-09-19: client asked for the 12 house regions themselves shaded
    # by element (Fire/Earth/Air/Water) -- each region's element follows
    # the RASHI occupying it for THIS chart (not the fixed house number),
    # since a sign's element is a fixed astrological fact but which house
    # that sign falls in shifts with the ascendant. Filled BEFORE the
    # border/diagonal lines and BEFORE the rashi numbers/planet boxes
    # below, so those still draw crisply on top of the shading rather
    # than being obscured by it.
    polygons = _region_polygons(x0, y0 + footer_h, size)
    c.setLineWidth(0)
    for house_num in range(1, 13):
        rashi_num = houses.get(house_num)
        element = _ELEMENT_BY_RASHI.get(rashi_num) if rashi_num else None
        if element is None:
            continue
        poly = polygons[house_num - 1]
        c.setFillColor(HexColor(_ELEMENT_FILL[element]))
        path = c.beginPath()
        path.moveTo(*poly[0])
        for pt in poly[1:]:
            path.lineTo(*pt)
        path.close()
        c.drawPath(path, fill=1, stroke=0)

    c.setStrokeColor(HexColor("#8a94a6"))
    c.setLineWidth(0.75)
    c.rect(x0, y0 + footer_h, size, size, fill=0, stroke=1)
    T = (x0 + size / 2, y0 + footer_h + size)
    B = (x0 + size / 2, y0 + footer_h)
    L = (x0, y0 + footer_h + size / 2)
    R = (x0 + size, y0 + footer_h + size / 2)
    TL, TR = (x0, y0 + footer_h + size), (x0 + size, y0 + footer_h + size)
    BL, BR = (x0, y0 + footer_h), (x0 + size, y0 + footer_h)
    c.setLineWidth(0.5)
    for a, b in [(TL, BR), (TR, BL), (T, R), (R, B), (B, L), (L, T)]:
        c.line(a[0], a[1], b[0], b[1])

    # Two footer lines: which color is which element (matching the house
    # shading above), then the existing planet-condition flag key.
    _draw_legend_line(c, x0, y0 + 10.5, _ELEMENT_LEGEND_SEGMENTS)
    c.setFillColor(HexColor("#555555"))
    c.setFont("Helvetica-Oblique", 5.6)
    c.drawString(x0, y0 + 2, FLAG_LEGEND)

    for house_num in range(1, 13):
        poly = polygons[house_num - 1]
        cx, cy = _centroid(poly)
        rashi_num = houses.get(house_num)
        if rashi_num is not None:
            outer_pt = poly[0]
            lx = cx + (outer_pt[0] - cx) * 0.55
            ly = cy + (outer_pt[1] - cy) * 0.55
            # Darkened from the original #8a8a8a now that the region
            # backgrounds behind it are more saturated (see _ELEMENT_FILL
            # above) -- keeps the number readable on all 4 shades.
            c.setFillColor(HexColor("#555555"))
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(lx, ly - 2.2, str(rashi_num))

        planets = planets_by_house.get(house_num, [])
        if not planets:
            continue
        max_w = size * (0.225 if _IS_KITE[house_num - 1] else 0.17)
        box_h, gap = 10.5, 1.4
        total_h = len(planets) * box_h + (len(planets) - 1) * gap
        top_y = cy + total_h / 2
        for i, planet in enumerate(planets):
            label = planet.chart_label()
            has_special = not planet.is_ascendant and _has_special_condition(planet)
            badge_pad = SPECIAL_BADGE_PAD if has_special else 0
            font_size = 6.0
            text_w = stringWidth(label, "Helvetica", font_size)
            box_w = min(max(text_w + 5 + badge_pad, 26), max_w)
            text_area_w = box_w - badge_pad
            by = top_y - i * (box_h + gap) - box_h
            bx = cx - box_w / 2
            fill, border, line_w = _box_style(planet)
            c.setFillColor(HexColor(fill))
            if line_w > 0:
                c.setStrokeColor(HexColor(border))
                c.setLineWidth(line_w)
                c.roundRect(bx, by, box_w, box_h, 1.6, fill=1, stroke=1)
            else:
                c.roundRect(bx, by, box_w, box_h, 1.6, fill=1, stroke=0)
            if has_special:
                _draw_special_badge(c, bx, by, box_w, box_h)
            # Label text colored by planet identity (see PLANET_TEXT_COLOR)
            # -- a third layer on top of the box's fill (element) and
            # border (Nature), matching the reference screenshot's own
            # planet-color coding.
            c.setFillColor(HexColor(_planet_text_color(planet)))
            font_name = "Helvetica-Bold" if planet.is_ascendant else "Helvetica"
            c.setFont(font_name, font_size)
            actual_w = stringWidth(label, font_name, font_size)
            while actual_w > text_area_w - 2 and font_size > 4.3:
                font_size -= 0.3
                c.setFont(font_name, font_size)
                actual_w = stringWidth(label, font_name, font_size)
            # Centered within the text area only (box_w minus the badge's
            # reserved strip), so the label never drifts under the badge.
            c.drawCentredString(bx + text_area_w / 2, by + box_h / 2 - font_size * 0.35, label)


class NorthIndianChartFlowable(Flowable):
    """A ReportLab Flowable that draws one native diamond chart, so it can
    sit in a normal Platypus story alongside this report's other tables."""

    def __init__(self, chart: KundliChartData, size):
        super().__init__()
        self.chart = chart
        self.size = size
        self.header_h = 18
        self.footer_h = 20
        self.width = size
        self.height = size + self.header_h + self.footer_h

    def wrap(self, avail_width, avail_height):
        return self.width, self.height

    def draw(self):
        planets_by_house = self.chart.planets_by_house()
        _draw_chart(self.canv, 0, 0, self.size, self.chart.title,
                    self.chart.houses, planets_by_house,
                    header_h=self.header_h, footer_h=self.footer_h)


# ---------------------------------------------------------------------
# Native replacement tables (House/Rasi/Planets, Planet/Position/Degree/
# Flags/Nature/Nak-Pada/Interpretation) -- built with this report's own
# table styling instead of Excel's default grid/font.
# ---------------------------------------------------------------------

_NAVY = HexColor("#1a2744")
_GREY_LINE = HexColor("#969696")

_HEADER_STYLE = ParagraphStyle("KundliTableHeader", fontName="Helvetica-Bold",
                                fontSize=7.5, leading=9, alignment=TA_CENTER,
                                textColor=rl_colors.white)
_BODY_STYLE = ParagraphStyle("KundliTableBody", fontName="Helvetica", fontSize=7,
                              leading=8.5, textColor=rl_colors.black)
_BODY_BOLD_STYLE = ParagraphStyle("KundliTableBodyBold", fontName="Helvetica-Bold",
                                   fontSize=7, leading=8.5, textColor=rl_colors.black)
_BODY_CENTER_STYLE = ParagraphStyle("KundliTableBodyCenter", parent=_BODY_STYLE,
                                     alignment=TA_CENTER)


def _esc(text) -> str:
    return _xml_escape("" if text is None else str(text))


def _P(text, style=_BODY_STYLE):
    return Paragraph(text, style)


def _rich_planet_code(planet: PlanetBox) -> str:
    """The planet's code (e.g. "Ma", "Ma(R)"), colored via
    _planet_text_color -- the SAME function that colors that planet's
    label on the diamond chart, so a planet reads as the same identity
    color everywhere it appears on the page. The Planet/Position table
    additionally shades this same cell's background by the planet's own
    element and its border by its Nature (see build_planet_detail_table),
    mirroring the chart box's fill+border+text combination exactly; the
    shared multi-planet House/Rasi/Planets cell can only carry the text
    color, not a per-planet background/border."""
    code_display = f"{planet.code}(R)" if planet.retro and not planet.is_ascendant else planet.code
    color = _planet_text_color(planet)
    return f'<font color="{color}"><b>{_esc(code_display)}</b></font>'


def _rich_chart_label(planet: PlanetBox) -> str:
    """Same content as PlanetBox.chart_label(), but with just the planet
    code portion colored/bolded (via _rich_planet_code) while the
    degree/nakshatra/flag remainder stays plain body text."""
    parts = [planet.degree]
    if planet.nak_abbr:
        parts.append(f"{planet.nak_abbr}{planet.pada}")
    rest = " ".join(p for p in parts if p)
    if planet.flag:
        rest = f"{rest} {planet.flag}".strip()
    rest_esc = _esc(rest)
    code_html = _rich_planet_code(planet)
    return f"{code_html} {rest_esc}" if rest_esc else code_html


def _base_style(highlights=None):
    cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, _GREY_LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [rl_colors.white, HexColor("#f7f5ef")]),
    ]
    for row, col, color in highlights or []:
        cmds.append(("BACKGROUND", (col, row), (col, row), color))
    return TableStyle(cmds)


def build_house_rashi_table(chart: KundliChartData, page_width: float, col_widths=None) -> Table:
    """Rebuilds the "House / Rāśi / Planets" summary table using this
    report's own styling instead of Excel's default grid. `col_widths`
    (optional, explicit point widths for the 3 columns) overrides the
    default page_width-fraction sizing -- used when this table is placed
    in a narrower column than the full page (see build_kundli_chart_section
    below), where House/Rāśi only need a small fixed width regardless of
    how narrow the table as a whole is."""
    # Plain "Rasi" rather than the diacritical "Rāśi" the Excel
    # template uses -- Helvetica's WinAnsiEncoding doesn't have those
    # accented characters, which would otherwise reproduce the exact
    # missing-glyph "black box" bug already fixed elsewhere in this report
    # for AI-generated text (see overview_pdf_writer.py's _sanitize_unicode).
    headers = ["House", "Rasi", "Planets"]
    rows = [[_P(h, _HEADER_STYLE) for h in headers]]
    by_house = chart.planets_by_house()
    for house_num in range(1, 13):
        rashi_num = chart.houses.get(house_num)
        rashi_abbr = RASHI_ABBR[rashi_num - 1] if rashi_num else ""
        planets = by_house.get(house_num, [])
        planets_text = ", ".join(_rich_chart_label(p) for p in planets)
        rows.append([
            _P(str(house_num), _BODY_CENTER_STYLE),
            _P(rashi_abbr, _BODY_CENTER_STYLE),
            _P(planets_text, _BODY_STYLE),
        ])
    col_widths = col_widths or [page_width * w for w in (0.12, 0.13, 0.75)]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(_base_style())
    return table


def build_planet_detail_table(chart: KundliChartData, page_width: float) -> Table:
    """Rebuilds the "Planet / Position / Degree / Flags / Nature / Element
    / Nak/Pada / Interpretation" detail table using this report's own
    styling. The Element column (see element_reaction() above) is what the
    client asked for directly: "identify the reaction based on vedic text
    how firy element will behave in different rashi" -- read straight off
    this table rather than requiring a mental cross-check against the
    chart's own elemental shading."""
    headers = ["Planet", "Position", "Degree", "Flags", "Nature", "Element", "Nak/Pada", "Interpretation"]
    rows = [[_P(h, _HEADER_STYLE) for h in headers]]
    # Same fixed order as the chart itself (Ascendant, then Su..Ke, then
    # the outer planets), not insertion order, so this table reads the
    # same way every time regardless of how the source data was assembled.
    order = ["Asc", "Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke", "Ur", "Ne", "Pl"]
    by_code = {p.code: p for p in chart.planets}
    # Per-row cell styling for the Planet column, collected alongside the
    # rows themselves -- fill = this planet's own element, border =
    # Benefic/Malefic, exactly mirroring _box_style()'s fill+border on the
    # diamond chart (client, 2026-09-19: "Make sure chart color match with
    # table planet colors" / "text background color matches with the
    # Planet element"). A Table cell can carry its own BOX and BACKGROUND
    # via TableStyle even though the House/Rasi/Planets table's shared
    # "Planets" list cell can't (that one stays text-color-only, see
    # _rich_chart_label).
    planet_cell_cmds = []
    for code in order:
        p = by_code.get(code)
        if p is None:
            continue
        row_idx = len(rows)  # index this row will have once appended below
        rashi_num = chart.houses.get(p.house)
        rashi_abbr = RASHI_ABBR[rashi_num - 1] if rashi_num else ""
        position = f"{rashi_abbr}·H{p.house}"
        # 2026-09-20: prefer the full nakshatra name when the caller has one
        # (e.g. a hand-built test fixture), but fall back to the short
        # abbr+pada form (e.g. "Pun2") when it doesn't -- extract_kundli_
        # charts() in generate_overview_report.py never sets nak_full,
        # since this workbook's own Nak/Pada columns are themselves already
        # in that abbreviated form for 3 of the 4 charts (D1 is the odd one
        # out, spelling the full name there -- see _split_nak_pada's
        # docstring), so showing the abbreviated form here is consistent
        # with what the sheet itself calls "Nak/Pada" everywhere else.
        nak_pada = f"{p.nak_full}({p.pada})" if p.nak_full else (
            f"{p.nak_abbr}{p.pada}" if p.nak_abbr else "")
        rashi_element = _ELEMENT_BY_RASHI.get(rashi_num)
        label, _desc = element_reaction(p.code, rashi_element)
        element_html = (f'<font color="{_ELEMENT_LABEL_COLOR.get(label, "#333333")}">'
                         f'<b>{_esc(label)}</b></font>') if label else ""

        if not p.is_ascendant:
            tattva = PLANET_TATTVA.get(p.code)
            fill_hex = _ETHER_FILL if tattva == "ether" else _ELEMENT_FILL.get(tattva)
            if fill_hex:
                planet_cell_cmds.append(("BACKGROUND", (0, row_idx), (0, row_idx), HexColor(fill_hex)))
        # Constant border width here too, matching _box_style -- see its
        # comment: the special condition reads from the Flags column, not
        # from a thickness change on this same Nature-colored border.
        planet_cell_cmds.append(("BOX", (0, row_idx), (0, row_idx), 0.9,
                                  HexColor(_nature_border_color(p))))

        rows.append([
            _P(_rich_planet_code(p), _BODY_BOLD_STYLE),
            _P(position, _BODY_CENTER_STYLE),
            _P(p.degree, _BODY_CENTER_STYLE),
            _P(p.flag, _BODY_CENTER_STYLE),
            _P(p.nature, _BODY_CENTER_STYLE),
            _P(element_html, _BODY_CENTER_STYLE),
            _P(nak_pada, _BODY_STYLE),
            _P(_esc(p.interpretation), _BODY_STYLE),
        ])
    col_widths = [page_width * w for w in (0.06, 0.08, 0.08, 0.06, 0.07, 0.09, 0.09, 0.47)]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(_base_style())
    table.setStyle(TableStyle(planet_cell_cmds))
    return table


def build_kundli_chart_section(chart: KundliChartData, page_width: float, chart_size=None) -> list:
    """Returns the flowables for one full divisional chart page's content
    (chart diagram + both tables) -- everything except the PageBreak
    between charts, which the caller adds.

    2026-09-21: client asked that one chart's diagram + both tables always
    fit on a single page ("all info about one chart and table of specific
    division are in one page"), rather than the House/Rasi/Planets table
    sitting in its own full-width block below the diagram (which, at 13
    planet rows, routinely pushed the Planet-detail table onto a second,
    mostly-empty page). The diamond diagram is capped at `chart_size`,
    well under page_width, so a wide blank strip always sat to its right
    doing nothing -- the House/Rasi/Planets table now lives there instead
    ("align table in right corner ... there is open space"), as a 2-column
    row with the diagram, which reclaims that table's ~150-200pt of
    vertical space for the Planet-detail table below. Chart size was also
    trimmed slightly (0.62->0.55 of page_width, 300->260pt cap) for extra
    margin -- verified against real workbook data (13-row D1/Bhava Chalit
    charts) to fit one page with room to spare."""
    chart_size = chart_size or min(page_width * 0.55, 260)
    chart_flowable = NorthIndianChartFlowable(chart, chart_size)

    side_gap = 10
    side_table_width = page_width - chart_size - side_gap
    # Fixed (not fraction-of-width) House/Rāśi columns -- a house number or
    # 2-letter rashi abbreviation needs the same small width regardless of
    # how narrow the table around it is; the Planets column gets whatever
    # is left, which matters more here than in the full-width case since
    # this table is now considerably narrower.
    house_col_w, rasi_col_w = 20, 24
    planets_col_w = max(side_table_width - house_col_w - rasi_col_w, 60)
    house_table = build_house_rashi_table(
        chart, side_table_width, col_widths=[house_col_w, rasi_col_w, planets_col_w])

    top_row = Table([[chart_flowable, house_table]], colWidths=[chart_size, side_table_width])
    top_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (1, 0), (1, 0), side_gap),
    ]))

    story = [
        top_row,
        Spacer(1, 8),
        build_planet_detail_table(chart, page_width),
    ]
    return story


# ---------------------------------------------------------------------
# "Troubles & Misfortune" page (2026-09-21) -- a concise, client-readable
# distillation of the client's D30-based KP medical-astrology analysis
# (see generate_overview_report.py's extract_troubles_misfortune(), which
# reads D30NatalTransit!BA:BN). That sheet's own layout is working
# scratch for the astrologer -- boolean helper columns, raw significator
# grade tables, house-list stacks -- none of which belongs in front of a
# client. This keeps the actual verdicts and their direct supporting
# facts, and drops the computational scaffolding entirely (client:
# "Make sure you concise detail").
# ---------------------------------------------------------------------

_TM_TITLE_NAVY = HexColor("#152b52")
_TM_TITLE_STYLE = ParagraphStyle("TroublesTitle", fontName="Helvetica-Bold", fontSize=16,
                                  textColor=_TM_TITLE_NAVY, leading=19, alignment=TA_CENTER,
                                  spaceAfter=3)
_TM_SUBTITLE_STYLE = ParagraphStyle("TroublesSubtitle", fontName="Helvetica-Oblique", fontSize=8,
                                     textColor=_GREY_LINE, alignment=TA_CENTER, spaceAfter=8)
_TM_SECTION_STYLE = ParagraphStyle("TroublesSection", fontName="Helvetica-Bold", fontSize=9.5,
                                    textColor=_TM_TITLE_NAVY, spaceBefore=8, spaceAfter=3)
_TM_BODY_STYLE = ParagraphStyle("TroublesBody", fontName="Helvetica", fontSize=7.5, leading=9.5,
                                 alignment=TA_LEFT)
_TM_TABLE_BODY_STYLE = ParagraphStyle("TroublesTableBody", fontName="Helvetica", fontSize=7,
                                       leading=8.5)


def _tm_p(text, style=_TM_TABLE_BODY_STYLE):
    return Paragraph(_esc(text) if text else "", style)


def build_troubles_misfortune_section(data: dict, page_width: float) -> list:
    """Returns the flowables for the "Troubles & Misfortune" page -- a
    concise read of the client's D30/KP medical-astrology indicators, from
    the dict generate_overview_report.extract_troubles_misfortune() reads
    out of D30NatalTransit!BA:BN. Everything here is condensed to fit one
    page: each deity's guidance is one sentence plus a short named-
    condition list (not the sheet's own two full tables), the KP verdicts
    are stated directly (not the significator grade tables that produced
    them), and the whole page uses this module's compact table styling
    (matching the Kundli chart pages it follows) rather than the sheet's
    own grid."""
    story = [
        Paragraph("TROUBLES &amp; MISFORTUNE", _TM_TITLE_STYLE),
        Paragraph("D30 (Trimsamsa) &amp; KP indicators for wellness awareness "
                  "&mdash; not a medical diagnosis; see Disclaimer.", _TM_SUBTITLE_STYLE),
    ]

    # -- Panchatattva deity table --
    deities = data.get("deities") or []
    if deities:
        headers = ["Deity", "Planets", "Health Concern", "Watch For"]
        rows = [[_tm_p(h, _HEADER_STYLE) for h in headers]]
        for d in deities:
            rows.append([
                _tm_p(d["deity"]), _tm_p(d["planets"]),
                _tm_p(d["effect"]), _tm_p(d["watch_for"]),
            ])
        col_widths = [page_width * w for w in (0.08, 0.11, 0.46, 0.35)]
        table = Table(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(_base_style())
        story += [table, Spacer(1, 6)]

    # -- Traditional marka (longevity) clues --
    clues = data.get("clues") or []
    if clues:
        story.append(Paragraph("Traditional Longevity Indicators", _TM_SECTION_STYLE))
        headers = ["Source", "Sign / Nature", "Clue"]
        rows = [[_tm_p(h, _HEADER_STYLE) for h in headers]]
        for c in clues:
            rows.append([_tm_p(c["label"]), _tm_p(c["detail"]), _tm_p(c["clue"])])
        col_widths = [page_width * w for w in (0.24, 0.20, 0.56)]
        table = Table(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(_base_style())
        story += [table, Spacer(1, 6)]

    # -- Current Dasha, disease-relevant periods --
    dasha = data.get("dasha") or []
    if dasha:
        story.append(Paragraph("Current Dasha &mdash; Disease-Relevant Periods", _TM_SECTION_STYLE))
        headers = ["Level", "Lord", "Period", "Body Focus", "Tendency"]
        rows = [[_tm_p(h, _HEADER_STYLE) for h in headers]]
        for row in dasha:
            rows.append([
                _tm_p(row["level"]), _tm_p(row["lord"]), _tm_p(row["period"]),
                _tm_p(row["body"]), _tm_p(row["tendency"]),
            ])
        col_widths = [page_width * w for w in (0.11, 0.08, 0.30, 0.24, 0.27)]
        table = Table(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(_base_style())
        story += [table, Spacer(1, 6)]

    # -- KP verdict summary --
    csl1 = data.get("csl1") or {}
    csl6 = data.get("csl6") or {}
    summary = data.get("summary") or {}
    verdict_lines = []
    if csl1.get("verdict"):
        verdict_lines.append(
            f'<b>General Health</b> (1st CSL {_esc(csl1.get("csl") or "")}): {_esc(csl1["verdict"])}')
    if csl6.get("verdict"):
        organs = ", ".join(o for o in [csl6.get("organs_csl"), csl6.get("organs_nl")] if o)
        line = f'<b>Disease Diagnosis</b> (6th CSL {_esc(csl6.get("csl") or "")}): {_esc(csl6["verdict"])}'
        if organs:
            line += f' &mdash; areas indicated: {_esc(organs)}.'
        verdict_lines.append(line)
    if summary.get("verdict"):
        verdict_lines.append(f'<b>Overall KP Verdict:</b> {_esc(summary["verdict"])}')
    if summary.get("implication"):
        verdict_lines.append(_esc(summary["implication"]))

    if verdict_lines:
        story.append(Paragraph("KP Verdict Summary", _TM_SECTION_STYLE))
        for line in verdict_lines:
            story.append(Paragraph(line, _TM_BODY_STYLE))
            story.append(Spacer(1, 3))

    return story


# ---------------------------------------------------------------------
# "Planetary Characteristics & Remedies" page (2026-09-21) -- client asked
# to "use whole worksheet and its table to generate report": D30NatalTransit
# has a second table (columns AL:AU, see generate_overview_report.py's
# extract_planetary_characteristics()) giving each planet's Jaimini Chara
# Karaka role plus its own Characteristics / Marriage / Health / Career /
# Remedies write-up -- distinct content from the Troubles & Misfortune page
# above, so it gets its own page rather than being folded in.
# ---------------------------------------------------------------------

_PLANET_FULL_NAME = {
    "Su": "Sun", "Mo": "Moon", "Ma": "Mars", "Me": "Mercury", "Ju": "Jupiter",
    "Ve": "Venus", "Sa": "Saturn", "Ra": "Rahu", "Ke": "Ketu", "Asc": "Ascendant",
}
_CK_FULL_NAME = {
    "AmK": "Amatya Karaka", "AK": "Atma Karaka", "BK": "Bhratri Karaka",
    "MK": "Matri Karaka", "PK": "Putra Karaka", "GK": "Gnati Karaka",
    "PiK": "Pitri Karaka", "DK": "Dara Karaka",
}
def _pc_planet_cell(planet_code: str, ck: str):
    color = "#000000" if planet_code == "Asc" else PLANET_TEXT_COLOR.get(planet_code, "#222222")
    name = _PLANET_FULL_NAME.get(planet_code, planet_code)
    lines = [f'<font color="{color}"><b>{_esc(planet_code)}</b></font>', f'<font size="6">{_esc(name)}</font>']
    if ck:
        ck_name = _CK_FULL_NAME.get(ck, ck)
        lines.append(f'<font size="6" color="#7a7a7a">{_esc(ck)} &mdash; {_esc(ck_name)}</font>')
    return Paragraph("<br/>".join(lines), ParagraphStyle(
        "PlanetCharPlanet", fontName="Helvetica", fontSize=7.5, leading=9, alignment=TA_CENTER))


def build_planetary_characteristics_section(rows: list, page_width: float,
                                             d30_chart_cells: dict | None = None) -> list:
    """Returns the flowables for the "Planetary Characteristics & Remedies"
    page -- one row per planet (+ Ascendant), each with its Jaimini Chara
    Karaka role and the sheet's own Characteristics / Marriage / Health /
    Career / Remedies text for that planet, from the list
    generate_overview_report.extract_planetary_characteristics() returns.
    Kept to this module's compact table styling (matching the other pages
    it sits alongside) rather than the sheet's own wide grid.

    2026-09-21: `d30_chart_cells` (optional, from generate_overview_report.
    py's extract_d30_south_indian_chart()) adds the D-30 Trimsamsa South
    Indian style mini-chart to one side of the page, above the table --
    "There is d30 chart in this page its south indian style ... print it
    in one side of page" -- using the same "open space beside a compact
    chart" layout as the D1/D9/Bhava Chalit Kundli pages, just with a
    caption instead of a second table filling the other side."""
    story = [
        Paragraph("PLANETARY CHARACTERISTICS &amp; REMEDIES", _TM_TITLE_STYLE),
        Paragraph("Jaimini Chara Karaka roles, D30-based life-area themes, and traditional "
                  "remedies for each planet &mdash; for reflection and awareness, not prescriptive "
                  "medical or legal advice; see Disclaimer.", _TM_SUBTITLE_STYLE),
    ]

    if d30_chart_cells:
        chart_size = min(page_width * 0.30, 165)
        chart_flowable = SouthIndianChartFlowable(d30_chart_cells, ["D30", "Trimsamsa"], chart_size)
        caption = Paragraph(
            "<b>D30 (Trimsamsa) Chart</b> &mdash; South Indian style. Each sign shows "
            "the planets/points falling in it for this divisional chart, and the ruling "
            "Panchatattva deity governing that D30 degree &mdash; the same deities as the "
            "Troubles &amp; Misfortune page.",
            _TM_BODY_STYLE)
        side_gap = 12
        caption_width = page_width - chart_size - side_gap
        chart_row = Table([[chart_flowable, caption]], colWidths=[chart_size, caption_width])
        chart_row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (1, 0), (1, 0), side_gap),
        ]))
        story += [chart_row, Spacer(1, 8)]

    if not rows:
        story.append(Paragraph("Planetary characteristics data not available for this run.",
                                _TM_BODY_STYLE))
        return story

    # Plain "&" here, not "&amp;" -- _tm_p() below runs _esc() (XML-escape)
    # on every header string itself, so a pre-escaped "&amp;" would get
    # escaped a second time and show up as the literal text "&amp;" on the
    # page (caught by visual inspection of the rendered page, 2026-09-21).
    headers = ["Planet", "Characteristics", "Marriage & Spouse", "Health", "Career / Finance", "Remedies"]
    table_rows = [[_tm_p(h, _HEADER_STYLE) for h in headers]]
    for row in rows:
        table_rows.append([
            _pc_planet_cell(row["planet"], row.get("ck") or ""),
            _tm_p(row["characteristics"]),
            _tm_p(row["marriage"]),
            _tm_p(row["health"]),
            _tm_p(row["career"]),
            _tm_p(row["remedies"]),
        ])
    col_widths = [page_width * w for w in (0.09, 0.18, 0.18, 0.15, 0.17, 0.23)]
    table = Table(table_rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(_base_style())
    story.append(table)

    return story


# ---------------------------------------------------------------------
# D-30 (Trimsamsa) South Indian style mini-chart (2026-09-21) -- "There is
# d30 chart in this page its south indian style ... print it in one side of
# page". A classic 4x4 South Indian grid: fixed sign positions (top row
# Pisces/Aries/Taurus/Gemini, then clockwise around a blank/merged 2x2
# center that carries the chart's own name), unlike the North Indian
# diamond used for D1/D9/Bhava Chalit above -- this is a different, fixed
# layout convention, not just a different chart_size. See
# generate_overview_report.py's extract_d30_south_indian_chart() for how
# the sign->{planets, deity} data is read off D30NatalTransit's own
# on-sheet mini-chart (columns Z:AK).
# ---------------------------------------------------------------------

_SI_GRID_RASHI = [
    ["Pi", "Ar", "Ta", "Ge"],
    ["Aq", None, None, "Cn"],
    ["Cp", None, None, "Le"],
    ["Sg", "Sc", "Li", "Vi"],
]
_DEITY_COLOR = {
    "Indra": "#4a7fc1", "Agni": "#c1554f", "Varuna": "#2f8fae",
    "Vaayu": "#6b6b6b", "Kubera": "#9c7a1f",
}


def _si_planet_color(code: str) -> str:
    if code == "Asc":
        return "#000000"
    return PLANET_TEXT_COLOR.get(code, "#333333")


def _draw_colored_tokens_centered(c, tokens, cx, cy, font_name="Helvetica-Bold", font_size=6.3):
    """Draws a horizontal row of tokens centered on cx, each colored by
    _si_planet_color -- the canvas equivalent of _rich_planet_code's
    per-planet coloring, needed here because this is direct canvas drawing
    (a South Indian cell), not a Paragraph that could carry inline <font>
    tags."""
    widths = [stringWidth(t, font_name, font_size) for t in tokens]
    space_w = stringWidth(" ", font_name, font_size)
    total_w = sum(widths) + space_w * (len(tokens) - 1)
    x = cx - total_w / 2
    c.setFont(font_name, font_size)
    for tok, w in zip(tokens, widths):
        c.setFillColor(HexColor(_si_planet_color(tok)))
        c.drawString(x, cy, tok)
        x += w + space_w


def _draw_south_indian_chart(c, x0, y0, size, cells: dict, center_lines):
    """Draws one 4x4 South Indian divisional chart at (x0, y0)-(x0+size,
    y0+size). `cells` is {rashi_abbr: {"planets": [...], "deity":
    str|None}} as returned by extract_d30_south_indian_chart(); a missing
    or emptied entry just draws that sign's box blank. `center_lines` (1-2
    short strings) is drawn inside the merged center 2x2 block, e.g.
    ["D30", "Trimsamsa"]."""
    cell = size / 4.0
    grid = _SI_GRID_RASHI

    for row in range(4):
        for col in range(4):
            rashi = grid[row][col]
            if rashi is None:
                continue
            cx0 = x0 + col * cell
            cy0 = y0 + (3 - row) * cell

            rashi_num = RASHI_NUM.get(rashi)
            element = _ELEMENT_BY_RASHI.get(rashi_num)
            if element:
                c.setFillColor(HexColor(_ELEMENT_FILL[element]))
                c.rect(cx0, cy0, cell, cell, fill=1, stroke=0)
            c.setStrokeColor(HexColor("#8a94a6"))
            c.setLineWidth(0.6)
            c.rect(cx0, cy0, cell, cell, fill=0, stroke=1)

            c.setFillColor(HexColor("#6b6b6b"))
            c.setFont("Helvetica", 6)
            c.drawString(cx0 + 2, cy0 + cell - 8, rashi)

            info = cells.get(rashi) or {}
            planets = info.get("planets") or []
            deity = info.get("deity")

            if planets:
                lines = [planets] if len(planets) <= 2 else [planets[:2], planets[2:]]
                base_y = cy0 + cell * 0.5 + (2 if len(lines) > 1 else -1)
                for i, line_tokens in enumerate(lines):
                    _draw_colored_tokens_centered(
                        c, line_tokens, cx0 + cell / 2, base_y - i * 7.5)
            if deity:
                c.setFillColor(HexColor(_DEITY_COLOR.get(deity, "#6b6b6b")))
                c.setFont("Helvetica-Oblique", 5.5)
                c.drawCentredString(cx0 + cell / 2, cy0 + 3, deity)

    center_x0, center_y0, center_size = x0 + cell, y0 + cell, cell * 2
    c.setFillColor(HexColor("#1a2744"))
    c.rect(center_x0, center_y0, center_size, center_size, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#8a94a6"))
    c.setLineWidth(0.6)
    c.rect(center_x0, center_y0, center_size, center_size, fill=0, stroke=1)
    c.setFillColor(rl_colors.white)
    line_h = 12
    ty = center_y0 + center_size / 2 + (len(center_lines) - 1) * line_h / 2
    for i, line in enumerate(center_lines):
        c.setFont("Helvetica-Bold", 10 if i == 0 else 8)
        c.drawCentredString(center_x0 + center_size / 2, ty - i * line_h - 3, line)

    c.setStrokeColor(HexColor("#8a94a6"))
    c.setLineWidth(1.1)
    c.rect(x0, y0, size, size, fill=0, stroke=1)


class SouthIndianChartFlowable(Flowable):
    """A ReportLab Flowable that draws one South Indian style divisional
    chart, so it can sit in a normal Platypus story -- the South Indian
    counterpart to NorthIndianChartFlowable above."""

    def __init__(self, cells: dict, center_lines, size):
        super().__init__()
        self.cells = cells
        self.center_lines = center_lines
        self.size = size
        self.width = size
        self.height = size

    def wrap(self, avail_width, avail_height):
        return self.width, self.height

    def draw(self):
        _draw_south_indian_chart(self.canv, 0, 0, self.size, self.cells, self.center_lines)


def build_south_indian_charts_section(charts: list, page_width: float) -> list:
    """Returns the flowables for a "Divisional Charts -- South Indian
    Style" page: up to 4 of the mini-charts D30NatalTransit itself draws
    (D1 Rasi, D9 Navamsa, D3 Drekkana, D30 Trimsamsa), 2 per row, from the
    list generate_overview_report.extract_all_south_indian_charts()
    returns. 2026-09-21: client removed the Planetary Characteristics page
    these used to live on ("remove the PLANETARY CHARACTERISTICS &
    REMEDIES page") but immediately clarified "You can still print the
    charts from the D30NatalTransit worksheet" -- so this is its own page,
    right after the North Indian D1/D9/Bhava Chalit Kundli pages (which
    come from a different sheet/range and a different chart drawing
    convention -- not a duplicate of those)."""
    story = [
        Paragraph("DIVISIONAL CHARTS &mdash; SOUTH INDIAN STYLE", _TM_TITLE_STYLE),
        Paragraph("D1 (Rasi), D9 (Navamsa), D3 (Drekkana) and D30 (Trimsamsa), as drawn on "
                  "D30NatalTransit. The D30 chart's cells also show the ruling Panchatattva "
                  "deity for that degree &mdash; see Troubles &amp; Misfortune.",
                  _TM_SUBTITLE_STYLE),
    ]

    if not charts:
        story.append(Paragraph("Divisional chart data not available for this run.", _TM_BODY_STYLE))
        return story

    gap = 16
    chart_size = (page_width - gap) / 2
    flowables = [SouthIndianChartFlowable(c["cells"], [c["label"], c["subtitle"]], chart_size)
                 for c in charts]

    grid_rows = []
    for i in range(0, len(flowables), 2):
        pair = flowables[i:i + 2]
        if len(pair) == 1:
            pair = [pair[0], ""]
        grid_rows.append(pair)

    grid = Table(grid_rows, colWidths=[chart_size, chart_size])
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (1, 0), (1, -1), gap),
    ]
    if len(grid_rows) > 1:
        cmds.append(("TOPPADDING", (0, 1), (-1, -1), gap))
    grid.setStyle(TableStyle(cmds))
    story.append(grid)

    return story
