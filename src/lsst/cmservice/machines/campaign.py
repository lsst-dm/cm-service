"""Module for state machine implementations related to Campaigns.

A Campaign state machine should be a simple one, since a Campaign itself does
not need to implement much in the way of Actions or Triggers. A campaign's
status should generally reflect the "worst-case" status of any of Nodes active
in its namespace.

Since a campaign is mostly a container, the critical path of its state machine
should focus on validity and completeness of its graph, while providing useful
information about the overall campaign progress to pilots and other users.
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid5

from sqlmodel import select
from transitions import EventData
from transitions.extensions.asyncio import AsyncMachine

from ..common import timestamp
from ..common.enums import ManifestKind, StatusEnum
from ..common.graph import graph_from_edge_list_v2, validate_graph
from ..common.logging import LOGGER
from ..db.campaigns_v2 import ActivityLog, Campaign, Edge, Node
from .node import NodeMachine

logger = LOGGER.bind(module=__name__)


TRANSITIONS = [
    # The critical/happy path of state evolution from waiting to accepted
    {
        "trigger": "start",
        "source": StatusEnum.waiting,
        "dest": StatusEnum.running,
        "conditions": "has_valid_graph",
    },
    {
        "trigger": "finish",
        "source": StatusEnum.running,
        "dest": StatusEnum.accepted,
        "conditions": "is_successful",
    },
    # User-initiated transitions
    {"trigger": "pause", "source": StatusEnum.running, "dest": StatusEnum.paused},
    {
        "trigger": "resume",
        "source": StatusEnum.paused,
        "dest": StatusEnum.running,
        "conditions": "has_valid_graph",
    },
]
"""Transitions available to a Campaign, expressed as source-destination pairs
with a named trigger-verb.
"""


class InvalidCampaignGraphError(Exception): ...


class CampaignMachine(NodeMachine):
    """Class representing the stateful structure of a Campaign State Machine,
    including callbacks and actions to be executed during transitions.
    """

    __kind__ = [ManifestKind.campaign]

    def __init__(
        self, *args: Any, o: Campaign, initial_state: StatusEnum = StatusEnum.waiting, **kwargs: Any
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

    async def error_handler(self, event: EventData) -> None:
        """Error handler function for the Stateful Model, called by the Machine
        if any exception is raised in a callback function.
        """
        if TYPE_CHECKING:
            assert self.db_model is not None

        if event.error is None:
            return

        logger.exception(event.error, id=self.db_model.id)
        if self.activity_log_entry is not None:
            self.activity_log_entry.detail["trigger"] = event.event.name
            self.activity_log_entry.detail["error"] = str(event.error)
            self.activity_log_entry.finished_at = timestamp.now_utc()

    async def prepare_activity_log(self, event: EventData) -> None:
        """Callback method invoked by the Machine before every state-change."""

        if TYPE_CHECKING:
            assert self.db_model is not None

        if self.activity_log_entry is not None:
            return None

        from_state = StatusEnum[event.transition.source] if event.transition else self.state
        to_state = (
            StatusEnum[event.transition.dest] if event.transition and event.transition.dest else self.state
        )

        self.activity_log_entry = ActivityLog(
            namespace=self.db_model.id,
            operator=event.kwargs.get("operator", "daemon"),
            from_status=from_state,
            to_status=to_state,
            detail={},
            metadata_={"request_id": event.kwargs.get("request_id")},
        )

    async def finalize(self, event: EventData) -> None:
        """Callback method invoked by the Machine unconditionally at the end
        of every callback chain.
        """
        if TYPE_CHECKING:
            assert self.db_model is not None
            assert self.session is not None

        # The activity log entry is added to the db. For failed transitions it
        # may include error detail. For other transitions it is not necessary
        # to log every attempt, so if no callback has registered any detail
        # for the log entry it is not persisted.
        if self.activity_log_entry is None:
            return
        elif self.activity_log_entry.finished_at is None:
            return

        try:
            self.session.add(self.activity_log_entry)
            await self.session.commit()
        except Exception:
            logger.exception()
            await self.session.rollback()
        finally:
            self.session.expunge(self.activity_log_entry)
            self.activity_log_entry = None

        await self.session.close()
        self.session = None
        self.activity_log_entry = None

    async def is_successful(self, event: EventData) -> bool:
        """A conditional method associated with a transition.

        This callback should assert that the campaign is in a complete and
        accepted state by the virtue of all its Nodes also being in a complete
        and accepted state. The campaign's "END" node is used as a proxy
        for this assertion, because by the rules of the campaign's graph, the
        "END" node may only be reached if all other nodes have been success-
        fully evolved by an executor.
        """
        if TYPE_CHECKING:
            assert self.db_model is not None
            assert self.session is not None
        end_node = await self.session.get_one(Node, uuid5(self.db_model.id, "END.1"))
        logger.info(f"Checking whether campaign {self.db_model.name} is finished.", end_node=end_node.status)
        return end_node.status is StatusEnum.accepted

    async def has_valid_graph(self, event: EventData) -> bool:
        """A conditional method associated with a transition.

        This callback asserts that the campaign graph is valid as a condition
        that must be met before the campaign may transition to a "ready" state.
        """
        if TYPE_CHECKING:
            assert self.db_model is not None
            assert self.session is not None

        edges = await self.session.exec(select(Edge).where(Edge.namespace == self.db_model.id))
        graph = await graph_from_edge_list_v2(edges.all(), self.session)
        # FIXME allow for revisions to start/end nodes
        source = uuid5(self.db_model.id, "START.1")
        sink = uuid5(self.db_model.id, "END.1")
        graph_is_valid = validate_graph(graph, source, sink)
        if not graph_is_valid:
            raise InvalidCampaignGraphError("Invalid campaign graph")
        return graph_is_valid
