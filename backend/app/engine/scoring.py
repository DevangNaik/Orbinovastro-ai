"""
CCSI house-significator additive scoring -- faithful Python port of
`Score_Additive` / `Flag_Additive` / `Core_ScoreAndFlag`
(`ScoringModule.bas`).

IMPORTANT -- what this module can and cannot do right now:

The SCORING ARITHMETIC below is fully confirmed from the client's VBA
source and ported line-for-line (see `core_score_and_flag`). As of
2026-09-23, the real EventList/Events-Master data feeding it is ALSO now
confirmed:

- The real table is per-SELECTED-EVENT (140 named events, e.g. "Green
  Card / Permanent Residency (Natal)"), not per generic life-category as
  first assumed. Each event row carries six fixed house-list tiers:
  A-Prime, B-Secondary, C-Supportive (positive) and DI-Bad, D2-Worse,
  D3-Worst (negative). See `_production/data/EventList_export_2026-09-23.json`
  (built by `build_eventlist_json.py` from the client's real worksheet
  export) and `event_settings_table_for_event` below, which turns one
  event's JSON record into an `EventSettingsTable` for
  `core_score_and_flag`.
- The numeric weight per tier is CONFIRMED (client screenshot,
  2026-09-23): A-Prime=+3, B-Secondary=+2, C-Supportive=+1, DI-Bad=-1,
  D2-Worse=-2, D3-Worst=-3 -- see `TIER_WEIGHTS` below. This exactly
  matches the "-3..+3" range already read out of `ScoringModule.bas`, and
  is no longer a guess.

Still open, per the project roadmap doc: how `sig` / `nlof` / `slof` (the
per-planet significator house-lists fed into this scoring function) are
themselves generated, and how the results get assembled into the
client's `HIT_CALC` sheet. This module only ports the scoring arithmetic
and the event-settings table construction; it does not yet produce a
significator string for a real chart.

The `EXAMPLE_EVENT_SETTINGS` table in this module's tests remains a
clearly-fake fixture for testing the raw arithmetic in isolation -- do
not use it, or any score computed from it, in a client-facing report.
Use `event_settings_table_for_event` with real EventList data instead.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Confirmed by the client via screenshot, 2026-09-23: the fixed numeric
# weight for each of the six EventList tiers. Same six tiers, same
# weights, for every event -- only the house lists vary per event.
TIER_WEIGHTS: dict[str, float] = {
    "A-Prime": 3.0,
    "B-Secondary": 2.0,
    "C-Supportive": 1.0,
    "DI-Bad": -1.0,
    "D2-Worse": -2.0,
    "D3-Worst": -3.0,
}

TIER_ORDER = ["A-Prime", "B-Secondary", "C-Supportive", "DI-Bad", "D2-Worse", "D3-Worst"]

_DEFAULT_EVENTLIST_JSON = (
    Path(__file__).resolve().parents[3]
    / "_production" / "data" / "EventList_export_2026-09-23.json"
)

POS_HIT_UNIT = 1.0
NEG_HIT_UNIT = 1.0

BONUS_SIG = 0.0
BONUS_NLOF = 1.0
BONUS_SLOF = 2.0
PRIMARY_FACTOR = 3.0
NEG_PRIMARY_FACTOR = 3.0

_NEG_PRIME_HEADER_VARIANTS = {"D WORST", "D3-WORST", "D2-WORSE", "DI-BAD", "D-WORST"}
_NEG_HEADER_VARIANTS = {"DI-BAD", "D2-WORSE", "D3-WORST", "D-WORST", "D WORST"}

_HOUSE_NUM_RE = re.compile(r"\d+")


@dataclass
class EventSettingsColumn:
    """One column of the client's Event Settings table: a named
    life-event category, the houses that support it, its weight, and
    whether it's marked as a positive-prime or negative-prime category.
    `weak` mirrors the VBA's "Wk:" prefix convention (reduces the
    effective weight by 1 for this column only)."""
    header: str          # e.g. "A-Prime", "D-Worst", "Marriage", ...
    houses: list[int]    # house numbers 1-12 this column covers
    weight: float        # -3..+3 typically
    weak: bool = False


@dataclass
class EventSettingsTable:
    """Python equivalent of the three Excel ranges `Score_Additive` reads
    (`headerRow1`, `housesRow3`, `scoreRow4`), one `EventSettingsColumn`
    per spreadsheet column. Build this from real data with
    `event_settings_table_for_event` -- see module docstring."""
    columns: list[EventSettingsColumn] = field(default_factory=list)


def event_settings_table_for_event(event: dict) -> EventSettingsTable:
    """Builds a real `EventSettingsTable` for ONE selected event, from a
    record in `EventList_export_2026-09-23.json` (the client's real
    EventList worksheet, normalized by `build_eventlist_json.py`).

    Each event has six fixed tiers (`TIER_ORDER`) with confirmed weights
    (`TIER_WEIGHTS`, confirmed by the client 2026-09-23) -- only the
    house lists per tier vary per event. This matches how the client
    described actually using the sheet: pick ONE event (e.g. from the
    `SelectedEvent` dropdown seen in the EventSetting screenshot), and
    `Score_Additive` scores a chart's sig/nlof/slof against that one
    event's six tiers.
    """
    tiers = event["tiers"]
    columns = [
        EventSettingsColumn(
            header=tier_name,
            houses=list(tiers.get(tier_name, [])),
            weight=TIER_WEIGHTS[tier_name],
        )
        for tier_name in TIER_ORDER
    ]
    return EventSettingsTable(columns=columns)


def load_eventlist(path: Optional[Path] = None) -> list[dict]:
    """Loads the normalized EventList JSON (see `build_eventlist_json.py`).
    Returns the list of event records (each has `event_id`, `event`,
    `tiers`, and the rest of the EventList metadata columns)."""
    p = path or _DEFAULT_EVENTLIST_JSON
    data = json.loads(Path(p).read_text())
    return data["events"]


def find_event(events: list[dict], *, event_id: str = None, name: str = None) -> Optional[dict]:
    """Looks up one event record by `event_id` (e.g. "EVT132") or by exact
    `event` name (e.g. "Green Card / Permanent Residency (Natal)").
    Returns None rather than guessing if no exact match is found."""
    for e in events:
        if event_id and e["event_id"] == event_id:
            return e
        if name and e["event"] == name:
            return e
    return None


def extract_houses_1_to_12(text: str) -> list[str]:
    """Port of `ExtractHouses12`: pull all integers 1-12 out of free text,
    as strings (matching the VBA's dictionary-key-as-string convention)."""
    if not text:
        return []
    out = []
    for m in _HOUSE_NUM_RE.findall(text):
        v = int(m)
        if 1 <= v <= 12:
            out.append(str(v))
    return out


def _build_weight_map(table: EventSettingsTable) -> dict[str, float]:
    """Port of `BuildWeightMap`."""
    weight_map: dict[str, float] = {}
    for col in table.columns:
        w = col.weight - 1 if col.weak else col.weight
        for h in col.houses:
            if 1 <= h <= 12:
                weight_map[str(h)] = w
    return weight_map


def _is_neg_prime_header(hdr: str, neg_prime_tag: str) -> bool:
    h = hdr.strip().upper()
    if h == neg_prime_tag.strip().upper():
        return True
    return h in _NEG_PRIME_HEADER_VARIANTS


def _build_prime_sets(
    table: EventSettingsTable, pos_prime_tag: str, neg_prime_tag: str
) -> tuple[set[str], set[str]]:
    """Port of `BuildPrimeSetsFromTags`."""
    pos_prime: set[str] = set()
    neg_prime: set[str] = set()
    for col in table.columns:
        if col.header.strip().upper() == pos_prime_tag.strip().upper():
            pos_prime.update(str(h) for h in col.houses if 1 <= h <= 12)
        elif _is_neg_prime_header(col.header, neg_prime_tag):
            neg_prime.update(str(h) for h in col.houses if 1 <= h <= 12)
    return pos_prime, neg_prime


def _build_polarity_sets(table: EventSettingsTable) -> tuple[set[str], set[str]]:
    """Port of `BuildPolaritySetsFromHeaders`."""
    pos_set: set[str] = set()
    neg_set: set[str] = set()
    for col in table.columns:
        h = col.header.strip().upper()
        is_neg = h in _NEG_HEADER_VARIANTS
        target = neg_set if is_neg else pos_set
        target.update(str(house) for house in col.houses if 1 <= house <= 12)
    return pos_set, neg_set


def _list_polarity_with_presence(tokens: list[str], weight_map: dict[str, float]) -> tuple[int, bool]:
    """Port of `ListPolarityWithPresence`. Returns (polarity, has_match)
    where polarity is -1/0/+1."""
    saw_pos = saw_neg = has_match = False
    for k in tokens:
        if k in weight_map:
            w = weight_map[k]
            has_match = True
            if w > 0:
                saw_pos = True
            if w < 0:
                saw_neg = True
            if saw_pos and saw_neg:
                return 0, True
    if not has_match:
        return 0, False
    if saw_pos != saw_neg:
        return (1 if saw_pos else -1), True
    return 0, True


def _sum_tokens_weighted(tokens: list[str], weight_map: dict[str, float]) -> float:
    """Port of `SumTokensWeighted`."""
    return sum(weight_map.get(k, 0.0) for k in tokens if k in weight_map)


def _sum_tokens_level_bonus_and_flag(
    tokens: list[str],
    weight_map: dict[str, float],
    pos_prime: set[str],
    neg_prime: set[str],
    level_bonus: float,
    primary_factor: float,
    level_name: str,
    flags: list[str],
) -> float:
    """Port of `SumTokensLevelBonusAndFlag`."""
    total = 0.0
    for k in tokens:
        if k not in weight_map:
            continue
        bump = level_bonus
        if k in pos_prime:
            bump = bump * primary_factor
            if level_bonus > 0:
                flags.append(f"{k}-POSPRIME-{level_name}")
        elif k in neg_prime:
            bump = -bump * NEG_PRIMARY_FACTOR
            if level_bonus > 0:
                flags.append(f"{k}-NEGPRIME-{level_name}")
        total += bump
    return total


def _any_token_in_set(tokens: list[str], s: set[str]) -> bool:
    return any(k in s for k in tokens)


def _count_hits_ser(sig_tok: list[str], nlof_tok: list[str], slof_tok: list[str], s: set[str]) -> int:
    """Port of `CountHitsSER`."""
    n = 0
    if _any_token_in_set(sig_tok, s):
        n += 1
    if _any_token_in_set(nlof_tok, s):
        n += 1
    if _any_token_in_set(slof_tok, s):
        n += 1
    return n


@dataclass
class ScoreAndFlag:
    score: float
    flag: str


def core_score_and_flag(
    sig: str,
    nlof: str,
    slof: str,
    table: EventSettingsTable,
    *,
    tag_text: str = "A-Prime",
    enforce_unanimity: bool = True,
) -> ScoreAndFlag:
    """Port of `Core_ScoreAndFlag` (shared by `Score_Additive` and
    `Flag_Additive` in the VBA -- unified here into one call that returns
    both, since Python has no UDF-duplication constraint).

    `sig`/`nlof`/`slof`: free text containing house numbers (as the VBA
    extracts via regex) -- typically the significator house-list for a
    planet itself (SIG), for its Nakshatra Lord (NLOF), and for its Sub
    Lord (SLOF) respectively. See module docstring: how these three
    strings get built in the first place, per planet, is still an open
    question pending client confirmation -- this function assumes they
    are already correctly formed.
    """
    weight_map = _build_weight_map(table)
    pos_prime, neg_prime = _build_prime_sets(table, tag_text, "D-Worst")

    sig_tok = extract_houses_1_to_12(sig)
    nlof_tok = extract_houses_1_to_12(nlof)
    slof_tok = extract_houses_1_to_12(slof)

    pol_s, has_s = _list_polarity_with_presence(sig_tok, weight_map)
    pol_n, has_n = _list_polarity_with_presence(nlof_tok, weight_map)
    pol_l, has_l = _list_polarity_with_presence(slof_tok, weight_map)

    if enforce_unanimity:
        if not (has_s or has_n or has_l):
            return ScoreAndFlag(0.0, "")
        ref_pol = 0
        if has_s:
            ref_pol = pol_s
        if ref_pol == 0 and has_n:
            ref_pol = pol_n
        if ref_pol == 0 and has_l:
            ref_pol = pol_l
        if (
            ref_pol == 0
            or (has_s and pol_s != ref_pol)
            or (has_n and pol_n != ref_pol)
            or (has_l and pol_l != ref_pol)
        ):
            return ScoreAndFlag(0.0, "")

    existence = (
        _sum_tokens_weighted(sig_tok, weight_map)
        + _sum_tokens_weighted(nlof_tok, weight_map)
        + _sum_tokens_weighted(slof_tok, weight_map)
    )

    flags: list[str] = []
    level = (
        _sum_tokens_level_bonus_and_flag(sig_tok, weight_map, pos_prime, neg_prime, BONUS_SIG, PRIMARY_FACTOR, "SIG", flags)
        + _sum_tokens_level_bonus_and_flag(nlof_tok, weight_map, pos_prime, neg_prime, BONUS_NLOF, PRIMARY_FACTOR, "NLOF", flags)
        + _sum_tokens_level_bonus_and_flag(slof_tok, weight_map, pos_prime, neg_prime, BONUS_SLOF, PRIMARY_FACTOR, "SLOF", flags)
    )

    pos_set, neg_set = _build_polarity_sets(table)
    pos_hits = _count_hits_ser(sig_tok, nlof_tok, slof_tok, pos_set)
    neg_hits = _count_hits_ser(sig_tok, nlof_tok, slof_tok, neg_set)

    base = existence + level
    adjust = pos_hits * POS_HIT_UNIT - neg_hits * NEG_HIT_UNIT
    score = base + adjust
    flag_text = ", ".join(flags)

    return ScoreAndFlag(score, flag_text)


def score_additive(sig: str, nlof: str, slof: str, table: EventSettingsTable, **kw) -> float:
    """Port of `Score_Additive` UDF."""
    return core_score_and_flag(sig, nlof, slof, table, **kw).score


def flag_additive(sig: str, nlof: str, slof: str, table: EventSettingsTable, **kw) -> str:
    """Port of `Flag_Additive` UDF."""
    result = core_score_and_flag(sig, nlof, slof, table, **kw).flag
    return result if result else "None"
