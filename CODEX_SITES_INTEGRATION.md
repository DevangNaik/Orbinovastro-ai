# Adding the ORBINOVASTRO AI features to the OpenAI Sites project

**Give this whole document to Codex** as the spec for the page/section it should
build. It describes an existing, already-built, already-tested backend — Codex's
job is to build a **frontend page that calls it**, not to reimplement any of the
astrology math itself.

> **Update (2026-09-24, latest again): the chart wheel was flipped left-right, and every reference chart view needs a richer per-planet table matching the client's own Excel Kundli chart.** The client sent their own Horosoft screenshot and Excel Kundli chart as "the standard practice" reference and pointed out two things:
> 1. **The North Indian chart wheel geometry was mirrored.** House 4 (and everything on "that side") was drawn on the right when it belongs on the left, and vice versa — confirmed against the client's own real chart. **The corrected polygon table is in the "Chart wheel diagram" section below — if Codex already built the wheel, replace the old table with the corrected one exactly, don't just eyeball a fix.** This applies to all four wheels (D1, Bhava Chalit, D9, Cuspal) at once, since they share one shared geometry table.
> 2. **Add Degree, Nakshatra(Pada), Conjunction degrees, and a "meaning of position" sentence to the chart views, plus a distinct color per planet and an element-tinted house box** — matching the level of detail and visual polish in the client's own Excel chart, "adopted for client presentation" (the client's own words) rather than copied verbatim (their Excel is a working tool, not client-facing design). `/api/chart`'s `planets` array gained three new fields for this (`meaning`, `conjunctions`, `nature`) — see the new "Planet color scheme and the enriched Planet Details Table" section below for the full spec, table layout, and column mapping. **Apply this to all four reference chart views, not only D1** — the client explicitly asked for this.
>
> No other endpoint's request/response shape changed in this update.

> **Update (2026-09-24, latest): each Preview placement now carries a new
> `flags` array -- Retrograde / Combust / Exalted / Debilitated / Own Sign /
> Vargottama -- and the client also caught (and this fixes) a real bug
> where Rahu was never shown as retrograde even though it always should be.
> No new endpoint -- same `/api/teaser` response shape you already render,
> with one addition:**
> - Every entry in `placements` (Ascendant + all 9 planets) now has a
>   `flags: string[]` field: zero or more of `"Retrograde"`, `"Combust"`,
>   `"Exalted"`, `"Debilitated"`, `"Own Sign"`, `"Vargottama"`. It can be an
>   empty array -- most placements won't have any of these. See the updated
>   example under `/api/teaser` below (Mars: `["Retrograde", "Own Sign"]`).
> - **These flags are already woven into the `narrative` prose for that
>   placement** (e.g. "This also happens to be one of Mars's own signs..."),
>   so nothing breaks if you only ever render `narrative` and ignore
>   `flags` entirely. The `flags` array exists so you can additionally show
>   a small badge/chip next to the placement label, consistent with the
>   existing "Retrograde and beta markers should be visually distinct"
>   guidance in the Visual design pass section below -- e.g. next to
>   "**Mars retrograde in Aries · House 3**", add small chips reading
>   "Own Sign" for each other flag present. Not required if it adds real
>   complexity; the narrative text alone already communicates it.
> - **Bug fix, no frontend change needed:** Rahu will now correctly show
>   `"retrograde": true` (and `"Retrograde"` in `flags`) like Ketu always
>   has -- previously a backend bug always reported Rahu as non-retrograde
>   regardless of its actual computed position. If your Chart/Transit/KP
>   tabs render `retrograde`, they'll pick this fix up automatically, no
>   code change required there either.
> - These flags use standard classical Vedic rules (documented in the
>   `disclaimer` field, updated -- see below), not yet the client's own
>   exact proprietary Kundli-worksheet formulas for these same markers
>   (that logic lives in unported Excel and is a separate, larger future
>   task). Vargottama additionally inherits the existing D9/Navamsa "beta"
>   caveat. No wording change needed on your end beyond rendering the
>   updated `disclaimer` text as you already do.
> - Also as of the same date: the **paid Overview Report PDF** (downloaded
>   via the `/api/overview-report` button, see item 3 below) now includes a
>   "Transit Basis" row at the top of its Transit Information table,
>   spelling out in plain language whether the shown transit is the current
>   moment or a custom date/time, and which location "Local" refers to.
>   This is entirely inside the generated PDF -- **no frontend change needed
>   for this one**, since your page doesn't render that table itself, it
>   just triggers the download.

> **Update (2026-09-27): the Preview's house numbers now use a different
> convention than before -- cuspal (Bhava Chalit / Nirayana bhava), not
> whole-sign -- and this must be visibly indicated to the visitor.** No new
> endpoint or request shape -- `/api/teaser`'s response fields are the same
> ones you already render. What changed server-side: each placement's
> `house` is now computed the same way as `/api/chart`'s own `house` field
> (cuspal/Bhava Chalit, the KP convention), instead of the whole-sign
> counting it used before (which matched `/api/chart`'s `rasi_house`
> instead). `sign` is unaffected -- it was always, and still is, the D1/Rasi
> sign. **Practical effect: the Preview's house numbers will now match the
> Chart tab's Bhava Chalit view, not its D1 view, and for some charts every
> placement can shift by a full house at once** (this happens when the
> Ascendant itself sits close to a sign boundary -- it's expected, not a
> bug). The client explicitly asked that this be indicated to visitors, not
> left implicit, so:
> - Add one short, static line directly under the "Planetary Placements"
>   section heading (see item 2 below) -- this doesn't come from the API,
>   it's fixed copy: **"Sign = your D1 (Rasi) birth chart. House = cuspal
>   (Bhava Chalit / Nirayana bhava)."**
> - The `disclaimer` field's wording has also been updated to spell this out
>   in full (see the new example under `/api/teaser` below) -- keep
>   rendering it as before, no layout change needed there.
> If you already built the Preview against the earlier `/api/teaser`
> contract, the only change needed is adding that one static line under the
> table heading -- everything else (field names, table structure) is
> unchanged.

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

> **Update (2026-09-24, later still still): correction -- there should be
> ONE Transit input on this whole page, not two.** The previous version of
> this update told you to build a dedicated Transit sub-section (with its
> own "Use birth location" toggle) specifically for the "Get My Full
> Report" flow. That was a mistake on this document's part and it produced
> exactly the confusion the client then reported: the page already HAS a
> Transit tab (item 5 below, the one that calls `/api/transit`) -- adding a
> second, separate transit control inside the Preview/Report flow duplicated
> it and desynced from it. **If you already built that second control per
> the earlier instruction, remove it.** The corrected, final rule: "Get My
> Full Report" reuses the exact date/time currently held by the page's ONE
> existing Transit tab -- it does not get its own date/time input at all.
> The transit location is always the birth chart's own location, full stop
> -- never ask the visitor for a separate transit location anywhere on this
> page. See the rewritten item 3 under "What to build" and the rewritten
> `/api/overview-report` request section below for the specifics.

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
     **Directly under this section's heading, add one short static caption
     line (fixed copy, not from the API): "Sign = your D1 (Rasi) birth
     chart. House = cuspal (Bhava Chalit / Nirayana bhava)."** -- small,
     unobtrusive text (similar weight to a caption or the beta chips
     elsewhere on the page), but visible without scrolling to the bottom
     disclaimer. This exists because `house` is now computed on a
     different convention than `sign` (see the update banner at the top of
     this doc), and the client wants that distinction visible, not just
     buried in the disclaimer paragraph.
     **The client has approved a specific reference layout for this
     section -- a real two-column table, not cards or a bulleted list:**
     - Column 1 header: "Placement". Column 2 header: "What it may signify
       for you".
     - One row per entry. Column 1 is a short, bold label built from
       `name`, `sign`, and `house` (e.g. "**Sun in Virgo · House 9**" --
       on `retrograde: true` add "retrograde" into the label itself, e.g.
       "**Mars retrograde in Aries · House 4**", rather than a separate
       badge). Column 2 is the `narrative` text, rendered as normal body
       text (no need to bold anything inside it -- the narrative's own
       wording already calls out the notable bits, like a debilitated or
       own-sign placement).
     - A thin row divider between entries, generous row padding (the
       reference the client approved uses noticeably more vertical
       breathing room than a dense data table -- this is meant to read
       calmly, not like a spreadsheet).
     - A small copy-to-clipboard icon in the table's top-right corner
       (copies the whole placements section as text) is a nice touch the
       client specifically liked, but skip it if it adds real complexity --
       it's optional polish, not a requirement.
     - Use the site's own color palette and type here -- NOT a plain
       black-background/white-text theme. The client's reference example
       happened to be rendered on black, but their explicit note was "of
       course with color pattern matching with site" -- match
       orbinovastro.com's existing colors, fonts, and card/table styling.
   - `synthesis` -- a closing structural paragraph (kendra/trikona house
     counts, and which houses carry extra weight in this specific chart).
     Lead with a short bold label the client's approved reference uses --
     "**The larger pattern:**" -- followed by the paragraph as body text.
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

   **Transit for this report — reuse the page's ONE existing Transit tab,
   do not build a second transit input anywhere else** (this corrects a real
   bug from an earlier build: a second, separate transit control got added
   to the Preview/Report flow, which desynced from the real Transit tab and
   produced a report that ignored what the visitor had actually set):
   - The page already has exactly one Transit input — the date/time picker
     in the Transit tab (item 5 below), used for `/api/transit`. "Get My
     Full Report" reuses that SAME state. It does not get its own date/time
     field, its own picker, or any location control of its own.
   - If the Transit tab's date/time is still blank, that means "right now"
     — omit `year`/`month`/`day`/`hour`/`minute` from the `transit` object
     in the `/api/overview-report` request entirely (same meaning it
     already has for `/api/transit`). If the visitor has set a specific
     date/time in the Transit tab, send that exact value.
   - **Transit location is always the birth chart's own location — never
     ask the visitor for a separate transit location anywhere on this
     page.** Simply omit `transit.latitude`/`longitude`/`place` from the
     request always; the backend defaults them to the birth details
     automatically. There is nothing to toggle and nothing to sync — this
     is just always true.
   - Net effect: the only thing that varies in the `transit` object across
     requests is the date/time, taken directly from the Transit tab's
     current state; everything else about "transit" for this report is
     simply "the birth chart's own location."
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

**UPDATE (2026-09-24, newest) — the small in-box numeral was the wrong
number, and the sign-abbreviation text should come out entirely.** Two
pieces of client feedback, read together:

1. *"The Rashi Number are not correct. this should be Cap as 10 not Cap
   1."* -- the small muted numeral currently drawn near each box's
   center-ward vertex (added in the "later still again" UPDATE box
   below, point 2) is the box's own **house-position number** (fixed by
   geometry -- box position 1 is always the top kite, no matter the
   chart). That's a different thing from what the client means by
   "Rashi Number": the sign's own **fixed zodiacal index**, the same for
   every chart regardless of ascendant -- Aries=1, Taurus=2, Gemini=3,
   Cancer=4, Leo=5, Virgo=6, Libra=7, Scorpio=8, Sagittarius=9,
   Capricorn=10, Aquarius=11, Pisces=12. For a Capricorn-ascendant chart,
   Capricorn sits in the house-1 (top) box -- the old numeral correctly
   showed "1" for that box's *house position*, but the client wants "10"
   there, because Capricorn is universally the 10th sign. **Change the
   numeral to this fixed Rashi index of whichever sign occupies that
   box**, not the house-position number:
   ```js
   const RASHI = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                  "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"];
   const rashiNumber = (sign) => RASHI.indexOf(sign) + 1; // 1-based, fixed, never depends on ascendant
   ```
   Apply this per box, using whichever `sign` that box already resolves
   to under "Which sign goes in which box, per chart type" below (D1's
   `wholeSignHouseList` result, Bhava Chalit/Cuspal's `houses[n-1].sign`,
   D9's navamsa sign for that box) -- the box-to-sign resolution logic
   itself is unchanged, only what number gets printed once you know the
   sign changes.
2. *"Make it look like this... if you want you can write 1-12 Rashi
   number below in text so all Cap Aqu etc will go away from chart"* --
   the client attached a reference wheel (Ra(R)/Mon/Ma-style compact
   planet labels, small numbers 1-12 clustered at the diamond's center,
   **no sign-abbreviation text anywhere** in any box) and asked for that
   treatment. **This reverses point 4 in the "later still again" UPDATE
   box below** ("Do NOT drop the sign abbreviation line") -- that
   guidance is now superseded: **drop the sign-abbreviation text (e.g.
   "Cap", "Aqu") from inside every box entirely**, for all four chart
   views. The box now shows only: the fixed Rashi number near the
   center-ward vertex (per point 1 above) and the planet label(s), if
   any. Optionally add one small static legend below each wheel (or once
   for the whole page, since it never changes) spelling out the mapping,
   e.g. `"1 Aries · 2 Taurus · 3 Gemini · 4 Cancer · 5 Leo · 6 Virgo · 7
   Libra · 8 Scorpio · 9 Sagittarius · 10 Capricorn · 11 Aquarius · 12
   Pisces"` -- small, muted, one line, so a visitor can still look up
   what a number means without it cluttering every box.
   This is a text-labels-only change -- it does **not** touch the
   Fire/Earth/Air/Water element-tinted box backgrounds, the per-planet
   accent colors, the compact `Code(R) DD°MM'` planet-label format, or
   the box polygon geometry, all of which stay exactly as already
   specified; only the sign-abbreviation text line and the numeral's
   meaning change.
3. This applies to **all four chart views** (D1, Bhava Chalit, D9,
   Cuspal) -- same as every other wheel-formatting rule in this section,
   they all share one rendering path.

**UPDATE (2026-09-24, newest again) — full, authoritative planet-label
content/placement/order/color rules, from the client's own detailed
spec.** This consolidates and, in two places, corrects earlier pieces of
this section (marked below) -- it is the source of truth for what a
wheel's planet label says and looks like. Build every piece of the label
from calculated `/api/chart` fields; never parse it back out of an
already-formatted string.

1. **Placement.** Unchanged from above: the box is chosen by D1 sign
   placement (`wholeSignHouseList`/`rasi_house` for D1, the equivalent
   per-chart-type mapping for the other three views). The small numeral
   printed in that box is the sign's fixed **Rashi number** (point 1 of
   the UPDATE box just above) -- never a house number. House number is a
   separate, derived fact (from the Ascendant plus sign placement),
   already exposed via `house`/`rasi_house` and used elsewhere (the
   Planet Details Table's Sign/House line) -- it is not printed as the
   box's numeral.
2. **Main label line**:
   ```
   {PlanetAbbrev}{" (R)" if retrograde} {DegreeInSign}°{Minutes}′ {NakshatraAbbrev}{Pada} {ConditionFlags}
   ```
   Example: `Ma(R) 12°13′ Asw4 D↓` (Mars, retrograde, 12°13′ into its
   sign, Ashwini nakshatra pada 4, one condition flag active). Another:
   `Ju 9°07′ U.A4 D↓` means Jupiter, 9°07′ into Capricorn, Uttara Ashadha
   pada 4, debilitated -- the label conveys position and condition only;
   that Capricorn is the 1st house (because this chart's Ascendant is
   Capricorn) is a separate fact, shown via the Rashi number "10" on the
   box plus the Planet Details Table's own House column, not squeezed
   into this string.
   - `PlanetAbbrev` = the `code` field, or `Asc` for the Ascendant (point 8).
   - Degree = `degree_in_sign` converted to whole degrees + minutes,
     rounded consistently to the nearest minute (carry a rollover to the
     next whole degree if rounding produces 60 minutes).
   - Nakshatra abbreviation + pada, no space between them (`Rev4`,
     `Swa4`, `Chi1`) -- see the abbreviation table, point 4.
   - Condition flags (point 5) appended last, only when true.
3. **Retrograde shown exactly once.** `(R)` right after the planet code
   is the ONLY retrograde marker in this label. ~~The compact `R*` flag
   code~~ **Client-caught bug, fixed here: do NOT also append `R*` to
   this label's trailing condition flags** -- the engine's `"Retrograde"`
   flag (compact code `R*`) means exactly the same thing as `(R)`, so a
   label showing both (as the live wheel currently does: `Ma(R) 12°13'
   Asw4 R*`) displays retrograde twice. Drop `R*` specifically from the
   wheel label; the other four compact codes (`C^`/`E↑`/`D↓`/`V▫`) are
   unaffected. (The Planet Details Table's own Flags line and legend are
   a separate context with no inline `(R)` of their own to duplicate
   against -- `R*` stays there unchanged.)
4. **Nakshatra abbreviations.** No 3-letter table existed in this doc
   before now; the client's own reference screenshot fixes 10 of the 27:
   `Ashwini→Asw, Ardra→Ard, Chitra→Chi, Hasta→Has, Swati→Swa,
   Anuradha→Anu, Mula→Moo, Uttara Ashadha→U.A, Shravana→Sra,
   Revati→Rev`. The remaining 17 are **NOT yet confirmed against any
   client source** -- proposed as a deterministic extension of the same
   visible pattern (first 3 letters of the common spelling; the six
   Purva/Uttara-prefixed pairs instead use `P.`/`U.` + the first letter
   of the second word, matching `U.A` above): `Bharani→Bha,
   Krittika→Kri, Rohini→Roh, Mrigashira→Mrg, Punarvasu→Pun, Pushya→Pus,
   Ashlesha→Asl, Magha→Mag, Purva Phalguni→P.P, Uttara Phalguni→U.P,
   Vishakha→Vis, Jyeshtha→Jye, Purva Ashadha→P.A, Dhanishta→Dha,
   Shatabhisha→Sha, Purva Bhadrapada→P.B, Uttara Bhadrapada→U.B`.
   **BETA for these 17 specifically** -- flag to the client for
   confirmation against whatever tool produced their reference
   screenshot; swap in their exact values if theirs differ, same
   discipline as this engagement's other not-yet-client-confirmed
   conventions (e.g. `functional_nature`).
5. **Condition flags** (`D↓` debilitated, `E↑` exalted, `C^` combust,
   `V▫` vargottama) -- straight from the `flags` array (minus
   `R*`/Retrograde, point 3), shown only when that specific flag is
   present for that entry. Never inferred from the label's color (point
   6) -- two fully independent pieces of information.
6. **Label color = the planet's own fixed classical ELEMENT, not Nature,
   not planet identity.** This point has now been corrected TWICE by the
   client in quick succession, in this order -- kept visible so the
   history is legible, not because either intermediate version should be
   built:
   - ~~Each planet's (and the Ascendant's) in-box label renders as its
     own chip with background = that body's own accent color~~
     **SUPERSEDED #1** (per-planet-identity color -- see the strikethrough
     note at the "Planet color scheme" section below).
   - ~~Color the wheel label from the entry's `nature` field
     (`"Malefic"`/`"Benefic"`), reusing the Nature badge's existing
     colors~~ **SUPERSEDED #2** -- the client's very next message replaced
     this with element-based coloring, below. If Nature-based coloring
     was already built from an earlier version of this doc, replace it.

   **Current, final rule:** color the wheel label from two NEW fields
   `/api/chart` now returns on every planet, the Ascendant, and the outer
   planets -- `planet_element` and `rashi_element` -- which are
   deliberately two separate facts, never to be confused:
   - `planet_element` -- the planet's own FIXED classical Pancha Tattva
     element, the same for that planet on every chart, regardless of
     which sign it's currently in: `Su`/`Ma` → Fire, `Mo`/`Ve` → Water,
     `Me` → Earth, `Sa` → Air, `Ju` → Ether/Space. `null` for
     `Ra`/`Ke`/`Ur`/`Ne`/`Pl` and for the Ascendant -- no classical
     rulership exists for these five bodies (nodes and outer planets),
     and none for the Ascendant (it isn't a planet); render these with
     one neutral/muted label color, not a guessed element.
   - `rashi_element` -- the element of whichever SIGN that entry
     currently occupies (`Aries`/`Leo`/`Sagittarius` → Fire,
     `Taurus`/`Virgo`/`Capricorn` → Earth, `Gemini`/`Libra`/`Aquarius` →
     Air, `Cancer`/`Scorpio`/`Pisces` → Water) -- always present, even
     for the Ascendant and the outer planets, since it only depends on
     the sign, not on planetary rulership.
   - **Use `planet_element` for the label's color. Never `rashi_element`.**
     A planet's label color must NOT change depending on which sign it's
     transiting through -- e.g. Mars in Cancer keeps its Fire-colored
     label even though Cancer's own `rashi_element` is Water; this
     mismatch is intentional and meaningful (not a bug to "fix" into
     agreement). Real example from this engagement's own reference
     chart: Sun sits in Virgo (`rashi_element: "Earth"`) but still has
     `planet_element: "Fire"`, and its label must render Fire's color.
   - Adopt 5 distinct colors for Fire/Water/Earth/Air/Ether, plus one
     neutral/muted color for `null` (nodes, outer planets, Ascendant) --
     from orbinovastro.com's own palette, consistent everywhere a planet
     label appears in the wheel.
   - **`element_match`** (optional): if any part of the UI wants to
     describe the relationship between a planet's own element and the
     sign it's currently in (e.g. a tooltip or narrative line), compute
     it client-side as `planet_element === rashi_element` (both
     non-null) -- this is NOT a field `/api/chart` returns; derive it
     from the two fields above if and when the UI needs it, and never
     use it (or `rashi_element`) to pick the label's color.
   - Condition flags (point 5) and dignity/retrograde/combust/vargottama
     stay completely independent of this element color -- never let one
     override or imply the other.
   - **Scope note:** this element-based rule is specifically for the
     wheel's planet-label color. The separate "Planet color scheme"
     section below (distinct per-planet hues, used for planet code/name
     coloring in the Planet Details Table and the Preview placements
     table) still stands as its own, different rule unless the client
     says otherwise -- flag it back to the client if they intended
     element-based coloring to replace that too, rather than assuming so
     silently.
7. **Ordering when a box holds more than one occupant.** Stack each
   occupant on its own line (already specified), ordered by the fixed
   classical sequence -- Ascendant first if present, then `Su, Mo, Ma,
   Me, Ju, Ve, Sa, Ra, Ke, Ur, Ne, Pl`, skipping whichever aren't present
   in that box -- **not** sorted by degree. Confirmed against the
   client's own reference chart: house 6 there shows `Su → Ur → Pl` (not
   degree order -- Pl's 11°22′ is actually the lowest of the three) and
   house 3 shows `Sa → Ke`, both matching this fixed sequence, not
   degree order. Keep every stacked label fully inside the box, no
   overlap (already specified above).
8. **Ascendant.** `Asc {DegreeInSign}°{Minutes}′ {NakshatraAbbrev}{Pada}`
   -- a real position, nakshatra, and pada (from `/api/chart`'s
   `ascendant` object), but never a retrograde `(R)` or a combust/dignity
   flag (it isn't a planet). Use the neutral color from point 6.
9. **Uranus/Neptune/Pluto.** Same positional label format as any planet
   -- but mark them "supplementary" in the wheel's legend (e.g. a
   footnote: "Ur/Ne/Pl: position shown for reference; no classical
   Nature, dignity, KP rulership, or graha-drishti aspects are assigned
   to them"), always the neutral color from point 6 (`planet_element` is
   `null` for these three, same as it is for Nature), and never draw an
   aspect line to/from them through this label -- consistent with the
   engine, which already returns `nature: ""` and empty
   `aspects`/`aspected_by` for these three.
10. **Legend, updated to cover all of the above** -- one compact key
    near each wheel (or once for the page): (a) the `planet_element`
    color mapping from point 6 (five swatches -- Fire/Water/Earth/Air/
    Ether -- plus a neutral swatch for `null`, e.g. labeled "N/A"), (b)
    the four remaining condition-flag codes (`C^`/`E↑`/`D↓`/`V▫` -- `R*`
    excluded per point 3), and (c) the Rashi-number-to-sign mapping
    (previous UPDATE box's point 2), if that legend line was added.
    House meaning and aspect interpretation belong in the Planet Details
    Table's Meaning/Aspects columns (already specified) -- never
    squeezed into this label.

Applies to all four chart views (D1, Bhava Chalit, D9, Cuspal) -- same
shared rendering path as the rest of this section.

**CORRECTED 2026-09-24 (latest) — the polygon table below was mirrored left-right; if Codex already built the wheel from the old table, replace it with this corrected one.** The client sent a real Horosoft screenshot and their own Excel Kundli chart as the standard-practice reference and pointed out the live wheel was flipped — concretely, house 4 (and everything on "that side") was drawn on the right when it belongs on the left (and vice versa for the other side). Root cause, confirmed by re-deriving the geometry from the client's own reference: the original table numbered the 12 boxes going **clockwise** from the top box (1→2 upper-right→3→4 right kite→...→10 left kite→...), but the correct, standard North Indian convention numbers them going **counter-clockwise** from the top (1→2 upper-**left**→3→4 **left** kite→...→10 **right** kite→...). This was independently confirmed against the client's own real Excel chart: house 4 (Aries, containing Mars for the reference birth chart) sits in the **left** kite there, and house 10 (Libra, containing Mercury) sits in the **right** kite — the opposite of what the old table drew. **The fix is a simple mirror**: every polygon/label coordinate below has its x mirrored (`x → 400 − x`) from the original table, with the same house numbers — nothing else about the geometry, the box shapes, or the sign-placement logic changes.

This is the same North Indian diamond-chart algorithm already built, tested,
and in production in this engagement's standalone reference app
(`frontend/index.html`, also corrected this round) — copy the geometry and
logic exactly rather than inventing a new layout, so all four planet-bearing
wheels (D1, Bhava Chalit, D9, Cuspal) stay visually and structurally
consistent with each other and with the standalone app. **This fix applies
to all four chart views** — they all draw from this one shared polygon
table, so correcting it here corrects every one of them at once; there is
no separate per-chart-type geometry to fix.

**Geometry** — a 400×400 SVG viewBox. The diamond is an outer square plus
both diagonals plus the diamond connecting the four side-midpoints. Houses
1/4/7/10 (the "kendra" kite shapes at top/right/bottom/left) sit at the four
side-midpoints; the other 8 houses are the corner triangles the diagonals cut
each corner into. House 1 (the ascendant's box) is always the top kite,
regardless of which sign occupies it — this is what makes it "North Indian"
style rather than a fixed-sign layout. House numbers increase **counter-clockwise**
from the top box — 2 and 3 are on the upper-left, 4 is the left kite, 5 and 6
are lower-left, 7 is the bottom kite, 8 and 9 are lower-right, 10 is the
right kite, 11 and 12 are upper-right. Exact polygon points and label-center
coordinates for houses 1–12 (as SVG `<polygon points="...">` and text
x/y — **corrected, mirrored table**):

```
1:  polygon "200,0 300,100 200,200 100,100"   label (200, 95)
2:  polygon "0,0 200,0 100,100"               label (100, 38)
3:  polygon "0,0 0,200 100,100"               label (42, 100)
4:  polygon "0,200 100,100 200,200 100,300"   label (95, 200)
5:  polygon "0,200 0,400 100,300"             label (42, 300)
6:  polygon "0,400 200,400 100,300"           label (100, 362)
7:  polygon "200,400 100,300 200,200 300,300" label (200, 305)
8:  polygon "200,400 400,400 300,300"         label (300, 362)
9:  polygon "400,400 400,200 300,300"         label (358, 300)
10: polygon "400,200 300,300 200,200 300,100" label (305, 200)
11: polygon "400,200 400,0 300,100"           label (358, 100)
12: polygon "400,0 200,0 300,100"             label (300, 38)
```

Draw all 12 polygons (house 1's box gets a subtle fill to mark it as the
ascendant; the rest transparent), then an outer 2px border rect, then a small
"ASC ↑" label at the top-center (200, 14). Each house box's text: ~~the sign
abbreviation (first 3 letters) on the first line in the accent color, then~~
**SUPERSEDED (see the "UPDATE (2026-09-24, newest)" box at the top of this
section): no sign-abbreviation text -- start straight with** one line per
occupying planet's 2-letter code (append a small "ᴿ" superscript
or similar retrograde mark if `retrograde` is true) -- this line format itself
is further superseded below by the compact `Code(R) DD°MM'` format anyway.
**Adopt the client's own
per-planet color scheme** (see the new "Planet color and element scheme"
section below) for each planet's code label here too, not just in the data
table underneath — the wheel and the table should read as one consistent
system, the way the client's own Excel chart does (colored planet codes
inside the wheel boxes, the same colors reused in the table beneath it).

**UPDATE (2026-09-24, later still again) — visual reference for the wheel
itself, from a real third-party chart (Horosoft-style "Lagna Chart") the
client sent as a formatting example.** This is a LAYOUT/formatting
reference only — three specific things to adopt from it, and two things
NOT to drop just because this particular example doesn't show them:

1. **Adopt: a compact per-planet in-box label with degree and retrograde
   inline**, e.g. `Ma(R) 12°14'` — planet code, a small `(R)` immediately
   after the code only when `retrograde` is true (not a separate
   superscript mark), then degree°minute′ (convert `degree_in_sign`'s
   decimal degrees to whole degrees + minutes — e.g. `12.319` → `12°19'`),
   in that planet's own accent color. This replaces the plainer "2-letter
   code + superscript ᴿ" format described just above — use this compact
   DMS-with-inline-retrograde format instead.
2. ~~Adopt: a small house-number numeral near each box's inner
   (center-ward) vertex — a subtle gray/muted small number (1–12,
   matching the polygon table's own house numbering above)~~ **SUPERSEDED
   (see the "UPDATE (2026-09-24, newest)" box at the top of this
   section): the number shown there is the sign's fixed Rashi index, not
   the house-position number.** Position stays the same — close to where
   that house's polygon point touches the diamond's center, the same way
   the reference image shows small numbers clustered near the middle of
   the chart.
3. **Adopt: properly centered planet labels within each box.** Stack each
   box's planet label(s) centered both horizontally and vertically
   around that house's label-anchor coordinate from the polygon table
   above, with consistent, even line spacing — don't let labels drift
   toward one edge of the kite/triangle or overlap the box's border,
   which is what "properly centered" is asking to fix versus whatever
   the current build renders. ~~(and the sign abbreviation above them)~~
   **SUPERSEDED — no sign abbreviation to center any more, see the
   "UPDATE (2026-09-24, newest)" box at the top of this section.**
4. ~~Do NOT drop: the sign abbreviation line, or the Fire/Earth/Air/Water
   element-tinted box backgrounds already specified above and in the
   "Planet color scheme" section below. This reference example happens to
   use plain white boxes with no sign label at all — that's simply how
   that third-party tool renders it, not an instruction to remove either
   feature from this build. Both stay exactly as already specified.~~
   **SUPERSEDED (2026-09-24, newest) — the client has now asked for
   exactly that: see the "UPDATE (2026-09-24, newest)" box at the top of
   this section. Drop the sign-abbreviation text; the Fire/Earth/Air/
   Water element-tinted backgrounds are unaffected and stay as
   specified.**
5. ~~Do NOT add Uranus/Neptune/Pluto rows or wheel labels.~~
   **SUPERSEDED (2026-09-24, yet even later still): DO add them now** —
   see the UPDATE box at the top of the "Planet color scheme and the
   enriched Planet Details Table" section below. `/api/chart` now returns
   real position data for all three, so the wheel diagram should draw
   them in their correct house box, same label format as any other
   planet, with their own accent colors.

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
  "20.19°") beneath ~~the sign abbreviation~~ **the box's Rashi number
  (see the "UPDATE (2026-09-24, newest)" box at the top of this section
  — no sign abbreviation text any more)**, since the point of this chart is
  the cusp positions themselves.

## Planet color scheme and the enriched Planet Details Table (updated, 2026-09-24 later still)

**UPDATE (2026-09-24, final on this point) -- the "Nature" badge decision.**
Client's own real Excel "Nature" column was cross-checked against both
fields this engine computes: it matches `functional_nature` exactly for
all 7 classical rasi-ruling planets (Su/Mo/Ma/Me/Ju/Ve/Sa), not the fixed
`nature` field (which disagrees on Sun/Jupiter/Saturn). The client's own
decision on how to render this, verbatim: *"make functional_nature the
primary badge labeled 'Functional Nature', since it matches the Excel
chart. Show fixed nature as a smaller, separately labeled 'Natural
Nature' note. Don't label either one simply 'Nature'; that hides the
distinction."* This **replaces every earlier instruction in this doc**
that said to render a single bare "Nature" badge, or that showed
`functional_nature` as a secondary "Functional: X" tag next to an
unlabeled primary "Nature" badge (see the "SUPERSEDED" notes below where
this applied) -- the rule from here on:

- **Primary badge, labeled "Functional Nature"** -- from the
  `functional_nature` field (`"Malefic"` / `"Benefic"` / `null` → shown
  as a dash for Rahu, Ketu, Uranus, Neptune, Pluto, and the Ascendant).
- **Smaller, separately labeled note, "Natural Nature"** -- from the
  fixed `nature` field (`"Malefic"` / `"Benefic"`, or a dash for the
  Ascendant which has no `nature` key at all, and for Uranus/Neptune/
  Pluto whose `nature` is `""`).
- **Neither is ever labeled just "Nature" alone** -- always the full
  "Functional Nature" / "Natural Nature" label, everywhere this appears
  (the Planet Details Table's third line, any tooltip, any legend).
- **Rahu and Ketu: show exactly what the API returns, with these same
  explicit labels** -- `Functional Nature: —` (it's `null` for both --
  no textbook rule the client's own data confirms exists yet for the
  lunar nodes) and `Natural Nature: Malefic` for both. **Do NOT implement
  any node-specific functional-nature rule** (a "takes the nature of a
  close conjunct planet, else its sign's dispositor" hypothesis was
  floated and fits this one reference chart, but the client explicitly
  asked to hold off implementing it until it can be checked against more
  real charts -- so Rahu/Ketu's Excel-vs-engine mismatch stays
  **openly flagged, not silently patched or guessed at**.)

This is a labeling/priority change only -- both fields were already
correctly computed and returned by `/api/chart` before this UPDATE box;
nothing on the backend changes here.

**UPDATE (2026-09-24, latest):** client feedback on the live "Conj. /
Aspects" cell -- the three stacked lines (`Conj:` / `Aspects:` /
`Aspected by:`) currently always render, showing `"Conj: —"` etc. as
filler even when there's genuinely nothing there. The client's exact
words: *"Do not print if there is no Conj, Aspect or Aspected by its
just filler with no info.. If there is then add that label."* **This
REVERSES the earlier guidance below** (originally: "Dash on any line
with nothing to show, never an omitted line" / "use a plain dash only
where a field is genuinely unavailable... never omit the line
entirely") -- that guidance is now superseded for these three specific
lines only. New rule, for all three lines, on every row (Ascendant,
the 9 classical grahas, and Ur/Ne/Pl alike):

- `conjunctions` empty → omit the "Conj:" line entirely (no line, no
  dash, nothing rendered for it).
- `aspects` empty, missing, or not present on this entry (e.g. the
  Ascendant has no `aspects` key at all) → omit the "Aspects:" line
  entirely.
- `aspected_by` empty → omit the "Aspected by:" line entirely.
- If a row has all three empty (e.g. a natal chart with an isolated
  outer planet, or an Ascendant nobody aspects), the whole cell is
  simply blank/empty for that row -- that's fine, don't substitute a
  single placeholder dash for the whole cell either.
- If a row has at least one of the three populated, show only that
  line (or those lines) with its real label and value -- e.g. a planet
  with an aspect but no conjunction and nothing aspecting it back shows
  just one line: `"Aspects: Mo (7th)"`, nothing else in that cell.

This does NOT change any other dash in the table (Nature/Functional
Nature/Flags dashes for the Ascendant or for Ur/Ne/Pl, the Meaning
column, etc.) -- those still render their existing dash-based
treatment; this fix is scoped only to the three Conj/Aspects/Aspected-by
lines inside the "Conj. / Aspects" cell.

**UPDATE (2026-09-24, yet even later still):** three more changes, all
server-side already, nothing structural for Codex to redesign:

1. **The numbers themselves shifted slightly.** `/api/chart` switched its
   ayanamsa/node convention to match the client's real Excel data exactly
   (previously an unconfirmed stand-in) -- expect every planet's degree to
   move by roughly 5 arcminutes (0.08°) from whatever was live before, and
   Rahu/Ketu specifically by close to a degree. This can occasionally flip
   a planet into a different nakshatra/pada or house near a boundary. No
   frontend change needed -- just don't be alarmed if a QA pass shows
   slightly different numbers than an earlier screenshot; the new ones are
   the correct ones now.
2. **New field: `functional_nature`.** A SEPARATE Benefic/Malefic
   classification from `nature` -- chart-specific (depends on which
   houses a planet rules from the CURRENT ascendant, not a fixed
   per-planet fact), labeled BETA. ~~Render it as a second small badge
   next to the existing Nature badge... e.g. `Malefic · Functional:
   Benefic · Retrograde`~~ **SUPERSEDED -- see the "UPDATE (2026-09-24,
   final on this point)" box at the top of this section: `functional_nature`
   is now the PRIMARY badge, labeled "Functional Nature"; `nature` is the
   smaller secondary note, labeled "Natural Nature" -- neither is ever
   labeled bare "Nature".** `null` for Rahu/Ketu and for Uranus/Neptune/
   Pluto (see point 3) -- shown as `Functional Nature: —`, not a missing
   badge.
3. **Uranus, Neptune, and Pluto now appear as three more rows.** The
   earlier guidance below saying not to add them is superseded -- ignore
   point 6 and the color-scheme note about them further down, both left
   in place but now out of date on this one point rather than rewritten
   line by line. They get real `degree_in_sign`/`nakshatra`/`pada`/
   `meaning`/`flags`/`house`/`rasi_house` like any planet, but a dash for
   `nature`, `functional_nature`, `conjunctions`, `aspects`, and
   `aspected_by` -- classical Parashari conjunctions/aspects and
   benefic/malefic groupings are graha-only concepts that don't extend to
   the outer planets. Give each of the three its own accent color too,
   same as the classical nine.

**UPDATE (2026-09-24, later still again):** the client used the live
page and refined this feedback further, twice more -- the version below
is the FINAL, exact spec (superseding an earlier two-column draft of this
same box; that draft is gone, replaced by this one, now three columns).
Read this box first, then the full section, which has been rewritten to
match:

1. **Exactly three columns per planet row.** No separate Sign/House,
   Degree, Nakshatra(Pada), Flags, or Nature columns -- those still fold
   into the first cell as before:
   - **"Planet / Position"** -- ~~stack these four lines vertically in one
     cell~~ **SUPERSEDED (2026-09-24, newest -- client asked to compact
     this cell, then refined it once more to drop the redundant 2-letter
     code): exactly THREE tightly-spaced lines, not four**:
     1. ~~`{code} {full name} · {sign} · House {N}` -- e.g. `Ma Mars ·
        Aries · House 4`~~ **SUPERSEDED again (2026-09-24, newest still)
        -- client caught that `{code} {full name}` reads as a duplicate
        (e.g. "Ma Mars", "Su Sun") since the code is just short for the
        name right next to it.** Replace the 2-letter code with a small
        decorative icon instead: `{icon} {full name} · {sign} · House
        {N}` -- e.g. `[Mars icon] Mars · Aries · House 4`.
        ~~Use these standard astrological glyphs (☉ ☽ ♂ ☿ ♃ ♀ ♄ ☊ ☋ ⛢ ♆
        ♇, ↑ for the Ascendant)~~ **SUPERSEDED once more (2026-09-24,
        newest still again) -- client asked for real, high-quality
        images of the actual planets, not text glyphs**, per body:
        - **Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus,
          Neptune, Pluto (10 real bodies):** a small circular icon
          cropped from a real, high-quality, public-domain astronomical
          photo of that body -- source from NASA's own official
          galleries (e.g. NASA Science's planet pages at
          science.nasa.gov, NASA's Solar System Exploration site at
          solarsystem.nasa.gov/planets, or the NASA Image and Video
          Library at images.nasa.gov -- all NASA-produced imagery is
          U.S. government work and public domain). **Download and
          self-host a cropped copy in the site's own image assets rather
          than hotlinking directly to a NASA URL** -- this keeps the
          icon's crop/framing/size consistent and doesn't depend on an
          external host staying up. Crop each to a centered circle on
          the planet's disc (not a mission spacecraft or a wide starfield
          shot), export at a size sharp on retina displays at the actual
          small display size the row uses (e.g. store 128px, display
          ~24-32px), and keep consistent brightness/contrast across the
          whole set so darker images (Uranus, Neptune) don't read as
          washed-out or unrecognizable next to brighter ones (Sun,
          Venus).
        - **Rahu and Ketu are not physical bodies** -- they're the
          Moon's ascending/descending orbital nodes, mathematical points
          with no surface, atmosphere, or photograph to source. Per the
          client's own confirmation, use their standard Hindu/Vedic
          iconographic depiction instead: a small, clean illustration of
          a **snake head** for Rahu and a **snake tail** for Ketu --
          distinct from each other and from any of the 10 real-body
          icons, and NOT a photograph (there's nothing physical to
          photograph).
        - **The Ascendant isn't a planet either** -- per the client's
          confirmation, use a simple rising-arrow icon (`↑` or an
          equivalent small arrow illustration), matching the wheel
          diagram's own existing "ASC ↑" marker.
        - **Visual consistency across all 13 icons:** give the Rahu/Ketu
          symbolic icons and the Ascendant's arrow icon the same circular
          frame/size/subtle-background treatment as the 10 photographic
          icons, so the row of icons reads as one consistent set rather
          than photos next to a completely different, ungrounded icon
          style for 3 of the 13 rows.
        Icons are decorative only -- the full name right next to it
        (`Mars`, not `Ma`) is the actual readable identifier, so nothing
        depends on the icon rendering correctly (e.g. a broken image) for
        the row to still make sense; use `alt="Mars"` (etc.) on each
        image for accessibility and as a fallback if it fails to load.
     2. `{DegreeInSign}° · {Nakshatra}({Pada})` -- e.g. `12.23° ·
        Ashwini(4)`. **Nakshatra(Pada) appears ONLY on this line** --
        don't repeat it anywhere else in this cell (the Meaning column's
        own sentence, in the separate "Meaning" cell, still leads with
        it as before -- that's a different column and stays unchanged).
     3. ~~Nature and flags together, e.g. `Malefic · R* · Own Sign`~~
        **SUPERSEDED (2026-09-24, final on this point) -- see the UPDATE
        box at the top of this section for the full "Functional Nature"
        vs. "Natural Nature" labeling decision.** This line now shows
        THREE things, each explicitly labeled: `Functional Nature: {X}`
        (primary/larger badge) · `Natural Nature: {Y}` (smaller,
        separate note) · flag badges -- e.g. `Functional Nature: Malefic
        · Natural Nature: Benefic · D↓` for Jupiter, or for Rahu:
        `Functional Nature: — · Natural Nature: Malefic · R*`. Neither
        nature value is ever labeled bare "Nature" on its own. Same
        compact flag codes and dash conventions as already specified
        (point 3 below and point 5's Ascendant-specific gaps), all
        styled as small colored badges/pills, not plain text. If the
        line gets visually crowded with all three, wrapping to a second
        sub-line within this same line-3 slot is fine -- the cell's
        overall 3-line count (this counts as one of the three) and
        tightened spacing from the change above still apply.
     Applies to the Ascendant row too, with its own existing dash
     conventions for Nature (it has none) unchanged.
     **Spacing (2026-09-24, newest):** reduce this cell's vertical
     padding from roughly 18px to ~10-12px, use a line-height of about
     1.35-1.45, and reduce the margin between these three lines (and
     between whichever populated lines remain in the "Conj. / Aspects"
     cell, per the omit-when-empty rule above) to 3-4px. Do **not** set
     a fixed row height or truncate/abbreviate the Meaning sentence --
     let it wrap normally, and let each row be only as tall as its
     tallest cell actually needs, and don't let the icon or tightened
     spacing clip any text on mobile. Keep the existing three-column
     layout, colors, badges, dividers, and mobile behavior (cells still
     stack on a phone) otherwise unchanged -- this is a spacing/
     line-count/icon change only, not a redesign. Verify Mars's three
     lines stay readable and that rows with short Meaning sentences no
     longer carry extra empty vertical space.
   - **"Conj. / Aspects"** (new, replacing the old "Details" cell's first
     half) -- stack three lines:
     1. **Conjunctions** -- other planets sharing this one's D1 sign, e.g.
        `"Conj: Sa · 3.3°"`.
     2. **Aspects** -- which planets/points THIS planet's classical
        drishti (whole-sign aspect) falls on, e.g. `"Aspects: Su (9th),
        Mo (7th)"`.
     3. **Aspected by** -- which planets' drishti falls on THIS one, e.g.
        `"Aspected by: Ma (7th)"`.
     ~~Dash on any line with nothing to show, never an omitted line.~~
     **SUPERSEDED (see the "UPDATE (2026-09-24, latest)" box at the top
     of this section): omit the line entirely when empty, don't show a
     dash filler.** Point 5 below (rewritten to match) still tells you
     which lines the Ascendant/outer planets never have data for.
   - **"Meaning"** (new, the old "Details" cell's second half, now its own
     column) -- just the full `meaning` sentence, given enough width to
     show it complete without horizontal clipping -- that was the
     client's original complaint about the pre-compaction layout, still
     the goal here.
   - Keep every existing value and sentence -- this is a re-layout, not a
     content cut. Use a plain dash (`—`) only where a field is genuinely
     unavailable for that row (see point 5 below for the Ascendant's
     specific gaps), never omit the line entirely. **Exception: the three
     Conj/Aspects/Aspected-by lines inside the "Conj. / Aspects" cell --
     see the "UPDATE (2026-09-24, latest)" box at the top of this
     section, which reverses this "never omit" rule for those three
     lines only (omit when empty, don't dash).**
   - On narrow/phone-width screens, let all three cells wrap their text
     rather than truncating or forcing horizontal scroll -- see the
     existing "Mobile-responsive" guidance further down, which already
     applies here.
2. **`/api/chart` now returns `flags` directly, on every planet AND on
   the `ascendant` entry** -- the old guidance below about falling back to
   the plain `retrograde` boolean when a tab doesn't also fetch
   `/api/teaser` no longer applies. Read `flags` straight off whichever
   chart-data response the table is already using; no second API call
   needed for this column any more.
3. **Compact flag notation, with a legend.** Instead of (or in addition
   to, your call) the full flag words, render the client's own compact
   codes: `R*` Retrograde, `C^` Combust, `E↑` Exalted, `D↓` Debilitated,
   `V▫` Vargottama. Put a small legend once per table (or a tooltip on
   hover) spelling out what each code means -- don't make a visitor
   memorize four symbols with no key.
4. **`aspects` / `aspected_by` are new fields, distinct from
   `conjunctions`.** Conjunctions is proximity (same sign). Aspects is a
   completely separate classical concept -- classical Parashari whole-sign
   graha drishti: every planet aspects the 7th sign from its own (full
   opposition, mutual for every planet including Rahu/Ketu), and Mars/
   Jupiter/Saturn each get two additional special aspects (Mars: 4th/8th;
   Jupiter: 5th/9th; Saturn: 3rd/10th). Both `aspects` and `aspected_by`
   are lists of `{code, aspect}` (e.g. `{"code": "Ju", "aspect": "5th"}`)
   -- render as `"Ju (5th)"`, comma-joined if more than one, ~~dash if
   empty~~ **line omitted entirely if empty (see the "UPDATE
   (2026-09-24, latest)" box at the top of this section)**. **This is
   NOT symmetric in general** -- Mars aspecting Venus at
   the 8th doesn't mean Venus aspects Mars back (only the universal 7th
   is always mutual) -- so `aspects` and `aspected_by` can legitimately
   differ for the same planet; render both, don't assume one implies the
   other.
5. **Ascendant row -- exactly which fields are real vs. dashed, now fixed
   server-side for the real ones:** the live page previously showed a
   Degree for the Ascendant but no Nakshatra(Pada) -- that's because
   `/api/chart`'s `ascendant` object never had those fields at all. It now
   has `degree_in_sign`, `nakshatra`, `nakshatra_lord`, `pada`, `meaning`,
   `flags` (only ever `["Vargottama"]` or `[]`), and `aspected_by` (real
   -- planets aspecting the 1st house/Lagna is a standard, uncontroversial
   idea) -- render all of these the same way as any planet's row. It has
   **no** `code`/`retrograde`/`conjunctions`/`nature`/`aspects` -- the
   Ascendant isn't a planet, so it never casts a conjunction or an aspect
   of its own; use a dash for Nature/Flags' nature half (that's in the
   "Planet / Position" cell, unaffected by the latest UPDATE box), but
   for the "Conj. / Aspects" cell specifically **omit the Conjunctions
   and Aspects lines entirely for the Ascendant row** (per the "UPDATE
   (2026-09-24, latest)" box at the top of this section -- it never has
   either, so those two lines just never render for this row). Aspected
   By is real for the Ascendant and DOES render, with its normal
   omit-if-empty treatment like any other row.
6. ~~Uranus / Neptune / Pluto are intentionally still not in this
   table.~~ **SUPERSEDED (see the UPDATE box at the top of this section):
   they're in now.** `/api/chart`'s `planets` array has 12 entries, not 9
   -- the classical 9 grahas plus Ur/Ne/Pl, each with real position data
   but a dash for Nature/Functional Nature/Conjunctions/Aspects/Aspected
   By.
7. **Which field feeds the "Sign · House" line under each chart tab** --
   same house-field rule the wheel diagrams themselves already use, now
   also driving this table: `rasi_house` for D1, `house` for Bhava Chalit,
   `navamsa_house` for D9 (from `/api/navamsa`, not `/api/chart` -- see
   that endpoint's own contract further down), and the matching cusp
   number for Cuspal. `sign` (D1/Rasi) stays the same across D1, Bhava
   Chalit, and Cuspal; D9's sign line instead uses `navamsa_sign`.


The client sent their own Excel Kundli chart as the reference for how much
detail and what visual treatment a chart page should have, and asked that
the site adopt "the best for client presentation" from it, applied to
**every** reference chart view (D1, Bhava Chalit, D9, Cuspal), not only D1.
`/api/chart`'s `planets` array (and, as of this update, its `ascendant`
object too) carries these fields — every one of them is a natal fact (this
planet's actual position/relationships), so the SAME enriched table below
is correct to show underneath all four wheel diagrams; only which
house-box the planet is drawn in changes between the four chart types, not
this table's content.

**Fields on each entry in `/api/chart`'s `planets` array, and now also on
its `ascendant` object** (see the updated `/api/chart` contract further
down for the full shape):
- `degree_in_sign` — e.g. `25.512` (25°30′44″). Show degrees/minutes/seconds
  or decimal degrees, either is fine.
- `nakshatra` / `pada` — show together as `"{nakshatra}({pada})"`,
  e.g. `"Chitra(1)"`, matching the client's own Excel table's exact format.
  **Now present on the Ascendant entry too** — the earlier version of this
  endpoint never computed these for the Ascendant, which is why the live
  Ascendant row showed a Degree but no Nakshatra(Pada); fixed server-side,
  nothing to work around on the frontend any more.
- `meaning` — one ready-to-render sentence, e.g. `"Chitra(1):
  craftsmanship and a natural sense of design or charisma; Virgo adds
  careful and detail-driven."` — put this straight into an "Interpretation"
  / "Meaning" column, no client-side composition needed. Also present on
  the Ascendant entry.
- `flags` — a list of zero or more of `"Retrograde"`, `"Combust"`,
  `"Exalted"`, `"Debilitated"`, `"Own Sign"`, `"Vargottama"` — **read this
  straight from `/api/chart`, no fallback or second API call needed any
  more** (see the "UPDATE" box at the top of this section: this used to
  only exist on `/api/teaser`'s response, and `/api/chart` only had a bare
  `retrograde` boolean — that gap is why, e.g., a debilitated Jupiter
  showed no badge on the chart-wheel views even when the Free Preview tab
  stated it correctly. Fixed server-side; both endpoints now report
  identical flags for the same chart). Render using the compact codes from
  the UPDATE box (`R*`/`C^`/`E↑`/`D↓`/`V▫`) with a legend, on the fourth
  line of the "Planet / Position" cell alongside `nature`. The Ascendant's
  `flags` is only ever `["Vargottama"]` or `[]` — it isn't a planet, so it
  has no Retrograde/Combust/dignity of its own.
- `conjunctions` — a list of `{code, orb_degrees}` for every other planet
  sharing this one's D1 sign (empty if none). Render on the first line of
  the "Conj. / Aspects" cell, e.g. `"Conj: Sa · 3.3°"` for a planet
  listing one conjunction, joined with commas if there's more than one.
  ~~or a dash if the list is empty~~ **SUPERSEDED (UPDATE, 2026-09-24,
  latest): omit the "Conj:" line entirely if the list is empty — no
  line, no dash.** This is exactly the information a visitor needs to
  understand why two planet codes appear stacked in the same house box.
  Not present on the Ascendant entry (it isn't a planet, so it can't be
  "in conjunction" with one in this sense) — omit the line for the
  Ascendant row too, same as any other empty case.
- `aspects` / `aspected_by` — **new**, each a list of `{code, aspect}`
  (e.g. `{"code": "Ju", "aspect": "5th"}`) — classical Parashari whole-sign
  graha drishti, a completely separate concept from `conjunctions` (see
  the UPDATE box's point 4 above for the full rule). Render as the second
  and third lines of the "Conj. / Aspects" cell: `"Aspects: Ju (5th), Mo
  (7th)"` and `"Aspected by: Ma (7th)"`, comma-joined. ~~dash if either
  list is empty~~ **SUPERSEDED (UPDATE, 2026-09-24, latest): omit
  whichever of the two lines is empty, independently — a planet can have
  a real "Aspects:" line and no "Aspected by:" line, or vice versa, so
  check each list separately.** The Ascendant entry has a real
  `aspected_by` (planets can aspect the 1st house/Lagna, omit-if-empty
  like normal) but no `aspects` key at all — it never casts one, so
  that line is always omitted for the Ascendant, not dashed.
- `nature` — `"Malefic"` or `"Benefic"`, or an empty string for Uranus/
  Neptune/Pluto (dash). Not present on the Ascendant entry either — use a
  dash there. **Render as the smaller, secondary "Natural Nature" note
  (see the "UPDATE (2026-09-24, final on this point)" box at the top of
  this section) — never labeled bare "Nature".**
- `functional_nature` — `"Malefic"` / `"Benefic"` / `null`. A SEPARATE,
  chart-specific classification from `nature` -- based on which houses
  this planet RULES from the current ascendant, not a fixed per-planet
  fact, so it can (and does, for real charts) disagree with `nature`.
  `null` for Rahu/Ketu and for Uranus/Neptune/Pluto — dash. **This is now
  the PRIMARY badge, labeled "Functional Nature"** (see the "UPDATE
  (2026-09-24, final on this point)" box at the top of this section —
  it matches the client's real Excel Nature column exactly for the 7
  classical rasi-ruling planets, which `nature` alone does not).
- `planet_element` / `rashi_element` — **new**, both `"Fire"`/`"Water"`/
  `"Earth"`/`"Air"`/(`planet_element` only) `"Ether"`. `planet_element` is
  the planet's own FIXED classical element (Su/Ma=Fire, Mo/Ve=Water,
  Me=Earth, Sa=Air, Ju=Ether) — `null` for Ra/Ke/Ur/Ne/Pl and for the
  Ascendant (no classical rulership; not inferred from their sign).
  `rashi_element` is the element of whichever sign that entry currently
  occupies — always present, including for the Ascendant and the outer
  planets. **These drive the chart-wheel planet label's color** (see the
  "D1 planet-label rules" UPDATE box in the "Chart wheel diagram" section
  above for the full rule and worked examples) — use `planet_element`
  for that, never `rashi_element`; the two can and do disagree for the
  same planet (e.g. this engagement's own reference chart has the Sun in
  Virgo: `"planet_element": "Fire", "rashi_element": "Earth"`), and
  that's intentional, not a bug.

**A single planet-details table, one row per planet** (Ascendant + 12
planets — the classical 9 grahas plus Uranus/Neptune/Pluto — same order
as `/api/chart`'s `planets` array), exactly three
columns — see the UPDATE box at the top of this section for the full,
final spec: **"Planet / Position"** (Planet name; Sign · House for the
current tab; Degree · Nakshatra(Pada); Nature · Flags, each on its own
line), **"Conj. / Aspects"** (Conjunctions; Aspects; Aspected By, each on
its own line), and **"Meaning"** (the full sentence, alone, with room to
breathe). This mirrors the client's own Excel table's underlying column
set (Planet, Position, Degree, Flags, Nature, Nak/Pada, Interpretation)
plus the classical aspect data the client asked to add on top of it,
compacted into three wide, readable cells rather than one cramped
grid, and should sit directly beneath each of the four chart wheels,
using that chart type's own house-numbering convention in the
"Sign · House" line (`rasi_house` for D1, `house` for Bhava Chalit,
`navamsa_house` for D9, cusp number for Cuspal — same house-field rule as
the wheel itself, see above, and see the UPDATE box's point 7).

**UPDATE (2026-09-24, newest) — planet labels inside the wheel should be
colored, bordered background chips, not just colored text.** The client
sent a new reference screenshot of their own live D1 wheel (via a
different rendering tool) showing each planet's in-box label as a small
filled rounded chip -- a light background tint in that planet's own
color with a thin border in a deeper shade of the same color -- stacked
one chip per occupying planet/Ascendant when a box holds more than one
(e.g. house 6 in the reference has three separate stacked chips: Sun,
Uranus, Pluto, each its own color). This is IN ADDITION to the
already-specified per-planet distinct hue and the element-tinted house-box
background below -- both stay exactly as specified; this just changes
*how* each planet's own color is applied to its label (a filled, bordered
chip) rather than plain colored text on a transparent background:
- Each planet's (and the Ascendant's) in-box label renders as its own
  small chip: rounded-corner rectangle, background = that body's accent
  color at a light tint (e.g. ~15-20% opacity, so it stays readable and
  pastel, not a solid saturated fill), border = the same accent color at
  full/deeper saturation, text = the planet's usual label content and
  color (the compact `Code(R) DD°MM'` format already specified above).
- When a box holds more than one occupant, stack their chips vertically
  with a small gap between them (as in the reference) -- each chip keeps
  its own planet's color, they don't merge into one shared chip.
- The house box's own Fire/Earth/Air/Water element-tinted background
  (below) stays underneath these chips, unchanged -- the two are
  independent layers, not a replacement for one another. (The client's
  reference screenshot happens to show plain white boxes behind the
  chips; per the client's own confirmation, that's just how that
  particular tool renders it, not an instruction to drop the element
  tint here -- same treatment as the earlier "third-party reference"
  caveat elsewhere in this doc.)
- Apply the same chip treatment everywhere else a planet's color already
  appears per the "Planet color scheme" bullet below (the Planet Details
  Table, the Preview's placements table) only if it reads well there too
  -- your call on carrying it beyond the wheel itself, since the client's
  ask was specifically about the wheel's in-box labels.

**Planet color scheme.** Adopt one consistent accent color per planet,
reused everywhere that planet's code or name appears on the page (inside
the chart wheel boxes, in this table, in the Preview's placements table,
anywhere else) — this is what makes the client's own Excel chart easy to
scan at a glance, and the live site currently doesn't do it (every planet
renders in the same single accent color today). Pick the twelve colors from
orbinovastro.com's own palette (don't import the Excel screenshot's exact
hex values verbatim — those were tuned for a white Excel grid, not this
site's theme) but keep the same STRUCTURE the client's reference uses:
- A distinct hue per body: Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn,
  Rahu, Ketu, Uranus, Neptune, and Pluto (twelve total now — see the
  UPDATE box at the top of the previous section) each get their own
  color, consistent across every place they're rendered on the page. As
  of the UPDATE box just above, inside the wheel this renders as a
  bordered background chip in that color, not plain colored text.
- A light background tint per house box keyed to that box's sign's
  classical element (fire: Aries/Leo/Sagittarius, earth: Taurus/Virgo/
  Capricorn, air: Gemini/Libra/Aquarius, water: Cancer/Scorpio/Pisces) —
  four subtle, distinct tints, consistent across all twelve boxes and all
  four chart types. This is a purely decorative grouping (which element a
  sign belongs to is standard, universally-agreed classical astrology, not
  proprietary), so a small legend line near the wheel ("Fire · Earth · Air ·
  Water", matching the client's own reference) is a nice touch but not
  required. **Stays in place under the new per-planet chips (see the
  UPDATE box above) -- confirmed with the client, 2026-09-24, this is not
  being dropped.**
- The ascendant's own house box keeps its existing subtle highlight fill
  (already specified above) on top of its element tint, so it still reads
  as visually distinct from the other eleven boxes.

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
- **The client has directly approved a reference layout for this page** --
  a two-column "Placement / What it may signify for you" table, generous
  row spacing, a bold "The larger pattern:" lead-in on the closing
  synthesis paragraph. See the exact spec under "What to build" item 2
  above. Build the Preview tab to match that structure, but in
  orbinovastro.com's own colors and type -- the approved reference
  happened to be shown on a plain black background, which is NOT part of
  what was approved; match the site's real palette.
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
  "ayanamsa_deg": 23.94, "ayanamsa_mode": "Krishnamurti VP291 + confirmed diff",
  "ascendant": {
    "house": 1, "longitude": 294.8, "sign": "Capricorn", "sign_lord": "Sa",
    "degree_in_sign": 24.8, "nakshatra": "Dhanishta", "nakshatra_lord": "Ma", "pada": 3,
    "meaning": "Dhanishta(3): rhythm, recognition, and a pull toward group achievement; Capricorn adds disciplined and patient.",
    "flags": [],
    "aspected_by": [{"code": "Ma", "aspect": "4th"}],
    "planet_element": null, "rashi_element": "Earth"
  },
  "houses": [ {"house": 1, "longitude": 294.8, "sign": "Capricorn", "sign_lord": "Sa"}, "... 12 total, houses 1-12" ],
  "planets": [
    {
      "code": "Su", "name": "Sun", "longitude": 175.5,
      "sign": "Virgo", "sign_lord": "Me", "degree_in_sign": 25.5,
      "nakshatra": "Chitra", "nakshatra_lord": "Ma", "pada": 1,
      "retrograde": false, "house": 8, "rasi_house": 9,
      "meaning": "Chitra(1): craftsmanship and a natural sense of design or charisma; Virgo adds careful and detail-driven.",
      "conjunctions": [{"code": "Me", "orb_degrees": 4.19}],
      "nature": "Benefic",
      "functional_nature": "Malefic",
      "flags": [],
      "aspects": [{"code": "Ju", "aspect": "9th"}],
      "aspected_by": [{"code": "Ma", "aspect": "7th"}],
      "planet_element": "Fire", "rashi_element": "Earth"
    },
    "... note Sun here is a real example of planet_element != rashi_element",
    "... (Fire vs. Earth) -- intentional, see the wheel-label color rule above",
    "... 9 classical grahas total: Su, Mo, Ma, Me, Ju, Ve, Sa, Ra, Ke — a planet in its",
    "... sign of debilitation would instead show e.g. \"flags\": [\"Debilitated\"]",
    {
      "code": "Ur", "name": "Uranus", "longitude": 179.669,
      "sign": "Virgo", "sign_lord": "Me", "degree_in_sign": 29.669,
      "nakshatra": "Chitra", "nakshatra_lord": "Ma", "pada": 2,
      "retrograde": false, "house": 8, "rasi_house": 9,
      "meaning": "Chitra(2): craftsmanship and a natural sense of design or charisma; Virgo adds careful and detail-driven.",
      "conjunctions": [], "nature": "", "functional_nature": null,
      "flags": [], "aspects": [], "aspected_by": [],
      "planet_element": null, "rashi_element": "Earth"
    },
    "... plus Ne, Pl the same shape — real position/meaning/flags, dash",
    "... (empty/null) for nature/functional_nature/conjunctions/aspects/aspected_by,",
    "... planet_element also null (no classical rulership) but rashi_element still real"
  ],
  "disclaimer": "Mechanical-layer chart only: ... (show this to the user)"
}
```
`house` is Bhava Chalit (cuspal/Placidus) house placement. `rasi_house` is
classical D1/Rasi whole-sign house placement. They can legitimately differ
for a planet near a house cusp — see rule 5 above. Use `house` for the Bhava
Chalit view and `rasi_house` for the D1 view.

**`meaning`, `conjunctions`, `nature`, and `flags`** — see the "Planet
color scheme and the enriched Planet Details Table" section above for
exactly how to render these, and note they apply to every chart view
built from this endpoint's data (D1, Bhava Chalit, and — since D9/Cuspal
ultimately describe the same natal planets — these too), not only the D1
tab. **`flags` is new (2026-09-24, later still)** and, along with
`degree_in_sign`/`nakshatra`/`nakshatra_lord`/`pada`/`meaning`, is now also
present on the `ascendant` object (previously it had none of these five
fields at all — that gap is why the live Ascendant row showed a Degree but
no Nakshatra(Pada); see the section above for the full story). The
Ascendant's `flags` never includes Retrograde/Combust/Exalted/
Debilitated/Own Sign — only `"Vargottama"` or empty, since it isn't a
planet. **`aspects`/`aspected_by` are new (2026-09-24, later still
again)** — classical Parashari whole-sign graha drishti, see the same
section above for the full rule and rendering guidance; the Ascendant has
`aspected_by` but no `aspects` key. Rahu and Ketu never appear in each
other's `aspects`/`aspected_by` even though they're always exactly
opposite signs by definition — that's a deliberate carve-out (client
feedback), not a bug.

**`functional_nature` and Uranus/Neptune/Pluto are both new (2026-09-24,
yet even later still)** — see the UPDATE box at the top of the "Planet
color scheme and the enriched Planet Details Table" section above for
the full rendering guidance for both.

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
sign-in, even once auth is turned on elsewhere. A full chart PLACEMENT
analysis -- which sign and house every planet occupies, and what that
means in the practice's own real house/planet language -- but deliberately
stops short of the paid report's proprietary stress/support scoring
(`upgrade_pitch` says so explicitly; see `engine/teaser.py`'s module
docstring on the backend for the full reasoning, if you want it).

**Two different systems, on purpose:** each placement's `sign` is D1/Rasi
(straight zodiacal sign). Each placement's `house` is cuspal (Bhava
Chalit / Nirayana bhava) -- the same convention `/api/chart`'s own `house`
field and this practice's KP significators/paid scoring use. These are
not the same house-numbering convention as `/api/chart`'s `rasi_house` --
see the update banner at the top of this doc, and add the short static
caption line under the Planetary Placements heading per item 2 above.

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
  "blurb": "A Capricorn ascendant carries quiet discipline: composed and ambitious, patient in the way it builds. Paired with a Moon that dissolves easily into feeling, an emotional world that's porous, dreamy, and compassionate.",
  "executive_summary": "Devang Naik's chart opens with three placements that matter more than any other: Capricorn rising, Sun in Virgo, and Moon in Pisces. A Capricorn ascendant carries quiet discipline: composed and ambitious, patient in the way it builds. A Sun in Virgo anchors identity in competence, methodical and detail-oriented, defined by the standard of its own work. Paired with a Moon that dissolves easily into feeling, an emotional world that's porous, dreamy, and compassionate. Together, these three set the tone for everything else. The nine planets and twelve houses that follow are really the same story, told in more detail.",
  "placements": [
    {
      "code": "Asc", "name": "Ascendant", "sign": "Capricorn", "house": 1,
      "retrograde": false, "governs": "Self/Body", "house_domain": "Self/Personality",
      "narrative": "Your Ascendant rises in Capricorn (disciplined and patient). This practice calls it your Self/Body placement: it covers core identity, physical vitality, and the outward expression of will. It also defines your first house, the Self/Personality house, the part of life built around physical body, appearance, temperament, vitality, and overall approach to life. Think of it as the filter everything else in your chart passes through, your natural approach to life and the first impression you make on anyone you meet.",
      "flags": []
    },
    {
      "code": "Ma", "name": "Mars", "sign": "Aries", "house": 3,
      "retrograde": true, "governs": "Energy/Action", "house_domain": "Courage/Siblings",
      "narrative": "Mars sits in Aries for you (bold and quick to act), landing in your third house. This practice calls it the Courage/Siblings house, the part of life connected to younger co-borns, communication skills, mental strength, short travels, and creative drive, and Mars itself represents your Energy/Action: drive, assertiveness, competitiveness, and the capacity to initiate and defend. Keep an eye here: it's where that instinct tends to play out in real life. This also happens to be one of Mars's own signs, a naturally comfortable and stable placement. This one is retrograde in your chart. In Vedic practice, that usually means the energy runs inward first, more reflection and revisiting before it shows up as action, not a weaker placement.",
      "flags": ["Retrograde", "Own Sign"]
    }
    // ... 8 more entries: Su, Mo, Me, Ju, Ve, Sa, Ra, Ke, in that order,
    // same shape as above. 10 entries total (Ascendant + 9 planets). Note
    // `sign` (D1/Rasi) and `house` (cuspal/Bhava Chalit) can legitimately
    // point at what looks like a "mismatched" pairing compared to a plain
    // whole-sign chart -- that's expected, see the update banner at the
    // top of this doc. `flags` is usually an empty array -- most
    // placements won't trigger any of these six markers.
  ],
  "synthesis": "Step back and look at the whole chart: your nine planets are spread across 8 of the twelve houses in your life. 1 of them sit in the four \"power houses\" (self, home, relationships, and career), and 3 fall in the luckiest, most fortune-linked houses in the chart. That's the shape of it. What it doesn't tell you is which of these areas are running smoothly for you right now and which ones are under real pressure. That's a completely different question, tied to your current planetary period and today's sky, and it's exactly what the full Diagnostic Report is built to answer.",
  "upgrade_pitch": "Here's the honest split between what's free and what's not. Everything above tells you where each planet sits and what part of your life it touches. That's placement, and you now have all of it, for free. What it can't tell you is whether those placements are currently working in your favor, running under stress, or about to shift. That's a moving picture, driven by your current planetary period (dasha) and the sky right now, not a fixed one. Mapping that out, house by house and planet by planet, is exactly what the full Diagnostic Report does.",
  "book_url": "https://orbinovastro.square.site/s/appointments",
  "disclaimer": "A free preview only: which sign and house every planet occupies, and which of this practice's own real house/planet domains that activates. Sign (rashi) is your D1 (Rasi) birth chart placement. House (bhava) is cuspal (Bhava Chalit / Nirayana bhava), the same house convention this practice's KP significators and the paid Diagnostic Report's scoring use, so a planet's house can differ from a simple whole-sign count. Neither number is wrong. They're two established, valid conventions that answer slightly different questions. Each placement's Retrograde/Exalted/Debilitated/Own Sign flags use standard classical rules; Combust uses standard classical orbs; Vargottama compares this chart's D1 sign against its D9 Navamsa sign, so it carries the same beta caveat as the D9 feature. None of these flags are read from this practice's own Kundli worksheet, which computes them with its own unported formulas. All positions are Nirayana (sidereal), from the validated mechanical layer. Deliberately does not include KP significators, dasha/bhukti timing, or the proprietary connection-and-stress scoring (CCSI) the full paid Diagnostic Report is built on."
}
```

Rendering guidance (see "What to build" item 2 and "Visual design pass" above
for the full layout spec):
- `headline` — large opening line.
- `executive_summary` — a full paragraph, body text.
- `placements` — the approved two-column table (Placement / What it may
  signify for you) described in "What to build" item 2 above -- not cards,
  not a bulleted list. Include the static "Sign = D1 (Rasi)... House =
  cuspal (Bhava Chalit / Nirayana bhava)" caption line directly under the
  section heading, per item 2 above. Each entry's `narrative` already
  mentions any flag in prose, so `flags` (the new array -- see the update
  banner at the top of this doc) is optional to render separately; if you
  do add badges/chips for it, keep them small and consistent with the
  existing retrograde-marker treatment, not a second competing visual
  language.
- `synthesis` — a closing paragraph, led with a bold "The larger pattern:"
  label per the approved reference.
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

Request (same `BirthDetailsIn` shape as `/api/chart`, plus a `client_name`
and a `transit` object built from the page's ONE existing Transit tab --
see "What to build" item 3 above, do not build a second transit input):
```json
{
  "client_name": "Devang Naik",
  "birth": { "...same BirthDetailsIn shape as /api/chart..." },
  "transit": {
    "year": 2026, "month": 12, "day": 25, "hour": 0, "minute": 0,
    "utc_offset_hours": 5.5
  }
}
```
Only the date/time fields ever vary here, taken directly from the Transit
tab's current state:
- If the Transit tab's date/time is blank, omit the whole `transit` object
  (or send it with `year`/`month`/`day`/`hour`/`minute` all absent) -- this
  means "right now," the same as it already does for `/api/transit`.
- If the visitor set a specific date/time in the Transit tab, send that
  exact value, with whatever UTC offset the Transit tab itself uses for it
  (mirroring the birth details' own `utc_offset_hours` is fine, same as
  `/api/transit` already does).
- **Never send `latitude`/`longitude`/`place` on this request.** Leave them
  out always, every time -- the backend automatically uses the birth
  details' own location when they're absent, which is exactly the
  behavior wanted here. There is no transit-location control on this page
  at all.

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
   with their own narrative text, the "Sign = D1... House = cuspal..."
   caption line appears under the Planetary Placements heading, the closing
   synthesis and upgrade-pitch paragraphs both appear with the upgrade
   pitch visually distinct, and the "Book Your Full Reading" button opens
   `book_url` in a new tab. Cross-check one or two placements against the
   Chart tab's own output for the same birth details: `sign` must agree
   exactly with the D1 tab's sign for that planet, and `house` must agree
   exactly with the **Bhava Chalit** tab's `house` value for that planet
   (not the D1 tab's house number -- those can legitimately differ now,
   see the update banner at the top of this doc).
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
   window. **Orientation check (2026-09-24, latest again): for a chart with
   Capricorn rising, Mars (which lands in Aries, house 4) must render in the
   LEFT kite box, and Mercury (Libra, house 10) in the RIGHT kite box — if
   they're swapped, the corrected mirrored polygon table wasn't applied.**
   Also confirm the wheel diagram itself matches the latest visual-reference
   update: a small muted **Rashi number** (the sign's own fixed 1–12
   zodiacal index — e.g. Capricorn always shows "10", regardless of which
   house box it lands in) near each box's center-ward vertex — NOT the
   house-position number, and NOT a sign-abbreviation text label anywhere
   in the box (that text is dropped per the "UPDATE (2026-09-24, newest)"
   box in the "Chart wheel diagram" section — check a Capricorn-ascendant
   chart's house-1/top box specifically: it must show "10", not "1", and
   must not say "Cap" anywhere in the box). Each planet's in-box label
   still uses the compact `Code(R) DD°MM'` format (colored per planet),
   everything centered within its box, and the Fire/Earth/Air/Water
   element tint still present (that part was NOT dropped, only the
   sign-abbreviation text was). If a below-chart legend was added
   (optional per that UPDATE box), confirm it correctly maps all 12
   numbers to sign names.
   Also confirm each wheel's Planet Details Table beneath it uses the
   exact THREE-COLUMN layout ("Planet / Position" stacking Planet ·
   Sign/House-for-this-tab · Degree/Nakshatra(Pada) · Nature/Flags;
   "Conj. / Aspects" stacking Conjunctions · Aspects · Aspected By; then
   "Meaning" alone — see the "Planet color scheme and the enriched Planet
   Details Table" section above), colored consistently with the wheel's
   own planet-code colors, across all four views, not just D1, and
   readable without horizontal clipping (widen the Meaning column, or let
   it wrap on narrow screens). Specifically check: (a) the **Ascendant
   row** shows a real Nakshatra(Pada), Meaning, and (if anyone aspects the
   Lagna for this chart) an Aspected By line, with a dash for Nature (in
   the "Planet / Position" cell) but the Conjunctions and Aspects lines
   simply OMITTED (no line, no dash) since it never has either — if
   Nakshatra(Pada)/Meaning are blank instead, the backend fix didn't
   make it into this deploy; (a2) more generally, for EVERY row, any of
   Conj/Aspects/Aspected-by that's empty for that planet is omitted
   entirely, not shown as `"Conj: —"` filler (client feedback,
   2026-09-24, latest — see the UPDATE box at the top of the "Planet
   color scheme..." section) — a row can legitimately show just one of
   the three lines, or none at all, and that's correct; (b) for a chart
   with **Jupiter in Capricorn**
   (or any planet in its sign of debilitation/exaltation/own sign), that
   planet's fourth line shows the corresponding compact code (`D↓`/`E↑`/
   nothing extra for Own Sign's badge styling) — not just Retrograde;
   (c) the flag legend (`R*` `C^` `E↑` `D↓` `V▫`) is visible somewhere on
   or near the table; (d) a planet's Aspects and Aspected By lists can
   legitimately differ (e.g. Mars 8th-aspecting Venus doesn't mean Venus
   aspects Mars back) — that's correct, not a bug to "fix" into symmetry;
   (e) the Sign/House line actually changes when you switch tabs (D1 →
   Bhava Chalit → D9 → Cuspal) while Degree/Nakshatra/Meaning/Conjunctions/
   Aspects/Aspected By stay the same for that planet, since those are
   natal facts, not per-view ones; (f) Uranus, Neptune, and Pluto now
   DO appear, both in the wheel (correct house box, own accent color) and
   as three more table rows, each with real position/Meaning/Flags but a
   dash for Nature, Functional Nature, Conjunctions, Aspects, and Aspected
   By (see the "yet even later still" UPDATE box above — this is now the
   expected behavior, not a bug); (g) each row's `functional_nature`
   renders as its own small badge next to `nature`, and for at least one
   planet the two badges show DIFFERENT values (e.g. this engagement's
   real reference chart has Jupiter as natural Benefic but functional
   Malefic) — if they always match, functional_nature likely isn't wired
   up, it's silently mirroring nature instead; (h) each planet's
   chart-wheel label is colored by `planet_element` (five colors: Fire/
   Water/Earth/Air/Ether, plus neutral for Rahu/Ketu/Uranus/Neptune/
   Pluto/the Ascendant) — for this engagement's real reference chart, the
   Sun (in Virgo) must show its Fire color, NOT an Earth color, even
   though Virgo itself is an Earth sign (`rashi_element: "Earth"`) — if
   the Sun's label is colored like an Earth-element planet, `rashi_element`
   was used instead of `planet_element` by mistake; the element legend
   (5 colors + neutral) must be visible near the wheel.
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
8. Confirm there is exactly ONE Transit input on the whole page (the
   existing Transit tab) and that "Get My Full Report" has no transit
   input of its own. Then specifically test the wiring, since an earlier
   build got this wrong: (a) with the Transit tab's date/time still blank,
   generate a report and confirm its Client Information page shows the
   birth location with a transit time close to the actual moment you
   clicked the button; (b) set a clearly different date in the Transit
   tab (e.g. a date months away), generate another report, and confirm
   THIS TIME the Transit Information page shows exactly that date, still
   at the birth location (never a different location -- there's no control
   for that); (c) switch to the Transit tab itself and confirm computing a
   transit there still works exactly as before -- this change should be
   invisible to that existing feature.
