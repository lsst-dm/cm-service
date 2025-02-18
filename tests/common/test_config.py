from typing import Any

import pytest

from lsst.cmservice.common.enums import ScriptMethodEnum
from lsst.cmservice.config import Configuration


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
    assert config.script_handler == ScriptMethodEnum.htcondor
    del config

    # Update the configuration with a string (enum name)
    monkeypatch.setenv("SCRIPT_HANDLER", "bash")

    config = Configuration()
    assert config.script_handler == ScriptMethodEnum.bash

    # Use an unsupported value for the enum, expecting the default value
    monkeypatch.setenv("SCRIPT_HANDLER", "zsh")

    with pytest.warns():
        config = Configuration()

    assert config.script_handler == ScriptMethodEnum.htcondor
