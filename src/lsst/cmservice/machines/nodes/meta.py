import pickle
import shutil
from os.path import expandvars
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from anyio import Path
from fastapi.concurrency import run_in_threadpool
from transitions import EventData
from transitions.extensions.asyncio import AsyncEvent, AsyncMachine

from ...common import timestamp
from ...common.enums import ManifestKind, StatusEnum
from ...common.flags import Features
from ...common.logging import LOGGER
from ...config import config
from ...db.campaigns_v2 import ActivityLog, Campaign, Machine, Node
from ...db.session import db_session_dependency
from .. import lib
from ..abc import StatefulModel
from . import TRANSITIONS

logger = LOGGER.bind(module=__name__)


class NodeMachine(StatefulModel):
    """General state model for a Node in a Campaign Graph."""

    __kind__ = [ManifestKind.node]

    def __init__(
        self, *args: Any, o: Node, initial_state: StatusEnum = StatusEnum.waiting, **kwargs: Any
    ) -> None:
        self.db_model = o
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
        as a convenience to child classes.
        """
        pass

    def __getstate__(self) -> dict:
        """Prepares the stateful model for serialization, as with pickle."""
        # Remove members that are not picklable or should not be included
        # in the pickle
        state = self.__dict__.copy()
        del state["session"]
        del state["db_model"]
        del state["activity_log_entry"]
        return state

    async def error_handler(self, event: EventData) -> None:
        """Error handler function for the Stateful Model, called by the Machine
        if any exception is raised in a callback function.
        """
        if TYPE_CHECKING:
            assert self.db_model is not None

        if event.error is None:
            return

        logger.exception(event.error, id=str(self.db_model.id), exc=event.error.__class__.__qualname__)
        if self.activity_log_entry is not None:
            self.activity_log_entry.detail["trigger"] = event.event.name
            self.activity_log_entry.detail["error"] = str(event.error)
            self.activity_log_entry.detail["exception"] = event.error.__class__.__qualname__
            self.activity_log_entry.finished_at = timestamp.now_utc()

        # Auto-transition on error
        match event.event:
            case AsyncEvent(name="prepare"):
                await self.trigger("fail")
            case AsyncEvent(name="start"):
                await self.trigger("fail")
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
        assert self.db_model is not None, "Stateful Model must have a Node member."

        logger.debug("Preparing session for transition", id=str(self.db_model.id))
        if self.session is not None:
            await self.session.close()
        else:
            assert db_session_dependency.sessionmaker is not None
            self.session = db_session_dependency.sessionmaker()

    async def prepare_activity_log(self, event: EventData) -> None:
        """Callback method invoked by the Machine before every state-change."""
        if TYPE_CHECKING:
            assert self.db_model is not None

        if self.activity_log_entry is not None:
            return None

        logger.debug("Preparing activity log for transition", id=str(self.db_model.id))

        from_state = StatusEnum[event.transition.source] if event.transition else self.state
        to_state = (
            StatusEnum[event.transition.dest] if event.transition and event.transition.dest else self.state
        )

        self.activity_log_entry = ActivityLog(
            namespace=self.db_model.namespace,
            node=self.db_model.id,
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
            assert self.db_model is not None, "Stateful Model must have a Node member."
            assert self.session is not None
        logger.debug("Updating the ORM instance after transition.", id=str(self.db_model.id))

        if self.activity_log_entry is not None:
            self.activity_log_entry.to_status = self.state
            self.activity_log_entry.finished_at = timestamp.now_utc()

        # Ensure database record for transitioned object is updated
        self.db_model = await self.session.merge(self.db_model, load=False)
        self.db_model.status = self.state
        self.db_model.metadata_["mtime"] = timestamp.element_time()
        await self.session.commit()

    async def finalize(self, event: EventData) -> None:
        """Callback method invoked by the Machine unconditionally at the end
        of every callback chain. During this callback, if the activity log
        indicates that change has occurred, it is written to the db and the
        machine is serialized to the Machines table for later use.
        """
        if TYPE_CHECKING:
            assert self.db_model is not None
            assert self.session is not None

        # The activity log entry is added to the db. For failed transitions it
        # may include error detail. For other transitions it is not necessary
        # to log every attempt.
        if self.activity_log_entry is None:
            return
        elif self.activity_log_entry.finished_at is None:
            return

        # ensure the orm instance is in the session
        if self.db_model not in self.session:
            self.db_model = await self.session.merge(self.db_model, load=False)

        # flush the activity log entry to the db
        try:
            logger.debug("Finalizing the activity log after transition.", id=str(self.db_model.id))
            self.session.add(self.activity_log_entry)
            await self.session.commit()
        except Exception:
            logger.exception()
            await self.session.rollback()
        finally:
            self.session.expunge(self.activity_log_entry)
            self.activity_log_entry = None

        # create or update a machine entry in the db
        if Features.STORE_FSM in config.features.enabled:
            new_machine = Machine.model_validate(
                dict(id=self.db_model.machine or uuid4(), state=pickle.dumps(self.machine))
            )
            try:
                logger.debug("Serializing the state machine after transition.", id=str(self.db_model.id))
                await self.session.merge(new_machine)
                self.db_model.machine = new_machine.id
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

    __kind__ = [ManifestKind.start]

    def post_init(self) -> None:
        """Post init, set class-specific callback triggers."""
        self.machine.before_prepare("do_prepare")
        self.machine.before_unprepare("do_unprepare")
        self.machine.before_start("do_start")
        self.machine.before_reset("do_reset")

    async def get_artifact_path(self) -> Path | None:
        """Determine filesystem location as a `pathlib` or `anyio` ``Path``
        object, returning ``None`` if the path cannot be determined.
        """
        if self.session is None:
            return None
        if self.db_model is None:
            return None
        if TYPE_CHECKING:
            assert isinstance(self.db_model, Node)

        fallback_configuration = {"lsst": {"artifact_path": expandvars(config.bps.artifact_path)}}
        config_chain = await lib.assemble_config_chain(
            self.session, self.db_model, manifest_kind=ManifestKind.lsst, extra=[fallback_configuration]
        )
        artifact_path = config_chain["lsst"]["artifact_path"]
        return Path(artifact_path) / str(self.db_model.namespace)

    async def do_prepare(self, event: EventData) -> None:
        """Action method invoked when executing the "prepare" transition.

        For a Campaign to enter the ready state, the START node must consider:

        - artifact directory is created and writable.
        """
        if TYPE_CHECKING:
            assert isinstance(self.db_model, Node)
            assert self.session is not None

        logger.info("Preparing START node", id=str(self.db_model.id))

        if artifact_location := await self.get_artifact_path():
            await artifact_location.mkdir(parents=False, exist_ok=True)

    async def do_unprepare(self, event: EventData) -> None:
        if TYPE_CHECKING:
            assert isinstance(self.db_model, Node)
            assert self.session is not None

        logger.info("Unpreparing START node", id=str(self.db_model.id))

        artifact_location = await self.get_artifact_path()
        if artifact_location and artifact_location.exists():
            await run_in_threadpool(shutil.rmtree, artifact_location)

    async def do_start(self, event: EventData) -> None:
        """Callback invoked when entering the "running" state."""
        if TYPE_CHECKING:
            assert self.db_model is not None

        logger.debug("Starting START Node for Campaign", id=str(self.db_model.id))
        return None

    async def do_reset(self, event: EventData) -> None:
        logger.error("Resetting node")


class EndMachine(NodeMachine):
    """Specific state model for a Node of kind End.

    The End Node is responsible for wrapping-up the successful completion of a
    Campaign.
    """

    __kind__ = [ManifestKind.end]

    def post_init(self) -> None:
        """Post init, set class-specific callback triggers."""
        # Wrap up campaign butler collections
        # update parent campaign status
        self.machine.before_finish("do_finish")

    async def do_finish(self, event: EventData) -> None:
        """When transitioning to a terminal positive state, also set the same
        status on the Campaign.
        """
        if TYPE_CHECKING:
            assert self.db_model is not None
            assert self.session is not None
        # Set the campaign status to accepted.
        # TODO optionally, we could hydrate a Campaign FSM instance and call
        #      its trigger.
        parent_campaign = await self.session.get_one(Campaign, self.db_model.namespace, with_for_update=True)
        parent_campaign.status = StatusEnum.accepted
        parent_campaign.metadata_["mtime"] = timestamp.element_time()
        await self.session.commit()
