# UMI Clip firmware

The Clip's firmware: sensors → detectors → signed flags → session log (`.umis`), chirps and LED, BLE. It runs without the hardware: unit tests on the host, the whole application on the host in simulated time (SIL), and on a bare ESP32-S3 DevKitC with simulated sensors ([ADR 0003](../docs/architecture/adr/0003-hardware-abstraction.md)).

Binding references: [`protocol/README.md`](../protocol/README.md) (session log, signatures, BLE), [`protocol/constants.toml`](../protocol/constants.toml) (every threshold, through the generated `lib/umi_protocol/include/umi/protocol_gen.h`), [`protocol/sil-scenario.md`](../protocol/sil-scenario.md) (SIL input). Parts and pins: [`docs/hardware/assumptions.md`](../docs/hardware/assumptions.md).

## Layout

```
firmware/
  platformio.ini        environments (below)
  sdkconfig.defaults    ESP-IDF options: N16R8 flash/PSRAM, NimBLE, FAT long names, deterministic ECDSA
  partitions.csv        nvs, otadata, phy_init, ota_0, ota_1 (3 MB each), sessions (9.9 MB FAT)
  src/                  target only: app_main, the core task, BLE GATT (NimBLE), pin map
  sil/                  host only: the SIL program (CLI, file storage, printed chirps)
  lib/
    umi_hal/            interfaces only: small vtables { fn pointers + ctx }, bundled in umi_hal_t
    umi_core/           pure C11, no ESP-IDF: button, vibration, brake, pothole, SPL, air, flags,
                        feedback, record queue, recorder, warn-ahead, geo, settings, BLE payloads,
                        and umi_clip (the application that ties them together)
    umi_protocol/       .umis codec (writer, reader, records), CRC-16/32, flag signing message,
                        protocol_gen.h (generated, never edit)
    umi_drivers/        src/parsers: NMEA, Plantower, SHT4x, MAX17048, LSM6DSO32 (pure C, host-tested)
                        src/esp32: ESP-IDF glue (target only, selected by select_sources.py)
    umi_sim/            simulated parts fed by a scenario (all HAL sensors + button), software signer
  test/
    test_*/             Unity suites (pio test -e native)
    fakes.{h,c}         shared test doubles (RAM storage, recording buzzer/LED, log reader)
    scenarios/          hand-made SIL scenarios and their generator
  scripts/run-sil.sh    SIL on every scenario, checked with the Python reference codec
```

Dependencies only point down: `src/`, `sil/` → `umi_core` → `umi_hal` → `umi_protocol`; `umi_drivers` and `umi_sim` implement `umi_hal` (the simulated GNSS and PM feed the real NMEA and Plantower parsers). Real and simulated drivers never clash at link time because they are distinct types bound into a `umi_hal_t` by whoever builds the application.

## Environments

| Env | Command | What it is |
| --- | --- | --- |
| `native` | `pio test -e native` | Unity unit tests on the host (Apple clang / gcc, `-std=c11`, warnings are errors in our code). |
| `sil` | `pio run -e sil` | Host program `.pio/build/sil/program`: the real application on simulated sensors in simulated time, scenario in, `.umis` out. |
| `devkit` | `pio run -e devkit` | ESP32-S3-DevKitC-1 N16R8, ESP-IDF 6.1, `UMI_HW_SIM=1`: sensors replay `test/scenarios/devkit-demo.scn` embedded in flash; button, buzzer, LED, flash storage, signer, BLE are real. |
| `clip` | `pio run -e clip` | The Clip board, `UMI_HW_SIM=0`, real drivers. Compiles; the sensor drivers are unverified until the parts arrive. |

Requirements: PlatformIO Core 6.2 with the `espressif32` platform (the first ESP-IDF build downloads the framework, several minutes). Python is not needed to build: generated files are committed.

```bash
cd firmware
pio test -e native                     # all unit tests
pio run -e sil && scripts/run-sil.sh   # SIL on every scenario + decode/verify with umi_protocol
pio run -e devkit -t upload            # flash a DevKitC (USB-UART port)
pio device monitor -e devkit           # logs at 115200 baud
pio run -e clip
```

## The application loop

`umi_clip_step(now_ms)` (`lib/umi_core/src/clip.c`) is the whole application, and the target and the SIL run the same one:

1. Read every part through the HAL: IMU FIFO → vibration (gravity-removed vertical RMS) → pothole and hard-brake detectors; GNSS epochs → recorder, brake cross-check, warn-ahead; PM → AIR average; mic PCM → A-weighted LAeq; battery, SoC temperature.
2. Recorder: motion start, auto-pause, auto-stop, `SAMPLE`/`AIR`/`STATUS`/`TIME_SYNC`/`STATE`.
3. Button edges → debounced gestures → flags, voice window, undo, chirps.
4. Flush records to the log in time order.

On the target one FreeRTOS task (`umi-core`, core 1) calls it every 10 ms; drivers buffer between calls (GPIO ISR queue, IMU FIFO, I2S DMA, UART buffers). BLE runs in the NimBLE host task and never calls into the core: writes are posted to the core task's inbox; Live Status and Control Point replies go back through NimBLE's event queue.

**Record ordering.** The log must be in non-decreasing `t_ms`, but several records are dated before they are known: a flag at the press (decided after the 350 ms double-press gap or the 4 s voice window), an event at its onset (a brake waits for the next GNSS fix, a pothole for the second centred on its impact). Records go through a sorted queue (`record_queue.c`) and are written only up to a horizon: `now − 1 s`, pulled back to the oldest time any producer may still report (`*_pending_since`). A record that still arrives too late is dropped and counted, never written out of order.

## SIL

```
.pio/build/sil/program --scenario PATH --out PATH --device-id HEX --session-id N
                       [--key-hex 64HEX] [--activity ride|run] [--voice on|off] [--verbose]
```

| Option | |
| --- | --- |
| `--device-id` | u64 in hex, written in the header |
| `--session-id` | id of the first session; later sessions count up |
| `--key-hex` | raw P-256 private key: flags are signed (ECDSA P-256 / SHA-256, RFC 6979 deterministic nonces, raw `r ‖ s`). Without it flags are unsigned (`sig_alg 0`). The public key is printed. |
| `--activity` | header `activity` (default `unknown`) |
| `--voice` | voice keywords setting (default `on` in the SIL so `keyword` lines are exercised; the product default is off) |
| `--verbose` | print every chirp and LED change with its time |

The program steps every 10 ms from `t = 0` to 2.5 s after the last scenario line, then closes the open session with `END` (as an auto-stop would, without scripting five still minutes). Every session gets the simulated header flag. The first session is written to `--out`; any later one next to it as `<stem>.<session_id>.umis`. Skipped scenario lines are reported on stderr with their line number. Exit codes: `0` ok, `1` usage, `2` unreadable scenario, `3` no session recorded (never moved ≥ 6 km/h for 5 s), `4` records lost (storage).

Signatures are deterministic, so a run is reproducible byte for byte, and they match the Python reference signer (`umi_protocol.signing`): the signer reproduces RFC 6979's own P-256 test vector (`test_sim`) and every signature in `protocol/vectors`.

### Scenarios

`test/scenarios/*.scn` are generated by `test/scenarios/generate.py` (standard library only, fixed seed) from a short script per ride: speed profile, road texture, shocks, button edges, keywords. Regenerate with `python3 test/scenarios/generate.py`.

| Scenario | Content | Expected `.umis` |
| --- | --- | --- |
| `ride-brake` | 40 s at 18 km/h, a 4.5 m/s² brake for 0.8 s at 20.3 s | 1 `EVENT` hard brake (mean ≈ 4.3 m/s², ≈ 770 ms) |
| `ride-pothole` | 32 s, one shock at 20 s | 1 `EVENT` pothole (RMS ≈ 4.6 m/s², peak ≈ 19 m/s²) |
| `ride-flags` | a bouncy short press, a hold + "roadworks 92 % ca", a hold + "pothole 40 % es" undone by a double press, a silent hold | 4 `FLAG` (press; voice roadworks; voice kind 0 conf 40; voice kind 0), 1 `FLAG_UNDO` of seq 2 |
| `devkit-demo` | 110 s: brake, pothole, press, hold + keyword, a red light long enough to auto-pause, double press | 2 `EVENT`, 2 `FLAG`, 1 `FLAG_UNDO`, `STATE` 1 → 2 → 3 |

```bash
scripts/run-sil.sh                      # writes .pio/sil-out/*.umis, then inspect + verify
uv run python -m umi_protocol inspect .pio/sil-out/ride-flags.umis    # from the repo root
```

```
device    00a1b2c3d4e5f601 · session 3 · ride · hw 0 · fw 0.1.0 · simulated
duration  0:00:45
status    complete
records   air 4, flag 4, flag_undo 1, sample 45, state 1, status 1, time_sync 1
flag #0   0:00:06  press  [signed]
flag #1   0:00:13  voice roadworks (92 %, ca)  [signed]
flag #2   0:00:21  voice  [signed, undone]
flag #3   0:00:34  voice  [signed]
```

`test/scenarios/sil-test-key.pub.pem` is the public half of the script's key, RFC 6979 A.2.5's published test key: TEST ONLY.

## Devkit

| Function | DevKitC-1 | Notes |
| --- | --- | --- |
| Flag button | GPIO 0 (BOOT) | active low, on board |
| LED | GPIO 48 | on-board WS2812 (board v1.1 moved it to GPIO 38) |
| Buzzer | GPIO 4 | external piezo through an NPN transistor, 2-4 kHz |
| Sensors | — | replayed from `devkit-demo.scn` from boot; the session is closed when it ends |

Everything else is real: the session files on the `sessions` FAT partition (`/sessions/<id>.umis`, ids from an NVS counter), the flag key (generated on first boot, PSA, kept in NVS), the SoC temperature, BLE. The device id is the factory MAC until provisioning writes `device_id` to NVS. The Clip's draft pin map is in [`docs/hardware/assumptions.md`](../docs/hardware/assumptions.md) and `src/board.h`.

## BLE

One primary service `b6d20000-6a1e-4c3f-9a9e-2f1c0b5e4d01` (protocol/README.md §4), LE Secure Connections only, bonding, Just Works (the Clip has no display or keys). Advertises as `UMI Clip`.

| Characteristic | State |
| --- | --- |
| `0x0001` Device Info | done: device id, hw rev, firmware, public key, serial (empty until provisioning) |
| `0x0002` Live Status | done: read and notify on change (checked every second); `recorder_state` is `0` while idle |
| `0x0003` Session Index | done: up to 40 sessions, `first_unix_s` from each file's first `TIME_SYNC` |
| `0x0004` Control Point | `SET_TIME`, `HAZARDS_BEGIN/END`, `DELETE` done; `START_TRANSFER`, `ACK` answer `0x01` unsupported |
| `0x0005` Transfer Data | declared, not sent yet (chunked transfer is a follow-up) |
| `0x0006` Settings | done: TLV read/write, persisted in NVS |
| `0x0007` Hazards | done: feeds warn-ahead between `HAZARDS_BEGIN` and `HAZARDS_END` |

Indication status byte (the spec leaves it open): `0` ok, `1` unsupported, `2` invalid, `3` not found, `4` failed.

## Detection and measurement choices

Thresholds come from `constants.toml`; what is firmware-only tuning is a named constant next to the code that uses it.

- **Vibration**: acceleration projected on a 1 s low-pass gravity estimate, so the Clip's tilt does not matter; exact integer RMS over the last 100 samples.
- **Hard brake**: x axis (forward) minus a 2 s baseline that freezes while braking, 100 ms moving average, `> 3 m/s²` for `≥ 300 ms`, dated back by the average's delay, capped at 5 s, 3 s refractory. Confirmed by GNSS: the speed between the fixes around the brake must drop by half what the IMU integrated; without GNSS the IMU decides.
- **Pothole**: a sample `≥ 12 m/s²`, decided 500 ms later on the 1 s RMS centred on it (`≥ 4 m/s²`): a knock on the Clip has the peak but not the energy. Value = that RMS, onset = first loud sample (at most 500 ms before the peak).
- **SPL**: IEC 61672 A-weighting through the bilinear transform at the mic's 16 kHz (within 0.05 dB up to 2 kHz, −0.5 dB at 4 kHz), LAeq over 100 ms blocks and their 1 s energy mean; −26 dBFS = 94 dB SPL with 0 dBFS a full-scale sine (AES17). While the voice window is open, and for the second after, `noise_cdba` is not available: the rider's own voice is not street noise.
- **PM2.5**: average of the period's frames (atmospheric values), corrected for humidity with κ-Köhler (κ = 0.38, to calibrate).
- **Motion**: moving = fix with speed ≥ 6 km/h; still = fix below it, or no fix and vibration < 0.3 m/s²; no fix while shaking (a tunnel) is neither. A start needs 5 s of motion; pause after 30 s still, resume on motion, stop after 300 s still.
- **Gestures**: a level counts after 30 ms stable and dates from its first edge; a timer whose window an edge in debounce might still fall into waits for it.

## Tests

`pio test -e native` runs 10 suites (≈ 140 cases): `test_protocol` (CRC check values, header and record layout, every record round trip, truncation, bad CRC, unknown types, END check), `test_button`, `test_detectors`, `test_spl` (calibration and A-weighting response), `test_flags` (snapshot, keyword rules, signatures verified with micro-ecc, undo, feedback patterns), `test_recorder` (lifecycle, schedule, ordering, status flags, AIR, queue), `test_ble` (geo, warn-ahead, settings TLV, BLE payloads), `test_drivers` (NMEA, Plantower, SHT4x, MAX17048), `test_sim` (SHA-256 FIPS vectors, RFC 6979 vector, scenario parser, simulated world and mic level), `test_clip` (the application end to end on simulated parts).
