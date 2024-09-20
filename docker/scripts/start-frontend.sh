#!/bin/bash
set -euo pipefail

# The venv at /home/lsstsvc1/venv (with lsst.cmservice installed within), is
# already active at this point (arranged during container build)

cm-service init
uvicorn lsst.cmservice.main:app --host 0.0.0.0 --port 8080
