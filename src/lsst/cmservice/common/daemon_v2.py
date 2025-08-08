import pickle
from asyncio import Task as AsyncTask
from asyncio import TaskGroup, create_task
from collections.abc import Awaitable, Mapping
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from transitions import Event

from ..common import graph, timestamp
from ..common.enums import StatusEnum
from ..common.flags import Features
from ..config import config
from ..db.campaigns_v2 import Campaign, Edge, Machine, Node, Task
from ..db.session import db_session_dependency
from ..machines.node import NodeMachine, node_machine_factory
from .logging import LOGGER

logger = LOGGER.bind(module=__name__)


async def consider_campaigns(session: AsyncSession) -> None:
    """In Phase One, the daemon considers campaigns. Campaigns subject to
    consideration have a non-terminal prepared status (ready or running), and
    optionally tagged with a priority value lower than the daemon's own
    priority.

    For any campaigns thus discovered, the daemon then constructs a graph
    from the campaign's Edges, and starting at the START node, walks the graph
    until a Node is found that requires attention. Each Node found is added to
    the Tasks table as a queue item.
    """
    c_statement = (
        select(Campaign.id)
        .where(col(Campaign.status).in_((StatusEnum.ready, StatusEnum.running)))
        .with_for_update(key_share=True, skip_locked=True)
    )
    campaigns = (await session.exec(c_statement)).all()

    for campaign_id in campaigns:
        logger.info("Daemon considering campaign", id=campaign_id)

        # Fetch the Edges for the campaign
        e_statement = select(Edge).filter_by(namespace=campaign_id)
        edges = (await session.exec(e_statement)).all()
        campaign_graph = await graph.graph_from_edge_list_v2(edges=edges, session=session)

        for node in graph.processable_graph_nodes(campaign_graph):
            logger.info("Daemon considering node", id=str(node.id))
            desired_state = node.status.next_status()
            node_task = Task(
                id=uuid5(node.id, desired_state.name),
                namespace=campaign_id,
                node=node.id,
                status=desired_state,
                previous_status=node.status,
            )
            statement = insert(node_task.__table__).values(**node_task.model_dump())  # type: ignore[attr-defined]

            # When testing or developing, allow the daemon to upsert tasks
            # that already exist by unsetting their submitted_at/finished_at
            if Features.ALLOW_TASK_UPSERT in config.features.enabled:
                statement = statement.on_conflict_do_update(
                    constraint="tasks_v2_pkey",  # FIXME discover this constraint programatically
                    set_={col(Task.finished_at): None, col(Task.submitted_at): None},
                )
            else:
                statement = statement.on_conflict_do_nothing()
            await session.exec(statement)  # type: ignore[call-overload]

    await session.commit()


async def consider_nodes(session: AsyncSession) -> None:
    """In Phase Two, the daemon considers Nodes. Nodes subject to consideration
    are only those Nodes found on the Tasks table that have a priority lower
    than the daemon's own priority, and share the daemon's site affinity.

    For each node considered by the daemon, the Node's FSM is loaded from the
    Machines table, or creates one if needed. The daemon uses methods on the
    Node's Stateful Model to evolve the state of the Node.

    After handling, the Node's FSM is serialized and the Node is updated with
    new values as necessary. The Task is not returned to the Task table.
    """
    # Select and lock unsubmitted tasks
    statement = select(Task).where(col(Task.submitted_at).is_(None))
    # TODO add filter criteria for priority and site affinity
    statement = statement.with_for_update(skip_locked=True)

    cm_tasks = (await session.exec(statement)).all()

    # Using a TaskGroup context manager means all "tasks" added to the group
    # are awaited when the CM exits, giving us concurrency for all the nodes
    # being considered in the current iteration.
    async with TaskGroup() as tg:
        for cm_task in cm_tasks:
            node = await session.get_one(Node, cm_task.node)

            # the task's status field is the target status for the node, so the
            # daemon intends to evolve the node machine to that state.
            try:
                assert node.status is cm_task.previous_status
            except AssertionError:
                logger.error("Node status out of sync with Machine", id=str(node.id))
                continue

            # Expunge the node from *this* session because it will be added to
            # whatever session the node_machine acquires during its transition
            session.expunge(node)

            node_machine: NodeMachine
            node_machine_pickle: Machine | None
            if node.machine is None:
                # create a new machine for the node
                node_machine = node_machine_factory(node.kind)(o=node, initial_state=node.status)
                node_machine_pickle = None
            else:
                # unpickle the node's machine and rehydrate the Stateful Model
                node_machine_pickle = await session.get_one(Machine, node.machine)
                node_machine = (pickle.loads(node_machine_pickle.state)).model
                node_machine.db_model = node
                # discard the pickled machine from this session and context
                session.expunge(node_machine_pickle)
                del node_machine_pickle

            # check possible triggers for state
            # TODO how to pick the "best" trigger from multiple available?
            # - Add a caller-backed conditional to the triggers, to identify
            #   triggers the daemon is "allowed" to use
            # - Determine the "desired" trigger from the task (source, dest)
            if (trigger := trigger_for_transition(cm_task, node_machine.machine.events)) is None:
                logger.warning(
                    "No trigger available for desired state transition",
                    source=cm_task.previous_status,
                    dest=cm_task.status,
                )
                continue

            # Add the node transition trigger method to the task group
            task = tg.create_task(node_machine.trigger(trigger), name=str(cm_task.id))
            task.add_done_callback(task_runner_callback)

            # wrap up - update the task and commit
            cm_task.submitted_at = timestamp.now_utc()
            await session.commit()


async def daemon_iteration() -> None:
    """A single iteraton of the CM daemon's work loop, which is carried out in
    two phases: Campaigns and Nodes.
    """
    if TYPE_CHECKING:
        assert db_session_dependency.sessionmaker is not None
    session = db_session_dependency.sessionmaker()
    iteration_start = timestamp.now_utc()
    logger.debug("Daemon V2 Iteration: %s", iteration_start)
    if Features.DAEMON_CAMPAIGNS in config.features.enabled:
        await consider_campaigns(session)
    if Features.DAEMON_NODES in config.features.enabled:
        await consider_nodes(session)
    await session.close()


def trigger_for_transition(task: Task, events: Mapping[str, Event]) -> str | None:
    """Determine the trigger name for transition that matches the desired state
    tuple as indicated on a Task.
    """

    for trigger, event in events.items():
        for transition_list in event.transitions.values():
            for transition in transition_list:
                if all(
                    [
                        transition.source == task.previous_status.name,
                        transition.dest == task.status.name,
                    ]
                ):
                    return trigger
    return None


async def finalize_runner_callback(context: AsyncTask) -> None:
    """Callback function for finalizing the CM Task runner."""

    # Using the task name as the ID of a task, get the object and update its
    # finished_at column. Alternately, we could delete the task from the table
    # now.
    if TYPE_CHECKING:
        assert db_session_dependency.sessionmaker is not None

    logger.info("Finalizing CM Task", id=context.get_name())
    async with db_session_dependency.sessionmaker.begin() as session:
        cm_task = await session.get_one(Task, UUID(context.get_name()))
        cm_task.finished_at = timestamp.now_utc()


def task_runner_callback(context: AsyncTask) -> None:
    """Callback function for `asyncio.TaskGroup` tasks."""
    if (exc := context.exception()) is not None:
        logger.error(exc)
        return

    logger.info("Transition complete", id=context.get_name())
    callbacks: set[Awaitable] = set()
    # TODO: notification callback
    finalizer = create_task(finalize_runner_callback(context))
    finalizer.add_done_callback(callbacks.discard)
    callbacks.add(finalizer)
