# Misc. Support Scripts Fail

## Output log file for a script does not exist.

```
uv run cm-client script get script-errors -o json --row_id 263                                                      [
    {
        "script_id": 263,
        "source": 1,
        "diagnostic_message": "ERROR Log file /sdf/group/rubin/shared/campaigns/users/usdf-cm-dev/nightly_validation_20250504_a1/step1a/prepare_000.log does not exist",
        "id": 17
    }
]
```

Issues
------
The reported script error is not the root cause of the problem. While true that the "prepare_000.log" doesn't exist, the reason it doesn't exist is that the prepare script failed to run and produce that log file. The root cause for the failure is elsewhere, so the reported diagnostic message is not useful.

Causes
------
- Condor submit failed because a daily stack was used with CVMFS which only has weeklies. In this case the

    ```
    cat prepare_000_condorsub.log
    /lscratch/lsstsvc1/slurm_job_id_4558237/condor/execute/dir_582026/condor_exec.exe: line 8: /cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib//d_2024_05_04/loadLSST.bash: No such file or directory
    ```

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

## File or Directory Already Exists
A file or directory specified for use by the workflow already exists and cannot be created.

Meaningful log messages:

- `FileExistsError: cannot create directory '/sdf/group/rubin/shared/campaigns/users/usdf-cm-dev/nightly_validation_20250504_b3/step1c/group0/job_000/submit': directory already exists`

Log Entry
```
{"name":"lsst.ctrl.bps.drivers","asctime":"2025-05-07T05:19:57.832716Z","message":"Submission process completed: Took 0.1005 seconds (timed code triggered exception of 'FileExistsError(\"cannot create directory \\'/sdf/group/rubin/shared/campaigns/users/usdf-cm-dev/nightly_validation_20250504_b3/step1c/group0/job_000/submit\\': directory already exists\") @ /sdf/group/rubin/sw/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/ctrl_bps/ge40ca33b87+822006b71e/python/lsst/ctrl/bps/bps_utils.py:119'); current memory usage: 0.181 Gibyte, delta: 0.000 Gibyte, peak delta: 0.000 Gibyte","levelno":20,"levelname":"INFO","filename":"drivers.py","pathname":"/sdf/group/rubin/sw/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/ctrl_bps/ge40ca33b87+822006b71e/python/lsst/ctrl/bps/drivers.py","lineno":333,"funcName":"submit_driver","process":21061,"processName":"MainProcess","MDC":{}}
```

```
{"name":"lsst.daf.butler.cli.utils","asctime":"2025-05-07T05:19:57.833108Z","message":"Caught an exception, details are in traceback:","levelno":40,"levelname":"ERROR","filename":"utils.py","pathname":"/sdf/group/rubin/sw/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/daf_butler/geaba3013f4+bfa974011d/python/lsst/daf/butler/cli/utils.py","lineno":204,"funcName":"exit_click_command_bad_status","process":21061,"processName":"MainProcess","exc_info":"Traceback (most recent call last):\n\n  File \"/sdf/group/rubin/sw/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/ctrl_bps/ge40ca33b87+822006b71e/python/lsst/ctrl/bps/cli/cmd/commands.py\", line 128, in submit\n    submit_driver(*args, **kwargs)\n\n  File \"/sdf/group/rubin/sw/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/ctrl_bps/ge40ca33b87+822006b71e/python/lsst/ctrl/bps/drivers.py\", line 343, in submit_driver\n    wms_workflow_config, wms_workflow = prepare_driver(config_file, **kwargs)\n                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n  File \"/sdf/group/rubin/sw/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/ctrl_bps/ge40ca33b87+822006b71e/python/lsst/ctrl/bps/drivers.py\", line 261, in prepare_driver\n    generic_workflow_config, generic_workflow = transform_driver(config_file, **kwargs)\n                                                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n  File \"/sdf/group/rubin/sw/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/ctrl_bps/ge40ca33b87+822006b71e/python/lsst/ctrl/bps/drivers.py\", line 211, in transform_driver\n    config, clustered_qgraph = cluster_qgraph_driver(config_file, **kwargs)\n                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n  File \"/sdf/group/rubin/sw/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/ctrl_bps/ge40ca33b87+822006b71e/python/lsst/ctrl/bps/drivers.py\", line 166, in cluster_qgraph_driver\n    config, qgraph = acquire_qgraph_driver(config_file, **kwargs)\n                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n  File \"/sdf/group/rubin/sw/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/ctrl_bps/ge40ca33b87+822006b71e/python/lsst/ctrl/bps/drivers.py\", line 129, in acquire_qgraph_driver\n    config = _init_submission_driver(config_file, **kwargs)\n             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n  File \"/sdf/group/rubin/sw/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/ctrl_bps/ge40ca33b87+822006b71e/python/lsst/ctrl/bps/drivers.py\", line 104, in _init_submission_driver\n    config = init_submission(config_file, validators=validators, **kwargs)\n             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n  File \"/sdf/group/rubin/sw/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/ctrl_bps/ge40ca33b87+822006b71e/python/lsst/ctrl/bps/initialize.py\", line 134, in init_submission\n    submit_path = mkdir(config[\"submitPath\"])\n                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n  File \"/sdf/group/rubin/sw/conda/envs/lsst-scipipe-10.0.0/share/eups/Linux64/ctrl_bps/ge40ca33b87+822006b71e/python/lsst/ctrl/bps/bps_utils.py\", line 119, in mkdir\n    raise type(exc)(f\"cannot create directory '{path}': {reason}\") from None\n\nFileExistsError: cannot create directory '/sdf/group/rubin/shared/campaigns/users/usdf-cm-dev/nightly_validation_20250504_b3/step1c/group0/job_000/submit': directory already exists\n","MDC":{}}
```

```@condorlog
...
022 (16452834.000.000) 2025-05-06 21:39:12 Job disconnected, attempting to reconnect
    Socket between submit and execute hosts closed unexpectedly
    Trying to reconnect to slot_lsstsvc1_31838_1_9@sdfmilan167.sdf.slac.stanford.edu <172.24.50.13:36401?CCBID=172.24.49.173:9618%3faddrs%3d172.24.49.173-9618%26alias%3dsdfiana012.sdf.slac.stanford.edu#11223378&PrivNet=sdfmilan167.sdf.slac.stanford.edu&addrs=172.24.50.13-36401&alias=sdfmilan167.sdf.slac.stanford.edu>
...
024 (16452834.000.000) 2025-05-06 22:19:12 Job reconnection failed
    Job disconnected too long: JobLeaseDuration (2400 seconds) expired
    Can not reconnect to slot_lsstsvc1_31838_1_9@sdfmilan167.sdf.slac.stanford.edu, rescheduling job
...
```

Issues
------
- In this instance, the failure is caused and raised by a single bps submit job, where a submit directory is created and then at some later point (in the same job/log file) the submit directory is created again, at which point it fails with the FileExistsError.
- The BPS submit was retried with the same settings in this case because of a HTCondor disconnect which caused rescheduling of the condor job without opportunity to clean up artifacts.
- In default operation modes, BPS uses a timestamp to disambiguate submit directories and output runs. Because CM Service is explicit about these things, out-of-band auto-recovery raises this issue.

Solutions
---------
- Between invocations of a *failed* job, CM Service should try to cull artifacts that may cause these issues, but in this instance there's no period of intervention for CM Service to do so.
- Should HTCondor be instructed not to retry these types of failures?
- CM Service could parse the output of bps commands to capture a dynamic submit path (and other details), but this is only possible when CM Service is involved in the bps command.

## File Not Found
A file specified for use by the workflow has not been found.

There are many ways a file may not be found by a workflow at runtime. In the example case, a BPS workflow's `pipelineYaml` file refers to a file that does not exist because of a typo in the Step Spec Block (a missing "/" between path components).

Other reasons could include an LSST version that does not contain the specified file; etc.

Meaningful log messages:

- `FileNotFoundError: [Errno 2] No such file or directory:`

Log Entry
```
{"name":"lsst.ctrl.bps.pre_transform","asctime":"2025-04-29T18:06:11.857649Z","message":"ERROR 2025-04-29T11:06:11.591-07:00 lsst.daf.butler.cli.utils ()(utils.py:204) - Caught an exception, details are in traceback:\nTraceback (most recent call last):\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gef4e5e10f2+f911d15c04/python/lsst/ctrl/mpexec/cli/cmd/commands.py\", line 194, in qgraph\n    pipeline_graph_factory = script.build(**kwargs, show=show)\n                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gef4e5e10f2+f911d15c04/python/lsst/ctrl/mpexec/cli/script/build.py\", line 121, in build\n    pipeline = f.makePipeline(args)\n               ^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gef4e5e10f2+f911d15c04/python/lsst/ctrl/mpexec/cmdLineFwk.py\", line 589, in makePipeline\n    pipeline = Pipeline.from_uri(args.pipeline)\n               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/sdf/data/rubin/shared/campaigns/LSSTCam-Nightly-Validation/lsst_devel/pipe_base/python/lsst/pipe/base/pipeline.py\", line 331, in from_uri\n    pipeline: Pipeline = cls.fromIR(pipelineIR.PipelineIR.from_uri(uri))\n                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/sdf/data/rubin/shared/campaigns/LSSTCam-Nightly-Validation/lsst_devel/pipe_base/python/lsst/pipe/base/pipelineIR.py\", line 1036, in from_uri\n    with loaded_uri.open(\"r\") as buffer:\n         ^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/lib/python3.12/contextlib.py\", line 137, in __enter__\n    return next(self.gen)\n           ^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/resources/g4a157353b6+d65b3c2b70/python/lsst/resources/_resourcePath.py\", line 1606, in open\n    with self._openImpl(mode, encoding=encoding) as handle:\n         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/lib/python3.12/contextlib.py\", line 137, in __enter__\n    return next(self.gen)\n           ^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/resources/g4a157353b6+d65b3c2b70/python/lsst/resources/file.py\", line 504, in _openImpl\n    with FileResourceHandle(mode=mode, log=log, uri=self, encoding=encoding) as buffer:\n         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/resources/g4a157353b6+d65b3c2b70/python/lsst/resources/_resourceHandles/_fileResourceHandle.py\", line 60, in __init__\n    self._fileHandle: IO = open(file=uri.ospath, mode=self._mode, newline=newline_arg, encoding=encoding)\n                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\nFileNotFoundError: [Errno 2] No such file or directory: '/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/drp_pipe/g11f32a4bda+cfad98a35cpipelines/LSSTCam/nightly-validation.yaml'","levelno":20,"levelname":"INFO","filename":"pre_transform.py","pathname":"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_bps/g0d662b932b+ebdee27649/python/lsst/ctrl/bps/pre_transform.py","lineno":135,"funcName":"execute","process":2364648,"processName":"MainProcess","MDC":{}}
```

Issues
------
- This error message is at INFO level
- The error message is buried in the traceback as the FileNotFoundError detail.

Solutions
---------
- ...

## No Quanta In Graph

Meaningful log messages:

- `Error: QuantumGraph was empty; ERROR logs above should provide details.`
- `Dropping task (.*) because no quanta remain.`
- `Initial data ID query returned no rows, so QuantumGraph will be empty.`

Solutions
---------
- Adjust data query.

## Database Error

Meaningful log messages:

- `sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) server closed the connection unexpectedly`

Solutions
---------
- This is a retriable failure, assuming a transient issue with the database.

## Problems with Butler Output Collection

Meaningful log messages:

- `ValueError: Output CHAINED collection '.*' and does not include the same sequence of (flattened) input collections '.*' as a contiguous subsequence. Use --rebase to ignore this problem and reset the output collection, but note that this may obfuscate what inputs were actually used to produce these outputs.`

Log Entry
```
{"name":"lsst.ctrl.bps.pre_transform","asctime":"2025-04-30T03:23:52.108512Z","message":"ERROR 2025-04-29T20:23:52.103-07:00 lsst.daf.butler.cli.utils ()(utils.py:204) - Caught an exception, details are in traceback:\nTraceback (most recent call last):\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gef4e5e10f2+f911d15c04/python/lsst/ctrl/mpexec/cli/cmd/commands.py\", line 201, in qgraph\n    if (qgraph := script.qgraph(pipeline_graph_factory, **kwargs, show=show)) is None:\n                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gef4e5e10f2+f911d15c04/python/lsst/ctrl/mpexec/cli/script/qgraph.py\", line 231, in qgraph\n    qgraph = f.makeGraph(pipeline_graph_factory, args)\n             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gef4e5e10f2+f911d15c04/python/lsst/ctrl/mpexec/cmdLineFwk.py\", line 642, in makeGraph\n    butler, collections, run = _ButlerFactory.makeButlerAndCollections(args)\n                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gef4e5e10f2+f911d15c04/python/lsst/ctrl/mpexec/cmdLineFwk.py\", line 395, in makeButlerAndCollections\n    butler, inputs, self = cls._makeReadParts(args)\n                           ^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gef4e5e10f2+f911d15c04/python/lsst/ctrl/mpexec/cmdLineFwk.py\", line 333, in _makeReadParts\n    self.check(args)\n  File \"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_mpexec/gef4e5e10f2+f911d15c04/python/lsst/ctrl/mpexec/cmdLineFwk.py\", line 273, in check\n    raise ValueError(consistencyError)\nValueError: Output CHAINED collection 'u/lsstsvc1/nightly_validation_20250423_c5' exists and does not include the same sequence of (flattened) input collections ('u/tobyj/nightlyValidation/20250424/w_2025_17/DM-XXXXX/step1b/group0/job_000', 'LSSTCam/runs/nightlyValidation/13', 'LSSTCam/runs/nightlyValidation/12', 'LSSTCam/runs/nightlyValidation/11', 'LSSTCam/raw/all', 'LSSTCam/calib/DM-50448/initial-ugri-flats/flat-i.20250424a', 'LSSTCam/calib/DM-50448/initial-ugri-flats/flat-r.20250424a', 'LSSTCam/calib/DM-50448/initial-ugri-flats/flat-g.20250424a', 'LSSTCam/calib/DM-50448/initial-ugri-flats/flat-u.20250424a', 'LSSTCam/calib/DM-50336/run7/ptc.20250423a', 'LSSTCam/calib/DM-50295/initial-i-flat/flat-i.20250420a', 'LSSTCam/calib/DM-50162/pseudoFlats/pseudoFlat.20250414b', 'LSSTCam/calib/DM-49175/run7/dark.20250320a', 'LSSTCam/calib/DM-49175/run7/bias.20250320a', 'LSSTCam/calib/DM-49175/run7/cti.20250320a', 'LSSTCam/calib/DM-49175/run7/bfk.20250320a', 'LSSTCam/calib/DM-49175/run7/ptc.20250320a', 'LSSTCam/calib/DM-49175/run7/linearizer.20250320a', 'LSSTCam/calib/DM-49175/run7/defects.20250401a', 'LSSTCam/calib/DM-49679/pseudoFlats/pseudoFlat.20250401b', 'LSSTCam/calib/DM-49832', 'LSSTCam/calib/DM-49832/unbounded', 'refcats/DM-33444', 'refcats/DM-39298', 'refcats/DM-42510', 'refcats/DM-46370/the_monster_20240904', 'refcats/DM-49042/the_monster_20250219', 'skymaps', 'pretrained_models/tac_cnn_comcam_2025-02-18', 'u/tobyj/nightlyValidation/20250424/w_2025_17/DM-XXXXX/step1a/group0/job_000') as a contiguous subsequence. Use --rebase to ignore this problem and reset the output collection, but note that this may obfuscate what inputs were actually used to produce these outputs.","levelno":20,"levelname":"INFO","filename":"pre_transform.py","pathname":"/cvmfs/sw.lsst.eu/almalinux-x86_64/lsst_distrib/w_2025_17/conda/envs/lsst-scipipe-10.0.0-exact/share/eups/Linux64/ctrl_bps/g0d662b932b+ebdee27649/python/lsst/ctrl/bps/pre_transform.py","lineno":135,"funcName":"execute","process":3318222,"processName":"MainProcess","MDC":{}}
```

Solutions
---------
- The bps workflow file template should set both `payload.output` and `payload.outputRun` parameters.
- The `payload.output` chained collection name should be scoped to the step/node, and the `payload.outputRun` should be scoped to the group/job/script/attempt.

# BPS Run

## Workflow Failed Successfully
In a workflow, the pipetaskInit step failed to execute because of underlying configuration issues. Despite this, the CM Service marked the script as "accepted" even though no work was performed; the subsequent script did fail because it could not find the RUN collection assumed created by the failing step.
