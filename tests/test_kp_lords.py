"""
Structural tests for the KP lordship-chain port (engine/kp_lords.py):
`get_nl_sl_ssl_from_deg` (port of `GetNL_SL_SSL_FromDeg`) and the
PlTblCl-equivalent table builder.

As with test_dasha.py: these confirm internal fidelity to the VBA
algorithm, not agreement with the client's real workbook output for a
real chart (no validated reference data available yet).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.engine.dasha import NAKSHATRA_SPAN, VIMSHOTTARI_ORDER_DEFAULT, vim_dasha_years
from app.engine.kp_lords import (
    build_planet_lord_table,
    get_nl_sl_ssl_from_deg,
    rashi_lord,
    sign_num_for_longitude,
)


def test_rashi_lord_matches_known_table():
    assert rashi_lord(1) == "Ma"   # Aries
    assert rashi_lord(4) == "Mo"   # Cancer
    assert rashi_lord(5) == "Su"   # Leo
    assert rashi_lord(12) == "Ju"  # Pisces
    assert rashi_lord(99) == ""    # out of range -> empty, no guessing


def test_sign_num_for_longitude_boundaries():
    assert sign_num_for_longitude(0.0) == 1     # 0 deg = start of Aries
    assert sign_num_for_longitude(29.999) == 1
    assert sign_num_for_longitude(30.0) == 2    # start of Taurus
    assert sign_num_for_longitude(359.999) == 12
    assert sign_num_for_longitude(360.0) == 1   # wraps
    assert sign_num_for_longitude(-1.0) == 12   # negative wraps to Pisces


def test_nl_at_nakshatra_start_has_zero_elapsed_fraction():
    # Degree 0.0 is the very start of Ashwini (nakshatra 0) -> NL = Ke,
    # and SL/SSL must also both be Ke (self-first, zero elapsed fraction).
    nl, sl, ssl = get_nl_sl_ssl_from_deg(0.0)
    assert nl == "Ke"
    assert sl == "Ke"
    assert ssl == "Ke"


def test_nl_cycles_every_9_nakshatras():
    # Nakshatra index 0, 9, 18 must all share the same NL (mod-9 cycle).
    starts = [i * NAKSHATRA_SPAN + 0.001 for i in (0, 9, 18)]
    nls = [get_nl_sl_ssl_from_deg(d)[0] for d in starts]
    assert len(set(nls)) == 1
    assert nls[0] == "Ke"


def test_sl_progression_matches_self_first_cumulative_shares():
    # Within nakshatra 0 (Ke, NL=Ke), the SL cycle is self-first starting
    # at Ke: Ke(7/120), Ve(20/120), Su(6/120), Mo(10/120), Ma(7/120),
  # Ra(18/120), Ju(16/120), Sa(19/120), Me(17/120). Probe just past each
    # cumulative boundary and confirm the SL advances to the next planet.
    order = VIMSHOTTARI_ORDER_DEFAULT  # starts at Ke already
    cumulative = 0.0
    boundaries = []
    for planet in order:
        cumulative += vim_dasha_years(planet) / 120.0
        boundaries.append(cumulative)

    # Just before the first boundary -> SL is Ke (first in cycle)
    deg = (boundaries[0] - 0.0005) * NAKSHATRA_SPAN
    _, sl, _ = get_nl_sl_ssl_from_deg(deg)
    assert sl == "Ke"

    # Just after the first boundary -> SL advances to Ve
    deg = (boundaries[0] + 0.0005) * NAKSHATRA_SPAN
    _, sl, _ = get_nl_sl_ssl_from_deg(deg)
    assert sl == "Ve"

    # Just after the second boundary -> SL advances to Su
    deg = (boundaries[1] + 0.0005) * NAKSHATRA_SPAN
    _, sl, _ = get_nl_sl_ssl_from_deg(deg)
    assert sl == "Su"

    # Right at the end of the nakshatra -> last planet in cycle (Me)
    deg = (NAKSHATRA_SPAN - 0.0001)
    _, sl, _ = get_nl_sl_ssl_from_deg(deg)
    assert sl == "Me"


def test_get_nl_sl_ssl_wraps_negative_and_over_360_degrees():
    a = get_nl_sl_ssl_from_deg(10.0)
    b = get_nl_sl_ssl_from_deg(10.0 + 360.0)
    c = get_nl_sl_ssl_from_deg(10.0 - 360.0)
    assert a == b == c


def test_build_planet_lord_table_self_referential_columns():
    # Construct longitudes so we know the NL of each planet by hand, then
    # confirm the second-order NLOFNL/NLOFSL/NLOFSSL columns are correct
    # self-referential lookups rather than fresh degree computations.
    longitudes = {
        "Su": 5.0,     # nakshatra 0 (Ashwini) -> NL=Ke
        "Mo": 20.0,    # nakshatra 1 (Bharani)  -> NL=Ve
        "Ma": 40.0,    # nakshatra 3 (Rohini)   -> NL=Mo
        "Me": 60.0,
        "Ju": 80.0,
        "Ve": 100.0,
        "Sa": 120.0,
        "Ra": 140.0,
        "Ke": 160.0,
    }
    table = build_planet_lord_table(longitudes)
    assert set(table.keys()) == set(longitudes.keys())

    for planet, row in table.items():
        assert row.planet == planet
        # NLOFNL(X) must equal the NL already stored for whichever planet
        # NL(X) resolved to (if that planet is itself in the table).
        nl_target = row.nakshatra_lord
        if nl_target in table:
            assert row.nl_of_nl == table[nl_target].nakshatra_lord
        sl_target = row.sub_lord
        if sl_target in table:
            assert row.nl_of_sl == table[sl_target].nakshatra_lord
        ssl_target = row.sub_sub_lord
        if ssl_target in table:
            assert row.nl_of_ssl == table[ssl_target].nakshatra_lord

        # rasi_lord must be internally consistent with the sign of the
        # supplied longitude
        assert row.rasi_lord == rashi_lord(sign_num_for_longitude(longitudes[planet]))


def test_build_planet_lord_table_missing_target_planet_returns_empty_not_guessed():
    # Only Sun supplied; whatever its NL/SL/SSL resolve to almost
    # certainly isn't in the table, so the second-order columns must come
    # back empty rather than silently computing something new.
    table = build_planet_lord_table({"Su": 5.0})
    row = table["Su"]
    if row.nakshatra_lord != "Su":
        assert row.nl_of_nl == ""
    if row.sub_lord != "Su":
        assert row.nl_of_sl == ""
    if row.sub_sub_lord != "Su":
        assert row.nl_of_ssl == ""
