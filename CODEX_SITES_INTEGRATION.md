# Adding the ORBINOVASTRO AI features to the OpenAI Sites project

**Give this whole document to Codex** as the spec for the page/section it should
build. It describes an existing, already-built, already-tested backend — Codex's
job is to build a **frontend page that calls it**, not to reimplement any of the
astrology math itself.

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
   `disclaimer` field; `/api/kp-beta` returns `beta_disclaimer`. Display these
   near the results, don't drop them. The KP Significators feature must always
   be visibly labeled "beta" — it is standard KP theory, not the client's own
   validated production scoring.
4. **`BASE_URL`** below is a placeholder — replace it with the real backend
   URL once it's deployed (e.g. `https://orbinovastro-ai.onrender.com`).

## What to build

Four features, mirroring what the existing standalone version already does
(you're welcome to ask to see it — it's a single-page app with a shared
"Birth Details" panel and Chart / Transit / KP Significators / Chat tabs):

1. A **Birth Details** form: name, date (year/month/day), time (hour/minute),
   UTC offset, latitude/longitude, and a place-name field with a "Look up"
   button that calls `/api/geocode` to fill in lat/long/UTC offset
   automatically.
2. A **Chart** view: calls `/api/chart`, shows the ascendant, a table of
   planets (sign, degree, nakshatra, pada, house), and the disclaimer. (A
   North Indian chart-wheel diagram is a nice-to-have if you want to match the
   visual richness of the standalone version — not required for a first cut.)
3. A **Transit** view: an optional date/time picker (blank = right now), calls
   `/api/transit`, shows each planet's current sign/nakshatra, which natal
   house it's transiting, and any conjunctions with natal planets.
4. A **KP Significators (beta)** view: calls `/api/kp-beta`, shows each
   planet's Sub Lord and the 4-level house significators, with the beta
   disclaimer prominently shown.
5. Optionally, a **Chat** view: streams from `/api/chat/stream` (Server-Sent
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
      "retrograde": false, "house": 8
    },
    "... 9 planets total: Su, Mo, Ma, Me, Ju, Ve, Sa, Ra, Ke"
  ],
  "disclaimer": "Mechanical-layer chart only: ... (show this to the user)"
}
```

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
   compute the chart — check the ascendant sign and a planet or two make
   sense (e.g. cross-check against a known reference chart).
3. Compute KP significators for the same birth details — the "beta" label
   must be visible.
4. Try the transit view with no date (defaults to now) and with a specific
   date.
5. If chat is built: ask "What sign is my Moon in?" and confirm the tool tag
   and streamed answer both appear.
