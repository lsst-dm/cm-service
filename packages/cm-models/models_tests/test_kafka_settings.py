import pytest


@pytest.fixture
def env_setup(request, monkeypatch):
    """Configure environment variables for multiple parameterized test
    scenarios.
    """
    # These vars may change between tests
    match request.param:
        case "scenario_env_strings":
            monkeypatch.setenv("KAFKA__BOOTSTRAP_SERVERS", "mockfka:9092,mockfkb:9092")
            monkeypatch.setenv("KAFKA_CONSUMER__AUTO_OFFSET_COMMIT", "0")
            monkeypatch.setenv("KAFKA_CONSUMER__TOPICS__0", "topicA")
            monkeypatch.setenv("KAFKA_CONSUMER__TOPICS__1", "topicB")
        case "scenario_env_json":
            monkeypatch.setenv("KAFKA__BOOTSTRAP_SERVERS", '["mockfka:9092","mockfkb:9092"]')
            monkeypatch.setenv("KAFKA_CONSUMER__AUTO_OFFSET_COMMIT", "false")
            monkeypatch.setenv(
                "KAFKA_CONSUMER__TOPICS",
                '["topicA", "topicB"]',
            )
        case _:
            ...

    # These vars do not change
    monkeypatch.setenv("KAFKA_CONSUMER__GROUP_ID", "mockers")


@pytest.mark.parametrize("env_setup", ["scenario_env_strings", "scenario_env_json"], indirect=True)
def test_kafka_settings(env_setup):
    """Test the validation and serialization of Kafka settings as populated by
    environment variables.
    """
    from lsst.cmservice.models.lib.kafka import settings

    k_settings = settings.KafkaSettings()  # type: ignore[call-arg]
    c_settings = settings.ConsumerSettings()  # type: ignore[call-arg]
    assert isinstance(k_settings.bootstrap_servers, list)
    assert len(k_settings.bootstrap_servers) == 2
    assert isinstance(c_settings.topics, list)
    assert len(c_settings.topics) >= 1

    consumer_conf = k_settings.model_dump(by_alias=True) | c_settings.model_dump(by_alias=True)
    assert consumer_conf["bootstrap.servers"] == ",".join(k_settings.bootstrap_servers)
    assert consumer_conf["client.id"] == k_settings.client_id
    assert consumer_conf["group.id"] == c_settings.group_id
    assert consumer_conf["auto.offset.reset"] == c_settings.auto_offset_reset
    assert consumer_conf["enable.auto.commit"] == c_settings.auto_offset_commit
