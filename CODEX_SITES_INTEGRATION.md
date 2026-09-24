# Adding the ORBINOVASTRO AI features to the OpenAI Sites project

**Give this whole document to Codex** as the spec for the page/section it should
build. It describes an existing, already-built, already-tested backend — Codex's
job is to build a **frontend page that calls it**, not to reimplement any of the
astrology math itself.

> **Update (2026-09-25): this is an incremental change to the already-live page,
> not a from-scratch rebuild.** The site at `orbinovastro.com/ai` is already
> connected to `BASE_URL` and working (Birth Details form, Chart, Transit, KP
> Significators beta) — keep that working exactly as-is. This update **adds**:
> a new **Preview** section (a free, shareable "candy" teaser that ends with a
> "Book Your Full Reading" button, meant to be the entry point for new
> visitors) and expands the **Chart** view into three linked reference charts
> — **D1 (Rasi)**, **Bhava Chalit**, and **D9 (Navamsa, beta)** — all
> explicitly labeled **Nirayana** (sidereal), since that's the system this
> engine uses throughout. See "What to build" below for the specifics and the
> new `/api/navamsa` and `/api/teaser` sections in the API contract.

> **Update (2026-09-26): the reference charts need an actual chart-wheel
> diagram, a dedicated cuspal chart, and a real visual-design pass — this
> is client-facing, and right now it's tables only.** No backend or API
> changes in this update — everything below uses data your page is already
> fetching. Three things to add:
> 1. **Draw a real North Indian diamond chart wheel** for D1, Bhava Chalit,
>    and D9 — not just tables. Exact geometry, house-box layout, and
>    labeling rules are given in the new "Chart wheel diagram" section
>    below — this is a validated, already-built algorithm (from this
>    engagement's standalone reference app), so reproduce it exactly rather
>    than designing your own layout.
> 2. **Add a fourth reference chart: Cuspal Chart (Nirayana house cusps).**
>    All 12 house cusps with sign, sign lord, and exact longitude — this
>    data is already in `/api/chart`'s `houses` array, nothing new to call.
>    See "Cuspal Chart" under "What to build" below.
> 3. **Raise the whole page's visual design** — this is what visitors see
>    right before deciding to book. See "Visual design pass" below for the
>    specific bar to hit.

> **Update (2026-09-24): a new paid feature — the real Overview Report PDF —
> is now live on the backend and ready to wire in.** This is the client's
> actual paid product: a ~10-page PDF (Executive Assessment, house/planet
> scorecard tables, strategic focus areas, conclusion) built from the same
> validated CCSI scoring engine, with an OpenAI-written interpretation layer.
> No backend changes needed on your side — just a new button/flow that calls
> `POST /api/overview-report` and downloads the PDF it returns. See the new
> rule 7 below, the new "Overview Report" item under "What to build", and the
> new `/api/overview-report` section in the API contract. The report's
> house/planet label wording now uses the client's own real, final text
> (an earlier version of this document flagged this as a placeholder --
> that has since been replaced; nothing for you to do about it either way,
> it's backend content, not something Codex renders directly).

> **Update (2026-09-24, later still): the Preview is now a full D1 chart
> analysis, not a one-paragraph blurb -- this is the free feature's whole
> reason for existing, so give it real layout attention.** The client's own
> feedback on the live Preview was direct: it "doesn't make the user order
> more... and doesn't even give trust." `/api/teaser`'s response shape has
> grown substantially as a result -- it still returns the original
> `headline`/`blurb`/`ascendant_sign`/`moon_sign`/`book_url` fields (nothing
> you already built breaks), but now ALSO returns `sun_sign`,
> `executive_summary` (an Ascendant/Sun/Moon "Big Three" synthesis
> paragraph), `placements` (an array of 10 objects -- the Ascendant plus all
> 9 planets -- each with its own D1 house, sign, and a full analytical
> narrative sentence written in the practice's own real house/planet
> language), `synthesis` (a chart-wide structural paragraph), and
> `upgrade_pitch` (an explicit, honest paragraph naming exactly what the
> paid Diagnostic Report adds beyond this free preview). See the rewritten
> `/api/teaser` section below for the full new contract and layout
> guidance -- this is a genuinely bigger view now, not a small tweak, and
> it should be laid out accordingly (see "Visual design pass" below too).

## Why this shape (read this before building)

The astrology calculations (Swiss Ephemeris positions, KP Sub Lords, house
placement, transits) run on a separate Python backend that is **not** part of
this Sites project and **cannot** be ported into it — Sites deploys to
Cloudflare Workers, which can't run a persistent Python process or the C
extension the ephemeris library depends on. That backend is already built,
tested (28 automated tests), and running; it just needs its own normal hosting
(Render/Railway/a VPS), separate from Sites.

**Rules for Codex to follow, not just suggestions:**

1. **Never invent or calculate an astrological position, sign, nakshatra,
   sub lord, or significator.** Every one of those values must come from a
   response returned by the API below. If a needed value isn't in an API
   response, say so in the UI rather than guessing.
2. **Never put the OpenAI key, or any other secret, in this Sites project.**
   The backend already holds its own OpenAI key server-side. This page only
   ever calls the backend's public HTTP endpoints — no keys needed here at all.
3. **Preserve every disclaimer.** `/api/chart` and `/api/transit` return a
   `disclaimer` field; `/api/kp-beta` and `/api/navamsa` return
   `beta_disclaimer`; `/api/teaser` returns its own `disclaimer`. Display these
   near the results, don't drop them. The KP Significators and D9 Navamsa
   features must always be visibly labeled "beta" — they're standard textbook
   theory, not the client's own validated production scoring.
4. **`BASE_URL`** is now live: **`https://orbinovastro-ai.onrender.com`**
   (deployed 2026-09-23 on Render). Use this exact URL everywhere `BASE_URL`
   appears below.
5. **`house` vs. `rasi_house` on `/api/chart` planets are both correct, by two
   different conventions — never treat one as a bug because it disagrees with
   the other.** `house` is Bhava Chalit (which Placidus cusp segment the
   planet's exact degree falls into — the KP convention). `rasi_house` is
   classical D1/Rasi whole-sign house (counted by sign distance from the
   ascendant's own sign). When you build the three-chart reference view below,
   the D1/Rasi chart must use `rasi_house`, and the Bhava Chalit chart must use
   `house` — don't use the same field for both.
6. **`/api/teaser` must never be placed behind any sign-in/paywall gate**, even
   after auth is switched on for the other endpoints — its entire purpose is
   to be usable by visitors who haven't signed up yet. It's the "candy" that
   should convert into a booking, so keep its call-to-action button (linking
   to `book_url` from the response) prominent and always visible.
7. **`/api/overview-report` is different from every other endpoint here: it
   returns a raw PDF binary, not JSON, and it is genuinely slow (roughly
   1–3 minutes, since it makes a real OpenAI call to write the report's
   interpretation text after computing the scoring).** Handle the response as
   a `blob`, not `.json()`, and trigger a file download from it (see the API
   contract section below for exact fetch code). Show a clear loading state
   for the full wait — "Generating your report — this can take a few
   minutes..." — rather than a spinner that looks stuck or a request that
   silently times out. This is the client's actual paid product, so it's
   worth the extra care: a visitor who clicks this button and sees nothing
   happen for two minutes will assume it's broken.

## What to build

Mirroring what the existing standalone version already does (you're welcome
to ask to see it — it's a single-page app with a shared "Birth Details" panel
and Preview / Chart / Transit / KP Significators / Chat tabs):

1. A **Birth Details** form: name, date (year/month/day), time (hour/minute),
   UTC offset, latitude/longitude, and a place-name field with a "Look up"
   button that calls `/api/geocode` to fill in lat/long/UTC offset
   automatically. (Already live — keep as-is.)
2. A **Preview** view (the client-facing "Free Preview" -- now a full D1
   analysis, not a short blurb): calls `/api/teaser` with just the birth
   details (no sign-in required) and renders, top to bottom:
   - The `headline`, as a large opening line.
   - `executive_summary` -- a full paragraph (Ascendant/Sun/Moon "Big
     Three" synthesis). Render as body text, not cramped into a card.
   - A **Planetary Placements** section built from the `placements` array
     (10 entries: Ascendant + all 9 planets). Each entry has `code`,
     `name`, `sign`, `house`, `retrograde`, `governs`, `house_domain`, and
     `narrative` (a full sentence or two of analysis for that placement).
     Render this as a clean, scannable list or table -- one row/card per
     placement, e.g. a compact header line ("Jupiter -- Capricorn -- House
     1") followed by the `narrative` text -- not as ten disconnected walls
     of text. A small "R" badge on `retrograde: true` rows is a nice touch
     (standard astrology convention).
   - `synthesis` -- a closing structural paragraph (kendra/trikona house
     counts). Render as body text.
   - `upgrade_pitch` -- the paragraph that explains exactly what the paid
     Diagnostic Report adds beyond this preview. Give this its own
     visually distinct block (not identical styling to the narrative
     paragraphs above it) immediately before the CTA, since it's doing the
     actual conversion work.
   - A prominent **"Book Your Full Reading"** button linking to the
     response's `book_url`, placed after `upgrade_pitch`.
   - `disclaimer` in small print at the very bottom -- don't let it
     compete visually with the content above it.
   This is a substantially longer view than before (roughly 10 planet-level
   paragraphs plus 3 summary paragraphs) -- it should still be the most
   inviting tab on the page, but "inviting" now means well-organized and
   easy to scan, not short. See "Visual design pass" below for the
   specific layout bar to hit.
3. An **Overview Report** feature (new — the client's actual paid product):
   a **"Get My Full Report"** button (placed prominently, e.g. as the natural
   next step after the Preview, or its own tab) that collects the same birth
   details plus a name, then calls `POST /api/overview-report`. On success,
   this returns a PDF binary — trigger a download of it (or open it in a new
   tab) rather than trying to render it inline. Show a loading state for the
   full 1–3 minute wait (see rule 7 above) and a clear error message if the
   call fails (surface the JSON `detail` field — see "Error handling" below).
   This is a paid feature: if/when auth is switched on for the site, this is
   one of the endpoints that should sit behind sign-in/subscription, same as
   `/api/chart`/`/api/kp-beta`/etc. — everything except `/api/teaser`.
4. A **Chart** view, expanded into **four linked reference charts** sharing
   one set of planet data from a single `/api/chart` call plus one
   `/api/navamsa` call — each one drawn as a real **North Indian chart-wheel
   diagram** (see "Chart wheel diagram" below for the exact algorithm),
   not just a table:
   - **D1 (Rasi)** — classical whole-sign chart. House placement uses each
     planet's **`rasi_house`** field from `/api/chart`. Each wheel box shows
     the whole-sign for that house (derive with `wholeSignHouseList` below,
     starting from the ascendant's sign).
   - **Bhava Chalit** — cuspal (Placidus) house chart. House placement uses
     each planet's **`house`** field from `/api/chart` (same data source as
     D1, different field — do not recompute anything). Each wheel box shows
     the **cusp sign straight from `/api/chart`'s `houses` array** (`houses[n-1].sign`
     for house n) — not the whole-sign — since a cuspal house's sign can
     differ from its whole-sign counterpart near a boundary.
   - **D9 (Navamsa, beta)** — calls `/api/navamsa` separately. Wheel boxes
     use whole-sign houses starting from `ascendant_navamsa_sign`; planets
     placed by `navamsa_house`. Show `beta_disclaimer` prominently; label
     the tab/section "D9 (beta)" so it's visually distinct from the two
     validated D1/Bhava Chalit views.
   - **Cuspal Chart (Nirayana house cusps)** — new, no planets on this one.
     A table of all 12 houses from `/api/chart`'s `houses` array: House,
     Cusp Sign, Cusp Sign Lord, Cusp Longitude (show degree-in-sign too —
     `longitude % 30` — alongside the full 0–360° value). Optionally reuse
     the same wheel diagram with each box labeled by its cusp sign and cusp
     degree instead of planets, purely as a visual anchor — the table is
     the part that matters. This is the raw cuspal data every KP
     astrologer expects to be able to see directly, separate from the
     Bhava Chalit planet-placement view.
   All four should be explicitly labeled **Nirayana (sidereal)** somewhere
   visible on the view — a one-line note near the disclaimer is enough (this
   engine only ever computes sidereal positions; the label just makes that
   explicit for anyone comparing against a Western/tropical chart elsewhere).
5. A **Transit** view: an optional date/time picker (blank = right now), calls
   `/api/transit`, shows each planet's current sign/nakshatra, which natal
   house it's transiting, and any conjunctions with natal planets. (Already
   live — keep as-is.)
6. A **KP Significators (beta)** view: calls `/api/kp-beta`, shows each
   planet's Sub Lord and the 4-level house significators, with the beta
   disclaimer prominently shown. (Already live — keep as-is.)
7. Optionally, a **Chat** view: streams from `/api/chat/stream` (Server-Sent
   Events) for a conversational interface — this is more involved to build
   than the others; skip it for a first cut if you want to ship faster.

Style it to match orbinovastro.com's existing design (colors, type, layout) —
the API doesn't care how it looks, only that the data displayed came from it.

## Chart wheel diagram (exact algorithm — reproduce, don't redesign)

This is the same North Indian diamond-chart algorithm already built, tested,
and in production in this engagement's standalone reference app
(`frontend/index.html`) — copy the geometry and logic exactly rather than
inventing a new layout, so all three planet-bearing wheels (D1, Bhava Chalit,
D9) stay visually and structurally consistent with each other and with the
standalone app.

**Geometry** — a 400×400 SVG viewBox. The diamond is an outer square plus
both diagonals plus the diamond connecting the four side-midpoints. Houses
1/4/7/10 (the "kendra" kite shapes at top/right/bottom/left) sit at the four
side-midpoints; the other 8 houses are the corner triangles the diagonals cut
each corner into. House 1 (the ascendant's box) is always the top kite,
regardless of which sign occupies it — this is what makes it "North Indian"
style rather than a fixed-sign layout. Exact polygon points and label-center
coordinates for houses 1–12 (as SVG `<polygon points="...">` and text
x/y):

```
1:  polygon "200,0 100,100 200,200 300,100"   label (200, 95)
2:  polygon "400,0 200,0 300,100"             label (300, 38)
3:  polygon "400,0 400,200 300,100"           label (358, 100)
4:  polygon "400,200 300,100 200,200 300,300" label (305, 200)
5:  polygon "400,200 400,400 300,300"         label (358, 300)
6:  polygon "400,400 200,400 300,300"         label (300, 362)
7:  polygon "200,400 300,300 200,200 100,300" label (200, 305)
8:  polygon "200,400 0,400 100,300"           label (100, 362)
9:  polygon "0,400 0,200 100,300"             label (42, 300)
10: polygon "0,200 100,300 200,200 100,100"   label (95, 200)
11: polygon "0,200 0,0 100,100"               label (42, 100)
12: polygon "0,0 200,0 100,100"               label (100, 38)
```

Draw all 12 polygons (house 1's box gets a subtle fill to mark it as the
ascendant; the rest transparent), then an outer 2px border rect, then a small
"ASC ↑" label at the top-center (200, 14). Each house box's text: the sign
abbreviation (first 3 letters) on the first line in the accent color, then
one line per occupying planet's 2-letter code (append a small "ᴿ" superscript
or similar retrograde mark if `retrograde` is true).

**Which sign goes in which box, per chart type:**
- **D1**: whole-sign houses starting from the ascendant's own sign. In
  pseudocode:
  ```js
  function wholeSignHouseList(house1Sign) {
    const RASHI = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                   "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"];
    const startIdx = RASHI.indexOf(house1Sign);
    return Array.from({length: 12}, (_, i) => ({
      house: i + 1, sign: RASHI[(startIdx + i) % 12],
    }));
  }
  ```
  Call with `data.ascendant.sign`; place each planet in the box matching its
  `rasi_house`.
- **Bhava Chalit**: do NOT use `wholeSignHouseList` — use `/api/chart`'s own
  `houses` array directly (`houses[n-1].sign` is house n's cusp sign, already
  computed server-side). Place each planet in the box matching its `house`
  field.
- **D9 (beta)**: same `wholeSignHouseList` function, called with
  `ascendant_navamsa_sign` from `/api/navamsa`. Place each planet in the box
  matching its `navamsa_house`.
- **Cuspal Chart**: same as Bhava Chalit's box-to-sign mapping (`houses[n-1].sign`),
  but no planets — instead label each box with its cusp longitude (e.g.
  "20.19°") beneath the sign abbreviation, since the point of this chart is
  the cusp positions themselves.

## Visual design pass — this is client-facing, raise the bar

This page is what a prospective client sees right before deciding whether to
book a paid reading, so it needs to look considered and trustworthy, not like
a debug dashboard. Concretely:

- **The Preview tab is the hero, and it is now a genuinely long-form page --
  design it like a short professional report, not a horoscope card.** Use
  real section structure (a short intro/executive-summary block, then a
  clearly delineated Planetary Placements section, then a closing
  synthesis + upgrade block), generous whitespace between sections, and a
  readable measure (don't let paragraphs run edge-to-edge on a wide
  screen). The "Book Your Full Reading" button should look like the
  obvious next action (real button styling, not a plain link) and should
  sit directly below the `upgrade_pitch` paragraph, not buried further
  down the page.
- **The `upgrade_pitch` block is the conversion moment -- give it a
  distinct visual treatment** (e.g. a subtly shaded panel or a border
  accent) so it reads as "here's what you get next," not as one more
  paragraph of chart description blending into the ones above it.
- **Consistent chart-wheel styling across D1 / Bhava Chalit / D9 / Cuspal.**
  Same wheel size and stroke weight in all four; a small accent-color tag or
  icon per chart type so a user can tell at a glance which one they're
  looking at (e.g. a "beta" chip already required for D9 — extend that same
  visual language rather than inventing a new one per view).
  Planet labels should be legible at a glance — don't cram 3+ planets into a
  box without adequate line spacing.
- **Typography and spacing**: a clear type scale (headline / section heading
  / body / caption), generous line-height on disclaimer text so it doesn't
  read as a wall of fine print, and consistent card/section padding across
  every tab.
- **Retrograde and beta markers should be visually distinct**, not just a
  letter suffix buried in text — a small superscript, badge, or color
  treatment that's consistent everywhere it appears.
- **Mobile-responsive**: the wheel diagrams and tables need to remain legible
  on a phone-width screen — stack panels vertically, let the SVG scale down
  proportionally rather than clipping.
- **Match orbinovastro.com's existing brand** (colors, type, header/footer
  treatment) rather than introducing a visually separate "tool" aesthetic —
  a visitor should feel like they're still on orbinovastro.com, not like
  they clicked into a different product.

## API contract

All endpoints are on `BASE_URL` (replace with the real deployed URL). All
`POST` bodies and responses are JSON.

### `GET /health`
`{"status": "ok"}` — use to check the backend is reachable.

### `POST /api/geocode`
Request:
```json
{"place": "Mumbai, India", "year": 1990, "month": 6, "day": 15, "hour": 12, "minute": 0}
```
`hour`/`minute` are optional (default 12:00) — only affect historical DST edge
cases, not accuracy of the location itself.

Response:
```json
{
  "place": "Mumbai, Maharashtra, India",
  "latitude": 19.0760, "longitude": 72.8777,
  "timezone_name": "Asia/Kolkata", "utc_offset_hours": 5.5,
  "note": ""
}
```
`timezone_name`/`utc_offset_hours` can be `null` for an unusual location
(e.g. open ocean) — `note` explains why when that happens.

### `POST /api/chart`
Request (`BirthDetailsIn` — this exact shape is reused by `/api/kp-beta` and
nested under `"birth"` in `/api/transit`):
```json
{
  "name": "Optional display name", "place": "Optional display place",
  "year": 1990, "month": 6, "day": 15,
  "hour": 14, "minute": 30, "second": 0,
  "utc_offset_hours": 5.5,
  "latitude": 19.0760, "longitude": 72.8777
}
```
Response (`ChartOut`):
```json
{
  "name": "", "place": "",
  "ayanamsa_deg": 23.94, "ayanamsa_mode": "Krishnamurti (KP)",
  "ascendant": {"house": 1, "longitude": 294.8, "sign": "Capricorn", "sign_lord": "Sa"},
  "houses": [ {"house": 1, "longitude": 294.8, "sign": "Capricorn", "sign_lord": "Sa"}, "... 12 total, houses 1-12" ],
  "planets": [
    {
      "code": "Su", "name": "Sun", "longitude": 175.5,
      "sign": "Virgo", "sign_lord": "Me", "degree_in_sign": 25.5,
      "nakshatra": "Chitra", "nakshatra_lord": "Ma", "pada": 1,
      "retrograde": false, "house": 8, "rasi_house": 9
    },
    "... 9 planets total: Su, Mo, Ma, Me, Ju, Ve, Sa, Ra, Ke"
  ],
  "disclaimer": "Mechanical-layer chart only: ... (show this to the user)"
}
```
`house` is Bhava Chalit (cuspal/Placidus) house placement. `rasi_house` is
classical D1/Rasi whole-sign house placement. They can legitimately differ
for a planet near a house cusp — see rule 5 above. Use `house` for the Bhava
Chalit view and `rasi_house` for the D1 view.

### `POST /api/navamsa` (BETA)
D9 Navamsa divisional chart — standard textbook formula (movable/fixed/dual
sign rule), not yet matched against the client's own workbook, hence "beta".

Request: same `BirthDetailsIn` shape as `/api/chart`.

Response (`NavamsaOut`):
```json
{
  "ascendant_navamsa_sign": "Leo", "ascendant_navamsa_sign_lord": "Su",
  "planets": [
    {
      "code": "Su", "name": "Sun",
      "navamsa_sign": "Scorpio", "navamsa_sign_lord": "Ma",
      "navamsa_house": 4
    },
    "... 9 planets total: Su, Mo, Ma, Me, Ju, Ve, Sa, Ra, Ke"
  ],
  "beta_disclaimer": "BETA: standard D9 Navamsa formula only. ... (show this prominently)"
}
```
`navamsa_house` is whole-sign house placement counted from
`ascendant_navamsa_sign` (Placidus cusps aren't recomputed for divisional
charts — that's not how D-charts work).

### `POST /api/teaser`
The free, client-facing "Free Preview" -- deliberately not gated behind
sign-in, even once auth is turned on elsewhere. A full D1 (Rasi) chart
PLACEMENT analysis -- which sign and house every planet occupies, and what
that means in the practice's own real house/planet language -- but
deliberately stops short of the paid report's proprietary stress/support
scoring (`upgrade_pitch` says so explicitly; see `engine/teaser.py`'s
module docstring on the backend for the full reasoning, if you want it).

Request: same `BirthDetailsIn` shape as `/api/chart` (only `name` and the
birth/location fields are used; `place` is ignored here).

Response (`TeaserOut`) -- note this grew substantially from the original
headline/blurb-only shape; every field below is present on every response:
```json
{
  "ascendant_sign": "Capricorn",
  "moon_sign": "Pisces",
  "sun_sign": "Virgo",
  "headline": "Devang Naik rises in Capricorn, Moon in Pisces.",
  "blurb": "A Capricorn ascendant carries quiet discipline -- composed, ambitious, patient in the way it builds. Paired with a Moon that dissolves easily into feeling -- an emotional world that is porous, dreamy, compassionate.",
  "executive_summary": "Devang Naik's Ascendant (Lagna) -- the structural frame through which every other placement in this chart is expressed, and the significator of Self/Personality -- falls in Capricorn. A Capricorn ascendant carries quiet discipline -- composed, ambitious, patient in the way it builds. The Sun, seat of core identity and executive will, is placed in Virgo: A Sun in Virgo anchors identity in competence -- methodical, detail-oriented, defined by the standard of its own work. The Moon, governing cognitive and emotional processing, is placed in Pisces: Paired with a Moon that dissolves easily into feeling -- an emotional world that is porous, dreamy, compassionate. Ascendant, Sun, and Moon together form the chart's baseline operating profile -- the reference frame against which the full nine-planet, twelve-house structure below is read.",
  "placements": [
    {
      "code": "Asc", "name": "Ascendant", "sign": "Capricorn", "house": 1,
      "retrograde": false, "governs": "Self/Body", "house_domain": "Self/Personality",
      "narrative": "The Ascendant -- karaka (significator) for Self/Body (core identity, physical vitality, and the outward expression of will) -- rises in Capricorn, defining the first house: Self/Personality (physical body, appearance, temperament, vitality, and overall approach to life). Every other placement in this chart is read relative to this one, making it the fixed reference point of the entire structure."
    },
    {
      "code": "Su", "name": "Sun", "sign": "Virgo", "house": 9,
      "retrograde": false, "governs": "Soul/Vitality", "house_domain": "Fortune/Dharma",
      "narrative": "Sun -- karaka (significator) for Soul/Vitality (inner life force, emotional security, and instinctive nurturing needs) -- is positioned in Virgo, within the ninth house: Fortune/Dharma (father, teachers, higher learning, spirituality, luck, and long-distance or foreign journeys). In structural terms, Sun channels its core signification into the domain of fortune/dharma, making this house one of the principal channels through which soul/vitality is expressed in this chart."
    }
    // ... 8 more entries: Mo, Ma, Me, Ju, Ve, Sa, Ra, Ke, in that order,
    // same shape as above. 10 entries total (Ascendant + 9 planets).
  ],
  "synthesis": "Viewed as a whole, this chart distributes its nine planetary placements across 8 of the twelve houses. 3 of 9 placements fall in the angular (kendra) houses -- the first, fourth, seventh, and tenth, the classical structural axis of self, home, partnership, and career -- and 2 of 9 fall in the trinal (trikona) houses -- the first, fifth, and ninth, associated with fortune, creativity, and higher purpose. These are structural counts, not a verdict of favorability: this preview describes WHERE each planet sits, not whether that placement is presently operating under supportive or adverse astrological pressure.",
  "upgrade_pitch": "This is precisely where the free preview stops, by design. Placement -- which sign, which house, which of your twelve life domains each planet activates -- is descriptive fact, and it is shown above in full, across all nine planets and the Ascendant. What it does not yet tell you is how those placements interact: which houses are presently reinforced and which are under measurable stress, both in this natal chart and under today's transiting sky, and how your current planetary period (dasha) is activating specific placements right now. That quantified, house-by-house diagnostic -- built on this practice's own proprietary connection-and-stress scoring methodology -- is the core of the full Diagnostic Report, delivered as a complete written assessment, not a set of raw numbers.",
  "book_url": "https://orbinovastro.square.site/s/appointments",
  "disclaimer": "A free preview only -- the D1 (Rasi) chart's placement structure: which sign and house every planet occupies, and which of this practice's own real house/planet domains that activates. All positions are Nirayana (sidereal), from the validated mechanical layer. Deliberately does NOT include KP significators (see the beta significators feature), dasha/bhukti timing, or the proprietary connection-and-stress scoring (CCSI) that the full paid Diagnostic Report is built on -- this preview describes WHERE each planet sits, not whether that placement is currently under astrological support or stress."
}
```

Rendering guidance (see "What to build" item 2 and "Visual design pass" above
for the full layout spec):
- `headline` — large opening line.
- `executive_summary` — a full paragraph, body text.
- `placements` — a scannable list/table, one row or card per entry, showing
  at minimum `name` + `sign` + `house` as a header and `narrative` as the
  body; a small badge on `retrograde: true` entries is a nice touch.
- `synthesis` — a closing paragraph, body text.
- `upgrade_pitch` — its own visually distinct block (this is the conversion
  moment — see "Visual design pass" above), directly followed by the
  **"Book Your Full Reading"** button linking to `book_url` (opens in a new
  tab).
- `disclaimer` — small print at the very bottom.
- `ascendant_sign`/`moon_sign`/`sun_sign`/`blurb` are still returned for
  convenience (e.g. if you want a short one-line sign summary somewhere in
  the header) but are fully subsumed by `executive_summary` — you don't need
  to render `blurb` separately if `executive_summary` is already shown.

### `POST /api/kp-beta`
Request: same `BirthDetailsIn` shape as `/api/chart`.

Response (`KPBetaOut`):
```json
{
  "beta_disclaimer": "BETA: standard KP Sub Lord + 4-level significator theory only. ... (show this prominently)",
  "planet_sub_lords": {
    "Su": {"nakshatra": "Chitra", "nakshatra_lord": "Ma", "sub_lord": "Ra", "house": 8},
    "...": "one entry per planet code (Su, Mo, Ma, Me, Ju, Ve, Sa, Ra, Ke)"
  },
  "house_significators": [
    {
      "house": 1, "occupants": ["Mo"], "owner": "Sa",
      "star_lord_of_occupants": ["Ma"], "star_lord_of_owner": ["Ve"],
      "cuspal_sub_lord": "Ju"
    },
    "... 12 total, houses 1-12"
  ]
}
```

### `POST /api/transit`
Request (`TransitRequestIn`) — `transit` is optional; omit it (or omit its
`year`) to mean "right now":
```json
{
  "birth": { "...same BirthDetailsIn shape as above..." },
  "transit": {
    "year": 2026, "month": 12, "day": 25,
    "hour": 0, "minute": 0, "utc_offset_hours": 5.5
  }
}
```
Response (`TransitOut`):
```json
{
  "transit_time_utc": "2026-12-24T18:30:00+00:00",
  "transit_time_source": "custom",
  "planets": [
    {
      "code": "Su", "name": "Sun", "longitude": 248.8,
      "sign": "Sagittarius", "sign_lord": "Ju", "degree_in_sign": 8.8,
      "nakshatra": "Mula", "nakshatra_lord": "Ke", "retrograde": false,
      "natal_house": 11, "conjuncts_natal": ["Ra"]
    },
    "... 9 planets total"
  ],
  "disclaimer": "Mechanical-layer transit only: ... (show this to the user)"
}
```

### `POST /api/chat` (non-streaming) and `POST /api/chat/stream` (SSE)
Request (`ChatRequestIn`):
```json
{
  "messages": [{"role": "user", "content": "What sign is my Moon in?"}],
  "birth_details": { "...optional BirthDetailsIn, or null if not known yet..." }
}
```
`/api/chat` responds once: `{"reply": "...", "used_chart_tool": true}`.

`/api/chat/stream` responds as Server-Sent Events, each line `data: {json}\n\n`:
```
{"type": "tool_used", "name": "compute_chart"}
{"type": "token", "text": "Your Moon "}
{"type": "token", "text": "is in Pisces."}
{"type": "done"}
```
or on failure: `{"type": "error", "detail": "..."}`. `name` in `tool_used` is
one of `compute_chart`, `compute_kp_significators_beta`, `geocode_place`,
`compute_transit` — use it to show which capability answered (and add a
"beta" tag when it's the KP one).

### `GET /api/auth-config`
```json
{"auth_enabled": false, "supabase_url": "", "supabase_anon_key": ""}
```
Currently always `auth_enabled: false` — every endpoint above is open access
today. Once the client sets up Supabase + Stripe on the backend side, this
flips to `true` and the endpoints above start requiring a signed-in,
subscribed user (a `401`/`402` response). Codex doesn't need to build any
sign-in UI for this yet — that will be a separate follow-up once the backend
side is actually configured.

### `POST /api/overview-report` (PAID — returns a PDF binary, not JSON)
The client's actual paid product: a ~10-page Overview Report PDF (Executive
Assessment + Legend, house scorecard, planet scorecard, strategic focus
areas, conclusion), built from the same validated CCSI scoring engine behind
`/api/ccsi`, with an OpenAI-written interpretation layer. **Takes roughly
1–3 minutes to respond** — see rule 7 above.

Request (same `BirthDetailsIn`/optional `transit` shape as `/api/transit`,
plus a `client_name`):
```json
{
  "client_name": "Devang Naik",
  "birth": { "...same BirthDetailsIn shape as /api/chart..." },
  "transit": { "...optional, same shape as /api/transit's transit field, or omit for right now..." }
}
```

Response on success: **not JSON** — a raw PDF binary
(`Content-Type: application/pdf`, `Content-Disposition: attachment;
filename="..."`). It also carries an `X-Labels-Are-Placeholder: true` response
header right now (see the update banner at the top of this doc) — no action
needed for this, just don't be surprised by it. Response on failure: normal
JSON error per "Error handling" below (e.g. a 502 if the report-generation
call itself fails).

Suggested fetch/download pattern:
```js
async function getOverviewReport(payload) {
  const resp = await fetch(`${BASE_URL}/api/overview-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Report generation failed." }));
    throw new Error(err.detail || "Report generation failed.");
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "overview-report.pdf";
  a.click();
  URL.revokeObjectURL(url);
}
```
Call this from behind a loading state that stays up for the full request —
don't set any client-side timeout shorter than a few minutes, and don't treat
a long wait as a failure on its own.

## Error handling

Every endpoint above returns a normal HTTP error status with a JSON body
`{"detail": "human-readable message"}` on failure (400 for bad input, 401/402
once auth is on, 502/503 for chat backend issues). Surface `detail` to the
user rather than a generic error.

## CORS note (for whoever deploys the backend, not Codex)

The backend currently allows requests from any origin (`allow_origins=["*"]`)
so this will work during testing with no changes. Before this goes live
publicly, that should be tightened to the exact Sites project URL and
orbinovastro.com — a one-line change in the backend's `main.py`, not
something Codex needs to handle.

## Testing checklist

1. `GET {BASE_URL}/health` returns `{"status": "ok"}`.
2. Fill in a known birth detail (or use "Look up" with a place name) and
   generate the **Preview** — confirm the headline and executive summary
   read sensibly, all 10 placement entries (Ascendant + 9 planets) render
   with their own narrative text, the closing synthesis and upgrade-pitch
   paragraphs both appear with the upgrade pitch visually distinct, and the
   "Book Your Full Reading" button opens `book_url` in a new tab. Cross-check
   one or two placements' `house`/`sign` values against the Chart tab's own
   output for the same birth details -- they must agree exactly (both read
   from the same underlying chart).
3. Compute the chart and check all **four reference views**, each with an
   actual chart-wheel diagram (not just a table): D1 shows each planet's
   `rasi_house` and its wheel boxes use whole-sign houses from the
   ascendant's sign; Bhava Chalit shows each planet's `house` and its wheel
   boxes use the cusp sign straight from the `houses` array (these can
   legitimately differ from D1's sign for the same box — that's expected,
   not a bug); D9 (beta) shows `navamsa_sign`/`navamsa_house` with its beta
   disclaimer visible; Cuspal Chart shows all 12 houses' sign/sign lord/
   longitude with no planets. Cross-check the ascendant sign and a planet or
   two against a known reference chart. Confirm the wheels look consistent
   with each other (same size/style) and are legible on a narrow/phone-width
   window.
4. Compute KP significators for the same birth details — the "beta" label
   must be visible.
5. Try the transit view with no date (defaults to now) and with a specific
   date.
6. If chat is built: ask "What sign is my Moon in?" and confirm the tool tag
   and streamed answer both appear.
7. Click "Get My Full Report", let it run the full 1–3 minutes without
   interrupting it, and confirm a real PDF downloads (open it and check it
   has multiple pages, not just a cover). Also try it with a deliberately
   invalid input (if easy to trigger) and confirm the error message shown to
   the user is readable, not a raw stack trace or a silent failure.
