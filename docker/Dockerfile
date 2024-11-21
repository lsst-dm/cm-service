# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.11
ARG UV_VERSION=0.5

#==============================================================================
# UV SOURCE IMAGE
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv


#==============================================================================
# BASE IMAGE
FROM python:${PYTHON_VERSION}-slim-bookworm AS base-image

# Upgrade base packages
RUN <<ENDRUN
set -e
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get -y upgrade
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
# RUNTIME IMAGE
FROM base-image AS runtime-image

# Expose the API port
EXPOSE 8080

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

# Run the Server
# TODO refactor module main to start unicorn instead of using a bash script
#      after eliminating db migration requirement here
COPY --chmod=755 <<EOF ./docker-entrypoint.sh
#!/bin/bash
python -m lsst.cmservice.cli.server init
uvicorn "\$@"
EOF

# Both the entrypoint and cmd can be disambiguated in the Helm chart / Compose file
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["lsst.cmservice.main:app", "--host", "0.0.0.0", "--port", "8080"]

# ENTRYPOINT ["/opt/venv/bin/python3", "-m"]
# CMD ["lsst.cmservice.daemon"]
