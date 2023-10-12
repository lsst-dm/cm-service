#!/usr/bin/env -S -i CM_PROD_DIR="${CM_PROD_DIR}" HOME="${HOME}" bash

# The shebang lines above are needed b/c setup lsst_distrib in putting
# the lsst python _after_ the virtual env python in the PATH, which
# is causing errors

# setup LSST env.
export WEEKLY='{lsst_version}'
source /cvmfs/sw.lsst.eu/linux-x86_64/lsst_distrib/${WEEKLY}/loadLSST.bash
setup lsst_distrib

# setup PanDA env.
latest_panda=$(ls -td /cvmfs/sw.lsst.eu/linux-x86_64/panda_env/v* | head -1)
setupScript=${latest_panda}/setup_panda_s3df.sh
source $setupScript ${WEEKLY}

env | grep PANDA

# let's drop a panda_auth status here for kicks
panda_auth status
