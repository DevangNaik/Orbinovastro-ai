"""
Parses HIT_CALC!G185:AE204 into clean, structured house/planet records.

Why this exists: the previous version of generate_overview_report.py just
JSON-dumped the raw cell block and asked the AI to figure out which
numbers were L/LT/TT for which house or planet. That is exactly the kind of
"hope the model parses the layout correctly" pattern that has repeatedly
caused silent, invisible bugs elsewhere in this client's spreadsheets (see
the ORBINOVASTRO Vastu project's parse_zone_life()/severity-column history).
This module parses the block deterministically in Python -- verified against
the client's own real pasted data, 2026-09-08 -- and only hands the AI
already-correct numbers.

Confirmed real layout (0-indexed row offsets within the read range; column
offsets within each row). Range shifted from G184:AE204 to G185:AE204 on
2026-09-08 -- the client converted this block to an Excel Table without a
real header row, so Excel auto-inserted its own placeholder header
("Column1", "Column2", ...) at what used to be row 184, one row above
everything below. Row IDENTITY here is resolved entirely by label-text
matching (see _match_row() below), never by fixed offset, so a stray
placeholder row would have been harmlessly ignored either way -- excluding
it from the read range just keeps things matching the client's own Table
exactly. The offsets below are relative to the CURRENT G185 start (i.e. one
less than the old G184-relative numbering):

  row 0  : decorative merged super-header ("BHAVA" over the house block,
           "Planet" over the planet block) -- col[3] == "BHAVA", rest blank.
  row 1  : block-1 title (col[0]) + "Bhava"/"BHAVA" label (col[1]) + house
           numbers 1..12 at col[3:15] + planet codes Asc..Ke at col[15:25].
  row 2  : NET Lagna Chart (L) data      -- label "CCSI- Lagna Chart"
  row 3  : blank spacer
  row 4  : NET Transit-to-Lagna (LT) data -- label "CCSI-Transit to Lagna"
  row 5  : blank spacer
  row 6  : NET Transit-to-Transit (TT) data -- label "CCSI- Transit to to Transit"
  row 7  : Life-area labels (houses) + planet signification labels --
           col[3:15] = 12 house life-area names, col[15:25] = 10 planet
           signification names. Marked with an explicit "LIFE AREA" label
           in col[0]/col[1] (added 2026-09-08 by the client specifically
           so this row can be found by CONTENT rather than inferred from
           its shape -- see the note on _match_row() below for why).
  rows 8-12: blank spacer rows
  row 13 : block-2 title ("Negative Hits Only...") + same header row shape
  row 14 : blank spacer
  row 15 : NEGATIVE-ONLY Transit-to-Transit -- label "CCSK-Tr to Tr" (sic)
  row 16 : blank spacer
  row 17 : NEGATIVE-ONLY Transit-to-Lagna -- label "CCSI -Tr to Lag"
  row 18 : blank spacer
  row 19 : NEGATIVE-ONLY Lagna -- label "CCSI Lagna"
  (a trailing blank row, sometimes present depending on paste, is harmless
  either way since row identity is label-based, not offset-based)

Column layout within every data/header row: col[0] = optional block title,
col[1] = row label ("Bhava" / "CCSI- Lagna Chart" / etc), col[2] = blank
spacer, col[3:15] = the 12 house-position values (houses 1-12, in order),
col[15:25] = the 10 planet values, in the fixed order
Asc, Su, Mo, Ma, Me, Ju, Ve, Sa, Ra, Ke.

Row IDENTITY is resolved by matching each row's label text (col[1], or
col[0] for the two title rows) against a small set of keyword rules --
NOT by fixed row-offset alone -- so an extra/missing blank spacer row
doesn't silently misalign the data. Every expected row must be found
exactly once; anything else raises RuntimeError with a specific, actionable
message rather than silently guessing (same discipline used throughout the
ORBINOVASTRO Vastu codebase's _find_primary_col()/parse_zone_life()).
"""

from __future__ import annotations

import re


HOUSE_COUNT = 12
PLANET_CODES = ["Asc", "Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]
PLANET_NAMES = {
    "Asc": "Ascendant",
    "Su": "Sun",
    "Mo": "Moon",
    "Ma": "Mars",
    "Me": "Mercury",
    "Ju": "Jupiter",
    "Ve": "Venus",
    "Sa": "Saturn",
    "Ra": "Rahu",
    "Ke": "Ketu",
}

# House column offsets within a row: houses at [3:15], planets at [15:25].
HOUSE_SLICE = slice(3, 15)
PLANET_SLICE = slice(15, 25)


def _cell(row, idx):
    if idx < len(row):
        return row[idx]
    return ""


def _label_of(row):
    """The text used to identify a row: block title (col0) takes priority
    over the row label (col1) since title rows carry their text in col0."""
    title = str(_cell(row, 0)).strip()
    label = str(_cell(row, 1)).strip()
    return title if title else label


def _to_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _match_row(rows, test_fn, description):
    """Finds exactly one row whose label matches test_fn(label_lower).
    Raises RuntimeError (loudly, never a silent guess) if zero or more
    than one row matches -- the sheet's layout must have changed and this
    parser needs a human to look at it before any report goes out."""
    matches = []
    for row in rows:
        label = _label_of(row).lower()
        if label and test_fn(label):
            matches.append(row)
    if len(matches) != 1:
        raise RuntimeError(
            f"CCSI matrix parse error: expected exactly ONE row for "
            f"'{description}', found {len(matches)}. The HIT_CALC!G185:AE204 "
            f"layout may have changed -- check the sheet before generating "
            f"a report (do not guess)."
        )
    return matches[0]


def parse_ccsi_matrix(rows: list[list]) -> dict:
    """rows: the raw 2D value grid from HIT_CALC!G185:AE204 (list of lists,
    as returned by read_excel_range()). Returns a fully-resolved, already-
    verified structure:

    {
      "houses": [ {"house": 1, "life_area": "Self/Personality",
                    "L": 5.0, "LT": -3.0, "TT": -5.0,
                    "L_neg": 0.0, "LT_neg": 8.0, "TT_neg": 8.0}, ... x12 ],
      "planets": [ {"code": "Asc", "name": "Ascendant",
                     "signification": "Self/Body",
                     "L": 5.0, "LT": -3.0, "TT": -5.0,
                     "L_neg": 0.0, "LT_neg": 8.0, "TT_neg": 8.0}, ... x10 ],
    }

    Every number is the client's own live CCSI figure, read directly --
    nothing here is recomputed or estimated.
    """
    # ---- locate the 6 net/negative-only data rows by label keyword ----
    net_l_row = _match_row(
        rows, lambda s: "lagna" in s and "chart" in s, "NET Lagna Chart (L)"
    )
    net_lt_row = _match_row(
        rows, lambda s: "transit to lagna" in s, "NET Transit-to-Lagna (LT)"
    )
    net_tt_row = _match_row(
        rows, lambda s: "to to" in s, "NET Transit-to-Transit (TT)"
    )
    neg_tt_row = _match_row(
        rows, lambda s: "tr to tr" in s, "NEGATIVE-ONLY Transit-to-Transit"
    )
    neg_lt_row = _match_row(
        rows, lambda s: "tr to lag" in s, "NEGATIVE-ONLY Transit-to-Lagna"
    )
    neg_l_row = _match_row(
        rows,
        lambda s: "lagna" in s and "chart" not in s and "transit" not in s and "tr to" not in s,
        "NEGATIVE-ONLY Lagna",
    )

    # ---- locate the life-area / planet-signification label row ----
    # 2026-09-08: originally found via a shape heuristic (the one row
    # whose 12 house-slots were ALL non-blank, non-numeric text) that
    # assumed exactly one such row exists anywhere in the 21-row range.
    # Broke on a second live client sheet (Priyanka Shah): the "Negative
    # Hits Only" block's own header row also has all-12-slots
    # non-blank/non-numeric content, so the heuristic ambiguously matched
    # two rows -- and correctly refused to guess which one was real
    # rather than risk silently mislabeling every house/planet. Fixed the
    # same way the six data rows above already are: the client added an
    # explicit "LIFE AREA" label to this row (col[0]/col[1], same spot
    # every other row's label lives) specifically so it can be found by
    # CONTENT, not inferred from shape.
    life_area_row = _match_row(
        rows, lambda s: "life" in s and "area" in s, "Life-Area label row"
    )

    house_life_areas = [str(v).strip() for v in life_area_row[HOUSE_SLICE]]
    planet_significations = [str(v).strip() for v in life_area_row[PLANET_SLICE]]

    houses = []
    for i in range(HOUSE_COUNT):
        houses.append({
            "house": i + 1,
            "life_area": house_life_areas[i] if i < len(house_life_areas) else f"House {i + 1}",
            "L": _to_number(net_l_row[HOUSE_SLICE][i]),
            "LT": _to_number(net_lt_row[HOUSE_SLICE][i]),
            "TT": _to_number(net_tt_row[HOUSE_SLICE][i]),
            "L_neg": _to_number(neg_l_row[HOUSE_SLICE][i]),
            "LT_neg": _to_number(neg_lt_row[HOUSE_SLICE][i]),
            "TT_neg": _to_number(neg_tt_row[HOUSE_SLICE][i]),
        })

    planets = []
    for i, code in enumerate(PLANET_CODES):
        planets.append({
            "code": code,
            "name": PLANET_NAMES[code],
            "signification": planet_significations[i] if i < len(planet_significations) else code,
            "L": _to_number(net_l_row[PLANET_SLICE][i]),
            "LT": _to_number(net_lt_row[PLANET_SLICE][i]),
            "TT": _to_number(net_tt_row[PLANET_SLICE][i]),
            "L_neg": _to_number(neg_l_row[PLANET_SLICE][i]),
            "LT_neg": _to_number(neg_lt_row[PLANET_SLICE][i]),
            "TT_neg": _to_number(neg_tt_row[PLANET_SLICE][i]),
        })

    missing = [h["house"] for h in houses if None in (h["L"], h["LT"], h["TT"])]
    if missing:
        raise RuntimeError(
            f"CCSI matrix parse error: house(s) {missing} have a blank/non-numeric "
            f"L, LT or TT value after parsing -- check the sheet before generating "
            f"a report (do not guess)."
        )
    missing_p = [p["code"] for p in planets if None in (p["L"], p["LT"], p["TT"])]
    if missing_p:
        raise RuntimeError(
            f"CCSI matrix parse error: planet(s) {missing_p} have a blank/non-numeric "
            f"L, LT or TT value after parsing -- check the sheet before generating "
            f"a report (do not guess)."
        )

    return {"houses": houses, "planets": planets}


# ==========================================================
# LIFE-AREA LABEL/DESCRIPTION SPLITTING
# ==========================================================
# 2026-09-15: "Split the Life Area in two columns" -- a house's life_area
# text is one cell on the client's sheet combining a short umbrella label
# and a longer description, e.g. "Self/Personality — physical body,
# appearance, temperament, vitality, and overall approach to life." These
# two helpers are shared by overview_pdf_writer.py (splits it for the PDF's
# Life Area / Description columns) and generate_overview_report.py (splits
# it again to hand the AI the label and its individual facets separately,
# so the AI's interpretation/guidance can speak to a house's SPECIFIC
# facets -- e.g. "friendships" or "income" for a Gains/Network house --
# rather than only the 2-3 word umbrella label).

def split_life_area(life_area: str) -> tuple[str, str]:
    """Splits a house's life-area text into its short label and its longer
    description, e.g. "Self/Personality — physical body, appearance,
    ..." -> ("Self/Personality", "physical body, appearance, ...").

    The client's own sheet writes each house's life area as one cell using
    an em dash (or occasionally a plain hyphen) as the label/description
    separator -- this looks for that separator rather than guessing a split
    point. If none is found, the whole string is kept as the label and the
    description is left blank rather than mis-splitting it."""
    for sep in (" — ", " – ", " - "):
        if sep in life_area:
            label, _, description = life_area.partition(sep)
            return label.strip(), description.strip()
    return life_area.strip(), ""


def split_karaka(description: str) -> tuple[str, str]:
    """Splits a trailing "Karaka: ..." planetary-ruler clause off a life-area
    description, e.g. "physical body, appearance, temperament, vitality,
    and overall approach to life. Karaka: Sun (soul, constitution)." ->
    ("physical body, appearance, temperament, vitality, and overall
    approach to life.", "Karaka: Sun (soul, constitution).").

    2026-09-15: a real client report (Nishil D. Naik) showed the sheet now
    appends this clause after the facets sentence on every house -- it
    wasn't present in this project's earlier test data, and left un-split
    it did two things wrong: (1) it got glued onto whatever the last facet
    happened to be in split_life_area_facets() below (no comma separates
    the facets sentence from "Karaka:", so the two ran together into one
    garbled fake facet), and (2) in the PDF it roughly doubled the
    Description column's text length, which is why splitting Life Area
    into Label + Description alone didn't fix the "rows are too tall"
    complaint for this client's real data -- Karaka needs its own column,
    not a bigger Description column.

    Looks for a case-insensitive "Karaka:" marker rather than assuming a
    fixed position. If none is found, the whole description is returned
    unchanged with an empty karaka string."""
    match = re.search(r"\bKaraka\s*:", description or "", flags=re.IGNORECASE)
    if not match:
        return (description or "").strip(), ""
    return description[:match.start()].strip(), description[match.start():].strip()


def split_life_area_facets(description: str) -> list[str]:
    """Breaks a life-area description into its individual listed facets,
    e.g. "physical body, appearance, temperament, vitality, and overall
    approach to life." -> ["physical body", "appearance", "temperament",
    "vitality", "overall approach to life"].

    Used to hand the AI prompt an explicit, enumerable list of the specific
    things a house's sheet says that house covers, rather than one long
    sentence it might read as decorative color text instead of a set of
    distinct facets to actually write about. Any trailing "Karaka: ..."
    clause is stripped first (see split_karaka()) -- it names a ruling
    planet, not a facet of the house to write interpretation/guidance
    about, so it has no business in this list."""
    facets_only, _ = split_karaka(description)
    text = facets_only.strip().rstrip(".").strip()
    if not text:
        return []
    text = re.sub(r"\band\b", ",", text, flags=re.IGNORECASE)
    return [part.strip() for part in text.split(",") if part.strip()]
