from lsst.cmservice.models.enums import StatusEnum


def test_common_status_enums() -> None:
    """Test common.enums.StatusEnum"""

    for status_enum in StatusEnum:
        if status_enum.is_bad():
            assert status_enum.value <= StatusEnum.rejected.value

        if status_enum.is_processable():
            assert status_enum.value >= StatusEnum.waiting.value
