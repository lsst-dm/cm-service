#!/bin/bash
set -eu

cm-service init
uvicorn lsst.cmservice.main:app --host 0.0.0.0 --port 8080
