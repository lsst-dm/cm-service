
# BPS Submit

## Butler Run Collection Already Exists

Meaningful log message: `Output run 'u/tobyj/hsc_micro_cm_dev/isr/group1/job_000' already exists, but --extend-run was not given.`

Log Entry
```
{"name":"lsst.ctrl.bps.pre_transform","asctime":"2025-04-11T18:24:37.349986Z","message":"ERROR 2025-04-11T11:24:37.336-07:00 lsst.daf.butler.cli.utils ()(utils.py:204) - Caught an exception, details are in traceback:\nTraceback (most recent call last):\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_15/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gd1ca4f5601+c57153a7c4/python/lsst/ctrl/mpexec/cli/cmd/commands.py\", line 201, in qgraph\n    if (qgraph := script.qgraph(pipelineObj=pipeline, **kwargs, show=show)) is None:\n                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_15/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gd1ca4f5601+c57153a7c4/python/lsst/ctrl/mpexec/cli/script/qgraph.py\", line 225, in qgraph\n    qgraph = f.makeGraph(pipelineObj, args)\n             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_15/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gd1ca4f5601+c57153a7c4/python/lsst/ctrl/mpexec/cmdLineFwk.py\", line 637, in makeGraph\n    butler, collections, run = _ButlerFactory.makeButlerAndCollections(args)\n                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_15/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gd1ca4f5601+c57153a7c4/python/lsst/ctrl/mpexec/cmdLineFwk.py\", line 393, in makeButlerAndCollections\n    butler, inputs, self = cls._makeReadParts(args)\n                           ^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_15/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gd1ca4f5601+c57153a7c4/python/lsst/ctrl/mpexec/cmdLineFwk.py\", line 331, in _makeReadParts\n    self.check(args)\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_15/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gd1ca4f5601+c57153a7c4/python/lsst/ctrl/mpexec/cmdLineFwk.py\", line 281, in check\n    raise ValueError(\nValueError: Output run 'u/tobyj/hsc_micro_cm_dev/isr/group1/job_000' already exists, but --extend-run was not given.\n","levelno":20,"levelname":"INFO","filename":"pre_transform.py","pathname":"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_15/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_bps/gaf473b166b+55ec7cd135/python/lsst/ctrl/bps/pre_transform.py","lineno":123,"funcName":"execute","process":4160304,"processName":"MainProcess","MDC":{}}
```

Issues
------
- This error message is at INFO level
- The error message is buried in the traceback as the ValueError detail.

Solutions
---------
- This could be checked before BPS submit with a butler registry query, to save time and surface the issue faster.
- Make `--extend-run` a default and/or opt-out flag.
- Always include a nonce in output run collections to ensure uniqueness
