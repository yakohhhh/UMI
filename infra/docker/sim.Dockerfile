# syntax=docker/dockerfile:1
#
# The Clip simulator (simulator/) as a container, to drive the API in
# infra/docker-compose.yml. Same layout as api.Dockerfile; build from the
# repository root:
#
#   docker build -f infra/docker/sim.Dockerfile -t umi-sim .
#   docker run --rm umi-sim places

ARG PYTHON_IMAGE=python:3.13-slim-trixie

FROM ghcr.io/astral-sh/uv:0.12 AS uv

FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=.python-version,target=.python-version \
    --mount=type=bind,source=protocol/python/pyproject.toml,target=protocol/python/pyproject.toml \
    --mount=type=bind,source=backend/pyproject.toml,target=backend/pyproject.toml \
    --mount=type=bind,source=simulator/pyproject.toml,target=simulator/pyproject.toml \
    uv sync --locked --no-dev --no-install-workspace --package umi-sim

COPY . .
# Editable, like the API: umi_sim reads the mock datasets relative to its source tree.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package umi-sim

FROM ${PYTHON_IMAGE} AS runtime
RUN groupadd --system --gid 10001 umi \
    && useradd --system --uid 10001 --gid umi --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin umi \
    && install -d -o umi -g umi /var/lib/umi-sim
COPY --from=build /app /app
WORKDIR /app
# Simulated Clips keep their keys across runs (mount a volume here), so the
# backend keeps recognising them and deduplicates re-uploaded sessions.
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UMI_SIM_KEYS_DIR=/var/lib/umi-sim/keys
USER umi
ENTRYPOINT ["umi-sim"]
CMD ["--help"]
