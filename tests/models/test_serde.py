import pytest
from pydantic import BaseModel, ValidationError

from lsst.cmservice.common.enums import ManifestKind, StatusEnum
from lsst.cmservice.common.types import KindField, StatusField


class TestModel(BaseModel):
    status: StatusField
    kind: KindField


def test_validators() -> None:
    """Test model field enum validators."""
    # test enum validation by name and value
    x = TestModel(status=0, kind="campaign")
    assert x.status is StatusEnum.waiting
    assert x.kind is ManifestKind.campaign

    # test bad input (wrong name)
    with pytest.raises(ValidationError):
        x = TestModel(status="bad", kind="edge")

    # test bad input (bad value)
    with pytest.raises(ValidationError):
        x = TestModel(status="waiting", kind=99)


def test_serializers() -> None:
    x = TestModel(status="accepted", kind="node")
    y = x.model_dump()
    assert y["status"] == "accepted"
    assert y["kind"] == "node"
