# 0005 · Device identity and signed flags

**Status** Accepted · November 2026

## Context

Rider flags reach the city's maintenance queue once five riders agree. A serial number sent over BLE can be copied, so a script could forge riders. The ESP32-S3 offers secure boot, flash encryption and eFuse-protected keys, but no ECDSA peripheral.

## Decision

- Each Clip gets a P-256 key pair at provisioning. The private key is generated on the device and stored encrypted (flash encryption, key derived through the eFuse HMAC peripheral); secure boot v2 stops a modified firmware from reading it. The public key is registered with the backend with the `device_id`.
- The Clip signs each flag (ECDSA P-256 over SHA-256, `protocol/README.md` §1.4). Telemetry is not signed because the phone must trim it.
- The backend accepts a flag only if the session comes from a Clip paired with the uploading rider and the signature verifies against that Clip's key; `(device_id, session_id, seq)` is unique.
- Simulated and devkit Clips use software keys and set the `simulated` header flag. Production refuses them.

## Consequences

- Forging a rider means owning a Clip and pairing it, which caps abuse per device; the backend still applies per-rider daily caps and plausibility checks.
- Key provisioning becomes a factory step (ticketed with the hardware bring-up).
- A legal check is pending on whether the button counts as a "communication system" under art. 18.2 RGC (see `docs/signalement-mains-libres.md`).
