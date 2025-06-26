import pytest

from lsst.cmservice.parsing.string import parse_element_fullname


@pytest.mark.parametrize(
    "fullname,expected",
    [
        ("campaign_name/step_name/group0/job_000/script_000", "script"),
        ("campaign_name/step_name/group0/job_000", "job"),
        ("campaign_name/step_name/group0", "group"),
        ("campaign_name/step_name", "step"),
        ("campaign_name", "campaign"),
        ("campaign-name", "campaign"),
    ],
)
def test_fullname_parsing(fullname: str, expected: str) -> None:
    """Test element fullname regex"""
    fullname_ = parse_element_fullname(fullname)
    assert getattr(fullname_, expected) is not None

    assert fullname_.fullname() == fullname
