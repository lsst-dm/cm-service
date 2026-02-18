# syntax=docker/dockerfile:1

ARG PYTHON_VERSION="3.13"
ARG DEBIAN_VERSION="trixie"
ARG UV_VERSION="0.10"
ARG NODE_VERSION="24-dev"
ARG ASGI_PORT="8080"

#==============================================================================
# UV SOURCE IMAGE
# - The DHI version of uv is in /usr/local/bin
FROM dhi.io/uv:${UV_VERSION} AS uv


#==============================================================================
# BUN SOURCE IMAGE
FROM dhi.io/bun:1-dev AS bun


#==============================================================================
# HTCONDOR SOURCE IMAGE
# - The easiest way to obtain an architecture-appropriate set of htcondor client
#   binaries is to install them into an otherwise bare conda environment.
FROM continuumio/miniconda3:latest AS htcondor
RUN conda create -p /opt/htcondor -c conda-forge htcondor-utils --no-default-packages


#==============================================================================
# BASE IMAGE
# - The base image is an updated debian python container with a nonroot user
#   created. This can be extended into include any *runtime* system dependencies
#   during the apt-get step.
FROM python:${PYTHON_VERSION}-slim-${DEBIAN_VERSION} AS base-image
ARG ASGI_PORT

# Upgrade base packages
RUN <<ENDRUN
set -e
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get -y upgrade
apt-get -y install libexpat1
apt-get clean
rm -rf /var/lib/apt/lists/*
ENDRUN

# Create nonroot lsstsvc1 user
RUN <<ENDRUN
set -e

groupadd --gid 1126 gu
groupadd --gid 4085 rubin-users
groupadd --gid 2218 lsst
groupadd --gid 3967 lsstsvc1
useradd lsstsvc1 --uid 17951 --no-user-group --gid gu --groups rubin-users,lsst,lsstsvc1 --create-home --shell /bin/bash
ENDRUN

# Expose the API port
EXPOSE ${ASGI_PORT}


#==============================================================================
# BUILDER IMAGE
FROM base-image AS build-image

# Install and Configure UV
ENV UV_PYTHON_PREFERENCE=system
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_FROZEN=1
ENV UV_LINK_MODE=copy
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies in case any source-distributions need to be built
# e.g., because wheels not available for the current os x arch combo.
RUN <<ENDRUN
set -e

apt-get update
apt-get -y install --no-install-recommends build-essential git libffi-dev curl
apt-get clean
rm -rf /var/lib/apt/lists/*
ENDRUN

WORKDIR /workdir
COPY . .

# Install project production dependency graph in /opt/venv
RUN --mount=type=cache,target=/root/.cache/uv --mount=from=uv,source=/usr/local/bin/uv,target=/usr/local/bin/uv <<ENDRUN
    set -e
    /usr/local/bin/uv sync --no-group dev --no-install-project --no-editable
ENDRUN


#==============================================================================
# BUILDER IMAGE - Web
FROM build-image AS web-builder
ARG PYTHON_VERSION
ENV UV_PYTHON_INSTALL_DIR=/opt/python/dist
ENV UV_PROJECT_ENVIRONMENT=/opt/python/venv
ENV UV_PYTHON_PREFERENCE=only-managed
ENV UV_PYTHON=cpython@${PYTHON_VERSION}

RUN --mount=from=bun,source=/usr/local/bin/bun,target=/usr/local/bin/bun <<ENDRUN
    set -e
    cd packages/cm-canvas
    /usr/local/bin/bun install
    /usr/local/bin/bun run build
ENDRUN

# Install web package dependency graph in /opt/venv
RUN --mount=type=cache,target=/root/.cache/uv --mount=from=uv,source=/usr/local/bin/uv,target=/usr/local/bin/uv <<ENDRUN
    set -e
    /usr/local/bin/uv sync --package lsst-cmservice-web --no-group dev --no-install-project --no-editable
ENDRUN

# Build static web content
RUN --mount=type=cache,target=/root/.cache/uv --mount=from=uv,source=/usr/local/bin/uv,target=/usr/local/bin/uv <<ENDRUN
    set -e
    /usr/local/bin/uv run script/render_jsonschema.py --clean --html --output docs
ENDRUN

# Create Nicegui Storage Path
RUN mkdir -p /opt/storage

#==============================================================================
# RUNTIME IMAGE - CM-Service
FROM base-image AS cmservice

# Copy the production virtual environment
COPY --from=build-image /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Switch to NONROOT user
USER lsstsvc1

WORKDIR /home/lsstsvc1

# Copy the application and examples
ENV CM_CONFIGS=/home/lsstsvc1/examples
COPY examples ./examples
COPY src/lsst ./lsst
COPY alembic ./alembic
COPY alembic.ini .

ENTRYPOINT ["/opt/venv/bin/python3", "-m"]
CMD ["lsst.cmservice.main"]


#==============================================================================
# RUNTIME IMAGE - Daemon
FROM cmservice AS cmworker

USER ROOT
COPY --from=htcondor /opt/htcondor /opt/htcondor

USER lsstsvc1
CMD ["lsst.cmservice.daemon"]


#==============================================================================
# RUNTIME IMAGE - Web
FROM gcr.io/distroless/cc-debian13:latest AS cmweb

ENV PATH="/opt/python/venv/bin:$PATH"
ENV NICEGUI_STORAGE_PATH=/home/nonroot/storage
ENTRYPOINT ["/opt/python/venv/bin/python3", "-m"]

WORKDIR /opt/python
COPY --from=web-builder /opt/python .

WORKDIR /home/nonroot
USER nonroot
COPY packages/cm-web/src/lsst ./lsst
COPY --from=web-builder /workdir/packages/cm-canvas/dist/*.iife.js ./lsst/cmservice/web/static/
COPY --from=web-builder /workdir/docs ./lsst/cmservice/web/static/docs
COPY --from=web-builder --chown=nonroot:nonroot /opt/storage ./storage

CMD ["lsst.cmservice.web.libexec.go"]
