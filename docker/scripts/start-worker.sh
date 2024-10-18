#!/bin/bash
set -eo pipefail

# The venv at /home/lsstsvc1/venv (with lsst.cmservice installed within), is
# already active at this point (arranged during container build)

# Setup partial Rubin stack
#source ./stack/loadLSST.bash
#setup ctrl_bps
#setup lsst_bps_plugins

cm-worker
