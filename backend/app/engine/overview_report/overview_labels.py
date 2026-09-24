"""
The 12 house "life area" descriptions and 10 planet "signification" strings
that the client's own `HIT_CALC` sheet carries in its "LIFE AREA" row (see
`ccsi_parser.py`'s module docstring: row 7 there holds this exact text) --
fed directly into the Overview Report's OpenAI prompt (`overview_narrative.
build_prompt()`) so the AI writes to the client's own house/planet framing
rather than inventing its own.

STATUS (2026-09-24, later still): REAL DATA. The client sent the actual
`HIT_CALC` "LIFE AREA" row (12 house cells + 10 Asc/planet cells) plus its
companion "KARAKA" row as a screenshot/paste of the live worksheet.
HOUSE_LIFE_AREAS/PLANET_SIGNIFICATIONS below are transcribed verbatim from
that export -- column order matched exactly against the sheet's own header
row (Bhava 1-12, then Asc/Su/Mo/Ma/Me/Ju/Ve/Sa/Ra/Ke), not reworded or
reorganized. `LABELS_ARE_PLACEHOLDER` is now False and
`OverviewReportOut.labels_are_placeholder` will report that; the Overview
Report's house/planet framing now matches the client's own production
wording rather than the earlier standard-textbook stand-in.

Also captured, from the same paste, the companion HOUSE_KARAKAS/
PLANET_KARAKAS dicts below (which planet(s) the client's sheet names as the
significator for each house/planet column). These are deliberately NOT
wired into HOUSE_LIFE_AREAS/PLANET_SIGNIFICATIONS (i.e. no "Karaka: ..."
clause is appended to those strings) -- `overview_pdf_writer.py`'s own
comments (near its house-table column-width logic) record that an earlier
version of this report DID show a Karaka column, and the client asked for
it to be removed ("Remove karaka from there"); `split_karaka()` in
`ccsi_parser.py` still exists purely to strip a "Karaka: ..." clause out of
a house's description IF one is present, specifically so it never leaks
into the Description column, not to display it. Given that prior decision,
this file keeps the two rows separate and only feeds HOUSE_LIFE_AREAS/
PLANET_SIGNIFICATIONS (no Karaka text) into the report -- HOUSE_KARAKAS/
PLANET_KARAKAS are kept here purely so this real data isn't lost, in case a
future round wants to surface it somewhere else. Wiring them in anywhere
would be a deliberate, separate decision, not an automatic consequence of
this file existing.

One thing transcribed as-is, not "corrected": the sheet's own PLANET_KARAKAS
row lists Moon (not Sun) as the karaka noted under the "Su" column, unlike
every other planet column, which self-references its own planet. This is the
client's own sheet content, verbatim -- not treated as a transcription error
and not changed, per this engagement's standing rule to transcribe the
client's proprietary data exactly rather than "fix" anything that looks
inconsistent without asking first.
"""
from __future__ import annotations

# Keyed 1-12. Format matches what ccsi_parser.split_life_area()/
# split_life_area_facets() expect to parse: "<short label> — <comma-
# separated facets sentence>." -- an em dash separates the label from the
# description, exactly like the client's own real sheet does (per
# ccsi_parser.py's own docstring/example).
HOUSE_LIFE_AREAS: dict[int, str] = {
    1: "Self/Personality — physical body, appearance, temperament, vitality, and overall approach to life.",
    2: "Wealth/Speech — money, family, possessions, voice, face, food habits, and self-acquired assets.",
    3: "Courage/Siblings — younger co-borns, communication skills, mental strength, short travels, and creative drive.",
    4: "Home/Mother — mother, property, vehicles, education, domestic comfort, and emotional foundation.",
    5: "Creativity/Children — children, intelligence, romance, speculation, authority, and past good deeds (poorvapunya).",
    6: "Service/Enemies — health, disease, debts, rivals, daily work, and obstacles overcome through effort.",
    7: "Marriage/Partner — spouse, marital life, business partnerships, sexuality, and significant relationships.",
    8: "Transformation/Longevity — life span, inheritance, hidden matters, sudden change, and occult interests.",
    9: "Fortune/Dharma — father, teachers, higher learning, spirituality, luck, and long-distance or foreign journeys.",
    10: "Career/Status — profession, public reputation, achievement, authority, and standing in society.",
    11: "Gains/Network — income, elder siblings, friendships, aspirations, and the fulfillment of hopes.",
    12: "Foreign/Investment/Loss/Liberation — expenditure, losses, foreign residence, spiritual release, and letting go.",
}

# Keyed by the same 10 codes hit_calc.py/ccsi.py already use: Asc, Su, Mo,
# Ma, Me, Ju, Ve, Sa, Ra, Ke. Reused verbatim by build_prompt() (see its
# instruction to "reuse it verbatim").
PLANET_SIGNIFICATIONS: dict[str, str] = {
    "Asc": "Self/Body — core identity, physical vitality, and the outward expression of will.",
    "Su": "Soul/Vitality — inner life force, emotional security, and instinctive nurturing needs.",
    "Mo": "Mind/Emotions — feelings, moods, receptivity, and the emotional undercurrent of decisions.",
    "Ma": "Energy/Action — drive, assertiveness, competitiveness, and the capacity to initiate and defend.",
    "Me": "Intellect/Speech — reasoning, communication, analysis, and the exchange of information.",
    "Ju": "Wisdom/Growth — expansion, optimism, higher knowledge, and the pursuit of meaning.",
    "Ve": "Love/Comfort — affection, aesthetics, pleasure, relationships, and material enjoyment.",
    "Sa": "Discipline/Karma — structure, responsibility, restriction, and the long-term consequences of action.",
    "Ra": "Desire/Ambition — cravings, obsession, disruption, and the pull toward unconventional paths.",
    "Ke": "Detachment/Moksha — release, spiritual liberation, endings, and freedom from material attachment.",
}

# Captured from the same client paste as HOUSE_LIFE_AREAS above (the sheet's
# companion "KARAKA" row). NOT currently consumed by any code path -- see
# module docstring.
HOUSE_KARAKAS: dict[int, str] = {
    1: "Sun (soul, constitution).",
    2: "Jupiter (family, wealth); Mercury (speech).",
    3: "Mars (courage, younger siblings).",
    4: "Moon (mother, peace of mind); Mars (real estate); Venus (vehicles).",
    5: "Jupiter (children, intelligence); Mars (speculation); Sun (fame, power).",
    6: "Mars (enemies, diseases, accidents, loans); Saturn (servants).",
    7: "Venus (wife, husband, marital bliss).",
    8: "Saturn (longevity, troubles); Rahu/Ketu (occult knowledge).",
    9: "Sun (father, boss); Jupiter (teacher, religion, fortune); Rahu/Ketu (pilgrimages, going abroad).",
    10: "Sun (career, achievements); Mercury (work, honors).",
    11: "Saturn (elder siblings); Moon (friends); Jupiter (gains); Mercury (credits).",
    12: "Venus (bed pleasures); Saturn (losses, hospitalization); Ketu (moksha).",
}

# Captured from the same client paste as PLANET_SIGNIFICATIONS above. NOT
# currently consumed by any code path -- see module docstring, including the
# note on the "Su" column's Moon reference being transcribed as-is.
PLANET_KARAKAS: dict[str, str] = {
    "Asc": "Sun (1st-house self, soul, constitution, health).",
    "Su": "Moon (1st-house mind; karaka for mother if stronger than Mars).",
    "Mo": "Moon (mind, mother, peace of mind, friends).",
    "Ma": "Mars (courage, siblings, enemies, accidents; karaka for younger siblings and in-laws).",
    "Me": "Mercury (speech, learning, memory, work; karaka for maternal relatives).",
    "Ju": "Jupiter (family, wealth, children, fortune, gains; karaka for husband, sons, paternal relatives).",
    "Ve": "Venus (vehicles, marital bliss, bed pleasures; karaka for wife and in-laws).",
    "Sa": "Saturn (service, longevity, losses; karaka for elder siblings).",
    "Ra": "Rahu (accidents, occult knowledge, foreign travel).",
    "Ke": "Ketu (occult knowledge, pilgrimages, moksha).",
}

LABELS_ARE_PLACEHOLDER = False
