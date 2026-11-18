# UMI infrastructure

Containers for the backend on simulated hardware: Postgres, the API, the demo seed and a fleet of simulated Clips. Nothing here is needed to develop: the backend runs on a SQLite file with `uv` alone ([ADR 0004](../docs/architecture/adr/0004-backend-stack.md)). Use the stack to run on Postgres, as production does, or to get the whole backend without installing Python.

| Path | |
| --- | --- |
| `docker-compose.yml` | `postgres`, `api`, and two one-shot services: `seed` and `sim` |
| `docker/api.Dockerfile` | The API image (`backend/`): migrates, then serves on port 8000 |
| `docker/sim.Dockerfile` | The simulator image (`simulator/`), entry point `umi-sim` |
| `docker/*.Dockerfile.dockerignore` | What each image takes from the repository (the build context is the root) |

Requirements: Docker Engine 23 or later with the Compose v2 plugin, or Docker Desktop. The images use BuildKit features (cache mounts, a `.dockerignore` per Dockerfile) that older builders do not have.

## Run it

From the repository root:

```bash
docker compose -f infra/docker-compose.yml up -d --wait    # Postgres, then the API on http://127.0.0.1:8000 (migrated)
docker compose -f infra/docker-compose.yml run --rm seed   # load the demo (the web app's mock datasets)
docker compose -f infra/docker-compose.yml run --rm sim    # seed, then 5 riders x 3 days of simulated rides
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev      # the web app against it
```

`export COMPOSE_FILE=infra/docker-compose.yml` (PowerShell: `$env:COMPOSE_FILE = "infra/docker-compose.yml"`) saves the `-f`.

| Service | Runs | Notes |
| --- | --- | --- |
| `postgres` | Postgres 16 | Data in the `postgres-data` volume. Published on `127.0.0.1:5432` only. |
| `api` | `umi-api migrate`, then `umi-api serve` | Healthy once `/healthz` answers, so after the migrations. `UMI_ENV=dev`: simulated Clips accepted, dev pairing and dev riders (backend README, Configuration). |
| `seed` | `umi-api seed` | Profiles `seed` and `sim`. Idempotent; running it again moves the demo to the current week and resets answers given on demo rides. |
| `sim` | `umi-sim fleet` against `http://api:8000` | Profile `sim`. Runs `seed` first, since ingest needs the street network. Clip keys live in the `sim-keys` volume, so a second run finds the same Clips and the API deduplicates their sessions. |

Arguments after the service name replace the default command, so any simulator command works; `exec` runs a backend command in the running API:

```bash
docker compose -f infra/docker-compose.yml run --rm sim fleet --riders 40 --days 14 --seed 7
docker compose -f infra/docker-compose.yml run --rm sim places
docker compose -f infra/docker-compose.yml exec api umi-api aggregate
```

Stop with `docker compose -f infra/docker-compose.yml down`; add `--volumes` to drop the database and the simulated Clips' keys.

## Settings

Compose reads them from the environment or from `infra/.env` (git-ignored).

| Variable | Default | |
| --- | --- | --- |
| `UMI_POSTGRES_PASSWORD` | `umi` | Password of the `umi` role. Set it before the first `up`: Postgres keeps the one the volume was created with. |
| `UMI_POSTGRES_PORT` | `5432` | Host port for Postgres (loopback only). Change it if a local Postgres already listens on 5432. |
| `UMI_API_PORT` | `8000` | Host port for the API (loopback only). |
| `UMI_SIM_RIDERS` / `UMI_SIM_DAYS` | `5` / `3` | Size of the default `sim` fleet. |

To run the API from source against the stack's database instead (debugger, `--reload`):

```bash
docker compose -f infra/docker-compose.yml up -d --wait postgres
export UMI_DATABASE_URL=postgresql+psycopg://umi:umi@127.0.0.1:5432/umi
uv run umi-api migrate && uv run umi-api seed && uv run umi-api serve --reload
```

## Images

- Multi-stage: `uv` installs the locked dependencies (`uv sync --locked --no-dev --package ...`) in a build stage; the runtime stage is `python:3.13-slim` with the virtual environment and the sources only.
- Dependencies are installed from `uv.lock` and the workspace manifests before the sources are copied, so editing code rebuilds one small layer.
- Workspace packages stay editable: `umi_api` finds `alembic.ini`, its migrations and `src/lib/mock/data` relative to its source tree, and `umi_sim` its datasets. The image keeps the repository's layout under `/app` for that reason.
- The processes run as the unprivileged user `umi` (uid 10001); the code is owned by root and read-only to them.

## Not for production as is

The stack is a development environment: dev authentication, simulated Clips accepted, a default database password and the demo data. A production deployment sets `UMI_ENV=production` (which refuses dev tokens and simulated Clips and turns off the pinned demo clock), real secrets, a managed Postgres with backups, TLS in front of the API, and `umi-api aggregate` on a schedule (backend README, Street scores).

## CI

`.github/workflows/infra.yml` builds both images, starts the stack, runs the `sim` service twice (first upload, then idempotent re-run), checks a few endpoints and fails on any 5xx in the API log. It is the only job that runs the migrations and the ingest on Postgres; the Python suites use SQLite.
