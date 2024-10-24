#!/bin/bash

# This script installs additional packages used by the dependency image but
# not needed by the runtime image, such as additional packages required to
# build Python dependencies.
#
# Since the base image wipes all the dnf caches to clean up the image that
# will be reused by the runtime image, we unfortunately have to do another
# apt-get update here, which wastes some time and network.

# Bash "strict mode", to help catch problems and bugs in the shell
# script. Every bash script you write should include this. See
# http://redsymbol.net/articles/unofficial-bash-strict-mode/ for details.
set -eo pipefail

# Display each command as it's run.
set -x

# Use stack environment
source ./stack/loadLSST.bash

# Create and activate a venv for the worker
python -m venv ./venv
source ./venv/bin/activate

# Upgrade pip, setuptools, wheel; install deps; install app
PIP_PROGRESS_BAR=off
pip install --upgrade --no-cache-dir pip setuptools wheel
pip install --quiet --no-cache-dir -r ./workdir/requirements/main.txt
pip install --no-cache-dir ./workdir
