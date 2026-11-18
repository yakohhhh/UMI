# UMI — Urban Motion Intelligence

A clip-on sensor for bikes, scooters and runners that scores every street for **comfort, safety, air and noise**, launching in Barcelona. Riders flag hazards hands-free with one button on the Clip; the city gets anonymised, aggregated street data.

This repository holds the whole software, from the Clip's firmware to the web apps. The hardware has not arrived yet, so everything runs on simulated hardware: virtual Clips record the same session logs a real one will.

| Component | Path | What it is |
| --- | --- | --- |
| Protocol | [`protocol/`](protocol/README.md) | The contract: the `.umis` session log, flag signatures, privacy trim, upload API, BLE GATT, shared constants generated into C, Python and TypeScript, golden vectors |
| Firmware | [`firmware/`](firmware/README.md) | The Clip (ESP32-S3, C11, ESP-IDF via PlatformIO): detectors, button gestures, signed flags, session log, BLE. Runs on the host, a DevKitC or the board |
| Simulator | [`simulator/`](simulator/README.md) | Fake hardware: virtual riders on the Barcelona street graph, virtual Clips, the phone's trim and upload, fleets |
| Backend | [`backend/`](backend/README.md) | FastAPI service: session ingest, map matching, hazards, k-anonymous street scores, the `/v1` API |
| Web | `src/` | Next.js: landing, rider app, City Insights (this README, from [Pages](#pages)) |
| Infra | [`infra/`](infra/README.md), [`.github/`](.github/workflows) | Docker Compose stack (Postgres, API, simulated fleet), CI per component |
| Docs | [`docs/architecture/`](docs/architecture/README.md) | System overview, where each privacy rule is enforced, decision records |

The mobile companion app (BLE transfer, privacy trim, post-ride questions) is next; until then the simulator plays the phone. The backlog is on the [project board](https://github.com/users/yakohhhh/projects/3); how we work is in [CONTRIBUTING.md](CONTRIBUTING.md).

## Getting started

| To work on | You need |
| --- | --- |
| Web | Node.js ≥ 20.9 |
| Protocol, backend, simulator | [uv](https://docs.astral.sh/uv/) (it installs Python 3.13 itself) |
| Firmware | [PlatformIO Core](https://platformio.org/install/cli) 6 (it installs the ESP-IDF toolchain on the first build) |

### The full stack on simulated hardware (5 minutes)

```bash
uv sync --all-packages --all-groups                          # Python workspace
uv run umi-api migrate && uv run umi-api seed                # SQLite database with the demo data
uv run umi-api serve                                         # API on http://127.0.0.1:8000
uv run umi-sim fleet --riders 40 --days 14 --api http://127.0.0.1:8000   # in a second terminal
npm install && NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev    # in a third: http://localhost:3000
```

The simulated riders pair their Clips, trim their rides and upload them; their flags become hazards on everyone's map once 3 riders agree and reach City Insights from 5. `docker compose -f infra/docker-compose.yml up -d --wait` runs the same backend on Postgres ([infra/README.md](infra/README.md)). The firmware's own logic runs on a laptop too: `cd firmware && pio test -e native && pio run -e sil` ([firmware/README.md](firmware/README.md)).

### Web app only

The web app runs on realistic local mocks, offline and without any backend:

```bash
npm install
npm run dev        # http://localhost:3000
```

| Script | |
| --- | --- |
| `npm run dev` | Development server |
| `npm run build` / `npm start` | Production build and server |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run mock:generate -- <path>` | Regenerate the mock datasets (see [Mock data](#mock-data)) |
| `npm run protocol:generate` / `protocol:check` | Regenerate the shared constants from `protocol/constants.toml` / check they are current |
| `npm run contract:generate` | Regenerate the JSON Schema of the web types the backend's contract test validates against |
| `npm run api:seed` / `api:dev` | Migrate and seed the backend / serve it with reload |
| `npm run sim:fleet` | Upload a simulated fleet to the local backend |
| `npm run test:py` / `firmware:test` | Python test suites / firmware host tests |

### Windows

Everything runs natively on Windows (no WSL needed):

1. Install Node.js LTS from [nodejs.org](https://nodejs.org) (or `winget install OpenJS.NodeJS.LTS`) and Git (`winget install Git.Git`), then open a new terminal.
2. `git clone https://github.com/yakohhhh/UMI.git`, `cd UMI`, `npm install`, `npm run dev`.
3. For the rest of the stack: `winget install astral-sh.uv` for the Python components, and `uv tool install platformio` for the firmware. Commands are the same as above; in PowerShell set variables with `$env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:8000"` before `npm run dev`.

If PowerShell answers *"running scripts is disabled on this system"*, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `npm.cmd` instead of `npm`. Keep the project outside OneDrive-synced folders: syncing `node_modules` slows installs down and can lock files.

### Environment

Copy `.env.example` to `.env.local` (`copy .env.example .env.local` on Windows). Every variable is optional.

| Variable | Effect |
| --- | --- |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | Switches every map from the free CARTO styles to Mapbox `dark-v11` / `light-v11` (MapLibre renders them; `mapbox://` URLs are rewritten). |
| `NEXT_PUBLIC_API_URL` | Base URL of the UMI backend (`backend/`). When set, `src/lib/api.ts` fetches it instead of the mocks; response shapes are the types in `src/lib/types.ts`, checked by the backend's contract test. |
| `NEXT_PUBLIC_SITE_URL` | Absolute URL used for metadata (Open Graph). |

The backend's settings (`UMI_*`) are in [backend/README.md](backend/README.md).

## Pages

**Landing (`/`)** — hero with split title and floating Clip, pinned exploded view of the 7 layers (housing with the sealed flag button → ESP32-S3 → GNSS → IMU → PM2.5 → mic → battery), "One ride" on a stylised Barcelona map (Gràcia → 22@, events and scores), four dimensions in horizontal scroll, pinned iPhone with three synced screens, product quotes revealed word by word, "For cities" data mode (rider-flagged hazards and why riders brake, from 5+ riders), how it works in six steps (clip on → ride → flag it → sync → ride report → better route), pricing (€119 / early bird €99, Premium €4.99/mo or €39.99/yr, City Insights pilot €14,900; verified hazard warnings are free for everyone), final CTA and footer. The navbar blurs and shrinks with a thin orange progress bar.

**Rider app (`/app`)** — collapsible sidebar, top bar (search ⌘K, notifications, account, Clip battery and sync), bottom navigation on mobile, page transitions and skeletons.

- `/app` — feed (Laia's rides and the people she follows), week stats, best time window, Clip, clubs.
- `/app/activities/[id]` — ride report: map coloured by segment, clickable events and flags, animated gauges, four synced charts that move a dot on the map, segments vs the street average. **Moments to check**: at most 2 hard brakes the app asks about ("Why did you brake?", 9 causes in three buckets: Street issue, Traffic, Just you) plus every flag pressed without a keyword — one tap each, skippable, only once the ride has ended. Each flag shows how it was made (button or voice) and where it is in its lifecycle: waiting for riders → verified → sent to the city → fixed (with the sensors' proof) or gone.
- `/app/map` — full-screen street map: Overall / Comfort / Safety / Air / Noise, 0–23 h slider with play, layers (bike lanes only, hard-brake hotspots, potholes, rider flags verified by 3+ riders — on by default, listed in the legend for keyboard users, with "Your Calmest route avoids it" when it does), street panel with the 24-hour profile, search, mobile drawers. Deep links: `?street=seg-301&metric=air&hour=8`, `?q=diagonal`.
- `/app/routes` — Fastest / Calmest / Cleanest with "+3 min for a far calmer ride", forecast for the departure time, routes drawn over the scored streets.
- `/app/exposure` — PM2.5 and noise per week or month vs WHO guidelines and the EU 2030 limit (10 µg/m³), year calendar heatmap, insights, the streets behind your dose.
- `/app/profile` — totals, records, badges, contributions with your **impact** (riders warned, flags verified, fixes, causes given), your flags and their status, a private **trust level** (0–10, no leaderboard) and the perks it unlocks, clubs, Clip settings (`#clip`: the flag button, voice keywords off by default, confirmation chirp, warn-ahead chirps), Premium (`#premium`), privacy and data export / deletion under GDPR and the EU Data Act (`#privacy`).

**City Insights (`/city`)** — shared filters on every page (period, districts, Bike / Run / All, mirrored in the URL) and the "Anonymised & aggregated — trip start/end trimmed" badge.

- `/city` — KPI tiles with sparklines and deltas, district choropleth (click a district to filter), ranking, signals to act on (including hazards riders keep flagging that are not in IRIS yet).
- `/city/surface` — sortable ranking of 335 segments linked to the map (hover a row, click a segment), CSV export, empty state for runners.
- `/city/safety` — proportional hard-brake hotspots, top 10 junctions with **why riders brake** there (cause mix from 5+ riders, rounded to 10 %), monthly trend per 1,000 rides, and **flagged by riders** (`#hazards`): hazards from 5+ different riders, their day-level dates and status (new, sent to IRIS, scheduled, fixed).
- `/city/air-noise` — hour × weekday heatmap with thresholds, daily profile weekdays vs weekends.
- `/city/api` — masked key (reveal / copy / rotate), quota, endpoints, request / response samples, privacy model.

### Loading, empty and error states

Every API call goes through `src/lib/api.ts` with a simulated latency. Append `?simulate=error` or `?simulate=empty` to any URL to see the error and empty states.

## Stack

- Next.js (App Router) · React 19 · TypeScript · Tailwind CSS v4 (CSS-first tokens in `src/app/globals.css`)
- Lenis smooth scroll synced with GSAP ScrollTrigger (pins and scrubs on the landing), SplitText
- Framer Motion for app micro-interactions and page transitions
- MapLibre GL via `react-map-gl/maplibre`, free CARTO Dark Matter / Positron styles, Mapbox optional
- Recharts · lucide-react · Radix primitives restyled in `src/components/ui` (shadcn-style)

MapLibre is pinned to v5: v6 is ESM-only and still settling with bundlers; v5 is what `react-map-gl` 8 targets.

If the remote basemap can't be loaded (offline, blocked network, missing token), maps switch after 6 s to a built-in style that draws the city outline and the districts, so the data layers stay readable.

## Design system

- **Colours** — asphalt `#0B1220` (900 → 50), paper `#F6F4EF`, signal `#FF5B1F` (the only accent: your trace, your actions), lane `#2F7FFF`.
- **Score scale** — blue = good (70–100), yellow = average (45–69), orange = poor (0–44). A colour is never alone: it always comes with the number or a label ("Calm", "Bumpy", "Polluted"…).
- **Type** — Space Grotesk (titles, tabular figures), IBM Plex Sans (text), IBM Plex Mono (labels). Self-hosted with `next/font/local`, SIL OFL 1.1 (see `src/app/fonts/OFL.txt`).
- **Shape** — 12–20 px radii, 1 px translucent borders, soft shadows, grain on dark surfaces.
- **Theme** — the landing is always dark; the app and City Insights have a light / dark toggle (dark by default).

Reusable building blocks: `ScoreBadge`, `ScoreGauge`, `ScoreRing`, `StatTile`, `KpiTile`, `Delta`, `Sparkline`, `ActivityCard`, `StreetMapCanvas`, `HourSlider`, `RouteCompareCard`, `TimelineChart`, `Segmented`, `Sheet`, `EmptyState`, `ErrorState`.

### Scores

Each street segment has four hourly scores (0–100), computed from the sensors: vibration (m/s² RMS) → comfort, hard brakes > 3 m/s² → safety, PM2.5 (µg/m³) → air, dB(A) → noise. The **overall** score is the weighted mean (comfort and safety 30 %, air and noise 20 %) pulled toward the weakest dimension — a street is only as calm as its worst aspect — and calibrated so 50 is the city's rush-hour median (`overallScore` in `src/lib/score.ts`).

### Flags and brake causes

Riders warn about a hazard without touching the phone — since RD 518/2026 (art. 18.2 RGC), Spanish traffic rules ban phones and earphones of any kind for cyclists and scooter riders — with one sealed button on the Clip:

| On the Clip | What happens |
| --- | --- |
| Short press | Drops a flag: time, GNSS position and a sensor snapshot. One chirp and an orange flash. |
| Hold ~1 s | A 4-second window to say one keyword (*obres · obras · roadworks*…), recognised on the Clip. Opt-in, off by default. |
| Double press | Undoes the last flag. |

The press fixes where and when; the keyword, or a tap after the ride, says what (roadworks, pothole, blocked lane, obstacle, dangerous spot). Nothing is lost if no word is said or understood. There is no always-listening wake word.

- **Lifecycle** — waiting for riders → verified (3+ different riders, including Clips that pass with the same sensor signature; on everyone's street map) → sent to the city (5+ riders; City Insights and the city's IRIS system) → fixed (the Clips measured the repair, e.g. "Comfort on this block 52 → 81") or gone. Lifetimes per kind are in `HAZARD_LIFETIME`.
- **Brake causes** — a hard brake is a fact, its cause is context: a dog crossing is not a false positive. Street issues go to the maintenance list once 5 riders agree, traffic causes still count for the junction's safety score, "just me" stays in the rider's ride. Unanswered brakes count at half weight (`brakeWeight`).
- **Warnings** — other riders see verified hazards before they leave (street map, and whether their Calmest route avoids them) and, if they choose, hear two low chirps from their Clip as they approach one.
- **Rewards follow outcomes, not presses** — no spendable points, no leaderboard, no pay per report. Riders see their impact (riders warned, flags verified, fixes, causes given), a private trust level that unlocks perks such as "Street steward", and now and then an unannounced thank-you (a Premium month, a tune-up at a partner bike shop, or give it to a cause). Answers earn nothing in themselves and all count the same, "just me" included, so nobody has a reason to exaggerate. The "Fixed" notification, with the sensors' proof, is the main reward. Verified hazard warnings are free for everyone.

## Motion and accessibility

- Animations use transform and opacity only. With `prefers-reduced-motion`, Lenis is off, nothing is pinned or scrubbed, sections are laid out statically (the phone screens follow a plain list of steps), and app transitions drop their movement.
- Mobile gets simplified sequences (no horizontal pin, sticky phone with scrolling steps).
- WCAG AA contrast on both themes, visible focus, skip links, landmarks, labelled controls. Maps have keyboard-accessible alternatives (street search and lists, sortable tables); charts carry text summaries; the mic only turns sound into dB(A), plus one keyword while the flag button is held if voice keywords are on — audio never leaves the Clip and is never stored, and the UI says so.
- Nothing asks for the phone while moving: flags are made on the Clip (chirp + LED, no screen, no earphones) and questions wait until the ride has ended.
- Performance: the hero title and paragraph animate in with CSS from the first paint (they are the LCP), looping animations pause in off-screen sections, and no continuous rAF loop runs while the pointer rests. Measure Lighthouse on `npm run build && npm start`: `npm run dev` ships unminified React and scores about 20 points lower (landing, mobile: ~69 in dev vs ~90 in production).

## Mock data

`src/lib/mock/data/*.json` is generated by `scripts/generate-mock-data.mjs` (deterministic seed):

- 335 street segments (~141 km) on real Barcelona coordinates — the Cerdà grid is fitted on census boundaries (45.1°, 133.4 m pitch) — each with 24 hourly scores, rider counts, surface and potholes;
- 31 activities: Laia (31, e-bike, Gràcia → 22@, ~8 km a day) and runs for Marc (marathon prep), with 1 Hz samples for the ride reports;
- 70 confirmed potholes, 64 hard-brake hotspots, a year of exposure, district aggregates, the City Insights datasets, and the stylised maps used by the landing.

Rider flags, "why did you brake?" answers and the hazards published to City Insights are hand-placed on top of the generated rides in `src/lib/mock/flags.ts` (no regeneration needed). Answers given in the app are kept in memory for the session, like a server would.

Value ranges follow the spec: PM2.5 5–35 µg/m³, noise 50–80 dB(A), hard brakes above 3 m/s². Dates are shifted by whole weeks at runtime so the demo always looks recent.

To regenerate, clone the Barcelona geodata and point the script at it:

```bash
git clone https://github.com/martgnz/bcn-geodata ../bcn-geodata
npm run mock:generate -- ../bcn-geodata
```

## Privacy model (shown in the product)

The first and last 200 m of every trip are trimmed on the phone before upload; a street segment and hour is published only once at least 5 different riders crossed it; City Insights and its API only serve hourly aggregates. Riders opt in to city sharing and can export (JSON) or delete their data at any time.

- **Flags** show on other riders' street maps once 3 different riders flagged or confirmed them, and reach City Insights only from 5, with day-level dates and never who flagged.
- **Why riders brake**: a junction's cause mix is published from 5 different riders, rounded to 10 %, with causes under 10 % merged into "other"; "just me" answers stay in the rider's own ride and leave street scores and city data.
- **Voice keywords** are off by default and recognised on the Clip. Audio stays a few seconds in the Clip's memory and is never stored or sent: only the keyword, the time and the place leave it.

## Project structure

```
protocol/                 the contract: constants.toml (+ codegen/), session log spec, python/ reference codec, vectors/
firmware/                 Clip firmware: lib/umi_hal, umi_core, umi_protocol, umi_drivers, umi_sim; src/ (ESP-IDF); sil/; test/
simulator/                umi-sim: street graph, riders, sensors, virtual Clips, phone, fleets, SIL scenarios
backend/                  umi-api: api/ schemas/ services/ domain/ repositories/ pipeline/ (ingest); migrations/; tests/
tests/e2e/                firmware, simulator and backend together
infra/                    docker-compose.yml and the API and simulator images
docs/                     architecture/ (overview and ADRs), hardware/ (assumed parts, bring-up checklist), design notes
src/
  app/                    routes (App Router), layouts, global styles, fonts
    app/                  rider app: feed, activities/[id], map, routes, exposure, profile
    city/                 City Insights: overview, surface, safety, air-noise, api
  components/
    landing/              landing sections and their motion
    app/                  rider app views (street-map/, routes/, exposure/, profile/)
    city/                 City Insights shell, filters, maps and views
    map/                  BaseMap (MapLibre, basemap selection, offline fallback)
    charts/ data/ score/  charts, KPI tiles, score badges and gauges
    shell/ ui/ brand/     app shell, restyled primitives, logo
  lib/
    api.ts                the only data entry point (mocks or NEXT_PUBLIC_API_URL)
    reports.ts            flag and brake-cause rules: rider thresholds, cause buckets, weights, lifetimes
    generated/            constants generated from protocol/constants.toml
    types.ts score.ts format.ts geo.ts street-geojson.ts
    mock/                 lazy JSON loaders and datasets; data/flags.json = hand-placed flags, answers and city hazards
scripts/generate-mock-data.mjs
```

## Credits

- Geometry: Ajuntament de Barcelona / CartoBCN via [bcn-geodata](https://github.com/martgnz/bcn-geodata), CC BY 4.0. All measurements are synthetic.
- Basemaps: © [CARTO](https://carto.com/attributions), © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
- Fonts: Space Grotesk and IBM Plex, SIL Open Font License 1.1.
