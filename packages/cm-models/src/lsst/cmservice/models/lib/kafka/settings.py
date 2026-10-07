"""Module describing settings used by Kafka clients."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, PlainSerializer
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..parsers import csv_serializer, csv_validator, parse_env_list


class ConsumerSettings(BaseSettings):
    """A BaseSettings class for Kafka consumer-specific parameters.

    Fields with ``exclude=True`` set are not passed to the Consumer constructor
    as configuration.

    Notes
    -----
    The default settings reflect the same defaults provided in the
    `librdkakfa`` library. These provide for a consumer that starts consuming
    at the end of a topic and auto-commits offsets.

    For a precise consumer, set ``auto_offset_commit`` and
    ``enable_auto_reset_store`` to ``False`` and manually call the offset store
    API (``store_offsets()`` followed by ``commit()``) or commit individual
    messages with ``commit(Message)``.
    """

    model_config = SettingsConfigDict(
        env_prefix="KAFKA_CONSUMER__",
        extra="ignore",
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
    )

    auto_offset_commit: Annotated[bool, Field(serialization_alias="enable.auto.commit")] = True
    auto_offset_reset: Annotated[
        Literal["earliest", "latest"], Field(serialization_alias="auto.offset.reset")
    ] = "latest"
    auto_offset_store: Annotated[bool, Field(serialization_alias="enable.auto.offset.store")] = True
    auto_commit_interval_ms: Annotated[int, Field(serialization_alias="auto.commit.interval.ms")] = 5_000
    min_queued_messages: Annotated[
        int,
        Field(
            description="Min number of fetched messages to maintain in the local consumer queue",
            serialization_alias="queued.min.messages",
        ),
    ] = 100_000
    max_queued_messages_kbytes: Annotated[
        int,
        Field(
            description="Max kbytes allocated to the local consumer queue",
            serialization_alias="queued.max.messages.kbytes",
        ),
    ] = 65_536
    max_poll_interval_ms: Annotated[int, Field(serialization_alias="max.poll.interval.ms")] = 300_000
    group_id: Annotated[str, Field(serialization_alias="group.id")] = "cmservice"
    topics: Annotated[list[str], BeforeValidator(parse_env_list), Field(exclude=True)] = Field(
        default_factory=list
    )
    max_send_queue_size: Annotated[
        int, Field(description="Maximum number of messages to hold in consumer runtime queue", exclude=True)
    ] = 100


class ProducerSettings(BaseSettings):
    """A BaseSettings class for Kafka producer-specific parameters.

    Fields with ``exclude=True`` set are not passed to the Producer constructor
    as configuration.

    Fields that are passed to the Producer constructor feature a
    ``serialization_alias``.
    """

    model_config = SettingsConfigDict(env_prefix="KAFKA_PRODUCER__", extra="ignore")

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
    message_timeout_ms: Annotated[int, Field(ge=0, serialization_alias="message.timeout.ms")] = 300_000
    topic: Annotated[str | None, Field(exclude=True)] = None
    tries: Annotated[int, Field(exclude=True)] = 5
    delay: Annotated[float, Field(exclude=True)] = 3.0
    backoff: Annotated[float, Field(exclude=True)] = 1.2


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

    model_config = SettingsConfigDict(env_prefix="KAFKA__", case_sensitive=False, extra="ignore")

    bootstrap_servers: Annotated[
        str | list[str],
        PlainSerializer(csv_serializer),
        BeforeValidator(csv_validator),
        Field(serialization_alias="bootstrap.servers"),
    ] = Field(default_factory=list)
    client_id: Annotated[str, Field(serialization_alias="client.id")] = Field(default="cmservice")
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
