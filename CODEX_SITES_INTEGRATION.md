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
"ASC ↑" label at the top-center (200, 14). Each house box's text: the sign
abbreviation (first 3 letters) on the first line in the accent color, then
one line per occupying planet's 2-letter code (append a small "ᴿ" superscript
or similar retrograde mark if `retrograde` is true). **Adopt the client's own
per-planet color scheme** (see the new "Planet color and element scheme"
section below) for each planet's code label here too, not just in the data
table underneath — the wheel and the table should read as one consistent
system, the way the client's own Excel chart does (colored planet codes
inside the wheel boxes, the same colors reused in the table beneath it).

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

## Planet color scheme and the enriched Planet Details Table (new, 2026-09-24 latest)

The client sent their own Excel Kundli chart as the reference for how much
detail and what visual treatment a chart page should have, and asked that
the site adopt "the best for client presentation" from it, applied to
**every** reference chart view (D1, Bhava Chalit, D9, Cuspal), not only D1.
`/api/chart`'s `planets` array gained four new fields this round — every
one of them is a natal fact (this planet's actual position/relationships),
so the SAME enriched table below is correct to show underneath all four
wheel diagrams; only which house-box the planet is drawn in changes between
the four chart types, not this table's content.

**New fields on each entry in `/api/chart`'s `planets` array** (see the
updated `/api/chart` contract further down for the full shape):
- `degree_in_sign` — already existed, e.g. `25.512` (25°30′44″). Show
  degrees/minutes/seconds or decimal degrees, either is fine, but show it
  somewhere it wasn't before if your current table omits it.
- `nakshatra` / `pada` — already existed. Show together as `"{nakshatra}({pada})"`,
  e.g. `"Chitra(1)"`, matching the client's own Excel table's exact format.
- `meaning` — **new**. One ready-to-render sentence, e.g. `"Chitra(1):
  craftsmanship and a natural sense of design or charisma; Virgo adds
  careful and detail-driven."` — put this straight into an "Interpretation"
  / "Meaning" column, no client-side composition needed.
- `conjunctions` — **new**. A list of `{code, orb_degrees}` for every other
  planet sharing this one's D1 sign (empty if none). Render as a short
  "Conj." column, e.g. `"Sa · 3.3°"` for a planet listing one conjunction,
  joined with commas if there's more than one, or blank if the list is
  empty — this is exactly the information a visitor needs to understand why
  two planet codes appear stacked in the same house box.
- `nature` — **new**. `"Malefic"` or `"Benefic"` (the Ascendant entry, if
  you render one in this table, has no `nature` — the API only returns this
  field on real planets, not the Ascendant/houses array). Use it to tint a
  small badge or the row itself, consistent with the Flags column's own
  badge treatment (see the existing "Retrograde and beta markers should be
  visually distinct" guidance below).

**A single planet-details table, one row per planet** (Ascendant + 9
planets, same order as `/api/chart`'s `planets` array), with columns:
**Planet · Sign/House · Degree · Nakshatra(Pada) · Flags · Nature ·
Conjunctions · Meaning** — this mirrors the client's own Excel table's
column set (Planet, Position, Degree, Flags, Nature, Nak/Pada,
Interpretation) reordered slightly for readability, and should sit directly
beneath each of the four chart wheels, using that chart type's own
house-numbering convention in the "Sign/House" column (`rasi_house` for D1,
`house` for Bhava Chalit, `navamsa_house` for D9, cusp number for Cuspal —
same house-field rule as the wheel itself, see above). The "Flags" column
isn't from `/api/chart` — it's the same `flags` array the Preview's
placements table already renders (Retrograde/Combust/Exalted/Debilitated/
Own Sign/Vargottama); if this table sits on a chart tab that doesn't already
fetch `/api/teaser`, it's fine to leave Flags blank there rather than make
an extra API call just for that one column — `/api/chart`'s own `retrograde`
boolean is always available as a minimum.

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
  Rahu, and Ketu each get their own color, consistent across every place
  they're rendered on the page. (If the D9/Cuspal views also show Uranus/
  Neptune/Pluto — they don't currently, `/api/chart` only returns the 9
  classical grahas plus Ascendant — skip this for now.)
- A light background tint per house box keyed to that box's sign's
  classical element (fire: Aries/Leo/Sagittarius, earth: Taurus/Virgo/
  Capricorn, air: Gemini/Libra/Aquarius, water: Cancer/Scorpio/Pisces) —
  four subtle, distinct tints, consistent across all twelve boxes and all
  four chart types. This is a purely decorative grouping (which element a
  sign belongs to is standard, universally-agreed classical astrology, not
  proprietary), so a small legend line near the wheel ("Fire · Earth · Air ·
  Water", matching the client's own reference) is a nice touch but not
  required.
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
  "ayanamsa_deg": 23.94, "ayanamsa_mode": "Krishnamurti (KP)",
  "ascendant": {"house": 1, "longitude": 294.8, "sign": "Capricorn", "sign_lord": "Sa"},
  "houses": [ {"house": 1, "longitude": 294.8, "sign": "Capricorn", "sign_lord": "Sa"}, "... 12 total, houses 1-12" ],
  "planets": [
    {
      "code": "Su", "name": "Sun", "longitude": 175.5,
      "sign": "Virgo", "sign_lord": "Me", "degree_in_sign": 25.5,
      "nakshatra": "Chitra", "nakshatra_lord": "Ma", "pada": 1,
      "retrograde": false, "house": 8, "rasi_house": 9,
      "meaning": "Chitra(1): craftsmanship and a natural sense of design or charisma; Virgo adds careful and detail-driven.",
      "conjunctions": [{"code": "Ur", "orb_degrees": 4.19}],
      "nature": "Benefic"
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

**New this round (2026-09-24, latest): `meaning`, `conjunctions`, and
`nature`** — see the new "Planet color scheme and the enriched Planet
Details Table" section above for exactly how to render these three, and
note they apply to every chart view built from this endpoint's data (D1,
Bhava Chalit, and — since D9/Cuspal ultimately describe the same natal
planets — these too), not only the D1 tab.

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
   Also confirm each wheel's Planet Details Table beneath it shows Degree,
   Nakshatra(Pada), Conjunctions, and Meaning for every planet, colored
   consistently with the wheel's own planet-code colors (see the new
   "Planet color scheme" section above), across all four views, not just D1.
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
