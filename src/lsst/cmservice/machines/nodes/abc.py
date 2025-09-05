"""Abstract Base Classes for Mixins related to node state machines."""

from abc import ABC, abstractmethod
from collections import ChainMap

from anyio import Path
from transitions import EventData

from ...common.types import AsyncSession
from ..abc import AnyStatefulObject


class ActionMixIn(ABC):
    """ABC for an Action Mixin."""

    artifact_path: Path
    command_templates: list[str]
    configuration_chain: dict[str, ChainMap]
    db_model: AnyStatefulObject
    session: AsyncSession
    templates: list[tuple[str, ...]]

    @abstractmethod
    async def action_prepare(self, event: EventData) -> None: ...

    @abstractmethod
    async def assemble_config_chain(self, event: EventData) -> None: ...

    @abstractmethod
    async def get_artifact_path(self, event: EventData) -> None: ...

    @abstractmethod
    async def render_action_templates(self, event: EventData) -> None: ...


class LaunchMixIn(ABC):
    """ABC for a Launch Mixin.

    A Launch Mixin provides a Node Machine with attributes and methods related
    to the execution of its payload.

    Notes
    -----
    A LaunchMixing implements the equivalent behavior of a "ScriptHandler"
    in the legacy CM Service.
    """

    artifact_path: Path
    configuration_chain: dict[str, ChainMap]
    db_model: AnyStatefulObject
    templates: list[tuple[str, ...]]

    @abstractmethod
    async def launch_prepare(self, event: EventData) -> None:
        """Method called to prepare the Node for launch. This should include,
        among other things, the determination of a runtime configuration needed
        for the launch mechanism to function. This will generally be the add-
        ition of a manifest to the node's "wms" configuration chain.
        """
        ...

    @abstractmethod
    async def launch(self, event: EventData) -> None: ...
