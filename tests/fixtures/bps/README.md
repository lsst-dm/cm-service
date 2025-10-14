# Pickled BPS Report Fixtures

## Creation
With a "real" bps workflow in a given state, create a pickle of the BPS Report output. The pickle should contain the entire object returned from the `wms_svc.report()` method.

```
import pathlib
import pickle
from lsst.utils import doImport

wms_svc_class = doImport("lsst.ctrl.bps.htcondor.HTCondorService")
wms_svc = wms_svc_class(config={})
bps_report = wms_svc.report(".")

fixture_output_file = pathlib.Path("../bps_report_STATE.pickle")
with fixture_output_file.open("wb") as file:
    pickle.dump(bps_report, file)
```

## Available Fixtures
- `bps_report_FAILED.pickle`: A workflow whose pipetaskInit job has failed
- `bps_report_RUNNING.pickle`: A workflow that is still running, but generally healthy
