"""
The OpenAI interpretation/guidance-writing layer for the ORBINOVASTRO Life
Balance Index (LBI) Overview Report -- ported from the client's own
`generate_overview_report.py` (its `build_prompt`/`generate_overview_data`/
`_validate_and_fill`/`parse_json_response`/`_row_schema_block` functions),
UNCHANGED in substance. This is exactly the part of that script that was
already Excel-independent -- it only ever consumed `parsed` (the CCSI
houses/planets structure) and a client name, never touched `win32com`, so
porting it here is a straight lift, not a re-implementation.

Two deliberate adaptations from the original script, both purely about
which OpenAI API surface is called, not about what gets asked for or how
the response is validated:

1. The original script called the Responses API (`client.responses.
   create(model=MODEL, input=prompt)`). This app's existing chat agent
   (`agent/chat.py`) already uses the Chat Completions API (`client.chat.
   completions.create(model=OPENAI_MODEL, messages=[...])`) -- adapted to
   match that existing convention rather than introduce a second OpenAI
   calling style into the same codebase.
2. The original script hardcoded `MODEL = "gpt-5-mini"` for this specific
   report-writing call (deliberately different from whatever model the
   client's other tools use for chat). That choice is preserved here via
   its own `OPENAI_OVERVIEW_MODEL` env var (default "gpt-5-mini"),
   separate from `agent/chat.py`'s `OPENAI_MODEL` (default "gpt-4o-mini")
   -- so this port doesn't silently downgrade a model choice the client
   already made for this exact purpose.

Every prompt-construction rule, every JSON-shape rule, and every
_validate_and_fill() defensive fallback is copied verbatim from the
client's own script -- see that file's own comments (preserved below)
for why each rule exists.
"""
from __future__ import annotations

import json
import os
import re

from openai import OpenAI

from .ccsi_parser import split_life_area, split_life_area_facets
from .lbi_legend import (
    CONCLUSION_ROWS,
    SCORECARD_CATEGORIES,
    STRATEGIC_FOCUS_AREAS,
    TIER_KEYS,
)

OPENAI_OVERVIEW_MODEL = os.environ.get("OPENAI_OVERVIEW_MODEL", "gpt-5-mini")


def parse_json_response(response_text: str) -> dict:
    """Handles JSON response, including accidental markdown fences."""
    clean_text = response_text.strip()

    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```(?:json)?", "", clean_text).strip()
        clean_text = re.sub(r"```$", "", clean_text).strip()

    return json.loads(clean_text)


def _row_schema_block(tier_field_note: str = "") -> str:
    return (
        '"assessment_tier": one of ' + json.dumps(TIER_KEYS) + ', '
        '"assessment_label": "2-4 word phrase consistent with that tier' + tier_field_note + '"'
    )


def build_prompt(client_name: str, parsed: dict) -> str:
    # 2026-09-15 (original script): "the Interpretation and Guidance only
    # focus on Life Area like Gains/Network but other [facets in the
    # description] are not supported in these" -- the client noticed the
    # AI was writing generically about a house's short umbrella label
    # (e.g. "Gains/Network") without ever touching the SPECIFIC facets
    # that house's own sheet lists (e.g. "friendships", "income", "hopes",
    # "networks"). Splitting each house's life_area into an explicit label
    # plus a facets LIST here -- rather than leaving it as one sentence
    # buried inside "life_area" that the AI can read past without
    # treating as a set of distinct things to write about -- and then
    # instructing the AI directly (below) to ground its interpretation/
    # guidance in the specific facet(s) most relevant to that house's own
    # numbers is meant to fix that, rather than just hoping a
    # differently-worded prompt nudges it in the right direction.
    houses_for_prompt = []
    for house in parsed["houses"]:
        label, description = split_life_area(house["life_area"])
        enriched = dict(house)
        enriched["life_area_label"] = label
        enriched["life_area_facets"] = split_life_area_facets(description)
        houses_for_prompt.append(enriched)

    houses_json = json.dumps(houses_for_prompt, ensure_ascii=False)
    planets_json = json.dumps(parsed["planets"], ensure_ascii=False)

    return f"""
You are preparing a premium, client-facing ORBINOVASTRO™ Life Balance Index
(LBI) report, matching the house style of ORBINOVASTRO's own reference
report format exactly (Executive Assessment, a per-house table, a
per-planet table, a Strategic Focus Areas table, a Scorecard table, and a
Conclusion with a Core Message).

Client Name: {client_name}

Each house and planet below already carries its own real, pre-computed CCSI
(Cusp Conflict Stress Indicator) figures, read directly from this client's
own chart -- do not recompute, re-derive, or second-guess these numbers,
use them exactly as given:
  L      = Natal life potential / lifelong promise (Lagna chart)
  LT     = Transit-to-natal activation (how current transits activate the
           natal chart)
  TT     = Immediate transit environment (current transit-to-transit
           conditions)
  *_neg  = the negative-only (afflicting-hits-only) component already
           folded into that same L/LT/TT figure -- useful context for how
           much of a mixed score is being offset by supporting hits, but
           NOT a separate number to report on its own.

Houses (life_area is this client's own sheet's own wording for the house's
overall theme -- do not quote or restate it verbatim anywhere in your
output; it and its split-out Life Area / Description columns are printed
in the report table right next to your interpretation, so repeating that
same sentence back is redundant to the reader. life_area_label is just the
short umbrella name pulled from that same text, e.g. "Gains/Network".
life_area_facets is the list of SPECIFIC things that house's own sheet says
it covers, e.g. for a Gains/Network house: ["gains", "income",
"friendships", "hopes", "networks"] -- this list is empty for a house
whose sheet entry has no further detail beyond the label itself):
{houses_json}

IMPORTANT -- write to the SPECIFIC facets, not just the umbrella label, and
do it concisely without repeating what the table already shows: when a
house's life_area_facets list is non-empty, its "interpretation" and
"guidance" MUST name whichever one or two of those specific facets are
actually most relevant to that house's own L/LT/TT pattern -- do not settle
for writing only about the short life_area_label in generic terms. For
example, for a Gains/Network house whose facets are gains, income,
friendships, hopes, and networks, do not write only "your networking is
favored right now" when the numbers more specifically support a statement
about income or friendships -- name the actual facet(s) the numbers are
about, the same way an experienced astrologer would zero in on the part of
a house's domain that a client's real chart is actually activating, rather
than describing the whole house in generic terms. Weave the facet name(s)
directly into your own original analytical sentence -- never open
"interpretation" or "guidance" with a restated or lightly-reworded copy of
the life_area/description text as a lead-in before getting to your actual
point; go straight to the analysis. If life_area_facets is empty for a
house, write about its life_area_label as you normally would, just as
concisely.

Planets (signification is this client's own sheet's own wording for what
that planet governs -- reuse it verbatim):
{planets_json}

For EVERY house and EVERY planet, choose an "assessment_tier" from this
EXACT fixed list (do not invent new tier names): {json.dumps(TIER_KEYS)}.
The tier is your own holistic verdict across L, LT and TT together (not a
mechanical average -- e.g. a very negative L with a very positive TT might
still be "positive" if the current environment strongly outweighs the
natal weakness, or "challenging" if the natal weakness dominates; use your
judgment exactly the way an experienced astrologer would). Also give a
short "assessment_label" (2-4 words, e.g. "Rebuilding", "Exceptional",
"Temporarily Challenged", "Highly Activated") that reads naturally with
that tier's color (green tiers = positive-sounding labels, yellow tiers =
neutral/transitional-sounding labels, red tiers = caution-sounding labels
-- never mismatch a red tier with a positive-sounding label or vice versa).

For "interpretation" and "guidance" text on each house/planet, also set
"interpretation_highlight" and "guidance_highlight" to one of "none",
"green", or "yellow": use "green" when that cell describes an especially
strong, stand-out supportive result worth calling out visually; "yellow"
when it flags something requiring attention, caution, or a decision point;
"none" otherwise (most rows should be "none" -- reserve the highlights for
genuinely notable rows, not routine ones).

You may emphasize a key phrase inside any longer piece of prose (interpretation,
guidance, summary, core message paragraphs) by wrapping it in double
asterisks, e.g. "the current environment **strongly outweighs** the natal
weakness" -- use this sparingly, only for the single most important phrase
in a passage, never for a whole sentence.

For "strategic_focus_areas", produce EXACTLY these {len(STRATEGIC_FOCUS_AREAS)}
areas, in this exact order, each with its own assessment_tier + a short
assessment_label + "guidance" (1-2 sentences) + "row_highlight" ("none" or
"yellow", for a genuine priority/caution area only): {json.dumps(STRATEGIC_FOCUS_AREAS)}

For "scorecard", produce EXACTLY these {len(SCORECARD_CATEGORIES)} categories,
in this exact order, each with its own assessment_tier + assessment_label
(no guidance text needed here): {json.dumps(SCORECARD_CATEGORIES)}

For "conclusion", produce EXACTLY these {len(CONCLUSION_ROWS)} rows, in this
exact order: {json.dumps(CONCLUSION_ROWS)}. The first row
("Overall Chart Strength") needs both a "tier" (one of {json.dumps(TIER_KEYS)})
and a "text" sentence; every other row needs only a "text" value (a phrase
or short sentence, no tier).

Return valid JSON only. Do not include markdown, explanations outside JSON,
code fences, generic astrology education, or disclaimers. Use this exact
JSON structure:

{{
  "executive_assessment": {{
    "overall_life_potential": {{"tier": "", "label": ""}},
    "current_activation": {{"tier": "", "label": ""}},
    "current_cosmic_environment": {{"tier": "", "label": ""}},
    "highest_opportunity": "",
    "highest_priority": "",
    "overall_life_phase": "",
    "summary": ""
  }},
  "houses": [
    {{"house": 1, {_row_schema_block()},
      "interpretation": "", "interpretation_highlight": "none",
      "guidance": "", "guidance_highlight": "none"}}
  ],
  "houses_closing": {{"heading": "Dominant House Pathway", "text": ""}},
  "planets": [
    {{"code": "Asc", {_row_schema_block()},
      "interpretation": "", "interpretation_highlight": "none",
      "guidance": "", "guidance_highlight": "none"}}
  ],
  "planets_closing": [
    {{"heading": "Strongest Planetary Combination", "text": ""}},
    {{"heading": "Planetary Priority", "text": "", "bullets": ["", "", ""]}}
  ],
  "strategic_focus_areas": [
    {{"area": "", {_row_schema_block()}, "guidance": "", "row_highlight": "none"}}
  ],
  "scorecard": [
    {{"category": "", {_row_schema_block()}}}
  ],
  "conclusion": {{
    "overall_chart_strength": {{"tier": "", "text": ""}},
    "primary_strengths": "",
    "highest_opportunities": "",
    "priority_areas": "",
    "current_life_theme": "",
    "long_term_direction": ""
  }},
  "core_message": {{
    "paragraphs": ["", "", "", ""]
  }}
}}

Rules:
1. Return exactly 12 records in "houses" (house 1 through 12, in order) and
   exactly 10 records in "planets" (codes Asc, Su, Mo, Ma, Me, Ju, Ve, Sa,
   Ra, Ke, in that order).
2. Never invent a house life-area, planet signification, or numeric L/LT/TT
   figure -- use exactly what was supplied above.
3. Keep the report factual, concise, readable and premium client-facing.
4. Do not make guaranteed predictions.
5. Do not use fear-based language.
6. Use practical and specific guidance.
7. Base every assessment on the combined L, LT and TT pattern for that row.
8. For every house with a non-empty life_area_facets list, name the
   specific facet(s) from that list in its interpretation/guidance rather
   than writing only about its life_area_label in generic terms.
9. Never restate life_area, life_area_label, or life_area_facets text
   verbatim (or near-verbatim) as a lead-in sentence in interpretation or
   guidance -- that text is already printed in the table's own Life Area
   and Description columns. Reference specific facets by name concisely,
   inside your own original analytical sentence, and start straight in on
   the analysis.
"""


def _validate_and_fill(report_data: dict, parsed: dict) -> dict:
    """Defensive pass over the AI's JSON: never trust a generated payload
    to have exactly the shape/length/order asked for -- pad, truncate, or
    substitute a safe neutral default and keep going rather than crashing
    or silently mis-aligning a table (same discipline as this project's
    other _find_primary_col()-style validations)."""

    def _default_row_extra():
        return {"assessment_tier": "neutral", "assessment_label": "Pending Review",
                "interpretation": "", "interpretation_highlight": "none",
                "guidance": "", "guidance_highlight": "none"}

    houses_ai = report_data.get("houses") or []
    by_house = {h.get("house"): h for h in houses_ai if isinstance(h, dict)}
    fixed_houses = []
    for i in range(1, 13):
        entry = by_house.get(i)
        if not isinstance(entry, dict):
            entry = {"house": i, **_default_row_extra()}
        fixed_houses.append(entry)
    report_data["houses"] = fixed_houses

    planets_ai = report_data.get("planets") or []
    by_code = {p.get("code"): p for p in planets_ai if isinstance(p, dict)}
    fixed_planets = []
    for p in parsed["planets"]:
        entry = by_code.get(p["code"])
        if not isinstance(entry, dict):
            entry = {"code": p["code"], **_default_row_extra()}
        fixed_planets.append(entry)
    report_data["planets"] = fixed_planets

    areas_ai = report_data.get("strategic_focus_areas") or []
    by_area = {a.get("area"): a for a in areas_ai if isinstance(a, dict)}
    fixed_areas = []
    for name in STRATEGIC_FOCUS_AREAS:
        entry = by_area.get(name)
        if not isinstance(entry, dict):
            entry = {"area": name, "assessment_tier": "neutral", "assessment_label": "Pending Review",
                      "guidance": "", "row_highlight": "none"}
        else:
            entry.setdefault("area", name)
        fixed_areas.append(entry)
    report_data["strategic_focus_areas"] = fixed_areas

    scorecard_ai = report_data.get("scorecard") or []
    by_cat = {s.get("category"): s for s in scorecard_ai if isinstance(s, dict)}
    fixed_scorecard = []
    for name in SCORECARD_CATEGORIES:
        entry = by_cat.get(name)
        if not isinstance(entry, dict):
            entry = {"category": name, "assessment_tier": "neutral", "assessment_label": "Pending Review"}
        else:
            entry.setdefault("category", name)
        fixed_scorecard.append(entry)
    report_data["scorecard"] = fixed_scorecard

    report_data.setdefault("executive_assessment", {})
    report_data.setdefault("houses_closing", {})
    report_data.setdefault("planets_closing", [])
    conclusion = report_data.setdefault("conclusion", {})
    if not isinstance(conclusion.get("overall_chart_strength"), dict):
        conclusion["overall_chart_strength"] = {"tier": "neutral", "text": ""}
    report_data.setdefault("core_message", {"paragraphs": []})

    return report_data


def generate_overview_data(client: OpenAI, client_name: str, parsed: dict) -> dict:
    """Calls OpenAI to write the interpretation/guidance layer over the
    already-computed, already-validated CCSI numbers in `parsed`, and
    defensively normalizes the response's shape before returning it.

    Uses the Chat Completions API (see module docstring for why, and for
    OPENAI_OVERVIEW_MODEL) -- a single non-streaming call, since this is a
    one-shot document-generation request, not a back-and-forth chat turn."""
    prompt = build_prompt(client_name, parsed)

    response = client.chat.completions.create(
        model=OPENAI_OVERVIEW_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = response.choices[0].message.content or ""

    report_data = parse_json_response(response_text)
    return _validate_and_fill(report_data, parsed)
