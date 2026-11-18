# UMI backend

The `/v1` REST API the web app calls (`src/lib/api.ts`), and the [ingest pipeline](#ingest) that turns a Clip's trimmed session log into a ride, its flags and street scores. FastAPI, SQLAlchemy 2 (async) and Alembic. Responses mirror `src/lib/types.ts` in camelCase, so setting `NEXT_PUBLIC_API_URL` switches the web app from its mocks to this service with no UI change. Decisions are in [ADR 0004](../docs/architecture/adr/0004-backend-stack.md) (stack), [ADR 0005](../docs/architecture/adr/0005-device-identity.md) (signed flags) and [ADR 0006](../docs/architecture/adr/0006-privacy-enforcement.md) (privacy).

## Quick start

From the repository root (Python 3.13 and [uv](https://docs.astral.sh/uv/)):

```bash
uv sync --all-packages --all-groups
uv run umi-api migrate && uv run umi-api seed && uv run umi-api serve --reload
```

The API listens on http://127.0.0.1:8000 (OpenAPI docs at `/docs`). The default database is the SQLite file `backend/umi-dev.db` (git-ignored); nothing else to install.

Point the web app at it:

```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev
```

The web app sends no `Authorization` header, so every request acts as the default rider (`laia`), like the mocks. CORS allows `http://localhost:3000` by default.

Feed it simulated rides (the simulator pairs its Clips, trims each session and uploads it, see [Ingest](#ingest)):

```bash
uv run umi-sim fleet --riders 40 --days 14 --api http://127.0.0.1:8000
uv run umi-api aggregate   # already done per upload outside production
```

Uploads are received at the real time, while "now" for the read endpoints stays pinned to the seeded demo (`UMI_PIN_CLOCK_TO_DATASET`): simulated rides show in the feeds and on the map, but "this week", "today" and the City Insights periods still count from the demo's Thursday evening.

| Command | |
| --- | --- |
| `uv run umi-api serve [--host --port --reload]` | Serve the API (uvicorn). |
| `uv run umi-api migrate [revision]` | Apply the Alembic migrations to `UMI_DATABASE_URL`. |
| `uv run umi-api seed [--data-dir]` | Load the web app's mock datasets, dates shifted to this week. Safe to run again. |
| `uv run umi-api aggregate` | Recompute every street's hourly scores from riders' passes (see [Street scores](#street-scores)). Production runs it on a schedule. |
| `uv run umi-api openapi [--output]` | Print or write the OpenAPI document. |
| `uv run pytest backend/tests` | Tests (SQLite in a temporary directory, seeded once per run). |
| `uv run ruff format backend && uv run ruff check backend && uv run mypy backend/src` | Format, lint, type-check (strict). |

## Configuration

Environment variables, prefix `UMI_` (`src/umi_api/settings.py`):

| Variable | Default | |
| --- | --- | --- |
| `UMI_ENV` | `dev` | `dev`, `test` or `production`. Production refuses dev tokens and simulated Clips. |
| `UMI_DATABASE_URL` | `sqlite+aiosqlite:///backend/umi-dev.db` | Postgres: `postgresql+psycopg://user:pass@host:5432/umi`. |
| `UMI_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated. |
| `UMI_DEV_DEFAULT_ATHLETE` | `laia` | Rider used when a request has no `Authorization` header (not in production). |
| `UMI_DEV_DEFAULT_CITY_ACCOUNT` | `ajuntament-bcn` | City Insights account behind `/v1/account/usage` (not in production). |
| `UMI_ACCEPT_SIMULATED` | `true` (`false` in production) | Accept sessions recorded with simulated sensor drivers, and uploads from Clips registered as simulated. |
| `UMI_AGGREGATE_ON_INGEST` | `true` (`false` in production) | Recompute the scores of the streets a ride went through right after its upload. Production schedules `umi-api aggregate` instead, so uploads never contend on the published scores. |
| `UMI_PIN_CLOCK_TO_DATASET` | `true` (`false` in production) | Use the seeded demo's moment as "now" (see [Seed](#seed)). |
| `UMI_MOCK_DATA_DIR` | `src/lib/mock/data` | Where `umi-api seed` reads the datasets. |

## Layers

```
src/umi_api/
  api/            FastAPI routers, dependencies, auth, error mapping. HTTP only.
  schemas/        Pydantic v2 response and request models, one per type of src/lib/types.ts.
  services/       Use cases: load through repositories, apply domain rules, build responses.
  domain/         Pure rules, no FastAPI or SQLAlchemy: scoring (score.ts), reports (reports.ts),
                  privacy (k-anonymity, cause mixes), hazard lifecycle, plausibility, aggregation,
                  week, exposure, routes, City Insights filters.
  pipeline/       Ingest stages as plain functions on plain values: decode, track, map matching,
                  readings, events, flags, ride report, passes, exposure. No FastAPI, no database.
  repositories/   Queries. They never commit: the service owns the transaction.
  db/             Models, portable column types, engine and sessions, upsert, Alembic runner.
  seed/           The demo: mock datasets, values api.ts hard-codes, the panel of other riders.
  settings.py  clock.py  main.py (create_app)  cli.py (umi-api)
migrations/       Alembic (hand-checked revisions: the initial schema, then ingest).
tests/            pytest + httpx ASGITransport; tests/parity holds the mocks' recorded answers,
                  tests/ingest synthesises signed, trimmed sessions on real streets.
```

`api` → `services` → `domain`, `pipeline` and `repositories` → `db`. The domain and the pipeline never import FastAPI or SQLAlchemy; their functions take plain values or structural protocols, so tests (and later a worker) call them directly. "Now" always comes from a `Clock`, never from `datetime.now()` inside a use case.

Authentication lives in `api/auth.py` only: `Authorization: Bearer dev:<athleteId>` acts as that rider, no header means `UMI_DEV_DEFAULT_ATHLETE`, and production answers `401` to both. Everything that needs the caller depends on `CurrentAthlete`, so real accounts replace one module.

Errors are JSON in FastAPI's `{"detail": "..."}` shape: `404` for anything unknown (including routes), `403` when a rider answers for someone else's ride or uploads from a Clip paired with someone else, `409` for an answer the app does not ask for or a Clip registered with another key, `413`/`415` for an upload too large or not a session log, `422` for invalid input (including a session log the ingest refuses, with the reason), `503` when the street network is not seeded.

## Endpoints

Everything `src/lib/api.ts` documents, same paths and shapes:

| | |
| --- | --- |
| Rider | `GET /v1/me`, `/v1/athletes/{id}`, `/v1/feed`, `/v1/activities/{id}`, `/v1/me/week`, `/v1/me/best-window`, `/v1/me/clip`, `/v1/me/exposure?range=365d`, `/v1/me/profile` |
| Answers | `POST /v1/me/activities/{id}/events/{eventId}/cause` `{"cause"}` · `POST /v1/me/activities/{id}/flags/{flagId}` `{"kind"}` |
| Street map | `GET /v1/streets?bbox=minLon,minLat,maxLon,maxLat`, `/v1/potholes`, `/v1/hotspots/hard-brakes`, `/v1/hazards`, `/v1/districts`, `/v1/city-outline` · `POST /v1/routes` |
| City Insights | `GET /v1/city/overview`, `/v1/city/surface/ranking`, `/v1/city/safety`, `/v1/city/hazards`, `/v1/city/air-noise`, all with `?period=7d\|30d\|90d\|12m&mode=all\|bike\|run&districts=Eixample,Gràcia` · `GET /v1/account/usage` |
| Ingest | `POST /v1/ingest/sessions` (body: a trimmed `.umis`, `Content-Type: application/vnd.umi.session`), see [Ingest](#ingest) |
| Development | `POST /v1/dev/devices`: register a simulated Clip and its rider, pair them, get the rider's token. Not mounted in production. |
| Ops | `GET /healthz` (process up), `GET /readyz` (database answers, else `503`) |

Answers are checked before they are stored: only the rider who recorded the activity, a cause only for a hard brake the app asked about (it can be changed), a kind only for a flag pressed without a recognised keyword (the keyword is signed by the Clip and never overridden). A cause given for a brake the pipeline linked to a hotspot also joins that hotspot's mix, once per brake.

## Privacy, where the API enforces it

- Thresholds come from `protocol/constants.toml` through `umi_protocol.constants`.
- Rider counts are counted from distinct riders when a query runs (`hazard_confirmations`, `hotspot_cause_answers`), never read from a stored status: a hazard is on the map from 3 riders and in City Insights from 5, whatever its `status` column says.
- City hazards carry day-level dates and never who flagged them.
- "Why riders brake" (`domain/privacy.py`): published from 5 distinct riders, "just me" excluded from shares and counts, shares rounded to 10 %, a cause that rounds under `cause_share_min` merged into "other", at most four named causes.
- Rider keys in aggregate tables (`rider_key`) are only ever counted, never returned.
- Uploads: a session without the `trimmed` header flag is refused, whatever client sent it, so an untrimmed trace is never stored; flags count only with a valid signature from the Clip paired with the uploader.
- Street scores: a segment-hour moves away from its baseline only from 5 distinct riders (`umi-api aggregate`).

## Database

38 tables, portable types only (strings, numbers, JSON, naive-UTC timestamps, enums as `VARCHAR(32)`), so the same migration runs on SQLite and Postgres. The main groups:

| | Tables |
| --- | --- |
| Riders | `athletes`, `follows`, `devices` (public key, pairing, settings, battery, last sync), `athlete_profiles`, `athlete_records`, `badges`, `athlete_badges`, `clubs`, `club_memberships`, `best_windows` |
| Rides | `activities` (unique `device_id, session_id`), `activity_details` (route, 1 Hz samples), `activity_segments`, `ride_events` (cause, ask, hotspot, the street pass that counts it), `flags` (unique `device_id, session_id, seq`, signature, keyword vs answered kind, hazard), `session_uploads` (the receipt a retried upload gets again) |
| Hazards | `hazards` (lifecycle and city status, first seen, last confirmed), `hazard_confirmations` (one row per distinct rider) |
| Streets | `street_segments`, `segment_hourly_scores` (published), `segment_hourly_baselines` (seeded, what passes merge into), `segment_surface_stats`, `segment_passes` (activity x segment x hour: rider, vibration, PM2.5, dB, brakes, weighted brakes), `potholes`, `brake_hotspots`, `hotspot_cause_answers` |
| City | `districts` (GeoJSON), `district_stats`, `city_outlines`, `city_kpis`, `city_monthly_brakes`, `city_air_noise`, `dataset_snapshots` |
| Riders' aggregates | `exposure_days`, `exposure_contributors`, `planned_routes` |
| City API | `api_keys`, `api_usage_days` |

A new migration: change the models, then from `backend/` run `uv run alembic revision --autogenerate -m "..."` and review it (no imports from `umi_api` in a revision). `tests/test_api_seed.py` fails while the models and the migrations disagree, and when a seeded value is longer than its column (SQLite ignores `VARCHAR` lengths, Postgres does not).

## Seed

`umi-api seed` reads `src/lib/mock/data/*.json` (including `flags.json`, the hand-placed flags, brake answers and city hazards) and the few values `src/lib/api.ts` hard-codes (`seed/demo.py`: Laia's Clip, profile, best window, City API key). Dates move by whole weeks from the mocks' `MOCK_ANCHOR` to now, exactly like `src/lib/mock/index.ts`, so weekday patterns stay intact.

- It is idempotent: rows keyed by the mocks' ids are inserted or updated, collections the demo owns are replaced. Running it again later moves the demo to the new week and resets answers given on demo rides.
- The mocks only carry totals for other riders ("23 riders flagged it", "28 riders answered here"). Since the API counts distinct riders, `seed/panel.py` writes one row per rider: pseudonymous keys, spread over the period, some on foot.
- The demo describes a Thursday evening. With `UMI_PIN_CLOCK_TO_DATASET` (default outside production), "now" is that moment (`dataset_snapshots.demo`), so "this week", "today" and "last 7 days" read like the mocks' `mockNow()`. Without a seeded dataset the system clock is used.

## Tests and parity with the mocks

`backend/tests/parity/mock-responses.json` is what `src/lib/api.ts` answers at a frozen instant, recorded by running the TypeScript mocks in Node. The tests seed the database from the same JSON at the same instant and compare endpoint by endpoint. Regenerate it after changing the mocks or `api.ts`:

```bash
node --experimental-transform-types --no-warnings --import ./backend/tests/parity/hooks.mjs backend/tests/parity/generate.mjs
```

Where the backend answers differently on purpose, the tests say so:

- Event and flag times are formatted from stored instants (start + the sample's clock). The mocks keep the original `HH:mm` strings, which are an hour off once the week shift crosses a daylight-saving change; one hand-placed flag time (`laia-20260926-1044-f0`, 11:00) is also a minute off its sample (11:01).
- Cause mixes are rounded from real per-rider answer counts, so a share can differ by 10 % from the mocks' idealised mixes (counts, thresholds and hs-1's mix match).
- With `mode=bike` or `mode=run`, riders and answers are counted on that kind of activity; the mocks rescaled the totals (and counted every rider for "Bike" on city hazards).
- Live hazards are listed most confirmed first, not in the mocks' file order.

The other City Insights filters still rescale one stored snapshot with the mocks' factors (`domain/city.py`), until the pipeline aggregates per period and mode.

## Ingest

`POST /v1/ingest/sessions` takes the trimmed session log exactly as the phone (today the simulator) re-encoded it (`protocol/README.md` §1-3) and answers once it is processed: synchronously, a ride is a few hundred milliseconds (ADR 0004). `services/ingest.py` is the use case; the stages are plain functions in `pipeline/`. Uploads are processed one at a time (`db/locks.py`: an `asyncio.Lock`, plus a transaction-scoped advisory lock on Postgres so several API processes queue too): each upload reads what the previous one wrote, so riders who flag the same corner at the same moment join one hazard instead of opening one each.

```mermaid
flowchart LR
  B[".umis body<br/>≤ 2 MiB"] --> R["read_upload<br/>decode · trimmed · complete<br/>TIME_SYNC · simulated"]
  R --> P{"Clip paired with<br/>the caller?"}
  P -- no --> F[403]
  P -- yes --> D{"(device, session)<br/>already stored?"}
  D -- yes --> S200["200, first receipt"]
  D -- no --> T["build_track<br/>plausibility"]
  T --> M["map_match<br/>street index"]
  M --> C["RideContext<br/>scores · hotspots<br/>open hazards · key · flags today"]
  C --> X["process<br/>flags · events · questions<br/>hazards · report · passes<br/>exposure · device"]
  X --> W[("one transaction<br/>activity · hazards<br/>confirmations · passes<br/>exposure · Clip · receipt")]
  W --> A["aggregate the<br/>ridden segments<br/>(UMI_AGGREGATE_ON_INGEST)"]
  A --> S201["201, receipt"]
```

| Status | When |
| --- | --- |
| `201` | `{"activityId", "segmentsMatched", "flags": {"accepted", "rejected"}, "events"}` |
| `200` | The same `(device_id, session_id)` was already uploaded: the first receipt, nothing duplicated (a retry racing the original also gets it). |
| `401` / `403` | Unknown rider; the Clip is unknown or paired with someone else. |
| `409` | The session is stored without a receipt (a demo ride imported by the seed). |
| `413` / `415` | Over 2 MiB (refused while reading); not `application/vnd.umi.session`. |
| `422` | Not a valid v1 log, not trimmed, incomplete (no `END`), no `TIME_SYNC`, simulated while `UMI_ACCEPT_SIMULATED` is off, or implausible (below). The `detail` says which. |
| `503` | The street network is not seeded. |

**Plausibility** (`domain/plausibility.py`, `pipeline/track.py`). Telemetry is not signed (the phone trims it), so it is checked:

- the session is refused when it ends in the future (beyond 5 min of clock drift) or more than a year ago, has fewer than two fixes inside Barcelona (`SERVICE_AREA`), or more than 20 % of its fixes are faster than the activity allows (60 km/h riding, 30 km/h running: a car or a train);
- single fixes are dropped when they are outside Barcelona, too fast, or a jump from the previous fix beyond the activity's speed plus 20 m of GNSS error (multipath); after three jumps in a row the new position is followed;
- timestamps that go back are refused by the decoder; a Clip that does not say what it recorded is a ride when its median moving speed is 12 km/h or more.

**Map matching** (`pipeline/matching.py`). The ~335 segments are indexed in a 50 m grid of edges, in memory, built on the first upload (`services/street_network.py`; restart the API after re-seeding). A fix goes to the nearest edge within 30 m whose axis is within 45° of the GNSS course; the current segment wins unless another is 8 m closer, so junctions do not flicker; blips of one or two fixes between two runs of the same segment are smoothed. A run of at least 2 fixes and 60 m is a pass. On the test corridor with 4 m of GNSS noise, 95+ % of fixes land on the right segment (`tests/ingest/test_ingest_pipeline.py`).

**The ride.** Distance and durations include the trimmed ends (`TRIM` metres, session clock), the trace and the samples do not: samples start 200 m in. Samples are `[t s, distance m, speed km/h, vib, PM2.5, dB, route index]`, at most 1,800 per report; PM2.5 holds the last `AIR` reading; a sensor that never reported reads as the street's typical value (and never feeds street scores). Scores use the `domain/scoring.py` conversions (`score.ts`); each segment row compares this pass with the street at that hour (`streetAverage`). The temperature is the Clip's own (`weather.condition` says so until a weather lookup exists); there is no elevation in protocol v1.

**Events.** Clip `EVENT` records (hard brake, pothole; a record repeated with the same kind and time counts once) plus derived `pm_spike` (`AIR` ≥ `detection.pm_spike_ugm3`) and `noise_peak` (`SAMPLE` ≥ `detection.noise_peak_dba`): readings above the threshold form an episode until two minutes below it, one event at the episode's peak. A brake within 40 m of a hotspot joins it (`hotspot_id`). At most `reports.max_questions_per_ride` brakes get `ask` (`domain.reports.pick_questions`): first a brake at a hotspot whose cause mix is not published yet (it brings the junction closer to 5 riders), then a brake away from any hotspot (new information), then one at a published hotspot; within a rank the harder, then the earlier; one per hotspot; never a brake that a flag pressed within 30 s already explains.

**Flags** (`pipeline/flags.py`). Undone flags (`FLAG_UNDO`) are ignored, not rejected. Each other flag is kept only if its signature verifies against the paired Clip's key, it was pressed inside Barcelona, and the rider has fewer than 20 flags that Barcelona day; otherwise it counts as rejected, never the whole ride. A recognised keyword (confidence ≥ `button.keyword_min_confidence`) is `keyword_kind`. A kept flag joins the nearest open hazard of a compatible kind (same kind, or either says none) within `reports.hazard_merge_radius_m`, or opens one that takes the flag's id; a pothole the Clip felt that close to an open pothole hazard confirms it too (`source = sensor`).

**Hazard lifecycle** (`domain/hazards.py`). One `hazard_confirmations` row per hazard and distinct rider (`rider_key` = athlete id): flagging the same place again only updates the time. After each upload the touched hazards are recounted: `pending` → `verified` at `privacy.map_min_riders` (on `/v1/hazards`) → `sent_to_city` at `privacy.city_min_riders` (`city_status = new`, on `/v1/city/hazards`); never backwards. The read endpoints still count distinct riders at query time (ADR 0006). Expiry, fixes with sensor proof and `riders_warned` are the lifecycle job's (see the follow-ups).

**Street passes and exposure.** One `segment_passes` row per segment and hour the pass began in (UTC hour starts are Barcelona hour starts; aggregation reads them in local time), with the rider, the mean vibration (rides only), PM2.5 and dB, and hard brakes at half weight until answered: a cause given later re-weighs them (`brake_weight`). The ride's minutes, ride-weighted PM2.5 and dB and dose are added to the rider's Barcelona day in `exposure_days`. The Clip gets its battery (last `STATUS`), firmware and last sync.

### Street scores

`services/aggregation.py` (`umi-api aggregate`, or after each upload for the ridden segments with `UMI_AGGREGATE_ON_INGEST`) publishes `segment_hourly_scores` from `segment_hourly_baselines` (the seeded scores) and the passes of the last 30 days, per segment and local hour (`domain/aggregation.py`):

- a segment-hour moves only once `privacy.segment_hour_min_riders` distinct riders passed there; one rider passing often, or four riders, leave the baseline as is;
- each dimension merges the baseline (worth 10 passes) with what was measured: comfort from rides' vibration (a runner's IMU measures strides), safety from weighted hard brakes per 100 ride passes, air and noise from everyone;
- every hour of the given segments is rewritten, so hours whose passes aged out go back to the baseline; the segments' all-day scores are the rounded mean of their hours, as in the mock generator. Run on the seeded demo alone, it changes nothing.

### Development pairing

Real Clips get their key at a factory step and pair from the companion app; neither exists yet. `POST /v1/dev/devices` (absent in production) registers a simulated Clip and its rider in one call:

```json
{"deviceId": "1f2e3d4c5b6a7980", "serial": "UMI-SIM-0001", "publicKeyPem": "-----BEGIN PUBLIC KEY-----...", "hwRev": 0,
 "firmware": "0.9.0", "simulated": true, "athlete": {"id": "sim-0001", "name": "Sim Rider 1", "vehicle": "e-bike"}}
```

It creates or updates the rider (development riders have no age: `0`), registers the Clip and pairs it, and answers `{"deviceId", "athleteId", "token": "dev:<athleteId>"}`: `201` the first time, `200` when the Clip is already registered with the same key (it may move to another rider), `409` for another key or a serial another Clip uses, `422` for a key that is not P-256 in PEM. The simulator (`simulator/`) pairs and uploads through it.

### Testing the ingest

`tests/ingest/` is a package (its helpers import relatively under pytest's importlib mode). `sessions.py` synthesises a ride along the seeded segments' coordinates at 1 Hz with `AIR`, `STATUS` and `TIME_SYNC` records, places hard brakes, presses (signed with deterministic software keys, or unsigned, or forged; undone or not) and noisy or polluted stretches by distance, adds GNSS noise, and trims it with `umi_protocol.trim_session`. The API under test receives uploads at the demo's pinned moment, on a private copy of the seeded database.
