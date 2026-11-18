# 0002 · One binary session format from the Clip to the database

**Status** Accepted · November 2026

## Context

The Clip records a ride on its flash, the phone pulls it over BLE, and the backend must verify and process it. Translating between formats on the way (binary on the Clip, JSON on the wire) means three codecs that drift, and it breaks the Clip's signatures on flags.

## Decision

The Clip's session log (`.umis`, `protocol/README.md`) is also the BLE transfer unit and the upload body. The phone decodes it, removes records for the privacy trim, and re-encodes it with the same codec; record payloads are copied byte for byte. Framing is type-length-value with a CRC-16 per record and a CRC-32 per file, little-endian, fixed-point units.

## Consequences

- Golden files in `protocol/vectors/` test every codec (C encoder byte for byte, Python and later TS decoders).
- Flags keep a signature that the backend verifies against the Clip's key.
- Per-record CRCs make a session readable up to the last good record after a power loss.
- Uploads are compact: about 30 bytes per second of riding (≈ 110 KB per hour) before compression.
- Debugging needs a tool to read the binary: `python -m umi_protocol inspect file.umis`.
