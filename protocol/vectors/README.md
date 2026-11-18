# Golden vectors

Session logs (`.umis`) and their expected decoding (`.json`) that every UMI codec is tested against. They are produced by the reference implementation (`protocol/python`, `umi_protocol`) with [`generate.py`](generate.py); every byte is deterministic.

| How each codec uses them | |
| --- | --- |
| Python (`umi_protocol`) | Regenerates every file in its tests and fails if one byte changes (`test_protocol_vectors.py`). |
| C (`firmware/lib/umi_protocol`) | Encodes the inputs of `minimal` and `full` below and must produce `minimal.umis` and `full.umis` **byte for byte**; decodes every `.umis` to the values in its `.json`. |
| Phone (planned) | Decodes every file; its privacy trim of `ride.umis` must equal `ride.trimmed.umis` byte for byte. |
| TypeScript (later) | Decodes every file to its `.json`. |

## Files

| File | Covers |
| --- | --- |
| `minimal.umis` | Header, `TIME_SYNC`, 3 `SAMPLE`, `END`: the smallest useful session. |
| `full.umis` | Every v1 record type except `TRIM`: `SAMPLE` (no fix, 2D, 3D, noise not available), `AIR` (negative temperature), `EVENT` hard brake and pothole, `FLAG` signed press + signed voice with a keyword (roadworks, 92 %, ca) + unsigned press, `FLAG_UNDO` of the unsigned flag, `STATUS` (low battery), `STATE` recording / auto-pause / resume, `END`. |
| `truncated.umis` | `minimal` cut by a power loss: no `END`, and the last `SAMPLE` fails its CRC (last byte flipped). Decodes to `TIME_SYNC` + 2 `SAMPLE`, `complete: false`. |
| `unknown-record.umis` | A record type from the future (`0x42`, kept as `unknown`) and a `SAMPLE` whose `len` is 28 (4 bytes appended by a later revision, ignored). |
| `ride.umis` | A realistic 3 km ride on real Barcelona streets (below), 698 records. |
| `ride.trimmed.umis` | `ride.umis` after the privacy trim (`protocol/README.md` §2). |
| `<name>.json` | Canonical decoding of `<name>.umis` (format below). |
| `test-key.pem` | The **TEST-ONLY** P-256 key that signs the vector flags. |
| `test-key.pub.pem` | Its public key, for `umi-protocol verify`. |

## Shared inputs

Every vector session has the same header:

| Field | Value |
| --- | --- |
| `header_flags` | `1` (simulated) |
| `device_id` | `0x00000000c11b0001` |
| `session_id` | `1` |
| `activity` | `1` (ride) |
| `hw_rev` | `0` |
| `fw_version` | `0.1.0` |

so the 32-byte header is `554d4953 01 20 0100 01001bc100000000 01000000 01 00 000100 000000` + `161a1f16` (its CRC-32, little-endian). Sessions start at `unix_ms = 1794988320000` (2026-11-18T07:52:00Z).

The `END` record is never an input: `t_ms` is the last record's `t_ms` unless stated, `record_count` and `file_crc32` follow from the bytes.

### `minimal`

| `type` | `t_ms` | Fields (in wire order) |
| --- | --- | --- |
| `TIME_SYNC` | 0 | `unix_ms` 1794988320000 |
| `SAMPLE` | 1000 | `lat_e7` 414029000, `lon_e7` 21564400, `speed_cms` 500, `heading_cdeg` 6500, `vib_mms2` 850, `noise_cdba` 6420, `hdop_d` 9, `fix` 3, `sats` 11 |
| `SAMPLE` | 2000 | 414029200, 21565000, 520, 6500, 1210, 6590, 9, 3, 12 |
| `SAMPLE` | 3000 | 414029400, 21565610, 510, 6600, 990, 6475, 8, 3, 12 |

`END`: `t_ms` 3000, `record_count` 4. File: 152 bytes.

### `full`

| `type` | `t_ms` | Fields (in wire order) |
| --- | --- | --- |
| `TIME_SYNC` | 0 | `unix_ms` 1794988320000 |
| `STATE` | 0 | `state` 1 (recording) |
| `SAMPLE` | 1000 | `lat_e7` 0, `lon_e7` 0, `speed_cms` 0, `heading_cdeg` 0, `vib_mms2` 640, `noise_cdba` 6230, `hdop_d` 255, `fix` 0, `sats` 3 |
| `SAMPLE` | 2000 | 414038900, 21586100, 480, 6420, 910, 6380, 12, 2, 6 |
| `AIR` | 2000 | `pm1_dug` 52, `pm25_dug` 87, `pm10_dug` 131, `temp_cc` −150, `rh_dpct` 712 |
| `EVENT` | 2400 | `kind` 1 (hard brake), `value_mms2` 3850, `peak_mms2` 6120, `duration_ms` 640, `lat_e7` 414038900, `lon_e7` 21586100 |
| `SAMPLE` | 3000 | 414039100, 21586500, 230, 6380, 1130, **65535** (not available), 9, 3, 9 |
| `FLAG` | 3200 | `seq` 0, `source` 1 (press), `kind` 0, `confidence` 0, `lang` 0, `lat_e7` 414039100, `lon_e7` 21586500, `speed_cms` 230, `vib_mms2` 1130, `noise_cdba` 65535, **signed** |
| `EVENT` | 3600 | `kind` 2 (pothole), 4630, 13900, 120, 414039100, 21586500 |
| `SAMPLE` | 4000 | 414039400, 21587100, 510, 6410, 4630, 6710, 8, 3, 11 |
| `FLAG` | 4100 | `seq` 1, `source` 2 (voice), `kind` 1 (roadworks), `confidence` 92, `lang` 1 (ca), 414039400, 21587100, 510, 4630, 6710, **signed** |
| `FLAG` | 4800 | `seq` 2, `source` 1, `kind` 0, `confidence` 0, `lang` 0, 414039400, 21587100, 510, 4630, 6710, unsigned (`sig_alg` 0, `sig_len` 0, zero signature) |
| `SAMPLE` | 5000 | 414039700, 21587700, 505, 6400, 1020, 6650, 8, 3, 11 |
| `FLAG_UNDO` | 5100 | `seq` 2 |
| `STATUS` | 5100 | `battery_pct` 18, `flags` 2 (low battery), `battery_mv` 3610, `board_temp_cc` 3125, `free_kib` 5120 |
| `STATE` | 36000 | `state` 2 (auto-pause) |
| `STATE` | 41000 | `state` 3 (resume) |
| `SAMPLE` | 42000 | 414040800, 21589000, 150, 6390, 700, 6120, 9, 3, 12 |

`END`: `t_ms` 42000, `record_count` 18. File: 654 bytes. Signed flags have `sig_alg` 1, `sig_len` 64 and the signature in `full.json`.

### `ride`

Gràcia to Glòries on a cold-started e-bike: Travessera de Gràcia → Passeig de Sant Joan → Avinguda Diagonal, about 3.04 km and 10 minutes, built from 30 real waypoints (`ROUTE` in `generate.py`). One `SAMPLE` per second (no fix for the first two), `TIME_SYNC` at the first fix (`t_ms` 3000), `AIR` every 10 s, `STATUS` every 60 s until the auto-stop, a hard brake and a 35 s stop at the Passeig de Sant Joan × Diagonal light (auto-pause, then resume), two potholes, and six flags:

| `seq` | Where | What | After the trim |
| --- | --- | --- | --- |
| 0 | 110 m | press | dropped (first 200 m) |
| 1 | 700 m | press | kept |
| 2 | 1.9 km | voice, roadworks (92 %, ca) | kept |
| 3 | 2.6 km | press, undone 1.5 s later | kept, with its `FLAG_UNDO` |
| 4 | 230 m before the end | press, undone 9 s later, after the kept window | kept, and so is its `FLAG_UNDO` |
| 5 | 90 m before the end | voice, keyword not understood (`kind` 0, 41 %, es) | dropped (last 200 m) |

The trim cuts 202 m at the start and 200 m at the end (`TRIM` record), keeps `TIME_SYNC` and every `STATUS`, and recomputes `END` (`t_ms` stays 882000, the auto-stop).

Positions come from integer waypoints and IEEE-exact arithmetic (products and square roots), and the noise from a small LCG, so the file is the same on every platform.

## Canonical JSON

`umi_protocol.to_json`, also `umi-protocol decode FILE`. Wire values only, never floats, so any language can produce and compare it:

```json
{
  "header": {"header_flags": 1, "device_id": "00000000c11b0001", "session_id": 1, "activity": 1, "hw_rev": 0, "fw_version": [0, 1, 0]},
  "records": [
    {"type": "time_sync", "t_ms": 0, "unix_ms": 1794988320000},
    {"type": "unknown", "type_id": 66, "t_ms": 1500, "payload": "dc050000667574757265"}
  ],
  "end": {"type": "end", "t_ms": 2000, "record_count": 4, "file_crc32": 2078124952},
  "complete": true,
  "issue": null
}
```

- `type` is the `[enum.record_type]` name; the other keys are the spec's field names in wire order, reserved bytes left out.
- `device_id` is 16 lowercase hex digits (a u64 is not a safe JSON number); `signature` and unknown `payload` are lowercase hex.
- Enum fields are integers. Payload bytes beyond the v1 layout are not part of the form.
- `end` is `null` and `issue` says why when `complete` is `false`. The `issue` text is informative; other codecs only need to match `complete`.
- One record per line keeps diffs readable; compare parsed JSON, not text.

## The test key

> **TEST ONLY.** `test-key.pem` is public. Never provision it on a Clip, never register its public key for a real device, never accept it in production. Anything it signs proves nothing.

| | |
| --- | --- |
| Private scalar (hex, what the firmware SIL signer loads) | `cc9984b4083513ef75c4ac63f128a5f81e7580ea86a99ad8d74a8d727b49a663` |
| Public key, uncompressed (65 B, as in BLE Device Info) | `049821678e2f8b14c1b66d21dc88711cdff89cc0e9364cf9b3ab89cc183c32b75751566fea5b91c3a300653b7bdbd75c1778d83300fa1b57c7763d50d76b83291f` |

Signatures are ECDSA P-256 over SHA-256 with **RFC 6979 deterministic nonces**, raw `r ‖ s`. A C signer reproduces them with deterministic ECDSA and SHA-256 (mbedTLS `mbedtls_ecdsa_sign_det_ext`); a signer with random nonces makes valid signatures that differ from the vectors, so compare by verifying, not by bytes.

## Regenerating

```bash
uv run python protocol/vectors/generate.py --check   # exit 1 and list the files that would change
uv run python protocol/vectors/generate.py           # rewrite them
```

Regenerate only for an intended protocol change, review the binary and JSON diffs, and update the C and phone codecs in the same pull request.
