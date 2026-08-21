from lsst.cmservice.models.enums import NotificationLabelEnum

from .abc import NotificationTransport
from .slack import SlackNotification


class NotificationTransportFactory:
    """A caching factory for creating notification transport instances.

    Transports are cached according to the associated label name.
    """

    def __init__(self) -> None:
        self._builders: dict[NotificationLabelEnum, type[NotificationTransport]] = {}
        self._transports: dict[str, NotificationTransport] = {}
        self.define_builders()
        self.build(NotificationLabelEnum.slack, "default")

    def define_builders(self) -> None:
        """Construct the registry of notification transport builders, which is
        a mapping of a transport kind to its constructor class.
        """
        self._builders[NotificationLabelEnum.default] = SlackNotification
        self._builders[NotificationLabelEnum.slack] = SlackNotification

    def build(self, kind: NotificationLabelEnum, name: str) -> None:
        """Build a notification transport based on the kind and name inputs"""
        if name not in self._transports:
            self._transports[name] = self._builders[kind]()

    def get(self, name: str) -> NotificationTransport:
        """Obtain the named transport from the collection of constructed
        transports or try to build it.
        """
        if name in self._transports:
            return self._transports[name]
        else:
            return self._transports["default"]

    @property
    def builders(self) -> list[str]:
        """Obtain the list of registered builders as names"""
        return [builder.name for builder in self._builders.keys()]


factory = NotificationTransportFactory()
