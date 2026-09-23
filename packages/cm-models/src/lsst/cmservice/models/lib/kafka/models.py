from pydantic import BaseModel, Field

from ...types import StatusField


class KafkaNotification(BaseModel):
    """Basic Kafka notification payload for a CM campaign"""

    node_name: str
    node_url: str
    campaign_name: str
    campaign_url: str
    from_status: StatusField
    to_status: StatusField
    metadata: dict = Field(default_factory=dict)


class ButlerCollectionKafkaNotification(KafkaNotification):
    """Notification payload that is geared toward the inclusion and enumeration
    of Butler collections and dataset types.
    """

    collections: list[str] = Field(default_factory=list)
    dataset_types: list[str] = Field(default_factory=list)
