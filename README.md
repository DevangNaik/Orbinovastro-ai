# ORBINOVASTRO — AI App

This is the first working slice of the AI Agent / web app described in the
project roadmap (`ai-agent-app-roadmap.md` in the ORBINOVASTRO Claude
project). It is deliberately built in de-risked layers: a validated
mechanical layer first, then clearly labeled beta layers on top, not a
feature-complete replacement for the production workbook.

## What this is

- A **FastAPI backend** (`backend/app/`) with:
  - A Python port of the **mechanical layer** of the astrology engine:
    planetary longitudes, signs, nakshatras (+ pada), ascendant, Placidus
    house cusps, and which house each planet occupies, via Swiss Ephemeris
    (`pyswisseph`) — no Excel, no COM, no Windows dependency. **Validated**,
    tested against a known reference chart.
  - A **BETA KP significators engine** (`engine/kp.py`): Sub Lord (per
    planet and per house cuspal point) and the classical 4-level house
    significator method (occupants / owner / star-lord-of-occupants /
    star-lord-of-owner). Standard textbook KP theory — **not** the client's
    proprietary scoring/ranking system, and not yet cross-checked against
    the production workbook's own output. Always labeled "beta" everywhere
    it appears.
  - A **place-name lookup** (`engine/geocode.py`): resolves a place name to
    real latitude/longitude via OpenStreetMap's Nominatim, and the UTC
    offset that place's timezone actually used at the given date/time
    (DST- and historical-zone aware, not a flat guess). Pure lookup, no
    astrology judgment.
  - A **transit engine** (`engine/transit.py`): current (or any given
    moment's) planetary positions placed against the natal chart — which
    natal house each transiting planet currently occupies, plus simple
    conjunctions with natal planets. Mechanical layer, not beta — but does
    NOT include transit-to-natal aspects (trine/square/opposition),
    dasha/bhukti overlay, or any event-timing judgment.
  - An **OpenAI-powered chat agent** with four tools (chart, KP-beta,
    geocode, transit), available both as a normal JSON response
    (`/api/chat`) and as a **token-by-token streaming** response over
    Server-Sent Events (`/api/chat/stream`).
  - **Optional user accounts, MFA, and subscription gating** (`auth.py`,
    `billing.py`) — built and tested, but **off by default**
    (`AUTH_ENABLED=false`). See "User accounts, MFA & subscription gating"
    below for what this is and the setup steps still needed on your end.
- A **menu-driven single-page frontend** (`frontend/index.html`) — four
  tabs sharing one Birth Details panel:
  - **Chart** — computes the chart and draws it as a real **North Indian
    diamond-style chart wheel** (not just a table), signs and planets
    placed by house, retrograde planets marked.
  - **Transit** — pick a date (or leave blank for right now) and see where
    the planets currently are relative to the natal chart.
  - **KP Significators (beta)** — Sub Lords and house significators, in
    plain tables, clearly beta-labeled.
  - **Chat** — the streaming, markdown-rendering assistant, with
    conversation memory (`localStorage`) and suggestion chips.
  - A **"Look up" button** next to the Place field calls the geocode
    endpoint and fills in latitude/longitude/UTC offset automatically.
- **Tests**: 28 passing —
  `test_ephemeris.py` (6), `test_kp_beta.py` (5), `test_geocode.py` (5),
  `test_transit.py` (4), `test_auth.py` (8).

## What this is NOT (yet)

Still explicitly out of scope, on purpose, until the client (Devang) signs
off on the underlying VBA logic or a beta feature is promoted:

- The client's proprietary **connection-scoring / ranking system**
  (`ConnSummaryCore`, `WTDSCORE`, the `BatchAnalyze_MD_Combinations_*`
  family, `Score_Additive`/`Flag_Additive`).
- Divisional (varga) charts beyond the basic D1 (Rasi) chart.
- Dasha/Bhukti/Antra **period selection and timing**.
- Transit-to-natal **aspects** (trine/square/opposition) beyond simple
  conjunction, and any event-timing/scoring judgment on top of transits —
  the client's workbook has considerably more under "transit and other
  tables" than this first cut covers; tell me which specific
  tables/reports matter most and I'll scope the next round around them.
- Birth Time Rectification (the `ModKP_BTR_STEP1/2/3` pipeline).
- The client's exact ayanamsa (`Devarajayan`, roadmap doc open question #1)
  and which house-cusp convention is live (#2/#14) — both still pending
  client confirmation; this app uses the standard Krishnamurti ayanamsa
  and sidereal cusps as well-defined stand-ins in the meantime.
- A working sign-in/sign-up screen — the backend scaffolding is built and
  tested, but actually turning it on needs your own Supabase and Stripe
  accounts (see below); nobody can sign up today.

The chat agent is instructed to only state positions/significators that
came from a tool call in that conversation, to always caveat the KP-beta
tool as beta, and to say plainly when something needs a not-yet-ported
part of the engine, rather than guessing.

## User accounts, MFA & subscription gating

Built and unit-tested (`app/auth.py`, `app/billing.py`,
`tests/test_auth.py`), but **disabled by default** — the app behaves
exactly as before until you turn this on. It can't be turned on from this
end because it needs accounts only you can create (Supabase, Stripe) and
real billing details.

**Why Supabase Auth + Stripe, not a direct Squarespace/Square bridge:**
orbinovastro.com's existing commerce (Squarespace with built-in Square
Payments) is built to gate Squarespace's own pages — there's no supported
way to point it at a separate app running elsewhere. Stripe Billing is the
standard way to add subscription gating to an app like this one, and runs
completely independently of Squarespace/Square — your existing site's
checkout is untouched either way.

**What's already built:**
- `app/auth.py` — verifies a Supabase-issued login token (JWT) and checks
  a local subscriber table for an active subscription. A FastAPI
  dependency (`require_active_subscription`) is already attached to every
  meaningful endpoint (`/api/chart`, `/api/kp-beta`, `/api/transit`,
  `/api/geocode`, `/api/chat`, `/api/chat/stream`) — today it's a no-op
  (open access, same as now); once enabled it blocks anyone without an
  active subscription.
- `app/billing.py` — a `/api/billing/webhook` endpoint that Stripe calls
  on checkout/subscription events, keeping a small local table (`backend/
  subscribers.db`, created automatically) of who has an active
  subscription.
- `GET /api/auth-config` — tells the frontend whether sign-in is turned on
  (so it knows whether to show an account/sign-in screen once that's
  built — see below).

**What's still needed from you before this can actually work:**
1. Create a Supabase project (free tier is enough) at supabase.com. Under
   Authentication settings, turn on email+password sign-up and TOTP MFA
   (authenticator-app codes).
2. Create a Stripe account, add a subscription Product/Price for this app,
   and add a webhook endpoint pointing at
   `https://<wherever-this-is-hosted>/api/billing/webhook` for the
   `customer.subscription.*` and `checkout.session.completed` events.
3. In `backend/.env`, set `AUTH_ENABLED=true` and fill in `SUPABASE_URL`,
   `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET` (from Supabase's API
   settings), and `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (from
   Stripe's dashboard). `.env.example` has the exact field names and where
   to find each value.
4. Tell me once that's done and I'll build the actual sign-up/sign-in/MFA
   screen in the frontend, wired to your real Supabase project — I can't
   build and test that screen honestly against a project that doesn't
   exist yet, so it isn't in this round.

I can't create these accounts or enter billing details on your behalf —
that part is yours to do (a password manager or your own browser is the
right place for that, not something to hand to an AI assistant).

## Running it locally

```powershell
cd ORBINOVASTRO\ai_app\backend
conda activate astroexcel        # or any Python 3.11+ env
pip install -r requirements.txt
copy .env.example .env
notepad .env                     # add your OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000 in a browser.

- `/api/chart`, `/api/kp-beta`, `/api/transit`, and `/api/geocode` work
  without any OpenAI key (pure math/lookup, no LLM call).
- `/api/chat` and `/api/chat/stream` need `OPENAI_API_KEY` set in `.env`.
- All of the above are open access today (`AUTH_ENABLED=false`) — see
  "User accounts, MFA & subscription gating" above to change that.

Run the tests from the `ai_app/` folder:

```powershell
cd ORBINOVASTRO\ai_app
pip install -r backend\requirements.txt
python -m pytest tests\ -v
```

Expect `28 passed`.

## Folder layout

```
ai_app/
  README.md                    (this file)
  backend/
    requirements.txt
    .env.example
    subscribers.db              (auto-created once AUTH_ENABLED=true; not in git)
    app/
      main.py                  FastAPI app + routes
      models.py                pydantic request/response shapes
      auth.py                  Supabase JWT verification + subscription gate (off by default)
      billing.py               Stripe webhook -> subscriber table
      engine/
        ephemeris.py           Swiss Ephemeris wrapper (validated mechanical layer)
        chart.py               orchestration: request fields -> NatalChart -> dict
        kp.py                  BETA: Sub Lord + 4-level house significators
        geocode.py             place name -> lat/lon/UTC offset
        transit.py             current/given-moment positions vs natal chart
      agent/
        chat.py                OpenAI tool-calling chat loop (non-streaming + streaming, 4 tools)
  frontend/
    index.html                 menu-driven UI: Chart (with wheel) / Transit / KP (beta) / Chat
  tests/
    test_ephemeris.py
    test_kp_beta.py
    test_geocode.py
    test_transit.py
    test_auth.py
```

## How this maps to the roadmap

This covers **Phase 1** (mechanical layer, validated) and **Phase 2**
(backend API + frontend — now menu-driven with a chart wheel, transit, and
geocoding, plus a first labeled-beta pass at KP significators) from
`ai-agent-app-roadmap.md`. Auth/billing scaffolding is early groundwork for
**Phase 4**. Next steps from there:

1. Get the client's read on the KP-beta output, and on which specific
   "transit and other tables" from the workbook matter most for the next
   round (the current transit feature is a first cut: positions + natal
   house + simple conjunction only).
2. Resolve the still-open mechanical-layer questions (`Devarajayan`'s real
   value, which house-cusp convention is live).
3. Port and validate the proprietary layer (`ConnSummaryCore`'s scoring,
   `Score_Additive`'s weighting) against real Excel output.
4. Create the Supabase + Stripe accounts (see above) so sign-up/MFA/
   subscription gating can actually be turned on and its sign-in screen
   built.
5. Phase 4 deployment to orbinovastro.com — see the roadmap doc's
   "Deployment options" section for the walkthrough.
