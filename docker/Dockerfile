# syntax=docker/dockerfile:1

ARG PYTHON_VERSION="3.13"
ARG UV_VERSION="0.9"
ARG NODE_VERSION="lts"
ARG ASGI_PORT="8080"

#==============================================================================
# UV SOURCE IMAGE
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv


#==============================================================================
# NODE.js SOURCE IMAGE
FROM node:${NODE_VERSION} AS nodejs


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
FROM python:${PYTHON_VERSION}-slim-bookworm AS base-image
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
COPY --from=uv /uv /bin/uv
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
RUN --mount=type=cache,target=/root/.cache/uv <<ENDRUN
    set -e
    /bin/uv sync --no-group dev --no-install-project --no-editable
ENDRUN


#==============================================================================
# BUILDER IMAGE - Web
FROM build-image AS web-builder

# Build distribution for IIFE canvas component
RUN --mount=from=nodejs,source=/usr/local,target=/usr/local <<ENDRUN
    set -e
    cd packages/cm-canvas
    npm install
    npm run build
ENDRUN

# Install web package dependency graph in /opt/venv
RUN --mount=type=cache,target=/root/.cache/uv --mount=from=uv,source=/uv,target=/bin/uv <<ENDRUN
    set -e
    /bin/uv sync --package lsst-cmservice-web --no-group dev --no-install-project --no-editable
ENDRUN

# Build static web content
RUN --mount=type=cache,target=/root/.cache/uv --mount=from=uv,source=/uv,target=/bin/uv <<ENDRUN
    set -e
    /bin/uv run script/render_jsonschema.py --clean --html --output docs
ENDRUN


#==============================================================================
# RUNTIME IMAGE - CM-Service
FROM base-image AS cmservice

# Make sure frontend output won't go into the layer store
VOLUME /output

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
FROM base-image AS cmweb

# Copy the application and static content
COPY packages/cm-web/src/lsst ./lsst
COPY --from=web-builder /opt/venv /opt/venv
COPY --from=web-builder /workdir/packages/cm-canvas/dist/*.iife.js ./lsst/cmservice/web/static/
COPY --from=web-builder /workdir/docs ./lsst/cmservice/web/static/docs
ENV PATH="/opt/venv/bin:$PATH"

ENTRYPOINT ["/opt/venv/bin/python3", "-m"]
CMD ["lsst.cmservice.web.libexec.go"]
