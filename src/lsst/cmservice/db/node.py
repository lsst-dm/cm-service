from __future__ import annotations

import re
from collections import ChainMap, defaultdict
from typing import TYPE_CHECKING, Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.orm.collections import InstrumentedList

from ..common.enums import LevelEnum, StatusEnum
from ..common.errors import (
    CMBadExecutionMethodError,
    CMBadFullnameError,
    CMBadStateTransitionError,
    CMIntegrityError,
    CMResolveCollectionsError,
    test_type_and_raise,
)
from ..common.logging import LOGGER
from ..common.notification import send_notification
from ..config import config
from .handler import Handler
from .row import RowMixin
from .spec_block import SpecBlock
from .specification import Specification

if TYPE_CHECKING:
    from .campaign import Campaign
    from .element import ElementMixin

logger = LOGGER.bind(module=__name__)


class NodeMixin(RowMixin):
    """Mixin class to define common features of database rows
    for tables with 'node' rows, i.e., ones that
    represent parts of the data processing chain.

    Mostly these are defined by having an associated
    `SpecBlock` that stores default parameters and
    a `process` function that does data processing
    """

    level: Any  # Associated LevelEnum of the configuable
    spec_block_: Any  # Specification block that carries defaults
    spec_: Any  # Specificaiton
    status: Any  # Current status of associated processing
    parent_id: Any  # Id of the parent row
    parent_: Any  # Parent of the current row
    collections: Any  # Definition of collection names
    child_config: Any  # Definition of child elements
    spec_aliases: Any  # Definition of aliases for SpecBlock overrides
    data: Any  # Generic configuraiton parameters
    prereqs_: Any  # Prerequistes to running this row
    handler: Any  # Class name of associated Handler object
    node_type: Any  # Type of this node

    async def get_spec_block(
        self,
        session: async_scoped_session,
    ) -> SpecBlock:
        """Get the `SpecBlock` object associated to a particular row

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        spec_block: SpecBlock
            Requested Specblock
        """
        await session.refresh(self, attribute_names=["spec_block_"])
        if isinstance(self.spec_block_, InstrumentedList):  # pragma: no cover
            return self.spec_block_[0]
        return self.spec_block_

    async def get_specification(
        self,
        session: async_scoped_session,
    ) -> Specification:
        """Get the `Specification` object associated to a particular row

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        specification: Specification
            Requested Specification
        """
        campaign = await self.get_campaign(session)
        await session.refresh(campaign, attribute_names=["spec_"])
        return campaign.spec_

    async def get_campaign(
        self,
        session: async_scoped_session,
    ) -> Campaign:
        """Get the parent `Campaign`

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        campaign: Campaign
            Parent campaign
        """
        raise NotImplementedError()

    async def get_parent(
        self,
        session: async_scoped_session,
    ) -> ElementMixin:
        """Get the parent `Element`

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        element : ElementMixin
            Requested parent Element
        """
        await session.refresh(self, attribute_names=["parent_"])
        if isinstance(self.parent_, InstrumentedList):  # pragma: no cover
            return self.parent_[0]
        return self.parent_

    async def get_handler(
        self,
        session: async_scoped_session,
    ) -> Handler:
        """Get the Handler object associated with a particular row

        Check if a handler class is defined for a particular row; if not, use
        the class as defined in the associated `SpecBlock`.

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        handler: Handler
            The handler in question
        """
        spec_block = await self.get_spec_block(session)
        handler_class = self.handler if self.handler else spec_block.handler
        handler_class = test_type_and_raise(handler_class, str, "Node.get_handler handler_class")
        return Handler.get_handler(
            spec_block.id,
            handler_class,
        )

    @staticmethod
    def _split_fullname(fullname: str) -> dict:
        """Parse a fullname into named fields

        Parameters
        ---------
        fullname: str
            String to be parsed

        Returns
        -------
        fields : dict
            Resulting fields
        """
        fullname_r = re.compile(
            (
                r"^"
                r"(?P<campaign>[\w]+){1}(?:\/)*"
                r"(?P<step>[\w]+){0,1}(?:\/)*"
                r"(?P<group>[\w]+){0,1}(?:\/)*"
                r"(?P<job>[\w]+){0,1}(?:\/)*"
                r"(?P<script>[\w]+){0,1}"
                r"$"
            ),
            re.MULTILINE,
        )
        fields = {"production": "DEFAULT"}

        if (match := re.match(fullname_r, fullname)) is None:
            raise CMBadFullnameError(f"Fullname {fullname} is not parseable")

        for k, v in match.groupdict().items():
            fields[k] = v

        return fields

    async def resolve_collections(
        self,
        session: async_scoped_session,
        *,
        throw_overrides: bool = True,
    ) -> dict:
        """Resolve the collections for a particular node

        Notes
        -----
        This will return a dict with all of the collections templates defined
        for this node resolved using collection aliases and collection templ-
        ates defined up the processing hierarchy

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        throw_overrides : bool
            If true, raise exception if MUST_OVERRIDE is present

        Returns
        -------
        resolved_collections: dict
            Resolved collection names
        """
        raw_collections: dict[str, str | list[str]] = await NodeMixin.get_collections(self, session)
        collection_dict = await self.get_collections(session)
        name_dict = self._split_fullname(self.fullname)
        lookup_chain = ChainMap(collection_dict, name_dict, defaultdict(lambda: "MUST_OVERRIDE"))

        resolved_collections = {
            k: (v if isinstance(v, str) else ",".join(v)) for k, v in raw_collections.items()
        }

        # It may take multiple passes to format all the placeholder
        # tokens in the collection strings, repeat the formatting until no such
        # tokens remain.
        while unresolved_collections := {
            k: v for k, v in resolved_collections.items() if re.search("{.*}", v)
        }:
            for k, v in unresolved_collections.items():
                resolved_collections[k] = v.format_map(lookup_chain)

        if throw_overrides:
            if [v for v in resolved_collections.values() if re.search("MUST_OVERRIDE", v)]:
                raise CMResolveCollectionsError(
                    "Attempts to resolve collection includes MUST_OVERRIDE. Make sure to provide "
                    "necessary collection names."
                )

        return resolved_collections

    async def get_collections(
        self,
        session: async_scoped_session,
    ) -> dict:
        """Get the collection configuration associated with a particular row.

        This starts with the collection configuration in the associated
        `SpecBlock` which is overriden the collection configuration of the row.

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        collections: dict
            Requested collection configuration
        """
        collections = {}
        if not hasattr(self, "collections"):  # pragma: no cover
            return {}

        if self.level == LevelEnum.script:
            parent_ = await self.get_parent(session)
            parent_colls = await parent_.get_collections(session)
            collections.update(parent_colls)
        elif self.level.value > LevelEnum.campaign.value:
            parent = await self.get_parent(session)
            parent_colls = await parent.get_collections(session)
            collections.update(parent_colls)
        spec_block = await self.get_spec_block(session)
        if spec_block.collections:
            collections.update(spec_block.collections)
        if self.collections:
            collections.update(self.collections)
        for key, val in collections.items():
            if isinstance(val, list):
                collections[key] = ",".join(val)
        return collections

    async def get_child_config(
        self,
        session: async_scoped_session,
    ) -> dict:
        """Get the child configuration associated with a particular row.

        This starts with the child configuration in the associated `SpecBlock`
        which is overriden with the child configuration of the row.

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        child_config: dict
            Requested child configuration
        """
        child_config: dict = {}
        if not hasattr(self, "child_config"):  # pragma: no cover
            return {}
        spec_block = await self.get_spec_block(session)
        if spec_block.child_config:
            child_config.update(**spec_block.child_config)
        if self.child_config:
            child_config.update(**self.child_config)
        return child_config

    async def data_dict(
        self,
        session: async_scoped_session,
    ) -> dict:
        """Get the data configuration associated to a particular row

        This will start with the data configuration in the associated
        `SpecBlock` and override it with with the data configuration in the row

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        data: dict
            Requested data configuration
        """
        data = {}
        if self.level is LevelEnum.script:
            parent_ = await self.get_parent(session)
            parent_data = await parent_.data_dict(session)
            data.update(parent_data)
        elif self.level.value > LevelEnum.campaign.value:
            parent = await self.get_parent(session)
            parent_data = await parent.data_dict(session)
            data.update(parent_data)
        spec_block = await self.get_spec_block(session)
        if spec_block.data:
            data.update(spec_block.data)
        if self.data:
            data.update(self.data)
        return data

    async def get_spec_aliases(
        self,
        session: async_scoped_session,
    ) -> dict:
        """Get the spec_aliases associated with a particular node

        This will start with the spec_aliases configuration in the associated
        `SpecBlock` and override it with with the data configuration in the row

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        spec_aliases: dict
            Requested spec_aliases configuration
        """
        ret_dict = {}
        if self.level == LevelEnum.script:
            raise NotImplementedError
        if self.level.value > LevelEnum.campaign.value:
            parent = await self.get_parent(session)
            parent_data = await parent.get_spec_aliases(session)
            ret_dict.update(parent_data)
        spec_block = await self.get_spec_block(session)
        if spec_block.spec_aliases:  # pragma: no cover
            ret_dict.update(spec_block.spec_aliases)
        if self.spec_aliases:
            ret_dict.update(self.spec_aliases)
        return ret_dict

    async def update_child_config(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> NodeMixin:
        """Update the child configuration associated with this Node

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        kwargs: Any
            Key-value pairs to update

        Returns
        -------
        node : NodeMixin
            Updated Node
        """
        if not hasattr(self, "child_config"):  # pragma: no cover
            raise CMBadExecutionMethodError(f"{self.fullname} does not have attribute child_config")

        if self.status.value >= StatusEnum.prepared.value:
            raise CMBadStateTransitionError(
                f"Tried to modify a node that is in use. {self.fullname}:{self.status}",
            )

        try:
            if self.child_config:
                the_child_config = self.child_config.copy()
                the_child_config.update(**kwargs)
                self.child_config = the_child_config
            else:
                self.child_config = kwargs.copy()
            await session.commit()
        except IntegrityError as msg:
            if TYPE_CHECKING:
                assert msg.orig  # for mypy
            await session.rollback()
            raise CMIntegrityError(params=msg.params, orig=msg.orig, statement=msg.statement) from msg
        return self

    async def update_collections(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> NodeMixin:
        """Update the collection configuration associated with this Node

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        kwargs: Any
            Key-value pairs to update

        Returns
        -------
        node : NodeMixin
            Updated Node
        """
        if not hasattr(self, "collections"):  # pragma: no cover
            raise CMBadExecutionMethodError(f"{self.fullname} does not have attribute collections")

        if self.status.value >= StatusEnum.prepared.value:
            raise CMBadStateTransitionError(
                f"Tried to modify a node that is in use. {self.fullname}:{self.status}",
            )

        try:
            if self.collections:
                the_collections = self.collections.copy()
                the_collections.update(**kwargs)
                self.collections = the_collections
            else:
                self.collections = kwargs.copy()
            await session.commit()
        except IntegrityError as msg:
            if TYPE_CHECKING:
                assert msg.orig  # for mypy
            raise CMIntegrityError(params=msg.params, orig=msg.orig, statement=msg.statement) from msg
        return self

    async def update_spec_aliases(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> NodeMixin:
        """Update the spec_alisases configuration associated with this Node

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        kwargs: Any
            Key-value pairs to update

        Returns
        -------
        node : NodeMixin
            Updated Node
        """
        if not hasattr(self, "spec_aliases"):  # pragma: no cover
            raise CMBadExecutionMethodError(f"{self.fullname} does not have attribute spec_aliases")

        if self.status.value >= StatusEnum.prepared.value:
            raise CMBadStateTransitionError(
                f"Tried to modify a node that is in use. {self.fullname}:{self.status}",
            )

        try:
            if self.spec_aliases:
                the_data = self.spec_aliases.copy()
                the_data.update(**kwargs)
                self.spec_aliases = the_data
            else:
                self.spec_aliases = kwargs.copy()
            await session.commit()
        except IntegrityError as msg:
            if TYPE_CHECKING:
                assert msg.orig  # for mypy
            await session.rollback()
            raise CMIntegrityError(params=msg.params, orig=msg.orig, statement=msg.statement) from msg
        return self

    async def update_data_dict(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> NodeMixin:
        """Update the data configuration associated with this Node

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        kwargs: Any
            Key-value pairs to update

        Returns
        -------
        node : NodeMixin
            Updated Node
        """
        if not hasattr(self, "data"):  # pragma: no cover
            raise CMBadExecutionMethodError(f"{self.fullname} does not have attribute data")

        if self.status.value >= StatusEnum.prepared.value:
            raise CMBadStateTransitionError(
                f"Tried to modify a node that is in use. {self.fullname}:{self.status}",
            )

        try:
            if self.data:
                the_data = self.data.copy()
                the_data.update(**kwargs)
                self.data = the_data
            else:  # pragma: no cover
                self.data = kwargs.copy()
            await session.commit()
        except IntegrityError as msg:
            if TYPE_CHECKING:
                assert msg.orig  # for mypy
            await session.rollback()
            raise CMIntegrityError(params=msg.params, orig=msg.orig, statement=msg.statement) from msg
        return self

    async def check_prerequisites(
        self,
        session: async_scoped_session,
    ) -> bool:
        """Check if the prerequisties for processing a particular node are
        completed.

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        done: bool
            Returns True if the prerequisites are done
        """
        try:
            await session.refresh(self, attribute_names=["prereqs_"])
        except Exception:
            return True
        for prereq_ in self.prereqs_:
            is_done = await prereq_.is_done(session)
            if not is_done:
                return False
        return True

    async def reject(
        self,
        session: async_scoped_session,
    ) -> NodeMixin:
        """Set a node as rejected

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        node: NodeMixin
            Node being rejected
        """
        if self.status in [StatusEnum.accepted, StatusEnum.rescued]:
            raise CMBadStateTransitionError(f"Can not reject {self} as it is in status {self.status}")

        await self.update_values(session, status=StatusEnum.rejected)
        return self

    async def accept(
        self,
        session: async_scoped_session,
    ) -> NodeMixin:
        """Set a node as accepted

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        node: NodeMixin
            Node being accepted
        """
        if self.status not in [
            StatusEnum.blocked,
            StatusEnum.running,
            StatusEnum.reviewable,
            StatusEnum.rescuable,
        ]:
            raise CMBadStateTransitionError(f"Can not accept {self} as it is in status {self.status}")

        await self.update_values(session, status=StatusEnum.accepted)

        if self.level is LevelEnum.campaign:
            if TYPE_CHECKING:
                assert isinstance(self, Campaign)
            await send_notification(for_status=StatusEnum.accepted, for_campaign=self)
        return self

    async def reset(
        self,
        session: async_scoped_session,
        *,
        fake_reset: bool = False,
    ) -> NodeMixin:
        """Reset a Node to `waiting`

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        fake_reset: bool
            Don't actually try to remove collections if True

        Returns
        -------
        node: NodeMixin
            Node being reset
        """
        if self.status not in [StatusEnum.blocked, StatusEnum.rejected, StatusEnum.failed, StatusEnum.ready]:
            raise CMBadStateTransitionError(f"Can not reset {self} as it is in status {self.status}")

        await self._clean_up_node(session, fake_reset=fake_reset)
        await self.update_values(session, status=StatusEnum.waiting, superseded=False)
        return self

    async def _clean_up_node(
        self,
        session: async_scoped_session,
        *,
        fake_reset: bool = False,
    ) -> NodeMixin:
        """Clean up stuff that a node has made

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        fake_reset: bool
            Don't actually try to remove collections if True

        Returns
        -------
        node: NodeMixin
            Node being cleaned
        """
        return self

    async def process(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        """Process this `Node` as much as possible

        This will create a `Handler` and pass this node to it for processing

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        changed : bool
            True if anything has changed
        status : StatusEnum
            Status of the processing
        """
        handler = await self.get_handler(session)
        logger.debug("Processing node with handler %s", handler.get_handler_class_name())
        return await handler.process(session, self, **kwargs)

    async def run_check(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        """Check on this Nodes's status

        This will create a `Handler` and pass this node to it for checking

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        changed : bool
            True if anything has changed
        status : StatusEnum
            Status of the processing
        """
        handler = await self.get_handler(session)
        return await handler.run_check(session, self, **kwargs)

    async def estimate_sleep_time(
        self,
        session: async_scoped_session,
        minimum_sleep_time: int = 10,
    ) -> int:
        """Estimate how long to sleep before calling process again.

        If a node is running, use the greater of minimum sleep time or
        the configured daemon processing interval.

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        sleep_time : int
            Time to sleep in seconds
        """
        await session.refresh(self, attribute_names=["status"])
        if self.status == StatusEnum.running:
            minimum_sleep_time = max(config.daemon.processing_interval, minimum_sleep_time)
        return minimum_sleep_time
