# 0006 · Privacy is enforced at the edge and checked at the server

**Status** Accepted · November 2026

## Context

The product promises that the first and last 200 m of a trip never leave the phone, that city data needs 5 distinct riders, that "just me" answers stay private, and that audio never leaves the Clip. Promises enforced in one place only fail silently when that place has a bug or a new client skips it.

## Decision

- Each rule is enforced where the data is born and checked again where it lands (table in `docs/architecture/README.md`).
- Trim: the phone trims (`umi_protocol.trim` is the reference); the backend refuses any session without the `trimmed` header flag.
- k-anonymity is computed at query time from distinct riders, never trusted from a stored status alone.
- Thresholds come from `protocol/constants.toml` and are covered by tests on both sides.
- Audio: the mic HAL only returns sound levels and keyword ids; there is no audio record type in the protocol.

## Consequences

- A DPIA is still required before launching voice keywords, and the trust level counts as profiling under GDPR (backlog).
