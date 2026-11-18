# umi-protocol

The reference implementation of [UMI protocol v1](../README.md) in Python: the `.umis` session log codec, the privacy trim, flag signatures and a small CLI. The backend and the simulator import it; the C firmware codec and the phone must agree with it on the [golden vectors](../vectors).

Pure Python on top of `cryptography`; Python ≥ 3.12. Shared numbers and enums come from `umi_protocol.constants`, generated from [`protocol/constants.toml`](../constants.toml) (never edit it by hand).

## Develop

From the repository root (one uv workspace for every Python package):

```bash
uv sync --all-packages --all-groups
uv run pytest protocol/python/tests
uv run ruff format protocol/python protocol/vectors && uv run ruff check protocol/python protocol/vectors
uv run mypy protocol/python/src
uv run python protocol/vectors/generate.py --check     # golden vectors unchanged
python3 protocol/codegen/generate.py --check           # constants.py in sync with constants.toml
```

## CLI

`umi-protocol` (or `python -m umi_protocol`):

```bash
uv run umi-protocol inspect ride.umis              # header, counts per record type, duration, distance, flags, completeness
uv run umi-protocol inspect ride.umis --json       # the same as JSON
uv run umi-protocol decode ride.umis               # canonical JSON, as in protocol/vectors/*.json
uv run umi-protocol trim ride.umis upload.umis     # the phone's privacy trim
uv run umi-protocol verify upload.umis --pubkey clip.pub.pem   # check every flag signature
```

Exit status: `0` success, `1` invalid input or a flag that does not verify (unsigned included), `2` usage error, `3` `trim` found nothing that may be uploaded (trip under 500 m).

## API

Everything public is exported from `umi_protocol`.

| Module | What |
| --- | --- |
| `records` | `Header` and one frozen dataclass per record (`Sample`, `Air`, `Event`, `Flag`, `FlagUndo`, `Status`, `TimeSync`, `State`, `Trim`, `End`), plus `UnknownRecord(type, payload)`. Field names and fixed-point units are the spec's; properties give SI units (`lat`, `speed_kmh`, `vib_mps2`, `noise_dba`, `pm25_ugm3`...) and `None` for `0xFFFF` (not available). |
| `codec` | `encode_session`, `decode_session` → `DecodedSession(header, records, complete, issue, end)`, the streaming `SessionWriter`, and the frame level (`read_frames`, `Frame`) for code that copies payloads untouched. |
| `session` | `Session`, a read view: absolute time (first `TIME_SYNC`), the path along fixed samples and its length, effective flags (`FLAG_UNDO` applied). |
| `trim` | `trim_session(bytes) → TrimResult` and the pure `plan_trim(path)`. |
| `signing` | `flag_message`, `sign_flag` / `verify_flag` (ECDSA P-256, SHA-256, RFC 6979), raw `r ‖ s` ↔ DER, key helpers (PEM, raw scalar hex for the firmware SIL, 65-byte uncompressed point for BLE Device Info). |
| `canonical` | `to_json` / `to_dict`: the canonical JSON of a decoded session, used by the vectors. |
| `geo`, `crc` | `haversine_m` (with `[geo] earth_radius_m`), CRC-16/CCITT-FALSE and CRC-32/ISO-HDLC. |
| `errors` | `ProtocolError` (a `ValueError`) → `HeaderError`, `RecordError`, `EncodeError`, `TrimError`. |

Write a session the way a Clip does, record by record:

```python
from umi_protocol import (
    Activity,
    Fix,
    Flag,
    FlagSource,
    HazardKind,
    Header,
    HeaderFlag,
    Lang,
    Sample,
    SessionWriter,
    TimeSync,
    sign_flag,
)

header = Header(header_flags=HeaderFlag.SIMULATED, device_id=0xC11B0001, session_id=7, activity=Activity.RIDE)
with open("ride.umis", "wb") as sink:
    writer = SessionWriter(sink, header)  # the file is a readable (incomplete) session after every append
    writer.append(TimeSync(t_ms=0, unix_ms=1_794_988_320_000))
    writer.append(Sample(1000, 414029000, 21564400, 500, 6500, 850, 6420, 9, Fix.THREE_D, 11))
    flag = Flag(1350, 0, FlagSource.PRESS, HazardKind.NONE, 0, Lang.NONE, 414029000, 21564400, 500, 850, 6420)
    writer.append(sign_flag(private_key, header.device_id, header.session_id, flag))
    writer.finalize()  # END: record count, duration, file CRC-32
```

Read, trim and verify, as the phone and the backend do:

```python
from umi_protocol import Session, trim_session, verify_flag

result = trim_session(data)
if result.data is None:
    print("nothing to upload:", result.reason)
else:
    session = Session.from_bytes(result.data)
    print(session.started_at, session.distance_m, session.header.trimmed)
    for flag in session.flags:  # undone flags are left out
        ok = verify_flag(public_key, session.header.device_id, session.header.session_id, flag)
```

## Behaviour worth knowing

- **Cut short vs invalid.** A missing `END`, a record cut off or the first record failing its CRC ends decoding there: `complete` is `False`, `issue` says where, and the records before are returned. Bytes no correct writer produces raise: bad header, a CRC-valid record shorter than its v1 layout, `t_ms` going back, `TRIM` anywhere but first (or without the `trimmed` flag, or missing when the flag is set), an `END` whose count or file CRC does not match, bytes after `END`.
- **Forward compatibility.** Unknown record types decode to `UnknownRecord` and are re-encoded as is; longer payloads are accepted and their extra bytes ignored (the frame level keeps them); unknown enum values stay plain integers instead of failing; a header longer than 32 bytes is skipped to `header_len`.
- **Validation on encode.** Records are plain values: ranges are checked when encoding, and `EncodeError` names the field (`Sample.lat_e7 = 3000000000 does not fit the wire type 'i'`). `SessionWriter` refuses what a reader would reject (out-of-order `t_ms`, misplaced `TRIM`, appending after `finalize`).
- **Reserved bytes** are written as zero and ignored when reading. `verify_flag` re-encodes the signed 28 bytes from the fields, so a flag whose reserved bytes are not zero does not verify (fail closed).
- **The trim is not idempotent** and refuses a session that already has the `trimmed` flag. A session cut short is trimmed and comes out with an `END`. `FLAG_UNDO` is kept with its flag even past the window, and unknown record types are cut like telemetry (`protocol/README.md` §2).
- **Deterministic signatures** (RFC 6979): the same key and flag always give the same bytes, which keeps the vectors stable.
