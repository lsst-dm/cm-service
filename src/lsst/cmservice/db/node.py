from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.orm.collections import InstrumentedList

from ..common.enums import LevelEnum, NodeTypeEnum, StatusEnum
from ..common.errors import (
    CMBadExecutionMethodError,
    CMBadFullnameError,
    CMBadStateTransitionError,
    CMIntegrityError,
    CMResolveCollectionsError,
)
from .handler import Handler
from .row import RowMixin
from .spec_block import SpecBlock
from .specification import Specification

if TYPE_CHECKING:
    from .campaign import Campaign
    from .element import ElementMixin


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
        """Get the Handler object associated to a particular row

        This will check if the handler class is defined
        for that particular row, if it is not, it
        will use the class as defined in the associated
        `SpecBlock`

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
        return Handler.get_handler(
            spec_block.id,
            handler_class,
        )

    def _split_fullname(self, fullname: str) -> dict:
        """Split a fullname into named fields

        Paramters
        ---------
        fullname: str
            String to be split

        Returns
        -------
        fields : dict
            Resulting fields
        """
        fields = {}

        tokens = fullname.split("/")
        if self.node_type == NodeTypeEnum.script:
            fields["script"] = tokens.pop()
        for i, token in enumerate(tokens):
            if i == 0:
                fields["production"] = token
            elif i == 1:
                fields["campaign"] = token
            elif i == 2:
                fields["step"] = token
            elif i == 3:
                fields["group"] = token
            elif i == 4:
                fields["job"] = token
            else:  # pragma: no cover
                raise CMBadFullnameError(f"Too many fields in {fullname}")
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
        This will return a dict with all of the collections
        templated defined for this node resovled using
        collection aliases and collection templates
        defined up the processing heirarchy

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
        my_collections = await NodeMixin.get_collections(self, session)
        collection_dict = await self.get_collections(session)
        name_dict = self._split_fullname(self.fullname)
        name_dict["out"] = collection_dict.pop("out")
        resolved_collections: dict = {}
        for name_, val_ in my_collections.items():
            if isinstance(val_, list):  # pragma: no cover
                # FIXME, see if this is now being tested
                resolved_collections[name_] = []
                for item_ in val_:
                    try:
                        f1 = item_.format(**collection_dict)
                    except KeyError:
                        f1 = val_
                    try:
                        resolved_collections[name_].append(f1.format(**name_dict))
                    except KeyError as e:
                        raise CMResolveCollectionsError(
                            f"Failed to resolve collection {name_} {f1} using: {name_dict!s}",
                        ) from e
                resolved_collections[name_] = ",".join(resolved_collections[name_])
            else:
                try:
                    f1 = val_.format(**collection_dict)
                except KeyError:
                    f1 = val_
                try:
                    resolved_collections[name_] = f1.format(**name_dict)
                except KeyError as msg:
                    raise CMResolveCollectionsError(
                        f"Failed to resolve collection {name_}, {f1} using: {name_dict!s}",
                    ) from msg
        if throw_overrides:
            for key, value in resolved_collections.items():
                if "MUST_OVERRIDE" in value:  # pragma: no cover
                    raise CMResolveCollectionsError(
                        f"Attempts to resolve {key} collection includes MUST_OVERRIDE. Make sure to provide "
                        "necessary collection names."
                    )
        return resolved_collections

    async def get_collections(
        self,
        session: async_scoped_session,
    ) -> dict:
        """Get the collection configuration
        associated to a particular row

        This will start with the collection
        configuration in the associated `SpecBlock`
        and override it with with the collection
        configuration in the row

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        collections: dict
            Requested collection configuration
        """
        ret_dict = {}
        if not hasattr(self, "collections"):  # pragma: no cover
            return {}

        if self.level == LevelEnum.script:
            parent_ = await self.get_parent(session)
            parent_colls = await parent_.get_collections(session)
            ret_dict.update(parent_colls)
        elif self.level.value > LevelEnum.campaign.value:
            parent = await self.get_parent(session)
            parent_colls = await parent.get_collections(session)
            ret_dict.update(parent_colls)
        spec_block = await self.get_spec_block(session)
        if spec_block.collections:
            ret_dict.update(spec_block.collections)
        if self.collections:
            ret_dict.update(self.collections)
        for key, val in ret_dict.items():
            if isinstance(val, list):
                ret_dict[key] = ",".join(val)
        return ret_dict

    async def get_child_config(
        self,
        session: async_scoped_session,
    ) -> dict:
        """Get the child configuration
        associated to a particular row

        This will start with the child
        configuration in the associated `SpecBlock`
        and override it with with the child
        configuration in the row

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        child_config: dict
            Requested child configuration
        """
        ret_dict: dict = {}
        if not hasattr(self, "child_config"):  # pragma: no cover
            return {}
        spec_block = await self.get_spec_block(session)
        if spec_block.child_config:
            ret_dict.update(**spec_block.child_config)
        if self.child_config:
            ret_dict.update(**self.child_config)
        return ret_dict

    async def data_dict(
        self,
        session: async_scoped_session,
    ) -> dict:
        """Get the data configuration
        associated to a particular row

        This will start with the data
        configuration in the associated `SpecBlock`
        and override it with with the data
        configuration in the row

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        data: dict
            Requested data configuration
        """
        ret_dict = {}
        if self.level == LevelEnum.script:
            parent_ = await self.get_parent(session)
            parent_data = await parent_.data_dict(session)
            ret_dict.update(parent_data)
        elif self.level.value > LevelEnum.campaign.value:
            parent = await self.get_parent(session)
            parent_data = await parent.data_dict(session)
            ret_dict.update(parent_data)
        spec_block = await self.get_spec_block(session)
        if spec_block.data:
            ret_dict.update(spec_block.data)
        if self.data:
            ret_dict.update(self.data)
        return ret_dict

    async def get_spec_aliases(
        self,
        session: async_scoped_session,
    ) -> dict:
        """Get the spec_alises
        associated to a particular node

        This will start with the spec_aliases
        configuration in the associated `SpecBlock`
        and override it with with the data
        configuration in the row

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
        """Update the child configuration
        associated to this Node

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
        """Update the collection configuration
        associated to this Node

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
        """Update the spec_alisases configuration
        associated to this Node

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
        """Update the data configuration
        associated to this Node

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
        """Check if the prerequisties
        for processing a particular row
        are completed

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
        except Exception:  # pylint: disable=broad-exception-caught
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
        if self.status not in [StatusEnum.running, StatusEnum.reviewable, StatusEnum.rescuable]:
            raise CMBadStateTransitionError(f"Can not accept {self} as it is in status {self.status}")

        await self.update_values(session, status=StatusEnum.accepted)
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
        if self.status not in [StatusEnum.rejected, StatusEnum.failed, StatusEnum.ready]:
            raise CMBadStateTransitionError(f"Can not reset {self} as it is in status {self.status}")

        await self._clean_up_node(session, fake_reset=fake_reset)
        await self.update_values(session, status=StatusEnum.waiting, superseded=False)
        return self

    async def _clean_up_node(  # pylint: disable=unused-argument
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

        This will create a `Handler` and
        pass this node to it for processing

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
        return await handler.process(session, self, **kwargs)

    async def run_check(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        """Check on this Nodes's status

        This will create a `Handler` and
        pass this node to it for checking

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
        job_sleep: int = 150,  # pylint: disable=unused-argument
        script_sleep: int = 15,
    ) -> int:
        """Estimate how long to sleep before calling process again

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        job_sleep: int = 150
            Time to sleep if jobs are running

        script_sleep: int = 15
            Time to sleep if scripts are running

        Returns
        -------
        sleep_time : int
            Time to sleep in seconds
        """
        sleep_time = 10
        await session.refresh(self, attribute_names=["status"])
        if self.status == StatusEnum.running:
            sleep_time = max(script_sleep, sleep_time)
        return sleep_time
