# ruff: noqa
"""Module for state machine implementations related to Nodes."""

import inspect
import pickle
import shutil
import sys
from collections.abc import Mapping
from functools import cache
from os.path import expandvars
from typing import Any, TYPE_CHECKING
from uuid import uuid4, uuid5

from anyio import Path
from fastapi.concurrency import run_in_threadpool
from sqlmodel.ext.asyncio.session import AsyncSession
from transitions import EventData
from transitions.extensions.asyncio import AsyncEvent, AsyncMachine

from ..common import timestamp
from ..common.enums import ManifestKind, StatusEnum
from ..common.logging import LOGGER
from ..config import config
from ..db.campaigns_v2 import ActivityLog, Machine, Node
from ..db.session import get_async_session
from .abc import StatefulModel

logger = LOGGER.bind(module=__name__)


TRANSITIONS = [
    # The critical/happy path of state evolution from waiting to accepted
    {
        "trigger": "prepare",
        "source": StatusEnum.waiting,
        "dest": StatusEnum.ready,
    },
    {
        "trigger": "start",
        "source": StatusEnum.ready,
        "dest": StatusEnum.running,
        "conditions": "is_startable",
    },
    {
        "trigger": "finish",
        "source": StatusEnum.running,
        "dest": StatusEnum.accepted,
        "conditions": "is_done_running",
    },
    # The bad transitions
    {"trigger": "block", "source": StatusEnum.running, "dest": StatusEnum.blocked},
    {"trigger": "fail", "source": StatusEnum.running, "dest": StatusEnum.failed},
    # User-initiated transitions
    {"trigger": "pause", "source": StatusEnum.running, "dest": StatusEnum.paused},
    {"trigger": "unblock", "source": StatusEnum.blocked, "dest": StatusEnum.running},
    {"trigger": "resume", "source": StatusEnum.paused, "dest": StatusEnum.running},
    {"trigger": "force", "source": StatusEnum.failed, "dest": StatusEnum.accepted},
    # Inverse transitions, i.e., rollbacks
    {"trigger": "unprepare", "source": StatusEnum.ready, "dest": StatusEnum.waiting},
    {"trigger": "stop", "source": StatusEnum.paused, "dest": StatusEnum.ready},
    {"trigger": "retry", "source": StatusEnum.failed, "dest": StatusEnum.ready},
]
"""Transitions available to a Node, expressed as source-destination pairs
with a named trigger-verb.
"""


class NodeMachine(StatefulModel):
    """General state model for a Node in a Campaign Graph."""

    __kind__ = [ManifestKind.node]
    node: Node | None
    machine: AsyncMachine
    activity_log_entry: ActivityLog | None = None
    session: AsyncSession | None = None

    def __init__(
        self, *args: Any, o: Node, initial_state: StatusEnum = StatusEnum.waiting, **kwargs: Any
    ) -> None:
        self.node = o
        self.machine = AsyncMachine(
            model=self,
            states=StatusEnum,
            transitions=TRANSITIONS,
            initial=initial_state,
            auto_transitions=False,
            prepare_event=["prepare_session", "prepare_activity_log"],
            after_state_change="update_persistent_status",
            finalize_event="finalize",
            on_exception="error_handler",
            send_event=True,
            model_override=True,
        )
        self.post_init()

    def post_init(self) -> None:
        """Additional initialization method called at the end of ``__init__``,
        as a convenenience to child classes.
        """
        pass

    def __getstate__(self) -> dict:
        """Prepares the stateful model for serialization, as with pickle."""
        # Remove members that are not picklable or should not be included
        # in the pickle
        state = self.__dict__.copy()
        del state["session"]
        del state["node"]
        del state["activity_log_entry"]
        return state

    async def error_handler(self, event: EventData) -> None:
        """Error handler function for the Stateful Model, called by the Machine
        if any exception is raised in a callback function.
        """
        if event.error is None:
            return

        logger.exception(event.error)
        if self.activity_log_entry is not None:
            self.activity_log_entry.detail["trigger"] = event.event.name
            self.activity_log_entry.detail["error"] = str(event.error)

        # Auto-transition on error
        match event.event:
            case AsyncEvent(name="finish"):
                # TODO if we need to distinguish between types of failures,
                #      e.g., fail vs block, we'd have to inspect the error here
                await self.trigger("fail")
            case _:
                ...

    async def prepare_session(self, event: EventData) -> None:
        """Prepares the machine by acquiring a database session."""
        # This positive assertion concerning the ORM member will prevent
        # any callback from proceeding if no such member is defined, but type
        # checkers don't know this, which is why it repeated in a TYPE_CHECKING
        # guard in each method that accesses the ORM member.
        assert self.node is not None, "Stateful Model must have a Node member."

        logger.debug("Preparing session for transition", id=str(self.node.id))
        if self.session is not None:
            await self.session.close()
        else:
            self.session = await get_async_session()

    async def prepare_activity_log(self, event: EventData) -> None:
        """Callback method invoked by the Machine before every state-change."""
        if TYPE_CHECKING:
            assert self.node is not None

        if self.activity_log_entry is not None:
            return None

        logger.debug("Preparing activity log for transition", id=str(self.node.id))

        from_state = StatusEnum[event.transition.source] if event.transition else self.state
        to_state = (
            StatusEnum[event.transition.dest] if event.transition and event.transition.dest else self.state
        )

        self.activity_log_entry = ActivityLog(
            id=uuid4(),
            namespace=self.node.namespace,
            node=self.node.id,
            operator="daemon",
            from_status=from_state,
            to_status=to_state,
            detail={},
            metadata_={},
        )

    async def update_persistent_status(self, event: EventData) -> None:
        """Callback method invoked by the Machine after every state-change."""
        # Update activity log entry with new state and timestamp
        if TYPE_CHECKING:
            assert self.node is not None, "Stateful Model must have a Node member."
            assert self.session is not None
        logger.debug("Updating the ORM instance after transition.", id=str(self.node.id))

        if self.activity_log_entry is not None:
            self.activity_log_entry.to_status = self.state
            self.activity_log_entry.detail["finished_at"] = timestamp.element_time()

        # Ensure database record for transitioned object is updated
        self.node = await self.session.merge(self.node, load=False)
        self.node.status = self.state
        await self.session.commit()

    async def finalize(self, event: EventData) -> None:
        """Callback method invoked by the Machine unconditionally at the end
        of every callback chain.
        """
        if TYPE_CHECKING:
            assert self.node is not None, "Stateful Model must have a Node member."
            assert self.session is not None

        # The activity log entry is added to the db. For failed transitions it
        # may include error detail. For other transitions it is not necessary
        # to log every attempt, so if no callback has registered any detail
        # for the log entry it is not persisted.
        if self.activity_log_entry is None:
            return
        elif not len(self.activity_log_entry.detail):
            return

        # ensure the orm instance is in the session
        if self.node not in self.session:
            self.node = await self.session.merge(self.node, load=False)

        # flush the activity log entry to the db
        try:
            logger.debug("Finalizing the activity log after transition.", id=str(self.node.id))
            self.session.add(self.activity_log_entry)
            await self.session.commit()
        except Exception:
            logger.exception()
            await self.session.rollback()
        finally:
            self.session.expunge(self.activity_log_entry)
            self.activity_log_entry = None

        # create or update a machine entry in the db
        new_machine = Machine.model_validate(
            dict(id=self.node.machine or uuid4(), state=pickle.dumps(self.machine))
        )
        try:
            logger.debug("Serializing the state machine after transition.", id=str(self.node.id))
            await self.session.merge(new_machine)
            self.node.machine = new_machine.id
            await self.session.commit()
        except Exception:
            logger.exception()
            await self.session.rollback()
        finally:
            self.session.expunge(new_machine)

        await self.session.close()
        self.session = None

    async def is_startable(self, event: EventData) -> bool:
        """Conditional method called to check whether a ``start`` trigger may
        be called.
        """
        return True

    async def is_done_running(self, event: EventData) -> bool:
        """Conditional method called to check whether a ``finish`` trigger may
        be called.
        """
        return True


class StartMachine(NodeMachine):
    """Conceptually, a campaign's START node may participate in activities like
    any other kind of node, even though its purpose is to provide a solid well-
    known root to the campaign graph. Some activities assigned to the Campaign
    Machine could also be modeled as belonging to the START node instead. The
    END node could serve a similar purpose.
    """

    __kind__ = [ManifestKind.node]

    def post_init(self) -> None:
        """Post init, set class-specific callback triggers."""
        self.machine.before_prepare("do_prepare")
        self.machine.before_unprepare("do_unprepare")
        self.machine.before_start("do_start")

    async def do_prepare(self, event: EventData) -> None:
        """Action method invoked when executing the "prepare" transition.

        For a Campaign to enter the ready state, the machine must consider:

        Conditions
        ----------
        - the campaign's graph is valid.

        Callbacks
        ---------
        - artifact directory is created and writable.
        """
        if TYPE_CHECKING:
            assert self.node is not None

        logger.info("Preparing START node", id=str(self.node.id))

        artifact_location = Path(expandvars(config.bps.artifact_path)) / str(self.node.namespace)
        await artifact_location.mkdir(parents=False, exist_ok=True)

    async def do_unprepare(self, event: EventData) -> None:
        if TYPE_CHECKING:
            assert self.node is not None

        logger.info("Unpreparing START node", id=str(self.node.id))
        artifact_location = Path(expandvars(config.bps.artifact_path)) / str(self.node.namespace)
        await run_in_threadpool(shutil.rmtree, artifact_location)

    async def do_start(self, event: EventData) -> None:
        """Callback invoked when entering the "running" state.

        There is no particular work performed when a campaign enters a running
        state other than to update the record's entry in the database which
        acts as a flag to an executor to signal that a campaign's graph Nodes
        may now be evolved.
        """
        if TYPE_CHECKING:
            assert self.node is not None

        logger.debug("Starting START Node for Campaign", id=str(self.node.id))
        return None


class StepMachine(NodeMachine):
    """Specific state model for a Node of kind GroupedStep.

    The Step-Nodes may be the most involved state models, as the logic that
    must execute during each transition is complex. The behaviors are generally
    the same as the "scripts" associated with a Step/Group/Job in the legacy
    CM implementation.

    A summary of the logic at each transition:

    - prepare
        - determine number of groups and group membership
        - create new Manifest for each Group
    - start
        - create new StepGroup Nodes (reading prepared Manifests)
        - create new StepCollect Node
        - create edges
    - finish
        - (condition) campaign graph is valid
    - unprepare (rollback)
        - no particular action taken, but know that on the next use of "prepare"
          new versions of the group manifests may be created.

    Failure modes may include
        - Butler errors (can't query for group membership)
        - Bad inputs (group membership rules don't make sense)
    """

    __kind__ = [ManifestKind.grouped_step]

    def __init__(
        self, *args: Any, o: Node, initial_state: StatusEnum = StatusEnum.waiting, **kwargs: Any
    ) -> None:
        super().__init__(*args, o, initial_state, **kwargs)
        self.machine.before_prepare("do_prepare")
        self.machine.before_start("do_start")
        self.machine.before_unprepare("do_unprepare")
        self.machine.before_finish("do_finish")

    async def do_prepare(self, event: EventData) -> None: ...

    async def do_unprepare(self, event: EventData) -> None: ...

    async def do_start(self, event: EventData) -> None: ...

    async def do_finish(self, event: EventData) -> None: ...

    async def is_successful(self, event: EventData) -> bool:
        """Checks whether the WMS job is finished or not based on the result of
        a bps-report or similar. Returns a True value if the batch is done and
        good, a False value if it is still running. Raises an exception in any
        other terminal WMS state (HELD or FAILED).

        ```
        bps_report: WmsStatusReport = get_wms_status_from_bps(...)

        match bps_report:
           case WmsStatusReport(wms_status="FINISHED"):
                return True
           case WmsStatusReport(wms_status="HELD"):
                raise WmsBlockedError()
           case WmsStatusReport(wms_status="FAILED"):
                raise WmsFailedError()
           case WmsStatusReport(wms_status="RUNNING"):
                return False
        ```
        """
        return True


class GroupMachine(NodeMachine):
    """Specific state model for a Node of kind StepGroup.

    A summary of the logic at each transition:

    - prepare
        - create artifact output directory
        - collect all relevant configuration Manifests
        - render bps workflow artifacts
        - create butler in collection(s)

    - start
        - bps submit
        - (after_start) determine bps submit directory

    - finish
        - (condition) bps report == done
        - create butler out collection(s)

    - fail
        - read/parse bps output logs

    - stop (rollback)
        - bps cancel

    - unprepare (rollback)
        - remove artifact output directory
        - Butler collections are not modified (paint-over pattern)

    Failure modes may include:
        - Unwritable artifact output directory
        - Manifests insufficient to render bps workflow artifacts
        - Butler errors
        - BPS or other middleware errors
    """

    __kind__ = [ManifestKind.step_group]

    ...


class StepCollectMachine(NodeMachine):
    """Specific state model for a Node of kind StepCollect.

    - prepare
        - create step output chained butler collection

    - start
        - (condition) ancestor output collections exist in butler?
        - add each ancestor output collection to step output chain

    - finish
        - (condition) all ancestor output collections in chain
    """

    __kind__ = [ManifestKind.collect_groups]

    ...


@cache
def node_machine_factory(kind: ManifestKind) -> type[NodeMachine]:
    """Returns the Stateful Model for a node based on its kind, by matching
    the ``__kind__`` attribute of available classes in this module.

    TODO: May "construct" new classes from multiple matches, but this is not
    yet necessary.
    """
    for _, o in inspect.getmembers(sys.modules[__name__], inspect.isclass):
        if issubclass(o, NodeMachine) and kind in o.__kind__:
            return o
    return NodeMachine
