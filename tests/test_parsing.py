import pytest

from lsst.cmservice.machines.lib import parse_custom_script_lines
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


@pytest.mark.parametrize(
    "command,output,expected",
    [
        # Templated command does not work as expected with shlex because line
        # is split into tokens on whitespace
        (
            "export ENV_VAR=--option {{ template.variable }}.ext",
            "export 'ENV_VAR=--option {{ template.variable }}.ext'",
            False,
        ),
        # Templated command does not work as expected when too many tokens are
        # taken, i.e., this assignment is broken out into too many tokens, and
        # quotes are introduced.
        (
            ["export", "ENV_VAR=--option", "{{ template.variable }}.ext"],
            "export ENV_VAR=--option '{{ template.variable }}.ext'",
            True,
        ),
        # Templated command works better when explicit tokens are provided as
        # complete strings.
        (
            ["export", "ENV_VAR=--option {{ template.variable }}.ext"],
            "export 'ENV_VAR=--option {{ template.variable }}.ext'",
            True,
        ),
        # Shlex does not permit shell redirections to survive
        (
            ["cat", "file.txt", ">", "another_file.txt"],
            "cat file.txt > another_file.txt",
            False,
        ),
        # Unless we use the full-string approach
        (
            "cat file.txt > another_file.txt",
            "cat file.txt > another_file.txt",
            True,
        ),
    ],
)
def test_shlexing(*, command: str | list[str], output: str, expected: bool) -> None:
    """Test the shell shlexing of arbitrary command strings."""
    command_ = parse_custom_script_lines(command)
    assert (command_ == output) is expected
