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
> new `/api/overview-report` section in the API contract. **One thing to flag
> to the client, not something for you to change:** the report's house/planet
> label wording is currently a standard-textbook placeholder, not the
> client's own final text — this doesn't affect anything you build, it's a
> backend content update coming later.

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
2. A **Preview** view (new — the client-facing "candy"): calls `/api/teaser`
   with just the birth details (no sign-in required), shows the `headline`
   and `blurb` text, and a prominent **"Book Your Full Reading"** button
   linking to the response's `book_url`. This should be the most inviting,
   least cluttered view on the page — ideally the first tab a new visitor
   lands on — since its whole job is to turn a curious visitor into a
   booking. Show the `disclaimer` in small print, but don't let it compete
   visually with the headline/blurb/button.
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

- **The Preview tab is the hero.** It's the entry point for new visitors and
  the one place with a single, clear conversion goal — give it the most
  generous whitespace, the largest type, and the most visual polish of any
  view. The "Book Your Full Reading" button should look like the obvious next
  action (real button styling, not a plain link), not compete with anything
  else on the page.
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
The free, client-facing "candy" preview — deliberately not gated behind
sign-in, even once auth is turned on elsewhere. No predictions, no
significators — just ascendant + Moon sign framing and a booking link.

Request: same `BirthDetailsIn` shape as `/api/chart` (only `name` and the
birth/location fields are used; `place` is ignored here).

Response (`TeaserOut`):
```json
{
  "ascendant_sign": "Capricorn", "moon_sign": "Pisces",
  "headline": "Devang rises in Capricorn, Moon in Pisces.",
  "blurb": "A Capricorn ascendant carries quiet discipline -- composed, ambitious, patient in the way it builds. Paired with a Moon that dissolves easily into feeling -- an emotional world that is porous, dreamy, compassionate.",
  "book_url": "https://orbinovastro.square.site/s/appointments",
  "disclaimer": "General sign-level preview, not a personalized reading -- book a full consultation for chart-specific guidance."
}
```
Render `headline` and `blurb` as the main content, with a prominent button
labeled something like **"Book Your Full Reading"** that links to `book_url`
(opens in a new tab). Show `disclaimer` in small print near the bottom.

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
   generate the **Preview** — confirm the headline/blurb read sensibly and
   the "Book Your Full Reading" button opens `book_url` in a new tab.
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
