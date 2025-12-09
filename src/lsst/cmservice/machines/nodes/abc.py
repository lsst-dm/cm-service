"""Abstract Base Classes for Mixins related to node state machines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import ChainMap
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from anyio import Path
from transitions import EventData

from ...common.launchers import LauncherCheckResponse
from ...common.types import AsyncSession
from ..abc import AnyStatefulObject


class MixIn(ABC):
    """ABC for a generic Mixin."""

    artifact_path: Path
    command_templates: list[str]
    configuration_chain: dict[str, ChainMap]
    db_model: AnyStatefulObject
    session: AsyncSession
    templates: set[tuple[str, ...]] | None = None

    async def _prepare_restart(self, event: EventData) -> None:
        """Method called when preparing a node for a "restart" trigger. Any
        MixIn with specific "restart" logic should implement it here. There is
        no guarantee of the order in which this method is called on multiple
        mixins. Every mixin should end this method with a ``super()`` call.
        """
        pass


class ActionMixIn(MixIn, ABC):
    """ABC for an Action Mixin."""

    @abstractmethod
    async def action_prepare(self, event: EventData) -> None: ...

    @abstractmethod
    async def action_unprepare(self, event: EventData) -> None: ...

    @abstractmethod
    async def action_reset(self, event: EventData) -> None: ...

    @abstractmethod
    async def assemble_config_chain(self, event: EventData) -> None: ...

    @abstractmethod
    async def get_artifact_path(self, event: EventData) -> None: ...

    @abstractmethod
    async def render_action_templates(self, event: EventData) -> None: ...

    @abstractmethod
    async def get_artifact(self, event: EventData, artifact: Path | str) -> AsyncGenerator[Path]:
        if TYPE_CHECKING:
            # mypy does not consider this a generator method without a yield
            # statement, even though it is abstract
            yield Path()
        ...


class LaunchMixIn(MixIn, ABC):
    """ABC for a Launch Mixin.

    A Launch Mixin provides a Node Machine with attributes and methods related
    to the execution of its payload.

    Notes
    -----
    A LaunchMixing implements the equivalent behavior of a "ScriptHandler"
    in the legacy CM Service.
    """

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

    @abstractmethod
    async def check(self, event: EventData) -> LauncherCheckResponse: ...
