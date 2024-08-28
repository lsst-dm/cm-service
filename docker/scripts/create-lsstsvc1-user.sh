#!/bin/bash
set -euo pipefail
set -x

groupadd --gid 1126 gu
groupadd --gid 4085 rubin-users
groupadd --gid 2218 lsst
groupadd --gid 3967 lsstsvc1

useradd lsstsvc1 --uid 17951 --no-user-group --gid gu --groups rubin-users,lsst,lsstsvc1 \
  --create-home --shell /bin/bash
