from pydantic import BaseModel, Field

from ...types import StatusField


class KafkaNotification(BaseModel):
    """Basic Kafka notification payload for a CM campaign.

    Each specific Kafka notification transport may manipulate this model as
    needed. The default implementation will add campaign-level metadata and
    further decorate Butler details according to node type.
    """

    node_name: str
    node_url: str
    campaign_name: str
    campaign_url: str
    from_status: StatusField
    to_status: StatusField
    metadata: dict = Field(default_factory=dict)
