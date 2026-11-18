# 0004 · FastAPI, SQLAlchemy, Postgres; no PostGIS yet

**Status** Accepted · November 2026

## Context

The web app was written against a planned FastAPI service (`src/lib/api.ts`, `src/lib/types.ts`). Processing is numeric Python work (map matching, signal statistics). The team knows Python and TypeScript. Barcelona's scored network is ~335 segments today.

## Decision

- FastAPI + Pydantic v2 for the HTTP layer; response models mirror `src/lib/types.ts` in camelCase so `NEXT_PUBLIC_API_URL` can switch the web app over without UI changes.
- Layers: `api/` (HTTP only) → `services/` (use cases) → `domain/` (pure rules: scores, privacy, flag lifecycle) and `repositories/` (SQLAlchemy). The domain never imports FastAPI or SQLAlchemy.
- SQLAlchemy 2 (async) with Alembic migrations. Postgres in production; SQLite for tests and zero-setup local runs. Portable column types only.
- Map matching uses an in-memory spatial index of the segments, loaded at start-up. PostGIS becomes worth its operational cost when the network or the query mix outgrows memory (tens of thousands of segments, or spatial queries from the city API); that will be a new ADR.
- Ingest is processed synchronously in the request for now (a ride is ~4k samples). A queue and worker come with real traffic; the pipeline is a plain function so moving it is mechanical.

## Consequences

- No Docker needed to develop or test the backend.
- Dialect-specific SQL is not allowed outside migrations.
