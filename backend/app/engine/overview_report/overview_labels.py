"""
The 12 house "life area" descriptions and 10 planet "signification" strings
that the client's own `HIT_CALC` sheet carries in its "LIFE AREA" row (see
`ccsi_parser.py`'s module docstring: row 7 there holds this exact text) --
fed directly into the Overview Report's OpenAI prompt (`overview_narrative.
build_prompt()`) so the AI writes to the client's own house/planet framing
rather than inventing its own.

STATUS (2026-09-24): PLACEHOLDER. The client's own exact wording for this
row was never captured into a permanent file during the CCSI validation
rounds -- only the row's NUMERIC cells were saved as test fixtures (see
`test_hit_calc_lagna_validated.py`/`test_hit_calc_lt_tt_validated.py`).
Rather than block the whole Overview Report endpoint on that one still-
missing piece, this module ships the STANDARD, textbook Vedic house-
signification and planet-signification wording instead -- the same
"standard textbook formula, explicitly labeled beta" approach the client
already approved for the D9 Navamsa engine (`varga.py`) when their own
workbook formula wasn't yet available. This is NOT the client's own
proprietary wording (which may group/word things differently -- e.g. a
"Gains/Network" house whose real sheet-text lists specific facets like
"friendships, hopes, income" the way `ccsi_parser.split_life_area_facets()`
already expects to parse out), so `OverviewReportOut.labels_are_placeholder`
is set True whenever this module's text is used, and the report itself
should not be treated as final client-facing output until the client's
real wording replaces these two dicts.

TO REPLACE WITH THE REAL DATA: once the client shares a screenshot/export
of `HIT_CALC`'s "LIFE AREA" row (12 house cells + 10 planet cells), replace
HOUSE_LIFE_AREAS/PLANET_SIGNIFICATIONS below with that exact text -- every
downstream consumer (this module's own callers, `overview_narrative.
build_prompt()`, `overview_pdf_writer.py`'s Table 1/Table 2 columns) reads
these two dicts and nothing else, so no other code needs to change.
"""
from __future__ import annotations

# Keyed 1-12. Format matches what ccsi_parser.split_life_area()/
# split_life_area_facets() expect to parse: "<short label> — <comma-
# separated facets sentence>." -- an em dash separates the label from the
# description, exactly like the client's own real sheet does (per
# ccsi_parser.py's own docstring/example).
HOUSE_LIFE_AREAS: dict[int, str] = {
    1: "Self/Personality — physical body, appearance, temperament, vitality, and overall approach to life.",
    2: "Wealth/Family — savings, family values, speech, and food habits.",
    3: "Courage/Siblings — initiative, communication, short journeys, and siblings.",
    4: "Home/Comforts — mother, property, vehicles, education, and emotional security.",
    5: "Creativity/Children — children, romance, intelligence, and speculative gains.",
    6: "Service/Health — daily work, health, debts, disputes, and obstacles.",
    7: "Partnerships — marriage, business partnerships, and public dealings.",
    8: "Transformation — longevity, sudden change, inheritance, and hidden matters.",
    9: "Fortune/Higher Learning — luck, higher education, long journeys, and faith.",
    10: "Career/Status — profession, public standing, authority, and achievement.",
    11: "Gains/Network — income, friendships, hopes, and networks.",
    12: "Loss/Spirituality — expenses, foreign residence, isolation, and spiritual pursuits.",
}

# Keyed by the same 10 codes hit_calc.py/ccsi.py already use: Asc, Su, Mo,
# Ma, Me, Ju, Ve, Sa, Ra, Ke. Reused verbatim by build_prompt() (see its
# instruction to "reuse it verbatim").
PLANET_SIGNIFICATIONS: dict[str, str] = {
    "Asc": "Self/Body — physical constitution, appearance, and overall life approach.",
    "Su": "Soul/Authority — willpower, vitality, father, and government/authority figures.",
    "Mo": "Mind/Emotions — mother, emotional nature, public, and daily fluctuations.",
    "Ma": "Courage/Drive — energy, siblings, property, and assertiveness.",
    "Me": "Intellect/Communication — reasoning, speech, trade, and analytical skill.",
    "Ju": "Wisdom/Growth — knowledge, wealth, children, and expansion.",
    "Ve": "Relationships/Comforts — love, marriage, luxury, and artistic sense.",
    "Sa": "Discipline/Structure — hard work, longevity, delays, and endurance.",
    "Ra": "Ambition/Obsession — worldly desire, unconventional paths, and sudden gain.",
    "Ke": "Detachment/Liberation — spirituality, isolation, and past-life karma.",
}

LABELS_ARE_PLACEHOLDER = True
