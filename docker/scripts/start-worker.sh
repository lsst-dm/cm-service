#!/bin/bash
set -eo pipefail

source ./stack/loadLSST.bash

echo "Splice worker task here..."
tail -f /dev/null
