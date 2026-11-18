# UMI protocol v1

The contract between the Clip, the phone and the backend. One binary format is used end to end: the Clip writes a **session log** (`.umis`) to its flash, the phone pulls it over BLE, trims it for privacy, re-encodes it with the same codec and uploads it as is. Nothing is translated to another format on the way, so one codec per language is enough and every component can be tested against the same golden files.

```
Clip (ESP32-S3)                       Phone (companion app)                    Backend
───────────────                       ─────────────────────                    ───────
sensors → detectors → session log ──BLE──▶ decode → privacy trim → re-encode ──HTTPS──▶ verify → process → aggregate
          flags signed on the Clip         (200 m each end, drop short trips)           (flag signatures, map matching,
                                                                                         k-anonymity, scores)
```

| Path | What |
| --- | --- |
| `constants.toml` | Every shared number and enum (thresholds, record types, wire codes). The only place to change them. |
| `codegen/generate.py` | Generates `firmware/lib/umi_protocol/include/umi/protocol_gen.h`, `protocol/python/src/umi_protocol/constants.py` and `src/lib/generated/protocol.ts`. `--check` fails on drift (CI). |
| `python/` | `umi-protocol`, the reference codec in Python: encode/decode, privacy trim, flag signing. Used by the backend and the simulator. |
| `vectors/` | Golden session files and their expected decoding. Every codec (C, Python, later TS) must read them identically, and the C encoder must reproduce them byte for byte. |

Conventions: little-endian, no padding, integers in fixed-point units given in the field name (`_e7` = degrees × 10⁷, `_cms` = cm/s, `_mms2` = mm/s², `_cdba` = 0.01 dB(A), `_dug` = 0.1 µg/m³, `_cc` = 0.01 °C, `_dpct` = 0.1 %). `0xFFFF` in an unsigned 16-bit measurement means *not available* (sensor off or not ready; `[format] not_available_u16`). Reserved bytes are written as zero and ignored by readers.

## 1. Session log (`.umis`)

```
┌────────────┬──────────┬──────────┬─────┬──────────┬──────────┐
│ header 32 B │ record 1 │ record 2 │ ... │ record n │ END      │
└────────────┴──────────┴──────────┴─────┴──────────┴──────────┘
```

A session is one ride or run, from motion start to auto-stop. The Clip appends records as they happen; a session cut short (battery, crash) simply has no `END` record and is still readable up to the last valid record.

### 1.1 Header (32 bytes)

| Offset | Size | Field | Notes |
| --- | --- | --- | --- |
| 0 | 4 | `magic` | ASCII `UMIS` |
| 4 | 1 | `format_version` | `1` |
| 5 | 1 | `header_len` | `32`; readers skip to this offset, so later versions may grow the header (bytes past 32 are covered by `file_crc32` only) |
| 6 | 2 | `header_flags` | bit 0 `simulated` (simulated sensor drivers), bit 1 `trimmed` (re-encoded by the phone after the privacy trim) |
| 8 | 8 | `device_id` | u64, burnt in at provisioning; shown as 16 lowercase hex digits |
| 16 | 4 | `session_id` | u32, per-device counter, never reused |
| 20 | 1 | `activity` | `0` unknown, `1` ride, `2` run |
| 21 | 1 | `hw_rev` | board revision, `0` = devkit / simulator |
| 22 | 3 | `fw_version` | major, minor, patch |
| 25 | 3 | reserved | zero |
| 28 | 4 | `header_crc32` | CRC-32/ISO-HDLC (zlib `crc32`) of bytes 0–27 |

### 1.2 Record framing

| Size | Field |
| --- | --- |
| 1 | `type` (see `[enum.record_type]`) |
| 1 | `len`, payload length 0–255 |
| `len` | payload; **always starts with `t_ms`** (u32, milliseconds since the session started, monotonic clock) |
| 2 | `crc16`: CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, no xor-out) of `type`, `len` and the payload |

Records are in non-decreasing `t_ms` order. An `EVENT` is stamped with its start and a voice `FLAG` with the moment of the press, but both are only complete later: the writer holds back the records that follow (a reorder buffer of a few seconds) rather than break the order, and readers reject a session whose `t_ms` goes back. A reader skips record types it does not know (forward compatibility) and stops at the first record whose CRC fails, reporting the session as truncated. A record type never changes meaning within a format version; fields are only ever appended at the end of a payload, so readers must accept a `len` larger than the one they know and ignore the extra bytes.

### 1.3 Records

**`SAMPLE` (1) — 24 bytes, once per second while recording.**

| Off | Size | Field |
| --- | --- | --- |
| 0 | 4 | `t_ms` u32 |
| 4 | 4 | `lat_e7` i32 |
| 8 | 4 | `lon_e7` i32 |
| 12 | 2 | `speed_cms` u16 (GNSS ground speed) |
| 14 | 2 | `heading_cdeg` u16 (0–35999) |
| 16 | 2 | `vib_mms2` u16 — RMS over the last second of the vertical acceleration with gravity removed |
| 18 | 2 | `noise_cdba` u16 — LAeq over the last second |
| 20 | 1 | `hdop_d` u8 (HDOP × 10, 255 = unknown, `[format] hdop_unknown`) |
| 21 | 1 | `fix` u8 (`0` none, `2` 2D, `3` 3D); without a fix `lat`, `lon`, `speed`, `heading` are 0 and must be ignored |
| 22 | 1 | `sats` u8 |
| 23 | 1 | reserved |

**`AIR` (2) — 16 bytes, every 10 s.**

| Off | Size | Field |
| --- | --- | --- |
| 0 | 4 | `t_ms` |
| 4 | 2 | `pm1_dug` u16 |
| 6 | 2 | `pm25_dug` u16 (humidity-corrected on the Clip) |
| 8 | 2 | `pm10_dug` u16 |
| 10 | 2 | `temp_cc` i16 |
| 12 | 2 | `rh_dpct` u16 |
| 14 | 2 | reserved |

**`EVENT` (3) — 20 bytes, detected on the Clip from the 100 Hz IMU.**

| Off | Size | Field |
| --- | --- | --- |
| 0 | 4 | `t_ms` (start of the event) |
| 4 | 1 | `kind` (`1` hard brake, `2` pothole) |
| 5 | 1 | reserved |
| 6 | 2 | `value_mms2` u16 — what the app shows: mean deceleration for a brake, 1 s vibration RMS for a pothole |
| 8 | 2 | `peak_mms2` u16 — instantaneous peak |
| 10 | 2 | `duration_ms` u16 |
| 12 | 4 | `lat_e7` i32 (last fix) |
| 16 | 4 | `lon_e7` i32 |

Detection rules (`[detection]`): hard brake = longitudinal deceleration > `hard_brake_mps2` for at least `hard_brake_min_ms`, then `hard_brake_refractory_ms` before the next one; pothole = 1 s vertical RMS ≥ `pothole_rms_mps2` with an impact peak ≥ `pothole_peak_mps2`. `pm_spike` and `noise_peak` are *not* Clip events: the backend derives them from `AIR` and `SAMPLE`.

**`FLAG` (4) — 94 bytes, the rider pressed the button.**

| Off | Size | Field |
| --- | --- | --- |
| 0 | 4 | `t_ms` (moment of the press) |
| 4 | 2 | `seq` u16, per session, from 0 |
| 6 | 1 | `source` (`1` press, `2` voice) |
| 7 | 1 | `kind` (`[enum.hazard_kind]`, `0` = no keyword: the rider says what it was after the ride) |
| 8 | 1 | `confidence` 0–100 (keyword recogniser; 0 for a press) |
| 9 | 1 | `lang` (`[enum.lang]`) |
| 10 | 2 | reserved |
| 12 | 4 | `lat_e7` i32 |
| 16 | 4 | `lon_e7` i32 |
| 20 | 2 | `speed_cms` u16 (sensor snapshot) |
| 22 | 2 | `vib_mms2` u16 |
| 24 | 2 | `noise_cdba` u16 |
| 26 | 2 | reserved |
| 28 | 1 | `sig_alg` (`0` none, `1` ECDSA P-256) |
| 29 | 1 | `sig_len` (`64` or `0`) |
| 30 | 64 | `signature`, raw `r ‖ s` big-endian, zero-filled when unsigned |

A voice flag whose keyword was not understood, or recognised below `keyword_min_confidence`, is written with `kind = 0`: nothing is lost, the rider answers after the ride.

**`FLAG_UNDO` (5) — 6 bytes:** `t_ms`, `seq` u16 of the flag cancelled by a double press. Readers drop that flag.

**`STATUS` (6) — 12 bytes, every 60 s:** `t_ms`, `battery_pct` u8, `flags` u8 (`[enum.status_flag]`), `battery_mv` u16, `board_temp_cc` i16, `free_kib` u16 (flash left for sessions).

**`TIME_SYNC` (7) — 12 bytes:** `t_ms`, `unix_ms` i64 (UTC). Written at the first GNSS fix and when the phone sets the time. Absolute time of any record = `unix_ms − sync.t_ms + record.t_ms`, using the first `TIME_SYNC`. A session without one cannot be placed in time and is rejected by the backend.

**`STATE` (8) — 6 bytes:** `t_ms`, `state` u8 (`1` recording, `2` auto-pause, `3` resume), reserved u8.

**`TRIM` (9) — 8 bytes, written by the phone only, right after the header:** `t_ms` = 0, `start_m` u16, `end_m` u16 (metres removed at each end).

**`END` (127) — 16 bytes, last record:**

| Off | Size | Field |
| --- | --- | --- |
| 0 | 4 | `t_ms` (session duration) |
| 4 | 4 | `record_count` u32, records before `END` |
| 8 | 4 | reserved |
| 12 | 4 | `file_crc32`, CRC-32/ISO-HDLC of every byte from offset 0 up to (excluding) the `END` record's `type` byte |

### 1.4 Flag signatures

Flags can send a city crew to a street, so each one is signed by the Clip that made it, with a key that never leaves the device (ESP32-S3 flash encryption + eFuse-protected key, see `docs/architecture/adr/0005-device-identity.md`).

```
message   = "UMI-FLAG-v1" (11 ASCII bytes) ‖ device_id (u64 LE) ‖ session_id (u32 LE) ‖ FLAG payload bytes 0–27
signature = ECDSA-P256( SHA-256(message) ), encoded raw r ‖ s (2 × 32 bytes, big-endian)
```

The signed part covers time, sequence, source, keyword, position and the sensor snapshot. It does **not** cover the kind a rider picks after the ride: that is an answer from the rider's account, not a device measurement. The backend stores `(device_id, session_id, seq)` as unique, so a replayed flag is ignored.

Telemetry (`SAMPLE`, `AIR`, `EVENT`) is not signed: the phone has to remove records for the privacy trim, which would break any signature over the whole log. Its integrity rests on the paired device and the authenticated rider (plausibility checks run server-side).

## 2. Privacy trim (on the phone, before upload)

The reference implementation is `umi_protocol.trim` (Python); the mobile app must match it on the golden vectors.

1. Compute the cumulative distance `d` along `SAMPLE` records that have a fix (`fix` ≥ 2), joining consecutive fixes and skipping samples without one: haversine `2·R·asin(√a)` with `R` = `[geo] earth_radius_m`, in metres, double precision. `total` is `d` at the last fix.
2. If the total is below `min_upload_distance_m` (500 m), **upload nothing**: a short trip is too close to someone's door.
3. Let `t_start` be the time of the first sample with `d ≥ trim_m` (200 m) and `t_end` the time of the last sample with `total − d ≥ 200 m`. If `t_start > t_end` (fixes too sparse), upload nothing. Drop every `SAMPLE`, `AIR`, `EVENT`, `FLAG` and `STATE` record, and every record of a type the phone does not know (it may carry a position), with `t_ms < t_start` or `t_ms > t_end`. Drop `FLAG_UNDO` the same way unless the flag it cancels is kept: it carries no position, and dropping it would revive a flag the rider cancelled. Keep `TIME_SYNC` and `STATUS`.
4. Write a `TRIM` record right after the header (`start_m` = ⌊`d` at `t_start`⌋, `end_m` = ⌊`total − d` at `t_end`⌋, capped at 65535), set the `trimmed` header flag, recompute the header CRC, and write a new `END` (`record_count`, `file_crc32` recomputed; `t_ms` kept, or the last record's `t_ms` for a session cut short, which comes out complete). Record payloads are copied byte for byte, so flag signatures stay valid.

A session that already has the `trimmed` flag is refused: trimming twice would cut another 200 m from each end, and `TRIM` would no longer say what was removed.

The backend refuses a session without the `trimmed` flag (`422`), so an untrimmed trace is never stored, whatever client sent it.

## 3. Upload (phone → backend)

```
POST /v1/ingest/sessions
Authorization: Bearer <rider token>
Content-Type: application/vnd.umi.session
<trimmed .umis bytes>
```

| Status | When |
| --- | --- |
| `201` | Processed. Body: `{ "activityId", "segmentsMatched", "flags": { "accepted", "rejected" }, "events" }` |
| `200` | Same `(device_id, session_id)` already uploaded: same body, nothing duplicated (safe retries) |
| `401` / `403` | Unknown rider, or the Clip is not paired with this rider |
| `413` | Larger than 2 MiB |
| `422` | Not a valid v1 log, no `TIME_SYNC`, not trimmed, or a simulated session while `UMI_ACCEPT_SIMULATED` is off |

Flags with a bad or missing signature are dropped one by one (counted in `rejected`), never the whole ride.

## 4. BLE GATT (Clip ↔ phone)

One primary service. UUIDs share the base `b6d2xxxx-6a1e-4c3f-9a9e-2f1c0b5e4d01`, where `xxxx` is the 16-bit id below. LE Secure Connections with bonding is required for every characteristic except Device Info.

| Id | Characteristic | Props | Payload |
| --- | --- | --- | --- |
| `0x0000` | Service | | |
| `0x0001` | Device Info | read | `device_id` u64, `hw_rev` u8, `fw` 3×u8, public key (65 B uncompressed P-256), serial (ASCII, rest) |
| `0x0002` | Live Status | read, notify | `battery_pct` u8, `status_flags` u8, `recorder_state` u8, `fix` u8, `sessions_pending` u16 |
| `0x0003` | Session Index | read | n × (`session_id` u32, `size` u32, `first_unix_s` u32) |
| `0x0004` | Control Point | write, indicate | opcode u8 + args: `0x01` START_TRANSFER(session_id u32, offset u32), `0x02` ACK(chunk_seq u16), `0x03` DELETE(session_id u32), `0x04` SET_TIME(unix_ms i64), `0x05` HAZARDS_BEGIN(count u16), `0x06` HAZARDS_END; indication = opcode echo + status u8 |
| `0x0005` | Transfer Data | notify | `chunk_seq` u16 + up to MTU − 5 bytes of the `.umis` file; the phone ACKs every 16 chunks, the Clip resends from the last ACK after 2 s |
| `0x0006` | Settings | read, write | TLV: `0x01` voice u8, `0x02` languages bitmask u8, `0x03` chirp u8, `0x04` warn_ahead u8, `0x05` sensors bitmask u8 |
| `0x0007` | Hazards | write | between HAZARDS_BEGIN/END: n × (`hazard_id` u32, `lat_e7` i32, `lon_e7` i32, `kind` u8) — verified hazards the Clip chirps for when the rider approaches (`warn_ahead_radius_m`) |

A session is deleted from the Clip only after the phone confirms the upload (`DELETE`), never on transfer alone.

## 5. Versioning

- Adding a record type, appending fields to a payload, adding an enum value: same `format_version`, readers must cope.
- Changing a field's meaning, size or order: bump `format_version`; the backend keeps decoding every version still in the field.
- `constants.toml` changes are reviewed like API changes: a threshold change alters every score.
