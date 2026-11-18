# 0001 · Monorepo, web app at the root, one Python workspace

**Status** Accepted · November 2026

## Context

UMI is one product made of a firmware, a backend, a simulator, a web app and soon a mobile app, all bound by one protocol. They change together: a new record type touches the firmware, the codec, the backend and the simulator in the same pull request. The Next.js app already lives at the repository root and teammates have branches on it.

## Decision

- One repository. Each component gets a top-level directory with its own README, toolchain and CI job: `firmware/`, `protocol/`, `backend/`, `simulator/`, `infra/`, `docs/`.
- The web app stays at the root (`src/`, `package.json`). Moving it to `apps/web` would break open branches and deployment settings for no functional gain; we can still do it later in one mechanical PR.
- Python packages (`protocol/python`, `backend`, `simulator`) form one uv workspace declared in the root `pyproject.toml`, with one lock file. The backend and the simulator import the same `umi_protocol` package instead of copying it.
- Shared numbers and enums live in `protocol/constants.toml` and are generated into C, Python and TypeScript. Generated files are committed (the firmware build must not need Python) and CI fails when they are stale.

## Consequences

- One PR can change the protocol and every consumer atomically; CI runs only the jobs whose paths changed.
- Contributors need Node, uv and PlatformIO only for the parts they touch.
