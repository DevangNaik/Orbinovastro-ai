"""Tests for engine/chart_narrative.py -- the shared sign/nakshatra phrase
banks (moved out of teaser.py this round so /api/chart can reuse them),
the `meaning` sentence builder, and `natal_conjunctions()`'s same-sign
angular-separation grouping. Also confirms `/api/chart`'s new `meaning`/
`conjunctions` fields are wired correctly end to end via chart_to_dict().

Run with:  python -m pytest tests/ -v   (from backend/)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.chart import chart_to_dict
from app.engine.chart_narrative import (
    BENEFIC_PLANETS, MALEFIC_PLANETS, NAKSHATRA_THEMES, SIGN_TRAITS,
    angular_separation, aspected_by_for_point, dignity_flag,
    functional_nature, houses_ruled_by, is_vargottama, natal_aspects,
    natal_conjunctions, planet_element, planet_flags, planet_nature,
    position_meaning, rashi_element,
)
from app.engine.ephemeris import (
    BirthMoment, compute_natal_chart, sign_index_for_longitude,
)
from app.engine.teaser import build_teaser


def _reference_chart():
    # Same real reference chart used throughout this engagement's tests
    # (1973-10-12, 14:55 IST, Amalsad -- the client's own real birth data).
    m = BirthMoment(year=1973, month=10, day=12, hour=14, minute=55, second=0,
                     utc_offset_hours=5.5, latitude=20.815615264029468, longitude=72.95947488134223)
    return compute_natal_chart(m)


def test_sign_traits_and_nakshatra_themes_cover_every_name():
    from app.engine.ephemeris import RASHI_NAMES
    assert set(SIGN_TRAITS) == set(RASHI_NAMES)
    assert len(NAKSHATRA_THEMES) == 27


def test_position_meaning_matches_the_expected_format():
    text = position_meaning("Capricorn", "Shravana", 4)
    assert text == "Shravana(4): listening, learning, and passing on what you know; Capricorn adds disciplined and patient."


def test_position_meaning_degrades_gracefully_for_an_unknown_name():
    # Never raises -- a data hiccup should shorten the sentence, not 500.
    text = position_meaning("Capricorn", "NotARealNakshatra", 1)
    assert "NotARealNakshatra(1)" in text
    assert "Capricorn adds disciplined and patient." in text


def test_angular_separation_matches_teaser_pys_own_copy():
    assert angular_separation(10.0, 10.0) == 0.0
    assert angular_separation(10.0, 20.0) == 10.0
    assert angular_separation(350.0, 10.0) == 20.0  # wraps past 360
    assert angular_separation(0.0, 180.0) == 180.0  # opposite points


def test_natal_conjunctions_groups_only_same_sign_planets():
    chart = _reference_chart()
    conj = natal_conjunctions(chart.planets)
    assert set(conj) == {p.code for p in chart.planets}
    by_code = {p.code: p for p in chart.planets}
    for code, hits in conj.items():
        p = by_code[code]
        for hit in hits:
            q = by_code[hit["code"]]
            assert q.sign == p.sign  # only same-sign planets are ever listed
            assert hit["orb_degrees"] >= 0.0


def test_natal_conjunctions_orb_is_symmetric_and_sorted_closest_first():
    chart = _reference_chart()
    conj = natal_conjunctions(chart.planets)
    for code, hits in conj.items():
        # sorted closest-first
        orbs = [h["orb_degrees"] for h in hits]
        assert orbs == sorted(orbs)
        # symmetric: if A lists B with orb X, B lists A with the same orb X
        for hit in hits:
            other_hits = {h["code"]: h["orb_degrees"] for h in conj[hit["code"]]}
            assert other_hits[code] == hit["orb_degrees"]


def test_chart_to_dict_wires_meaning_and_conjunctions_for_every_planet():
    chart = _reference_chart()
    data = chart_to_dict(chart)
    for p in data["planets"]:
        assert p["meaning"]  # never empty
        assert p["sign"] in p["meaning"]  # by construction, format check
        assert isinstance(p["conjunctions"], list)
        for hit in p["conjunctions"]:
            assert set(hit) == {"code", "orb_degrees"}


def test_planet_nature_matches_hit_calc_pys_own_classification():
    # Same grouping hit_calc.py's MALEFIC_PLANETS/BENEFIC_PLANETS already
    # uses internally for CCSI weighting -- duplicated, not imported (see
    # chart_narrative.py's own docstring for why), but must stay in sync.
    assert MALEFIC_PLANETS == {"Sa", "Ma", "Ra", "Ke"}
    assert BENEFIC_PLANETS == {"Su", "Me", "Mo", "Ju", "Ve"}
    for code in MALEFIC_PLANETS:
        assert planet_nature(code) == "Malefic"
    for code in BENEFIC_PLANETS:
        assert planet_nature(code) == "Benefic"
    assert planet_nature("Asc") == ""


def test_chart_to_dict_wires_nature_for_every_planet():
    chart = _reference_chart()
    data = chart_to_dict(chart)
    for p in data["planets"]:
        if p["code"] in ("Ur", "Ne", "Pl"):
            # Outer planets have no classical natural benefic/malefic
            # assignment -- see chart.py's own docstring.
            assert p["nature"] == ""
        else:
            assert p["nature"] in ("Malefic", "Benefic")


# --- 2026-09-24, later still: Ascendant nakshatra/pada/meaning gap and the
# /api/chart flags gap, both caught by the client on the live Planet
# Details Table ------------------------------------------------------------

def test_chart_to_dict_ascendant_gets_degree_nakshatra_pada_and_meaning():
    """The Ascendant row on the live table showed a Degree but no
    Nakshatra(Pada) -- chart_to_dict's `ascendant` dict never computed
    those fields at all (see chart.py's own note on this round's fix)."""
    from app.engine.ephemeris import nakshatra_for_longitude, sign_for_longitude

    chart = _reference_chart()
    data = chart_to_dict(chart)
    asc = data["ascendant"]
    expected_nak, expected_lord, expected_pada = nakshatra_for_longitude(
        chart.ascendant.longitude
    )
    _, _, expected_degree = sign_for_longitude(chart.ascendant.longitude)

    assert asc["nakshatra"] == expected_nak
    assert asc["nakshatra_lord"] == expected_lord
    assert asc["pada"] == expected_pada
    assert round(expected_degree, 3) == asc["degree_in_sign"]
    assert asc["meaning"]
    assert expected_nak in asc["meaning"]
    assert "flags" in asc


def test_dignity_flag_matches_the_known_real_reference_chart():
    """Cross-checks chart_narrative.dignity_flag directly against this
    engagement's own established facts: Jupiter sits in Capricorn (its
    classical sign of debilitation) in the client's real reference chart."""
    assert dignity_flag("Ju", "Capricorn") == "Debilitated"
    assert dignity_flag("Ma", "Aries") == "Own Sign"
    assert dignity_flag("Su", "Aries") == "Exalted"
    assert dignity_flag("Ra", "Capricorn") is None  # nodes excluded by design


def test_is_vargottama_matches_an_independent_d1_vs_d9_check():
    from app.engine.varga import navamsa_sign_index

    chart = _reference_chart()
    for p in chart.planets:
        expected = sign_index_for_longitude(p.longitude) == navamsa_sign_index(p.longitude)
        assert is_vargottama(p.longitude) == expected


def _real_client_reference_chart():
    """Same real, extensively-validated client reference chart used in
    test_teaser.py (1973-10-12, 14:55 IST, Amalsad, Gujarat) -- Jupiter is
    known-debilitated here, the exact case the client flagged as missing
    from the live /api/chart-backed Planet Details Table."""
    m = BirthMoment(year=1973, month=10, day=12, hour=14, minute=55, second=0,
                     utc_offset_hours=5.5, latitude=20.815615264029468,
                     longitude=72.95947488134223)
    return compute_natal_chart(m)


def test_chart_to_dict_flags_match_teasers_flags_for_the_same_chart():
    """The whole point of centralizing this logic in chart_narrative.py:
    /api/chart (chart_to_dict) and the Free Preview (build_teaser) must
    report the IDENTICAL flags for the same chart, off the same tables --
    including Jupiter's "Debilitated" flag, which /api/chart never
    reported at all before this round's fix."""
    chart = _real_client_reference_chart()
    data = chart_to_dict(chart)
    teaser = build_teaser(chart)

    # /api/chart also carries Uranus/Neptune/Pluto (teaser.py doesn't --
    # see chart.py's own docstring), so compare only the 9 classical
    # grahas both sides actually have an opinion on.
    teaser_flags_by_code = {p.code: set(p.flags) for p in teaser.placements if p.code != "Asc"}
    chart_flags_by_code = {
        p["code"]: set(p["flags"]) for p in data["planets"] if p["code"] in teaser_flags_by_code
    }

    assert chart_flags_by_code == teaser_flags_by_code
    assert "Debilitated" in chart_flags_by_code["Ju"]

    asc_chart_flags = set(data["ascendant"]["flags"])
    asc_teaser_flags = set(next(p for p in teaser.placements if p.code == "Asc").flags)
    assert asc_chart_flags == asc_teaser_flags


def test_chart_to_dict_jupiter_is_flagged_debilitated_end_to_end():
    """The exact regression the client reported from the live page: open
    a chart view, look at Jupiter's row -- it must say Debilitated."""
    chart = _real_client_reference_chart()
    data = chart_to_dict(chart)
    jupiter = next(p for p in data["planets"] if p["code"] == "Ju")
    assert "Debilitated" in jupiter["flags"]


def test_planet_flags_skips_combust_when_sun_longitude_is_missing():
    """A defensive edge case: if no Sun entry is ever passed in (shouldn't
    normally happen), planet_flags must not raise -- it just can't know
    about Combust for that call."""
    flags = planet_flags("Ve", "Virgo", 155.0, False, None)
    assert "Combust" not in flags


# --- 2026-09-24, later still again: classical Parashari graha drishti
# (planetary aspects), added to the Planet Details Table's Details cell
# alongside Conjunctions, per the client's own follow-up ask -----------

def test_natal_aspects_matches_hand_verified_real_reference_chart():
    """Cross-checked by hand against this engagement's own real reference
    chart (1973-10-12, 14:55 IST, Amalsad): Sun (Virgo) and Moon (Pisces)
    are exactly opposite signs, so they must mutually 7th-aspect each
    other; Jupiter (Capricorn) is a genuine, hand-verified 9th-house
    special aspect onto the Sun (Virgo) -- Capricorn + 8 signs = Virgo."""
    chart = _real_client_reference_chart()
    aspects = natal_aspects(chart.planets)

    su_aspects = {(a["code"], a["aspect"]) for a in aspects["Su"]["aspects"]}
    mo_aspects = {(a["code"], a["aspect"]) for a in aspects["Mo"]["aspects"]}
    assert ("Mo", "7th") in su_aspects
    assert ("Su", "7th") in mo_aspects  # the universal 7th is always mutual

    ju_aspects = {(a["code"], a["aspect"]) for a in aspects["Ju"]["aspects"]}
    assert ("Su", "9th") in ju_aspects


def test_natal_aspects_universal_7th_is_always_mutual():
    """The 7th/opposition aspect is the one relationship every graha
    shares, and it's inherently symmetric -- if P is opposite Q, Q is
    opposite P. Checked generically across the real chart, not just the
    one hand-verified Sun/Moon pair above."""
    chart = _real_client_reference_chart()
    aspects = natal_aspects(chart.planets)
    for code, data in aspects.items():
        for hit in data["aspects"]:
            if hit["aspect"] == "7th":
                back = {(h["code"], h["aspect"]) for h in aspects[hit["code"]]["aspects"]}
                assert (code, "7th") in back


def test_natal_aspects_special_aspects_are_not_generally_mutual():
    """Mars's 4th/8th (and Jupiter's/Saturn's own specials) are
    directional -- confirmed against the real chart, where Mars (Aries)
    8th-aspects Venus (Scorpio) but Venus does NOT aspect Mars back (their
    distance from Venus's side isn't one of Venus's own aspect distances).
    This isn't a bug -- it's the actual classical rule -- but worth
    locking in as a regression test so a future refactor can't silently
    "fix" it into false symmetry."""
    chart = _real_client_reference_chart()
    aspects = natal_aspects(chart.planets)
    ma_aspects = {(a["code"], a["aspect"]) for a in aspects["Ma"]["aspects"]}
    assert ("Ve", "8th") in ma_aspects
    ve_aspects = {a["code"] for a in aspects["Ve"]["aspects"]}
    assert "Ma" not in ve_aspects


def test_natal_aspects_every_planet_has_both_keys_even_with_no_hits():
    chart = _real_client_reference_chart()
    aspects = natal_aspects(chart.planets)
    for p in chart.planets:
        assert "aspects" in aspects[p.code]
        assert "aspected_by" in aspects[p.code]
        assert isinstance(aspects[p.code]["aspects"], list)
        assert isinstance(aspects[p.code]["aspected_by"], list)


def test_natal_aspects_no_planet_ever_aspects_itself():
    chart = _real_client_reference_chart()
    aspects = natal_aspects(chart.planets)
    for code, data in aspects.items():
        assert code not in {a["code"] for a in data["aspects"]}
        assert code not in {a["code"] for a in data["aspected_by"]}


def test_natal_aspects_rahu_and_ketu_never_aspect_each_other():
    """Client feedback (2026-09-24): Rahu and Ketu are always exactly 180
    degrees apart by definition (Ketu = Rahu + 180), so they are always in
    each other's 7th sign -- but that's a structural fact of how the lunar
    nodes work, not a real classical aspect relationship, and the client's
    own convention doesn't count it as one. Confirmed on the real
    reference chart, where Ra (Sagittarius) and Ke (Gemini) genuinely ARE
    opposite signs, so without the carve-out this would otherwise show up
    as a (false) mutual 7th aspect."""
    chart = _real_client_reference_chart()
    aspects = natal_aspects(chart.planets)
    ra_codes = {a["code"] for a in aspects["Ra"]["aspects"]} | {a["code"] for a in aspects["Ra"]["aspected_by"]}
    ke_codes = {a["code"] for a in aspects["Ke"]["aspects"]} | {a["code"] for a in aspects["Ke"]["aspected_by"]}
    assert "Ke" not in ra_codes
    assert "Ra" not in ke_codes


def test_aspected_by_for_point_finds_a_planet_aspecting_the_ascendant():
    """A synthetic case rather than relying on the real chart happening to
    have a hit on the Ascendant: place a fake Ascendant longitude exactly
    opposite Jupiter's real sign and confirm the universal 7th shows up."""
    chart = _real_client_reference_chart()
    jupiter = next(p for p in chart.planets if p.code == "Ju")
    opposite_longitude = (jupiter.longitude + 180.0) % 360.0
    hits = aspected_by_for_point(opposite_longitude, chart.planets)
    assert {"code": "Ju", "aspect": "7th"} in hits


def test_chart_to_dict_wires_aspects_for_every_planet_and_ascendant():
    chart = _real_client_reference_chart()
    data = chart_to_dict(chart)
    for p in data["planets"]:
        assert "aspects" in p
        assert "aspected_by" in p
        for group in (p["aspects"], p["aspected_by"]):
            for hit in group:
                assert set(hit) == {"code", "aspect"}
    asc = data["ascendant"]
    assert "aspected_by" in asc
    assert "aspects" not in asc  # Lagna never casts an aspect of its own


# --- Functional (house-lordship) benefic/malefic (2026-09-24, even later
# still) ---------------------------------------------------------------

def test_houses_ruled_by_saturn_for_taurus_ascendant_is_the_classic_yogakaraka():
    """Independent sanity check, not tied to the real reference chart:
    Saturn ruling both the 9th (trikona) and 10th (kendra) from a Taurus
    ascendant is a famous, textbook-standard yogakaraka fact -- if this
    doesn't come out right, the house-lordship math itself is wrong."""
    taurus_index = 1  # Aries=0, Taurus=1
    assert houses_ruled_by("Sa", taurus_index) == {9, 10}
    assert functional_nature("Sa", taurus_index) == "Benefic"


def test_functional_nature_matches_the_real_reference_chart_excel_data():
    """The client's real Excel 'Nature' column disagrees with the fixed
    natural classification for exactly 4 of 9 planets (Su, Ju, Sa, Ra) --
    functional_nature() reproduces all 3 of the non-node flips exactly for
    this chart's Capricorn ascendant, and leaves the 4th (Ra, a lunar
    node with no house lordship) deliberately unclassified rather than
    guessed. See ayanamsa-and-nature-findings-2026-09-24.md (project doc)
    for the full comparison and the classical reasoning behind each one."""
    chart = _real_client_reference_chart()
    asc_index = sign_index_for_longitude(chart.ascendant.longitude)
    expected = {
        "Su": "Malefic",   # rules only the 8th (dusthana) -- no kendra/trikona
        "Mo": "Benefic",   # rules only the 7th (kendra-only) -- keeps natural
        "Ma": "Malefic",   # rules 4th (kendra-only) + 11th -- keeps natural
        "Me": "Benefic",   # rules 6th + 9th (trikona) -- keeps natural
        "Ju": "Malefic",   # rules only 3rd + 12th -- no kendra/trikona
        "Ve": "Benefic",   # rules 5th (trikona) + 10th (kendra) -- yogakaraka
        "Sa": "Benefic",   # rules the 1st (Lagna) -- always auspicious
    }
    for code, expected_nature in expected.items():
        assert functional_nature(code, asc_index) == expected_nature, code
    # Rahu/Ketu deliberately left unclassified, not guessed.
    assert functional_nature("Ra", asc_index) is None
    assert functional_nature("Ke", asc_index) is None


def test_functional_nature_differs_from_natural_for_the_known_flips():
    chart = _real_client_reference_chart()
    asc_index = sign_index_for_longitude(chart.ascendant.longitude)
    for code in ("Su", "Ju", "Sa"):
        assert functional_nature(code, asc_index) != planet_nature(code)


def test_functional_nature_lagna_lord_is_always_benefic_even_if_naturally_malefic():
    """Generic rule check across all 12 possible ascendants: whichever
    planet rules the 1st house is always functionally Benefic, regardless
    of whether it's a natural malefic (e.g. Saturn/Mars ruling their own
    ascendant sign)."""
    for asc_index in range(12):
        for code in ("Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa"):
            if 1 in houses_ruled_by(code, asc_index):
                assert functional_nature(code, asc_index) == "Benefic"


def test_chart_to_dict_outer_planets_have_empty_conjunctions_and_aspects():
    """Classical Parashari conjunctions/graha-drishti are a graha-only
    concept -- Uranus/Neptune/Pluto never participate, even though they
    get houses/rasi_house/meaning/flags like any other planet."""
    chart = _real_client_reference_chart()
    data = chart_to_dict(chart)
    for p in data["planets"]:
        if p["code"] in ("Ur", "Ne", "Pl"):
            assert p["conjunctions"] == []
            assert p["aspects"] == []
            assert p["aspected_by"] == []
            assert p["meaning"]  # still gets a real meaning sentence
            assert 1 <= p["rasi_house"] <= 12


def test_chart_to_dict_wires_functional_nature_for_every_planet():
    chart = _real_client_reference_chart()
    data = chart_to_dict(chart)
    for p in data["planets"]:
        assert "functional_nature" in p
        if p["code"] in ("Ra", "Ke", "Ur", "Ne", "Pl"):
            assert p["functional_nature"] is None
        else:
            assert p["functional_nature"] in ("Benefic", "Malefic")


# --- planet_element / rashi_element (2026-09-24, newest) -- client-
# requested for coloring each chart-wheel planet label by the planet's
# own FIXED classical Pancha Tattva element, deliberately independent of
# whichever sign it's currently transiting (that's the separate
# rashi_element field) -- see chart_narrative.py's own comment.

def test_planet_element_fixed_classical_mapping():
    assert planet_element("Su") == "Fire"
    assert planet_element("Ma") == "Fire"
    assert planet_element("Mo") == "Water"
    assert planet_element("Ve") == "Water"
    assert planet_element("Me") == "Earth"
    assert planet_element("Sa") == "Air"
    assert planet_element("Ju") == "Ether"


def test_planet_element_is_none_for_nodes_and_outer_planets():
    # Client's own explicit instruction (2026-09-24): no classical
    # rulership exists for these five, so this must be None/unassigned,
    # never guessed or inferred from their current sign.
    for code in ("Ra", "Ke", "Ur", "Ne", "Pl"):
        assert planet_element(code) is None


def test_rashi_element_covers_all_twelve_signs():
    expected = {
        "Aries": "Fire", "Leo": "Fire", "Sagittarius": "Fire",
        "Taurus": "Earth", "Virgo": "Earth", "Capricorn": "Earth",
        "Gemini": "Air", "Libra": "Air", "Aquarius": "Air",
        "Cancer": "Water", "Scorpio": "Water", "Pisces": "Water",
    }
    for sign, element in expected.items():
        assert rashi_element(sign) == element


def test_planet_element_does_not_change_with_current_sign():
    """Regression for the client's own example: Mars in Cancer (a Water
    sign) must still report a Fire planet_element -- the two fields are
    completely independent. Uses the real reference chart, where three
    planets genuinely land in a different-element sign than their own
    fixed element (Sun in Virgo/Earth, Mercury in Libra/Air, Jupiter in
    Capricorn/Earth) -- not a hypothetical, real data from this
    engagement's own validated reference chart."""
    chart = _real_client_reference_chart()
    data = chart_to_dict(chart)
    by_code = {p["code"]: p for p in data["planets"]}
    mismatches = {"Su": ("Fire", "Earth"), "Me": ("Earth", "Air"), "Ju": ("Ether", "Earth")}
    for code, (expected_planet_element, expected_rashi_element) in mismatches.items():
        assert by_code[code]["planet_element"] == expected_planet_element
        assert by_code[code]["rashi_element"] == expected_rashi_element
        assert by_code[code]["planet_element"] != by_code[code]["rashi_element"]


def test_chart_to_dict_wires_planet_element_and_rashi_element_for_every_entry():
    chart = _real_client_reference_chart()
    data = chart_to_dict(chart)
    for p in data["planets"]:
        assert "rashi_element" in p and p["rashi_element"] in ("Fire", "Water", "Earth", "Air")
        if p["code"] in ("Ra", "Ke", "Ur", "Ne", "Pl"):
            assert p["planet_element"] is None
        else:
            assert p["planet_element"] in ("Fire", "Water", "Earth", "Air", "Ether")
    asc = data["ascendant"]
    assert asc["planet_element"] is None
    assert asc["rashi_element"] in ("Fire", "Water", "Earth", "Air")
