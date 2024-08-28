#!/bin/bash
set -eo pipefail
set -x

mkdir stack
cd stack

curl -sSL "https://ls.st/lsstinstall" | bash -s -- -S -v 9.0.0

source ./loadLSST.bash
conda clean -a -y
mamba clean -a -y

eups distrib install --no-server-tags -vvv "ctrl_bps" -t "latest"
eups distrib install --no-server-tags -vvv "lsst_bps_plugins" -t "latest"

find . -exec strip --strip-unneeded --preserve-dates {} + > /dev/null 2>&1 || true
find . -maxdepth 5 -name tests -type d -exec rm -rf {} + > /dev/null 2>&1 || true
find . -maxdepth 6 \( -path "*doc/html" -o -path "*doc/xml" \) -type d -exec rm -rf {} + > /dev/null 2>&1 || true
find . -maxdepth 5 -name src -type d -exec rm -rf {} + > /dev/null 2>&1 || true

curl -sSL "https://raw.githubusercontent.com/lsst/shebangtron/master/shebangtron" | python
