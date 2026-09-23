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
3. A **Chart** view, expanded into **three linked reference charts** sharing
   one set of planet data from a single `/api/chart` call plus one
   `/api/navamsa` call:
   - **D1 (Rasi)** — classical whole-sign chart. House placement uses each
     planet's **`rasi_house`** field from `/api/chart`.
   - **Bhava Chalit** — cuspal (Placidus) house chart. House placement uses
     each planet's **`house`** field from `/api/chart` (same data source as
     D1, different field — do not recompute anything).
   - **D9 (Navamsa, beta)** — calls `/api/navamsa` separately. Show its
     `beta_disclaimer` prominently; label the tab/section "D9 (beta)" so
     it's visually distinct from the two validated D1/Bhava Chalit views.
   All three should be explicitly labeled **Nirayana (sidereal)** somewhere
   visible on the view — a one-line note near the disclaimer is enough (this
   engine only ever computes sidereal positions; the label just makes that
   explicit for anyone comparing against a Western/tropical chart elsewhere).
   Simple tables are fine for a first cut; a North Indian chart-wheel diagram
   per view is a nice-to-have, not required.
4. A **Transit** view: an optional date/time picker (blank = right now), calls
   `/api/transit`, shows each planet's current sign/nakshatra, which natal
   house it's transiting, and any conjunctions with natal planets. (Already
   live — keep as-is.)
5. A **KP Significators (beta)** view: calls `/api/kp-beta`, shows each
   planet's Sub Lord and the 4-level house significators, with the beta
   disclaimer prominently shown. (Already live — keep as-is.)
6. Optionally, a **Chat** view: streams from `/api/chat/stream` (Server-Sent
   Events) for a conversational interface — this is more involved to build
   than the others; skip it for a first cut if you want to ship faster.

Style it to match orbinovastro.com's existing design (colors, type, layout) —
the API doesn't care how it looks, only that the data displayed came from it.

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
3. Compute the chart and check all **three reference views**: D1 shows each
   planet's `rasi_house`, Bhava Chalit shows each planet's `house` (these can
   legitimately differ for the same planet — that's expected, not a bug), and
   D9 (beta) shows `navamsa_sign`/`navamsa_house` with its beta disclaimer
   visible. Cross-check the ascendant sign and a planet or two against a known
   reference chart.
4. Compute KP significators for the same birth details — the "beta" label
   must be visible.
5. Try the transit view with no date (defaults to now) and with a specific
   date.
6. If chat is built: ask "What sign is my Moon in?" and confirm the tool tag
   and streamed answer both appear.
