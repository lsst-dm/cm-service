import pytest

from lsst.cmservice.models.lib import parsers


@pytest.mark.parametrize(
    "in_,out_",
    [
        ("a dirty string with special characters", "a_dirty_string_with_special_characters"),
        ("a!dirty/string@with[special]characters", "a_dirty_string_with_special_characters"),
    ],
)
def test_as_snake_case(in_: str, out_: str):
    """Test snake_case parsing of dirty strings"""
    assert parsers.as_snake_case(in_) == out_


@pytest.mark.parametrize(
    "in_,out_",
    [
        ("a dirty string with special characters", "a_dirty_string_with_special_characters"),
        ("a!dirty/string@with[special]characters", "a_dirty_string_with_special_characters"),
        ("u/{{username}}/{{detail}}", "u_{{username}}_{{detail}}"),
        ("${u}/{{username}}/{detail}", "__u__{{username}}__detail_"),
    ],
)
def test_as_templated_snake_case(in_: str, out_: str):
    """Test snake_case parsing of dirty strings with template variables"""
    assert parsers.as_templated_snake_case(in_) == out_


@pytest.mark.parametrize(
    "in_,out_",
    [
        ("/a/path/with/trailing/slash/", "/a/path/with/trailing/slash"),
        ("/a/path/without/trailing/slash", "/a/path/without/trailing/slash"),
        ("/a/path/with/double/trailing/slash//", "/a/path/with/double/trailing/slash"),
    ],
)
def test_strip_trailing_slash(in_: str, out_: str):
    """Test trailing slash parsing of strings"""
    assert parsers.strip_trailing_slash(in_) == out_
