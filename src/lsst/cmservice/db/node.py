from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.enums import LevelEnum, NodeTypeEnum, StatusEnum
from .handler import Handler
from .row import RowMixin
from .specification import SpecBlock, Specification

if TYPE_CHECKING:
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
    spec_block_assoc_: Any  # SpecBlockAssociation between SpecBlock and specificaiton
    spec_: Any  # Specificaiton
    spec_block_assoc_id: Any  # Foriegn key into SpecBlockAssociation
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
        async with session.begin_nested():
            await session.refresh(self, attribute_names=["spec_block_"])
            return self.spec_block_

    async def get_specification(
        self,
        session: async_scoped_session,
    ) -> Specification:
        """Get the `Specification` object associated this node

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        specification: Specification
            Requested Specification
        """
        async with session.begin_nested():
            await session.refresh(self, attribute_names=["spec_"])
            return self.spec_

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
        async with session.begin_nested():
            await session.refresh(self, attribute_names=["parent_"])
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
        if self.handler:
            handler_class = self.handler
        else:
            handler_class = spec_block.handler
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
            else:
                raise ValueError(f"Too many fields in {fullname}")
        return fields

    async def resolve_collections(
        self,
        session: async_scoped_session,
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

        Returns
        -------
        resolved_collections: dict
            Resolved collection names
        """
        my_collections = await NodeMixin.get_collections(self, session)
        collection_dict = await self.get_collections(session)
        name_dict = self._split_fullname(self.fullname)
        name_dict["root"] = collection_dict.pop("root")
        resolved_collections: dict = {}
        for name_, val_ in my_collections.items():
            if isinstance(val_, list):
                resolved_collections[name_] = []
                for item_ in val_:
                    try:
                        f1 = item_.format(**collection_dict)
                    except KeyError:
                        f1 = val_
                    try:
                        resolved_collections[name_].append(f1.format(**name_dict))
                    except KeyError as msg:
                        raise KeyError(
                            f"Failed to resolve collection {name_} {f1} using: {name_dict!s}",
                        ) from msg
            else:
                try:
                    f1 = val_.format(**collection_dict)
                except KeyError:
                    f1 = val_
                try:
                    resolved_collections[name_] = f1.format(**name_dict)
                except KeyError as msg:
                    raise KeyError(
                        f"Failed to resolve collection {name_}, {f1} using: {name_dict!s}",
                    ) from msg
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
        if not hasattr(self, "collections"):
            return {}

        async with session.begin_nested():
            if self.level == LevelEnum.script:
                parent_ = await self.get_parent(session)
                parent_colls = await parent_.get_collections(session)
                ret_dict.update(parent_colls)
            elif self.level.value > LevelEnum.campaign.value:
                await session.refresh(self, attribute_names=["parent_"])
                parent_colls = await self.parent_.get_collections(session)
                ret_dict.update(parent_colls)
            await session.refresh(self, attribute_names=["spec_block_"])
            if self.spec_block_.collections:
                ret_dict.update(self.spec_block_.collections)
            if self.collections:
                ret_dict.update(self.collections)
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
        if not hasattr(self, "child_config"):
            return {}
        async with session.begin_nested():
            await session.refresh(self, attribute_names=["spec_block_"])
            if self.spec_block_.child_config:
                ret_dict.update(**self.spec_block_.child_config)
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
        async with session.begin_nested():
            if self.level == LevelEnum.script:
                parent_ = await self.get_parent(session)
                parent_data = await parent_.data_dict(session)
                ret_dict.update(parent_data)
            elif self.level.value > LevelEnum.campaign.value:
                await session.refresh(self, attribute_names=["parent_"])
                parent_data = await self.parent_.data_dict(session)
                ret_dict.update(parent_data)
            await session.refresh(self, attribute_names=["spec_block_"])
            if self.spec_block_.data:
                ret_dict.update(self.spec_block_.data)
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
        async with session.begin_nested():
            if self.level == LevelEnum.script:
                raise NotImplementedError
            if self.level.value > LevelEnum.campaign.value:
                await session.refresh(self, attribute_names=["parent_"])
                parent_data = await self.parent_.get_spec_aliases(session)
                ret_dict.update(parent_data)
            await session.refresh(self, attribute_names=["spec_block_"])
            if self.spec_block_.spec_aliases:
                ret_dict.update(self.spec_block_.spec_aliases)
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
        if not hasattr(self, "child_config"):
            raise AttributeError(f"{self.fullname} does not have attribute child_config")

        if self.status.value >= StatusEnum.prepared.value:
            raise ValueError(f"Tried to modify a node that is in use. {self.fullname}:{self.status}")

        async with session.begin_nested():
            if self.child_config:
                the_child_config = self.child_config.copy()
                the_child_config.update(**kwargs)
                self.child_config = the_child_config
            else:
                self.child_config = kwargs.copy()
        await session.refresh(self)
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
        if not hasattr(self, "collections"):
            raise AttributeError(f"{self.fullname} does not have attribute collections")

        if self.status.value >= StatusEnum.prepared.value:
            raise ValueError(f"Tried to modify a node that is in use. {self.fullname}:{self.status}")

        async with session.begin_nested():
            if self.collections:
                the_collections = self.collections.copy()
                the_collections.update(**kwargs)
                self.collections = the_collections
            else:
                self.collections = kwargs.copy()
        await session.refresh(self)
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
        if not hasattr(self, "spec_aliases"):
            raise AttributeError(f"{self.fullname} does not have attribute spec_aliases")

        if self.status.value >= StatusEnum.prepared.value:
            raise ValueError(f"Tried to modify a node that is in use. {self.fullname}:{self.status}")

        async with session.begin_nested():
            if self.spec_aliases:
                the_data = self.spec_aliases.copy()
                the_data.update(**kwargs)
                self.spec_aliases = the_data
            else:
                self.spec_aliases = kwargs.copy()
        await session.refresh(self)
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
        if not hasattr(self, "data"):
            raise AttributeError(f"{self.fullname} does not have attribute data")

        if self.status.value >= StatusEnum.prepared.value:
            raise ValueError(f"Tried to modify a node that is in use. {self.fullname}:{self.status}")

        async with session.begin_nested():
            if self.data:
                the_data = self.data.copy()
                the_data.update(**kwargs)
                self.data = the_data
            else:
                self.data = kwargs.copy()
        await session.refresh(self)
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
        async with session.begin_nested():
            try:
                await session.refresh(self, attribute_names=["prereqs_"])
            except Exception:  # pylint: disable=broad-exception-caught
                return True
            print(f"N prereq {len(self.prereqs_)}")
            for prereq_ in self.prereqs_:
                print(prereq_)
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
            raise ValueError(f"Can not reject {self} as it is in status {self.status}")

        await self.update_values(session, status=StatusEnum.rejected)
        await session.commit()
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
        if self.status in [StatusEnum.running, StatusEnum.reviewable, StatusEnum.rescuable]:
            raise ValueError(f"Can not accept {self} as it is in status {self.status}")

        await self.update_values(session, status=StatusEnum.accepted)
        await session.commit()
        return self

    async def reset(
        self,
        session: async_scoped_session,
    ) -> NodeMixin:
        """Reset a Node to `waiting`

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        node: NodeMixin
            Node being reset
        """
        if self.status not in [StatusEnum.rejected, StatusEnum.failed, StatusEnum.ready]:
            raise ValueError(f"Can not reset {self} as it is in status {self.status}")

        await self._clean_up_node(session)
        await self.update_values(session, status=StatusEnum.waiting, superseded=False)
        await session.commit()
        return self

    async def _clean_up_node(
        self,
        session: async_scoped_session,
    ) -> NodeMixin:
        """Clean up stuff that a node has made

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        node: NodeMixin
            Node being cleaned
        """
        raise NotImplementedError

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
