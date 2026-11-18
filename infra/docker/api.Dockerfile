# syntax=docker/dockerfile:1
#
# The UMI API (backend/): FastAPI served by uvicorn, migrations applied on start.
# The build context is the repository root, because the API is one member of the
# uv workspace and the seed reads the web app's mock datasets:
#
#   docker build -f infra/docker/api.Dockerfile -t umi-api .
#
# api.Dockerfile.dockerignore, next to this file, limits the context to what the
# image needs.

ARG PYTHON_IMAGE=python:3.13-slim-trixie

FROM ghcr.io/astral-sh/uv:0.12 AS uv

FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Third-party dependencies first, from the lock and the workspace manifests
# alone, so a code change does not reinstall them.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=.python-version,target=.python-version \
    --mount=type=bind,source=protocol/python/pyproject.toml,target=protocol/python/pyproject.toml \
    --mount=type=bind,source=backend/pyproject.toml,target=backend/pyproject.toml \
    --mount=type=bind,source=simulator/pyproject.toml,target=simulator/pyproject.toml \
    uv sync --locked --no-dev --no-install-workspace --package umi-api

COPY . .
# Workspace members stay editable on purpose: umi_api finds alembic.ini, its
# migrations and the mock datasets relative to its source tree
# (umi_api/settings.py), so the tree keeps the repository's layout.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package umi-api

FROM ${PYTHON_IMAGE} AS runtime
RUN groupadd --system --gid 10001 umi \
    && useradd --system --uid 10001 --gid umi --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin umi
# Owned by root: the service cannot rewrite its own code.
COPY --from=build /app /app
WORKDIR /app
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
USER umi
EXPOSE 8000
CMD ["sh", "-c", "umi-api migrate && exec umi-api serve --host 0.0.0.0 --port 8000"]
