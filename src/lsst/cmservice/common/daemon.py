from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.future import select

from ..config import config
from ..db.queue import Queue
from ..db.script import Script
from .htcondor import build_htcondor_submit_environment, import_htcondor
from .logging import LOGGER

logger = LOGGER.bind(module=__name__)


async def daemon_iteration(session: async_scoped_session) -> None:
    iteration_start = datetime.now()
    # TODO limit query to queues that do not have a "time_finished"
    queue_entries = await session.execute(select(Queue).where(Queue.time_next_check < iteration_start))
    logger.debug("Daemon Iteration: %s", iteration_start)

    # TODO: should the daemon check any campaigns with a state == prepared that
    #       do not have queues? Queue creation should not be a manual step.
    queue_entry: Queue
    processed_nodes = 0
    for (queue_entry,) in queue_entries:
        try:
            queued_node = await queue_entry.get_node(session)
            if (
                queued_node.status.is_processable_script()
                if isinstance(queued_node, Script)
                else queued_node.status.is_processable_element()
            ):
                logger.info("Processing queue_entry %s", queued_node.fullname)
                await queue_entry.process_node(session)
                processed_nodes += 1
                sleep_time = await queue_entry.node_sleep_time(session)
            else:
                # Put this entry to sleep for a while
                logger.debug("Not processing queue_entry %s", queued_node.fullname)
                sleep_time = config.daemon.processing_interval
            time_next_check = iteration_start + timedelta(seconds=sleep_time)
            queue_entry.time_next_check = time_next_check
            logger.info(f"Next check for {queued_node.fullname} at {time_next_check}")
        except Exception:
            logger.exception()
            continue
    await session.commit()

    # Try to allocate resources at the end of the loop, but do not crash if it
    # doesn't work.
    # FIXME this could be run async
    try:
        if config.daemon.allocate_resources and processed_nodes > 0:
            allocate_resources()
    except Exception:
        logger.exception()


def allocate_resources() -> None:
    """Allocate resources for htcondor jobs submitted during the daemon
    iteration.
    """
    if (htcondor := import_htcondor()) is None:
        logger.warning("HTCondor is not available, not allocating resources")
        return

    coll = htcondor.Collector(config.htcondor.collector_host)

    # Do we need to allocate resources? i.e., are there idle condor jobs for
    # which we are responsible?

    # FIXME we should round-robin submits to available schedds and approximate
    # a global query for our idle jobs.

    # schedds = coll.locateAll(htcondor.DaemonTypes.Schedd)

    # Mapping of schedd ad to a list of its idle jobs
    # idle_jobs = {
    #     ad: htcondor.Schedd(ad).query(
    #         projection=["ClusterId"],
    #         constraint="(JobStatus == 1)",
    #         opts=htcondor.QueryOpts.DefaultMyJobsOnly,
    #     )
    #     for ad in schedds
    # }

    # # Filter query result to those schedds with idle jobs
    # idle_job_schedds = [k for k, v in idle_jobs.items() if v]

    # if not idle_job_schedds:
    #     return

    # the schedd to which we need to submit this job should be one where idle
    # jobs are available. Pick one per daemon iteration; if there are multiple
    # schedds with idle jobs, the next loop will pick it up.
    # schedd = htcondor.Schedd(idle_job_schedds.pop())

    # FIXME only queries the single schedd to which we are submitting jobs
    schedd_ad = coll.locate(htcondor.DaemonTypes.Schedd, name=config.htcondor.schedd_host)
    schedd = htcondor.Schedd(schedd_ad)

    idle_jobs = schedd.query(
        projection=["ClusterId"],
        constraint="(JobStatus == 1)",
        opts=htcondor.QueryOpts.DefaultMyJobsOnly,
    )
    if not idle_jobs:
        return

    # Set the htcondor config in the submission environment
    # The environment command in the submit file is a double-quoted,
    # whitespace-delimited list of name=value pairs where literal quote marks
    # are doubled ("" or '').
    submission_environment = " ".join([f"{k}={v}" for k, v in build_htcondor_submit_environment().items()])

    # The minimum necessary submission spec executes a resource allocation
    # script to the local universe and does not preserve the output.
    submission_spec = {
        "executable": f"{config.htcondor.remote_user_home}/.local/bin/allocateNodes.py",
        "arguments": (
            f"--auto --account {config.slurm.account} -n 50 -m {config.slurm.duration} "
            f"-q {config.slurm.partition} -g 240 {config.slurm.platform}"
        ),
        "environment": f'"{submission_environment}"',
        "initialdir": config.htcondor.working_directory,
        "batch_name": config.htcondor.batch_name,
        "universe": "local",
    }
    submit_ad = htcondor.Submit(submission_spec)

    # job cluster id of our resource allocation script; fire and forget
    cluster_id = schedd.submit(submit_ad)
    logger.info("Allocating Resources with condor job %s", cluster_id.cluster())
    logger.debug(cluster_id)
