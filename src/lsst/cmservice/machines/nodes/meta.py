"""Module defining the base StatefulModel of a CM Node as well as basic meta
nodes, including START/END/BREAKPOINT nodes.
"""

from __future__ import annotations

import pickle
import shutil
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import inspect
from sqlalchemy.orm import make_transient_to_detached
from sqlmodel import select
from transitions import EventData
from transitions.extensions.asyncio import AsyncEvent, AsyncMachine

from ...common import timestamp
from ...common.enums import ManifestKind, StatusEnum
from ...common.flags import Features
from ...common.graph import graph_from_edge_list_v2
from ...common.launchers import LauncherCheckResponse
from ...common.logging import LOGGER
from ...config import config
from ...db.campaigns_v2 import ActivityLog, Edge, Machine, Node
from ...db.session import db_session_dependency
from ...models.manifest import ButlerManifest
from ..abc import StatefulModel
from . import TRANSITIONS
from .mixin import FilesystemActionMixin, HTCondorLaunchMixin, NodeMixIn

logger = LOGGER.bind(module=__name__)


class NodeMachine(StatefulModel):
    """General state model for a Node in a Campaign Graph.

    The methods and attributes of this class are limited to those directly
    related to State Machine operations. Other functionality for specific kinds
    of Nodes are implemented as MixIn classes that extend this implementation.
    """

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
        del state["db_model"]
        del state["activity_log_entry"]
        if "launch_manager" in state.keys():
            del state["launch_manager"]
        if "session" in state.keys():
            del state["session"]
        return state

    def get_activity_log(self, event: EventData) -> ActivityLog:
        """Constructs and returns an activity log database entry for ad-hoc
        use. The entry is not part of any session.

        Both "from" and "to" states are set to the same value, making the log
        entry initially useful as a "milestone" entry since it does not
        represent a complete transition
        """
        from_state = StatusEnum[event.transition.source] if event.transition else self.state
        to_state = from_state

        activity_log_entry = ActivityLog(
            namespace=self.db_model.namespace,
            node=self.db_model.id,
            operator=event.kwargs.get("operator", "daemon"),
            from_status=from_state,
            to_status=to_state,
            detail={},
            metadata_={"request_id": event.kwargs.get("request_id")},
        )
        return activity_log_entry

    async def error_handler(self, event: EventData) -> None:
        """Error handler function for the Stateful Model, called by the Machine
        if any exception is raised in a callback function.
        """
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
        if not hasattr(self, "db_model") or self.db_model is None:
            raise RuntimeError("Stateful Model must have a Node member.")

        logger.debug("Preparing session for transition", id=str(self.db_model.id))
        if hasattr(self, "session"):
            await self.session.close()
        else:
            assert db_session_dependency.sessionmaker is not None
            self.session = db_session_dependency.sessionmaker()

    async def prepare_activity_log(self, event: EventData) -> None:
        """Callback method invoked by the Machine before every state-change."""
        if self.activity_log_entry is not None:
            return None

        logger.debug("Preparing activity log for transition", id=str(self.db_model.id))
        self.activity_log_entry = self.get_activity_log(event)

    async def repatriate_node(self, event: EventData) -> None:
        """Ensures the ORM model of the Node associated with this machine is
        integrated with the current database session.
        """
        # Repatriate the transient node object and add it to the session, along
        # with any modifications made during the machine transition functions
        if (insp := inspect(self.db_model)) is not None:
            if insp.transient:
                make_transient_to_detached(self.db_model)
        if self.db_model not in self.session:
            self.db_model = await self.session.merge(self.db_model, load=True)

    async def update_persistent_status(self, event: EventData) -> None:
        """Callback method invoked by the Machine after every state-change."""
        # Update activity log entry with new state and timestamp
        logger.debug("Updating the ORM instance after transition.", id=str(self.db_model.id))

        if self.activity_log_entry is not None:
            self.activity_log_entry.to_status = self.state
            self.activity_log_entry.finished_at = timestamp.now_utc()

        # Workaround to issue with sqlalchemy tracking changes to mutable types
        # Update the node mtime and reapply the entire metadata dict
        new_metadata = self.db_model.metadata_.copy()
        new_metadata["mtime"] = timestamp.element_time()

        # Repatriate the transient node object and add it to the session, along
        # with any modifications made during the machine transition functions
        await self.repatriate_node(event)
        self.db_model.status = self.state
        self.db_model.metadata_ = new_metadata
        await self.session.commit()

    async def finalize(self, event: EventData) -> None:
        """Callback method invoked by the Machine unconditionally at the end
        of every callback chain. During this callback, if the activity log
        indicates that change has occurred, it is written to the db and the
        machine is serialized to the Machines table for later use.
        """
        # ensure the orm instance is in the session and make sure any changes
        # to mutable mappings are captured.
        if not hasattr(self, "session"):
            logger.warning("Machine has no session, skipping finalize callback", node=str(self.db_model.id))
            return

        try:
            logger.debug("Repatriating and updating Node after transition", id=str(self.db_model.id))
            await self.repatriate_node(event)
            self.db_model.metadata_ = self.db_model.metadata_.copy()
            await self.session.commit()
        except Exception:
            logger.exception()
            await self.session.rollback()

        # The activity log entry is added to the db. For failed transitions it
        # may include error detail. For other transitions it is not necessary
        # to log every attempt.
        if self.activity_log_entry is None:
            return
        elif self.activity_log_entry.finished_at is None:
            return

        logger.debug("Finalizing the machine after transition.", id=str(self.db_model.id))

        # make sure any changes to mutable mappings are captured.
        self.db_model.metadata_ = self.db_model.metadata_.copy()

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
                new_machine = await self.session.merge(new_machine)
                self.db_model.machine = new_machine.id
                await self.session.commit()
            except Exception:
                logger.exception()
                await self.session.rollback()
            finally:
                if new_machine in self.session:
                    self.session.expunge(new_machine)

        await self.session.close()
        del self.session

    async def is_startable(self, event: EventData) -> bool:
        """Conditional method called to check whether a ``start`` trigger may
        be called.
        """
        return True

    async def is_restartable(self, event: EventData) -> bool:
        """Conditional method called to check whether a ``restart`` trigger may
        be called.
        """
        # Only machines with an explicit restart mechanism should implement
        # this callback.
        return False

    async def do_start(self, event: EventData) -> None:
        """Action method invoked when executing the "start" transition.

        For a Start node to enter the started state, it must call the "launch"
        method provided by its ``LaunchMixin``.
        """
        logger.debug(
            "Starting Node for Campaign", id=str(self.db_model.id), campaign=str(self.db_model.namespace)
        )

        if not hasattr(self, "configuration_chain"):
            # this can happen if the Node FSM was not pickled between trans-
            # itions (see `Features.STORE_FSM`).
            # TODO reconstitute the necessary parts of the configuration chain
            #      to affect a start trigger
            ...
        if hasattr(self, "launch"):
            await self.launch(event)  # pyright: ignore[reportAttributeAccessIssue]
        return None

    async def is_done_running(self, event: EventData) -> bool:
        """Conditional method called to check whether a ``finish`` trigger may
        be called.
        """
        logger.debug(
            "Checking whether Node is done running",
            id=str(self.db_model.id),
            campaign=str(self.db_model.namespace),
        )
        if hasattr(self, "check"):
            done = await self.check(event)  # pyright: ignore[reportAttributeAccessIssue]
        else:
            done = LauncherCheckResponse(success=True)

        launcher_metadata = {
            "timestamp": int(done.timestamp.timestamp()),
            "job_id": done.job_id,
            **done.metadata_,
        }
        new_metadata = self.db_model.metadata_.copy()
        new_metadata["launcher"] = launcher_metadata
        self.db_model.metadata_ = new_metadata
        return done.success


class StartMachine(NodeMachine, NodeMixIn, FilesystemActionMixin, HTCondorLaunchMixin):
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
        self.templates = {
            ("wms_submit_sh.j2", f"{self.db_model.name}.sh"),
        }

    async def butler_prepare(self, event: EventData) -> None:
        """Prepares Butler collections for the campaign."""
        self.butler = await self.get_manifest(ManifestKind.butler, ButlerManifest)

        # TODO Campaigns should support options about how their collections are
        # organized.
        # - CHAIN_ONLY: all input and ancillary collections are chained into a
        #               single collection used by each step.
        # - TAGGED_CHAIN: the first input collection is used with the campaign
        #                 predicates to create a tagged collection, which is
        #                 then chained to any addition input and/or ancillary
        #                 collections.
        # - NONE: no campaign-level collection is created. Instead, each step
        #         creates its own input collection by chaining the campaign
        #         inputs.
        self.command_templates = [
            (
                "{{butler.exe_bin}} collection-chain {{butler.repo}} {{butler.collections.campaign_output}}"
                "{% for collection in butler.collections.campaign_input %} {{collection}}{% endfor %}"
                "{% for collection in butler.collections.ancillary %} {{collection}}{% endfor %}"
            )
        ]
        # Prepare a Butler runtime config to add to the Node's config chain,
        # which includes additional collection information beyond what's spec-
        # ified in the Node's reference Butler manifest.
        butler_config: dict[str, Any] = {}
        butler_config["exe_bin"] = (
            "true" if Features.MOCK_BUTLER in config.features.enabled else config.butler.butler_bin
        )
        butler_config["collections"] = self.butler.spec.collections.model_copy(
            update={
                "tagged_input": f"{self.butler.spec.collections.campaign_public_output}/tagged",
                "chained_input": f"{self.butler.spec.collections.campaign_public_output}/chained",
            },
        )

        self.configuration_chain["butler"] = self.configuration_chain["butler"].new_child(butler_config)

    async def do_prepare(self, event: EventData) -> None:
        """Action method invoked when executing the "prepare" transition.

        For a Campaign to enter the ready state, the START node must consider:

        - artifact directory is created and writable.
        - mandatory campaign-level butler collections are created.
        """
        logger.info("Preparing START node", id=str(self.db_model.id))

        # Call prepare callback provided by Mixins
        await self.action_prepare(event)
        await self.butler_prepare(event)
        await self.launch_prepare(event)
        await self.render_action_templates(event)

    async def do_unprepare(self, event: EventData) -> None:
        logger.info("Unpreparing START node", id=str(self.db_model.id))
        await self.get_artifact_path(event)

        if await self.artifact_path.exists():
            await run_in_threadpool(shutil.rmtree, self.artifact_path)

    async def do_reset(self, event: EventData) -> None:
        logger.error("Resetting node")


class EndMachine(NodeMachine, NodeMixIn, FilesystemActionMixin, HTCondorLaunchMixin):
    """Specific state model for a Node of kind End.

    The End Node is responsible for wrapping-up the successful completion of a
    Campaign.
    """

    __kind__ = [ManifestKind.end]

    def post_init(self) -> None:
        """Post init, set class-specific callback triggers."""
        # Wrap up campaign butler collections
        # update parent campaign status
        self.machine.before_prepare("do_prepare")
        self.machine.before_start("do_start")
        self.machine.before_finish("do_finish")
        self.templates = {
            ("wms_submit_sh.j2", f"{self.db_model.name}.sh"),
        }

    async def butler_prepare(self, event: EventData) -> None:
        """Prepares Butler collections for the end of the campaign."""
        self.butler = await self.get_manifest(ManifestKind.butler, ButlerManifest)

        self.command_templates = [
            (
                "{{butler.exe_bin}} collection-chain {{butler.repo}} {{butler.collections.campaign_output}}"
                "{% for collection in butler.collections.step_collections %} {{collection}}{% endfor %} "
            ),
            (
                "{{butler.exe_bin}} collection-chain {{butler.repo}} "
                "{{butler.collections.campaign_public_output}} {{butler.collections.campaign_output}}"
            ),
        ]

        butler_config: dict[str, Any] = {}
        butler_config["exe_bin"] = (
            "true" if Features.MOCK_BUTLER in config.features.enabled else config.butler.butler_bin
        )
        butler_config["collections"] = self.butler.spec.collections.model_copy(
            update={
                "step_collections": self.collections,
            },
        )

        self.configuration_chain["butler"] = self.configuration_chain["butler"].new_child(butler_config)

    async def do_prepare(self, event: EventData) -> None:
        """Determine the set of step output collections to chain together for
        the campaign's output collection.
        """
        # For every node in the campaign graph of kind collect_groups, discover
        # its output collection.
        s = select(Edge).where(Edge.namespace == self.db_model.namespace)
        edges = (await self.session.exec(s)).all()
        graph = await graph_from_edge_list_v2(edges, self.session)

        collect_steps = [
            node[1]["model"]
            for node in graph.nodes.data()
            if node[1]["model"].kind is ManifestKind.collect_groups
        ]
        self.collections = [
            collect_step.configuration["butler"]["collections"]["step_output"]
            for collect_step in collect_steps
        ]

        # perform specific preparations
        await self.action_prepare(event)
        await self.launch_prepare(event)
        await self.butler_prepare(event)

        # Render executable artifacts
        await self.render_action_templates(event)

    async def do_finish(self, event: EventData) -> None:
        """When transitioning to a terminal positive state, also set the same
        status on the Campaign.
        """
        if TYPE_CHECKING:
            assert isinstance(self.db_model, Node)
        # Set the campaign status to accepted.
        # NOTE: Neither the node nor its related campaign object are not part
        # of the session at this point, so these changes are not materialized
        # by a commit in this method (see `update_persistent_status`)
        self.db_model.campaign.status = StatusEnum.accepted
        self.db_model.campaign.metadata_["mtime"] = timestamp.element_time()


class BreakPointMachine(NodeMachine):
    """Specific state model for a Node of kind Breakpoint.

    The BreakPoint Node is responsible for interrupting a campaign's graph
    until it is put into an accepted state by intentional manual action.

    The CM Daemon will refuse to evolve a Node of this kind.
    """

    __kind__ = [ManifestKind.breakpoint]
