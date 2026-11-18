# UMI software architecture

How the pieces fit, where each rule is enforced, and how we work before the hardware arrives. Decisions and their reasons are in [`adr/`](adr).

## System

```mermaid
flowchart LR
  subgraph Clip["Clip · ESP32-S3 (firmware/)"]
    S[Sensors<br/>IMU · GNSS · PM2.5 · mic · env] --> D[Detectors<br/>brake · pothole · SPL]
    B[Flag button] --> F[Flag manager<br/>signed flags]
    D --> L[(Session log .umis)]
    F --> L
  end
  subgraph Phone["Phone · companion app (planned)"]
    T[BLE transfer] --> P[Privacy trim<br/>200 m each end]
  end
  subgraph Backend["Backend (backend/)"]
    I[Ingest<br/>verify · decode] --> M[Pipeline<br/>map matching · events · flags]
    M --> DB[(Postgres)]
    DB --> A[REST API /v1]
  end
  L -- BLE GATT --> T
  P -- "HTTPS · trimmed .umis" --> I
  A --> W["Web (src/)<br/>rider app · City Insights"]
  A --> City[Ajuntament<br/>City API · IRIS export]
  Sim["Simulator (simulator/)<br/>fake Clip + phone"] -. same .umis .-> I
```

| Component | Path | Stack | Role |
| --- | --- | --- | --- |
| Protocol | `protocol/` | TOML + codegen, Python reference codec | The contract: session format, BLE GATT, upload, shared constants. |
| Firmware | `firmware/` | C11, ESP-IDF via PlatformIO, Unity tests | Sensors → detectors → session log; flag button, chirps and LED; BLE. Runs on the host, on a bare devkit, or on the Clip board. |
| Simulator | `simulator/` | Python | Fake hardware: virtual riders on the real Barcelona street graph produce `.umis` logs exactly like a Clip, then act as the phone (trim, upload). |
| Backend | `backend/` | Python, FastAPI, SQLAlchemy, Postgres | Ingest, processing pipeline, aggregates, the `/v1` API the web app already calls. |
| Web | `src/` | Next.js | Landing, rider app, City Insights. Uses local mocks, or the backend when `NEXT_PUBLIC_API_URL` is set. |
| Mobile | — | planned | BLE transfer, privacy trim, notifications. Until it exists, the simulator plays the phone. |

## One format, end to end

The Clip's session log is the upload format (see [`protocol/README.md`](../../protocol/README.md)). The phone only removes records and re-encodes; flags keep the Clip's signature all the way to the database. Every codec is tested against the same golden files in `protocol/vectors/`, and every shared number comes from `protocol/constants.toml` through code generation, so a threshold cannot silently differ between the Clip and the server.

## Working without the hardware

The firmware is split so that only a thin layer touches the chip:

```
firmware/
  src/                  ESP-IDF app_main: tasks, wiring (target only)
  lib/umi_hal/          interfaces: imu, gnss, pm, mic, env, button, buzzer, led, battery, storage, clock, signer
  lib/umi_core/         pure C: detectors, button state machine, flags, feedback patterns, SPL, warn-ahead
  lib/umi_protocol/     session log codec, CRCs, generated constants
  lib/umi_drivers/      real drivers; frame parsers (NMEA, PM) are pure C and tested on the host
  lib/umi_sim/          simulated drivers fed by a scenario file
```

| Target | Build | Sensors | Use |
| --- | --- | --- | --- |
| Host tests | `pio test -e native` | none | Unit tests of the core, codec and parsers. |
| Host SIL | `pio run -e sil` | scenario file | The real firmware logic on a laptop: raw sensor streams in, `.umis` out. |
| Devkit | `pio run -e devkit` | simulated (`UMI_HW_SIM`) | ESP32-S3 DevKitC before the board: real RTOS, flash, BLE, button, buzzer; sensors simulated. |
| Clip board | `pio run -e clip` | real | Once the parts are in. |

Higher up, `simulator/` produces whole rides and fleets for the backend, so ingest, scoring, flag verification and City Insights can be built and load-tested on realistic data today.

## Where each rule is enforced

| Rule | Enforced in | Backstop |
| --- | --- | --- |
| First and last 200 m never leave the phone; trips under 500 m are not uploaded | phone (`umi_protocol.trim`) | backend refuses sessions without the `trimmed` flag |
| Flags come from a real, paired Clip | Clip signs (P-256); backend verifies against the paired device's key | `(device, session, seq)` unique, plausibility checks |
| Flag on everyone's map from 3 riders, City Insights from 5 | backend hazard service (`[privacy]` constants) | queries filter on distinct riders, not on stored status alone |
| A street-hour is published from 5 distinct riders | backend aggregates | — |
| "Why riders brake": 5+ riders, shares rounded to 10 %, causes under 10 % merged, "just me" excluded | backend safety service | — |
| Audio never leaves the Clip | firmware: the mic driver only exposes dB(A) and a keyword id | no audio type exists in the protocol |
| At most 2 questions per ride, never while moving | backend picks them; the app shows them after the ride | — |

## Environments

| | Local | CI | Production |
| --- | --- | --- | --- |
| Database | SQLite file (zero setup) or Postgres via `infra/docker-compose.yml` | SQLite + Postgres service | Postgres |
| Simulated Clips | accepted | accepted | refused (`UMI_ACCEPT_SIMULATED=false`) |
| Auth | dev rider `laia` by default | dev | real accounts (see the backlog) |

## Conventions

- Code, API and UI copy in English. Times are UTC on the wire; the UI shows Europe/Madrid.
- API JSON is camelCase and mirrors `src/lib/types.ts`; Python code is snake_case.
- Every component has its own README with how to build, test and run it, and its own CI job.
