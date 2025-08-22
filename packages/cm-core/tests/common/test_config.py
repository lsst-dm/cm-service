from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest

from lsst.cmservice.core.common.enums import ScriptMethodEnum
from lsst.cmservice.core.config import Configuration


def test_config_nested_partial_update(monkeypatch: Any) -> None:
    """Tests the nested config modules for partial updates from environment
    variables.
    """
    # An all-defaults configuration
    config_a = Configuration()
    assert not config_a.db.echo
    assert config_a.htcondor.condor_q_bin == "condor_q"
    assert config_a.asgi.port == 8080
    assert config_a.logging.profile == "development"

    monkeypatch.setenv("LOGGING__PROFILE", "production")
    monkeypatch.setenv("ASGI__PORT", "5000")
    monkeypatch.setenv("HTCONDOR__CONDOR_Q_BIN", "/usr/local/bin/condor_q")
    monkeypatch.setenv("DB__ECHO", "1")

    # Partial updates in nested configuration models
    config_b = Configuration()
    assert config_b.db.echo
    assert config_b.htcondor.condor_q_bin == "/usr/local/bin/condor_q"
    assert config_b.asgi.port == 5000
    assert config_b.logging.profile == "production"


def test_config_enum_validation(monkeypatch: Any) -> None:
    """Tests that the enum validation of configuration settings can properly
    validate an enum value and a string (name).
    """
    config = Configuration()
    # The default setting value is an enum
    assert config.script_handler is ScriptMethodEnum.htcondor
    del config

    # Update the configuration with a string (enum name)
    monkeypatch.setenv("SCRIPT_HANDLER", "bash")

    config = Configuration()
    assert config.script_handler is ScriptMethodEnum.bash

    # Use an unsupported value for the enum, expecting the default value
    monkeypatch.setenv("SCRIPT_HANDLER", "zsh")

    with pytest.warns():
        config = Configuration()

    assert config.script_handler is ScriptMethodEnum.htcondor


def test_config_boolean_serialization(monkeypatch: Any) -> None:
    """Test the serialization of boolean field values to strings"""
    config = Configuration()
    assert type(config.panda.verify_host) is bool
    d = config.panda.model_dump(exclude_none=True)
    assert type(d["verify_host"]) is str
    assert d["verify_host"] in ["on", "off"]


def test_config_datetime() -> None:
    """Test the validation of datetime configuration parameters"""
    config = Configuration()

    # avoids mypy's narrowing on first assert behavior
    if not TYPE_CHECKING:
        assert config.panda.token_expiry is None

    # test validation and coercion on assignment
    config.panda.token_expiry = 1740147265  # type: ignore[assignment]
    assert isinstance(config.panda.token_expiry, datetime)
    assert config.panda.token_expiry.tzinfo is UTC

    # test coercion to UTC on assignment of tz-naive datetime
    naive_datetime = datetime(year=2025, month=1, day=2)  # noqa:DTZ001
    config.panda.token_expiry = naive_datetime
    assert (config.panda.token_expiry - naive_datetime.replace(tzinfo=UTC)) == timedelta(0)

    # test coercion to UTC on assignment of tz-aware datetime without changing
    # time
    non_utc_datetime = datetime(year=2025, month=2, day=2, tzinfo=ZoneInfo("America/Chicago"))
    config.panda.token_expiry = non_utc_datetime
    assert config.panda.token_expiry.tzinfo is UTC
    assert (config.panda.token_expiry - non_utc_datetime) == timedelta(0)
