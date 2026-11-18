# UMI simulator (`umi-sim`)

Fake hardware until the Clips arrive. Virtual riders ride the real Barcelona street graph of the web app's mock data; a virtual Clip records each ride into the same `.umis` session log the firmware writes (signed flags included); then the simulator plays the phone: privacy trim and upload. It can also export a ride as raw sensor streams for the firmware's SIL build.

```
streets.json ──▶ network ──▶ route ──▶ rider ──▶ button ──▶ sensors ──┬──▶ Clip ──▶ .umis ──▶ phone: trim ──▶ POST /v1/ingest/sessions
potholes, hotspots, flags (world)                                    └──▶ scenario ──▶ firmware SIL (pio run -e sil)
```

Everything is deterministic: the same seed gives the same ride, and the same ride recorded by the same Clip gives the same bytes (flag signatures are deterministic, RFC 6979).

## Quick start

From the repository root (Python 3.13 through uv, see the root `pyproject.toml`):

```bash
uv sync --all-packages --all-groups

uv run umi-sim places                      # named places (accents and case optional)
uv run umi-sim network                     # how much of the mock network is routable
uv run umi-sim ride --from "Gràcia" --to "22@" --at 2026-11-18T07:50 --rider sim-0001 --out out/ride.umis
uv run umi-protocol inspect out/ride.umis  # read it back with the reference codec
uv run umi-sim upload out/ride.umis --api http://localhost:8000
uv run umi-sim fleet --riders 40 --days 14 --seed 7                     # files only, under simulator/out/fleet
uv run umi-sim fleet --riders 40 --days 14 --seed 7 --api http://localhost:8000
uv run umi-sim scenario --from "Gràcia" --to "22@" --at 2026-11-18T07:50 --out scenario.txt
```

`python -m umi_sim` is the same command. Output goes to `simulator/out/` (gitignored) unless `--out` says otherwise.

| Command | Does |
| --- | --- |
| `places` | Lists the named places: a junction of the network each, with what it is good for (home, work, leisure). |
| `network` | Connectivity of the graph built from `streets.json` (327 of 335 segments, 97.6 % of the length, are in the routable component; the Ciutat Vella avenues are islands in the mock data). |
| `ride` | One ride: `--from`/`--to` (a place or `lat,lon`), `--at` (ISO 8601, Barcelona time unless it has an offset; default now), `--rider`, `--vehicle` (`e-bike`, `bike`, `scooter`, `run`; default: the rider's own), `--route fastest\|calmest`, `--seed`. Writes the Clip's session and prints what the phone would trim. |
| `upload FILE...` | Plays the phone for sessions a simulated Clip wrote: pairs the Clip (dev endpoint), trims each session and uploads it. `--api` or `$UMI_API_URL`. Exit 1 if any upload failed. |
| `fleet` | `--riders N` × `--days D` from `--start` (default: the last D days), `--seed`. Writes the files (`--out`, the default without `--api`) and/or uploads them (`--api`, at most `--concurrency` in flight). |
| `scenario` | A ride as a firmware SIL scenario (`protocol/sil-scenario.md`). |

Common options: `--data` (mock datasets; default `$UMI_SIM_DATA_DIR`, else `src/lib/mock/data`) and `--keys` (simulated Clips' keys; default `$UMI_SIM_KEYS_DIR`, else `~/.umi-sim/keys`).

## How a ride is made

| Module | What it models |
| --- | --- |
| `world.py` | The web app's mock datasets as typed values: 335 scored segments with 24 hourly scores and surface RMS, confirmed potholes, hard-brake hotspots, and the hazards riders flagged (`flags.json`, fixed ones excluded). |
| `network.py` | Segments are cut every few blocks, so a cross street usually meets one in its middle. The graph splits every segment where another crosses or ends on it (5 m tolerance), merges points closer than that into junctions and keeps the largest component. Dijkstra routes *fastest* (length / nominal riding speed per street kind and bike lane) or *calmest* (the same time, inflated on streets with a low overall score at that hour: Gràcia → 22@ at 8:00 takes 4 more minutes for an overall score of 64 instead of 47). |
| `places.py` | 21 named places, each a junction (`Gràcia` = Gran de Gràcia × Travessera, `22@` = Llacuna × Pallars...). |
| `rider.py` | A speed profile planned like vehicle motion: a limit at every metre (cruising pace per vehicle, street and rider, junction and turn slow-downs, red lights at junctions with traffic lights, the odd mid-ride stop long enough to auto-pause, hard brakes), one forward pass with the rider's acceleration and one backward pass with their braking. Hard brakes (3.2–5.5 m/s²) are drawn near hotspots (more at their peak hour) and as often as the streets' safety scores imply (`brakesFromSafetyScore`). Runners never brake hard. |
| `hazards.py` | The rider's thumb. Passing a hazard, they press with a probability set by the rider and by the hazard (roadworks are more striking than a hotspot). Riders with voice keywords on (opt-in, about a quarter) mostly hold and say the word; a slip of the thumb is usually undone with a double press. |
| `sensors.py` | What the Clip would read, per whole second: GNSS (1 Hz, slowly wandering error scaled by HDOP, worse in Gràcia's narrow streets, warm start, the odd outage), vertical vibration RMS (segment surface RMS scaled by speed and vehicle; impacts of the potholes the rider hits and of unmapped bumps), sound (`dbFromNoiseScore` of the street at that hour, traffic fluctuation, the odd horn above 80 dB(A)), one Plantower PM frame (`pmFromAirScore`, mixed over a few seconds, the odd idling bus, swollen by humidity as a laser counter sees it); temperature and humidity (Barcelona monthly normals, daily cycle, the same for everyone that day) and battery every 10 s; what the keyword recogniser heard for each hold (wind at speed lowers the odds and the confidence). |
| `clip.py` | The virtual Clip. Its recorder follows the firmware's (`firmware/lib/umi_core/src/recorder.c`): a session starts after 5 s above 6 km/h with a fix, SAMPLE every second while recording, AIR every 10 s (PM averaged, PM2.5 corrected for humidity with `[air]` kappa) and STATUS every 60 s for the whole session, auto-pause after 30 s still, END 300 s after the rider stopped, TIME_SYNC with the first fix after the start (the fix that starts a session is read before the session exists). EVENTs apply the `[detection]` rules (hard brake: mean > 3 m/s² for ≥ 300 ms, 3 s refractory; pothole: 1 s RMS ≥ 4 m/s² with a peak ≥ 12 m/s², 1.5 s refractory; none on runs). FLAG and FLAG_UNDO follow `umi_core/src/flags.c` (keyword kept only from 70 % confidence, one undo per flag) and every flag is signed with the Clip's P-256 key. Records are written in time order with `umi_protocol.SessionWriter`; records sharing a `t_ms` keep the order of one firmware step (time sync, state, sample, air, status, flags, events). |
| `phone.py` | Pairs a Clip, trims with `umi_protocol.trim_session` (200 m each end, nothing under 500 m) and uploads the trimmed bytes. Retries network errors and 5xx with exponential backoff (0.5 s, 1 s, 2 s...); a 4xx is final. |
| `scenario.py`, `frames.py` | SIL export: 100 Hz IMU (gravity on +z, x forward, y left; accelerations, turn rate, road vibration, impacts and hard brakes of the same ride), `$GNRMC`/`$GNGGA` with valid checksums, 32-byte Plantower frames as hex, 10 Hz sound levels, environment, battery, button edges (with contact bounce now and then) and keyword results. |
| `fleet.py` | Riders `sim-0001`... Who they are (vehicle mix 35 % e-bike, 30 % bike, 15 % scooter, 20 % runners; home and work junctions near named places; pace; flag habits; fastest or calmest) depends only on their id. The seed decides each day: commutes on most weekdays around 8:00 and 18:15, weekend outings to the seafront, runs out to the sea and back. Each Clip's battery carries over from ride to ride and is recharged overnight below 25 %. |

All shared numbers (rates, detection thresholds, button timings, privacy distances, the humidity kappa) come from `protocol/constants.toml` through `umi_protocol.constants`.

## Identities, keys and session ids

A rider's Clip is provisioned on first use: a random `device_id` and P-256 key, stored as `<rider>.json` and `<rider>.key.pem` (mode 0600) in the keys directory, then reused so the backend keeps verifying its flags. Delete the directory to get new Clips. These are simulated devices: the header carries the `simulated` flag and hardware revision 0, and production refuses them.

The firmware numbers sessions with a counter kept in flash. A virtual Clip numbers them by their start minute since 2024-01-01 UTC instead: ids still increase (a Clip cannot start two sessions in one minute: one lasts at least the 300 s auto-stop), and re-running a ride or a fleet gives the same `(device_id, session_id)`, which the backend deduplicates (`200`) rather than storing the ride twice. The flip side: two *different* rides simulated for one rider starting in the same minute (say, the same `--at` with another `--seed`) share an id, and the backend keeps the first.

## Backend contract

Development pairing, idempotent:

```
POST {api}/v1/dev/devices
{"deviceId": "<16 hex>", "serial": "UMI-SIM-0001", "publicKeyPem": "...", "hwRev": 0, "firmware": "0.1.0",
 "simulated": true, "athlete": {"id": "sim-0001", "name": "Sim Rider 1", "vehicle": "e-bike"}}
→ 201 (or 200 if known) {"deviceId", "athleteId", "token"}
```

Upload, as in `protocol/README.md` §3: `POST {api}/v1/ingest/sessions` with `Authorization: Bearer <token>`, `Content-Type: application/vnd.umi.session` and the trimmed `.umis` as the body → `201`/`200` `{"activityId", "segmentsMatched", "flags": {"accepted", "rejected"}, "events"}`. The backend must accept simulated sessions (`UMI_ACCEPT_SIMULATED`).

## Firmware SIL

```bash
uv run umi-sim scenario --from "Gràcia" --to "22@" --at 2026-11-18T07:50 --out scenario.txt
```

Time is milliseconds since power-on, 5 s before the rider moves off, and the scenario runs until the Clip has auto-stopped. The same ride's `.umis` from `umi-sim ride` (same places, time, rider and seed) is the simulator's own reading of it, and the firmware agrees with it:

```bash
(cd firmware && pio run -e sil)
firmware/.pio/build/sil/program --scenario scenario.txt --out sil.umis \
  --device-id <the Clip's device id> --session-id <the ride's session id> --activity ride \
  --key-hex <its key, umi_protocol.private_key_to_raw_hex>
```

`tests/test_sim_firmware_sil.py` (marker `e2e`, skipped until the SIL program is built; `$UMI_SIL_PROGRAM` overrides its path) does this for a ride, a scooter ride and a run, and checks that both sessions have the same header, duration, states, TIME_SYNC, sample times and fixes, AIR records (±1 unit), flags (seq, source, keyword; time within the debounce delay; the firmware's signatures verify with the Clip's key) and undos. On rides it checks the events too: same kinds, start times within 300 ms. What differs is the firmware's own signal processing: vibration and dB(A) computed from the IMU and the synthesised PCM, positions and speeds rounded through NMEA, and event values measured on the 100 Hz IMU. On runs the firmware's pothole detector still fires on stride impacts, while the simulator records no events on runs, matching the product's choice of no surface data for runners.

## Tests

```bash
uv run pytest simulator/tests
uv run ruff format simulator && uv run ruff check simulator
uv run mypy simulator/src
```

The suite (~6 s; `-m "not e2e"` leaves out the firmware comparison) covers the graph and routing, rider kinematics and determinism, sensor ranges (PM2.5 5–35 µg/m³, noise 50–80 dB(A), brakes > 3 m/s²), the recorder's records and states, flag signatures, the phone against a mocked backend (trimmed body, headers, retries), scenario validity (NMEA and Plantower checksums, 100 Hz IMU, debounced button gestures), a small fleet, to files and uploaded, and the firmware SIL against the virtual Clip (above).

## Limits

- No elevation: the mock data is flat, so slopes do not change speeds and the IMU has no pitch.
- The rider follows street centrelines; GNSS noise is the only lateral motion. Bikes do not lean in turns.
- Wind noise on the microphone is not modelled (the Clip filters it; see `docs/signalement-mains-libres.md`).
- Runners' strides are a sine at their cadence: enough to make the vibration RMS realistic, not a gait model.
