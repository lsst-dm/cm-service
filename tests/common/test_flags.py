import pytest

from lsst.cmservice.common.flags import EnabledFeatures, Features


def test_feature_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    # Empty features have nothing set
    features = EnabledFeatures()
    assert Features.DAEMON_V1 not in features.enabled
    assert features.enabled.value == 0

    # Setting features by env var should result in their being set in the
    # flags enum. Nonexistent features should not be an error.
    monkeypatch.setenv("FEATURE_DAEMON_V2", "1")
    monkeypatch.setenv("FEATURE_DAEMON_CAMPAIGNS", "on")
    monkeypatch.setenv("FEATURE_NO_SUCH_FEATURE", "true")
    features = EnabledFeatures()
    assert Features.DAEMON_V2 in features.enabled
    assert Features.DAEMON_CAMPAIGNS in features.enabled

    # Disabling a feature by env var should result in their not being set in
    # the flags enum, overriding the default or initial value
    monkeypatch.setenv("FEATURE_WEBAPP_V1", "0")
    features = EnabledFeatures(enabled=Features.WEBAPP_V1)
    assert Features.WEBAPP_V1 not in features.enabled
