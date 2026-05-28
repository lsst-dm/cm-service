#!/usr/bin/env python3.9
"""..."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from random import choice
from string import digits
from textwrap import dedent
from typing import Any

NOW = datetime.now(timezone.utc)  # noqa: UP017
DT_SLUG = NOW.strftime("%Y/%m/%d %H:%M:%S")

DAGMAN_DAG_LOG = dedent("""\
    000 (003.000.000) 2026-05-19 15:35:23 Job submitted from host: <172.19.0.3:9618?addrs=172.19.0.3-9618&alias=htcondor&noUDP&sock=schedd_40_03e0>
    ...
    001 (003.000.000) 2026-05-19 15:35:27 Job executing on host: <172.19.0.3:9618?addrs=172.19.0.3-9618&alias=htcondor&noUDP&sock=starter_60_067c_3>
    ...
    005 (003.000.000) 2026-05-19 15:35:27 Job terminated.
            (1) Normal termination (return value 0)
                    Usr 0 00:00:00, Sys 0 00:00:00  -  Run Remote Usage
                    Usr 0 00:00:00, Sys 0 00:00:00  -  Run Local Usage
                    Usr 0 00:00:00, Sys 0 00:00:00  -  Total Remote Usage
                    Usr 0 00:00:00, Sys 0 00:00:00  -  Total Local Usage
            0  -  Run Bytes Sent By Job
            0  -  Run Bytes Received By Job
            0  -  Total Bytes Sent By Job
            0  -  Total Bytes Received By Job
    ...
    """)  # noqa: E501

DAGMAN_DAG = dedent("""\
    JOB pipetaskInit "pipetaskInit.sub" DIR "jobs/pipetaskInit"
    JOB step1detector_1 "step1detector_1.sub" DIR "jobs/step1detector/1"
    PARENT pipetaskInit CHILD step1detector_1
    DOT mock_bps_submit_side_effect_001_version_1.dot
    NODE_STATUS_FILE mock_bps_submit_side_effect_001_version_1.node_status
    SET_JOB_ATTR bps_isjob= "True"
    SET_JOB_ATTR bps_project= "CM-MOCK"
    SET_JOB_ATTR bps_campaign= "CM-MOCK"
    SET_JOB_ATTR bps_run= "mock_bps_submit_side_effect_001_version_1"
    SET_JOB_ATTR bps_operator= "lsstsvc1"
    SET_JOB_ATTR bps_payload= "cm-mock"
    SET_JOB_ATTR bps_runsite= "DOCKER"
    SET_JOB_ATTR bps_run_quanta= "isr:4758;analyzeAmpInterfaceOffsetMetadata:4758;calibrateImage:4758;analyzeAmpOffsetMetadata:4758;analyzeCalibrateImageMetadata:4758;analyzeInitialSummaryStats:4758;standardizeSingleVisitStar:4758"
    SET_JOB_ATTR bps_job_summary= "pipetaskInit:1;step1detector:1;finalJob:1"
    SET_JOB_ATTR bps_wms_service= "lsst.ctrl.bps.htcondor.htcondor_service.HTCondorService"
    SET_JOB_ATTR bps_wms_workflow= "lsst.ctrl.bps.htcondor.htcondor_service.HTCondorWorkflow"
    FINAL finalJob "finalJob.sub" DIR "jobs/finalJob"
    SCRIPT POST finalJob /opt/sw/final_post.sh finalJob $DAG_STATUS $RETURN
""")  # noqa: E501

DAGMAN_NODE_STATUS = dedent(f"""\
    [
    Type = "DagStatus";
    DagFiles = {"mock_bps_submit_side_effect_001_version_1.dag"};
    Timestamp = {NOW.timestamp()};
    DagStatus = 5; /* "STATUS_DONE (success)" */
    NodesTotal = 3;
    NodesDone = 3;
    NodesPre = 0;
    NodesQueued = 0;
    NodesPost = 0;
    NodesReady = 0;
    NodesUnready = 0;
    NodesFutile = 0;
    NodesFailed = 0;
    JobProcsHeld = 0;
    JobProcsIdle = 0; /* includes held */
    ]
    [
    Type = "NodeStatus";
    Node = "pipetaskInit";
    NodeStatus = 5; /* "STATUS_DONE" */
    StatusDetails = "";
    RetryCount = 0;
    JobProcsQueued = 0;
    JobProcsHeld = 0;
    ]
    [
    Type = "NodeStatus";
    Node = "step1detector_1";
    NodeStatus = 5; /* "STATUS_DONE" */
    StatusDetails = "";
    RetryCount = 0;
    JobProcsQueued = 0;
    JobProcsHeld = 0;
    ]
    [
    Type = "NodeStatus";
    Node = "finalJob";
    NodeStatus = 5; /* "STATUS_DONE" */
    StatusDetails = "";
    RetryCount = 0;
    JobProcsQueued = 0;
    JobProcsHeld = 0;
    ]
    [
    Type = "StatusEnd";
    EndTime = {NOW.timestamp()};
    NextUpdate = 0;
    ]
""")

DAGMAN_STD_OUT = dedent(f"""\
    {DT_SLUG} Dag contains 3 total nodes
    {DT_SLUG} Bootstraping...
    {DT_SLUG} Submitting node pipetaskInit from file pipetaskInit.sub using direct job submission
    {DT_SLUG}       assigned HTCondor ID ({"".join([choice(digits) for _ in range(8)])}.0.0)
    {DT_SLUG} Submitting node step1detector_1 from file step1detector_1.sub using direct job submission
    {DT_SLUG}       assigned HTCondor ID ({"".join([choice(digits) for _ in range(8)])}.0.0)
    {DT_SLUG} Starting final node...
    {DT_SLUG} Submitting HTCondor Node finalJob job(s)...
    {DT_SLUG} Submitting node finalJob from file finalJob.sub using direct job submission
    {DT_SLUG}       assigned HTCondor ID ({"".join([choice(digits) for _ in range(8)])}.0.0)
    {DT_SLUG} **** condor_scheduniv_exec.{"".join([choice(digits) for _ in range(8)])}.0 (condor_DAGMAN) pid {"".join([choice(digits) for _ in range(6)])} EXITING WITH STATUS 0
""")  # noqa: E501


def no_op(argv: list) -> Any:
    """Default no-op behavior, returns a clean exit code unless error mode"""
    if os.environ.get("_ERRMODE", False):
        sys.exit(1)
    else:
        sys.exit(0)


def fake_bps(argv: list) -> Any:
    """A mock bps cli call that produces side effects:

    * a `./submit/...` directory is created
    * a `.qgraph` file is created in the submit directory
    * a fake BPS stdout response is written to stdout
    """
    bps_commands = {"submit", "report", "status"}
    bps_command: str | None = None
    for arg in argv:
        if arg in bps_commands:
            bps_command = arg
            break

    if bps_command is None:
        return no_op(argv)
    elif bps_command == "submit":
        return fake_bps_submit(argv)
    else:
        return no_op(argv)


def fake_bps_submit(argv: list) -> Any:
    bps_run_name = os.environ.get("BPS_RUN_NAME", "mock_bps_submit_side_effect_001_version_1")
    cwd = Path.cwd()
    submit_dir = cwd / "submit" / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"  # noqa: UP017
    qg_file = submit_dir / f"{bps_run_name}.qg"
    submit_dir.mkdir(parents=True, exist_ok=True)
    qg_file.write_bytes(b"\x04")

    # Need to write the fake details for bps status
    dagman_log_file = submit_dir / f"{bps_run_name}.dag.dagman.log"
    dagman_log_file.write_text(DAGMAN_DAG_LOG)
    dag_file = submit_dir / f"{bps_run_name}.dag"
    dag_file.write_text(DAGMAN_DAG)
    dagman_std_out = submit_dir / f"{bps_run_name}.dag.dagman.out"
    dagman_std_out.write_text(DAGMAN_STD_OUT)
    node_status_file = submit_dir / f"{bps_run_name}.node_status"
    node_status_file.write_text(DAGMAN_NODE_STATUS)

    sys.stdout.write(f"Submit dir: {submit_dir}\n")
    sys.stdout.write(f"Run Id: {''.join([choice(digits) for _ in range(8)])}.0\n")
    sys.stdout.write(f"Run Name: {bps_run_name}\n")
    return no_op(argv)


def fake_bps_report(argv: list) -> Any:
    return no_op(argv)


def main() -> Any:
    """Script entrypoint, will call a specific function with the balance of
    args based on invocation name.
    """
    invocation_name = Path(sys.argv[0]).name

    if invocation_name == "bps":
        return fake_bps(sys.argv[1:])
    else:
        return no_op(sys.argv[1:])


if __name__ == "__main__":
    main()
