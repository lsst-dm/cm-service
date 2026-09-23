"""Module describing settings used by Kafka clients."""

from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConsumerSettings(BaseSettings):
    """A BaseSettings class for Kafka consumer-specific parameters.

    Fields with ``exclude=True`` set are not passed to the Consumer constructor
    as configuration.
    """

    model_config = SettingsConfigDict(env_prefix="KAFKA_CONSUMER_", extra="ignore")

    auto_offset_commit: Annotated[bool, Field(serialization_alias="enable.auto.commit")] = True
    group_id: Annotated[str, Field(serialization_alias="group.id")] = "cmservice"
    offset_reset: Annotated[str, Field(serialization_alias="auto.offset.reset")] = "earliest"
    topics: Annotated[list[str], Field(exclude=True)] = Field(default_factory=list)


class ProducerSettings(BaseSettings):
    """A BaseSettings class for Kafka producer-specific parameters.

    Fields with ``exclude=True`` set are not passed to the Producer constructor
    as configuration.

    Fields that are passed to the Producer constructor feature a
    ``serialization_alias``.
    """

    model_config = SettingsConfigDict(env_prefix="KAFKA_PRODUCER_", extra="ignore")

    acks: Annotated[int, Field(ge=-1, le=1, serialization_alias="acks")] = -1
    batch_num_messages: Annotated[int, Field(ge=1, serialization_alias="batch.num.messages")] = 10_000
    batch_size: Annotated[int, Field(ge=1, serialization_alias="batch.size")] = 1_000_000
    message_key: Annotated[str | None, Field(exclude=True)] = None
    queue_buffering_max_kbytes: Annotated[
        int, Field(ge=1, serialization_alias="queue.buffering.max.kbytes")
    ] = 1_048_576
    queue_buffering_max_messages: Annotated[
        int, Field(ge=0, serialization_alias="queue.buffering.max.messages")
    ] = 100_000
    queue_buffering_max_ms: Annotated[int, Field(ge=0, serialization_alias="linger.ms")] = 5
    statistics_interval_ms: Annotated[int, Field(ge=0, serialization_alias="statistics.interval.ms")] = 30_000
    topic: Annotated[str | None, Field(exclude=True)] = None


class KafkaSettings(BaseSettings):
    """A BaseSettings class for common Kafka parameters.

    These may be set by environment variables as `KAFKA_<setting_name>` and
    each <setting_name> is further transformed into an `rdkafka` configuration
    key as needed.

    Fields with `exclude=True` will be excluded from serialization, i.e., when
    this settings model is serialized to configure a Kafka client, such a field
    is superfluous.

    Notes
    -----
    The optional ssl-related fields must be populated in order to support mTLS
    authentication with a Kafka broker; otherwise the client will fall back to
    unauthenticated access. Without at least the `ssl_ca_location` configured,
    SSL connections to brokers will fail if the broker cert cannot be verified.
    """

    model_config = SettingsConfigDict(env_prefix="KAFKA_", case_sensitive=False, extra="ignore")

    bootstrap_servers: str = Field(default="kafka:9092", serialization_alias="bootstrap.servers")
    client_id: str = Field(default="cmservice", serialization_alias="client.id")
    enable_ssl_certification_verification: bool = Field(
        default=True, serialization_alias="enable.ssl.certificate.verification"
    )
    security_protocol: str = Field(default="SSL", serialization_alias="security.protocol")
    ssl_ca_location: str | None = Field(default=None, serialization_alias="ssl.ca.location")
    ssl_certificate_location: str | None = Field(default=None, serialization_alias="ssl.certificate.location")
    ssl_key_location: str | None = Field(default=None, serialization_alias="ssl.key.location")


kafka_settings = KafkaSettings()
producer_settings = ProducerSettings()
consumer_settings = ConsumerSettings()
