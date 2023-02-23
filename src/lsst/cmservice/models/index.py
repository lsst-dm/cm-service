from pydantic import BaseModel
from safir.metadata import Metadata as SafirMetadata


class Index(BaseModel):
    """Metadata returned by the external root URL of the service."""

    metadata: SafirMetadata
