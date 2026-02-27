from pydantic import BaseModel, Field, SecretStr


class DatabaseConfiguration(BaseModel):
    """Database configuration nested model.

    Set according to DB__FIELD environment variables.
    """

    url: str = Field(
        default="",
        description="The URL for the cm-service database",
    )

    password: SecretStr | None = Field(
        default=None,
        description="The password for the cm-service database",
    )

    table_schema: str = Field(
        default="public",
        description="Schema to use for cm-service database",
    )

    echo: bool = Field(
        default=False,
        description="SQLAlchemy engine echo setting for the cm-service database",
    )

    max_overflow: int = Field(
        default=10,
        description="Maximum connection overflow allowed for QueuePool.",
    )

    pool_size: int = Field(
        default=5,
        description="Number of open connections kept in the QueuePool",
    )

    pool_recycle: int = Field(
        default=-1,
        description="Timeout in seconds before connections are recycled",
    )

    pool_timeout: int = Field(
        default=30,
        description="Wait timeout for acquiring a connection from the pool",
    )

    pool_fields: set[str] = Field(
        default={"max_overflow", "pool_size", "pool_recycle", "pool_timeout"},
        description="Set of fields used for connection pool configuration",
    )


settings = DatabaseConfiguration()
"""Configuration instance for cm-service models package."""
