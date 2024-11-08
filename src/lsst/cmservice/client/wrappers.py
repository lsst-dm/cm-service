from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeAlias

from pydantic import BaseModel, TypeAdapter

from .. import models

if TYPE_CHECKING:
    from .client import CMClient


def get_rows_no_parent_function(
    response_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    """Return a function that gets all the rows from a table
    and attaches that function to a client.

    This version will provide a function that always returns
    all the rows

    Parameters
    ----------
    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that return all the rows for the table in question
    """

    def get_rows(obj: CMClient) -> list[response_model_class]:
        results: list[response_model_class] = []
        params = {"skip": 0}
        adapter = TypeAdapter(list[response_model_class])
        while (paged_results := obj.client.get(query, params=params).raise_for_status().json()) != []:
            results.extend(adapter.validate_python(paged_results))
            params["skip"] += len(paged_results)
        return results

    return get_rows


def get_rows_function(
    response_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:  # pragma: no cover
    """Return a function that gets all the rows from a table
    and attaches that function to a client.

    This version will provide a function which can be filtered
    based on the id of the parent node.

    Parameters
    ----------
    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that return all the rows for the table in question
    """

    def get_rows(
        obj: CMClient,
        parent_id: int | None = None,
        parent_name: str | None = None,
    ) -> list[response_model_class]:
        results: list[response_model_class] = []
        params: dict[str, Any] = {"skip": 0}
        adapter = TypeAdapter(list[response_model_class])
        if parent_id:
            params["parent_id"] = parent_id
        if parent_name:
            params["parent_name"] = parent_name
        while (paged_results := obj.client.get(f"{query}", params=params).raise_for_status().json()) != []:
            results.extend(adapter.validate_python(paged_results))
            params["skip"] += len(paged_results)
        return results

    return get_rows


def get_row_function(
    response_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    """Return a function that gets a single row from a table (by ID)
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that returns a single row from a table by ID
    """

    def row_get(
        obj: CMClient,
        row_id: int,
    ) -> response_model_class:
        full_query = f"{query}/{row_id}"
        results = obj.client.get(full_query).raise_for_status().json()
        return TypeAdapter(response_model_class).validate_python(results)

    return row_get


def create_row_function(
    response_model_class: TypeAlias = BaseModel,
    create_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    """Return a function that creates a single row in a table
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    create_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the inputs value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that returns a single row from a table by ID
    """

    def row_create(obj: CMClient, **kwargs: Any) -> response_model_class:
        content = create_model_class(**kwargs).model_dump_json()
        results = obj.client.post(query, content=content).raise_for_status().json()
        return TypeAdapter(response_model_class).validate_python(results)

    return row_create


def update_row_function(
    response_model_class: TypeAlias = BaseModel,
    update_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    """Return a function that updates a single row in a table
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    update_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the input values

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that updates a row from a table by ID
    """

    def row_update(
        obj: CMClient,
        row_id: int,
        **kwargs: Any,
    ) -> response_model_class:
        full_query = f"{query}/{row_id}"
        content = update_model_class(**kwargs).model_dump_json()
        results = obj.client.put(full_query, content=content).raise_for_status().json()
        return TypeAdapter(response_model_class).validate_python(results)

    return row_update


def delete_row_function(
    query: str = "",
) -> Callable:
    """Return a function that deletes a single row in a table
    and attaches that function to a client.

    Parameters
    ----------
    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that delete a single row from a table by ID
    """

    def row_delete(
        obj: CMClient,
        row_id: int,
    ) -> None:
        full_query = f"{query}/{row_id}"
        obj.client.delete(full_query).raise_for_status()

    return row_delete


def get_row_by_fullname_function(
    response_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    """Return a function that gets a single row from a table (by fullname)
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that returns a single row from a table by fullname
    """

    def get_row_by_fullname(
        obj: CMClient,
        fullname: str,
    ) -> response_model_class | None:
        params = models.FullnameQuery(fullname=fullname).model_dump()
        response = obj.client.get(query, params=params)
        if response.status_code == 404:
            return None
        results = response.raise_for_status().json()
        return TypeAdapter(response_model_class).validate_python(results)

    return get_row_by_fullname


def get_row_by_name_function(
    response_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    """Return a function that gets a single row from a table (by name)
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that returns a single row from a table by name
    """

    def get_row_by_name(
        obj: CMClient,
        name: str,
    ) -> response_model_class | None:
        params = models.NameQuery(name=name).model_dump()
        response = obj.client.get(query, params=params)
        if response.status_code == 404:
            return None
        results = response.raise_for_status().json()
        return TypeAdapter(response_model_class).validate_python(results)

    return get_row_by_name


def get_node_property_function(
    response_model_class: TypeAlias,
    query: str = "",
    query_suffix: str = "",
) -> Callable:
    """Return a function that gets a property of a single row of a table
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    query: str
        http query

    query_suffix: str
        suffix of query specifying the property in question

    Returns
    -------
    the_function: Callable
        Function that returns a property of a single row from a table by name
    """

    def get_node_property(
        obj: CMClient,
        row_id: int,
    ) -> response_model_class:
        full_query = f"{query}/{row_id}/{query_suffix}"
        results = obj.client.get(full_query).raise_for_status().json()
        return TypeAdapter(response_model_class).validate_python(results)

    return get_node_property


def get_node_post_query_function(
    response_model_class: TypeAlias,
    query_class: TypeAlias,
    query: str = "",
    query_suffix: str = "",
) -> Callable:
    """Return a function that invokeds a post method on DB ojbject
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    query_class: TypeAlias
        Pydantic class used to serialize the query parameters

    query: str
        http query

    query_suffix: str
        suffix of query specifying the property in question

    Returns
    -------
    the_function: Callable
        Function that invokeds a post method on DB ojbject
    """

    def node_update(
        obj: CMClient,
        row_id: int,
        **kwargs: Any,
    ) -> response_model_class:
        full_query = f"{query}/{row_id}/{query_suffix}"
        content = query_class(**kwargs).model_dump_json()
        results = obj.client.post(full_query, content=content).raise_for_status().json()
        return TypeAdapter(response_model_class).validate_python(results)

    return node_update


def get_node_post_no_query_function(
    response_model_class: TypeAlias,
    query: str = "",
    query_suffix: str = "",
) -> Callable:
    """Return a function that invokeds a post method on DB ojbject
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    query: str
        http query

    query_suffix: str
        suffix of query specifying the property in question

    Returns
    -------
    the_function: Callable
        Function that invokeds a post method on DB ojbject
    """

    def node_update(
        obj: CMClient,
        row_id: int,
    ) -> response_model_class:
        full_query = f"{query}/{row_id}/{query_suffix}"
        results = obj.client.post(full_query).raise_for_status().json()
        return TypeAdapter(response_model_class).validate_python(results)

    return node_update


def get_general_post_function(
    query_class: TypeAlias = BaseModel,
    response_model_class: TypeAlias = Any,
    query: str = "",
    results_key: str | None = None,
) -> Callable:
    """Return a function that invokeds a post method on DB ojbject
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    query: str
        http query

    results_key
        Used to grab part of the response

    Returns
    -------
    the_function: Callable
        Function that invokeds a post method on DB ojbject
    """

    def general_post_function(
        obj: CMClient,
        **kwargs: Any,
    ) -> response_model_class:
        content = query_class(**kwargs).model_dump_json()
        results = obj.client.post(query, content=content).raise_for_status().json()
        if results_key is None:
            return TypeAdapter(response_model_class).validate_python(results)
        return TypeAdapter(response_model_class).validate_python(results[results_key])  # pragma: no cover

    return general_post_function


def get_general_query_function(
    query_class: TypeAlias = BaseModel,
    response_model_class: TypeAlias = Any,
    query: str = "",
    query_suffix: str = "",
    results_key: str | None = None,
) -> Callable:
    """Return a function that invokeds a get method on DB ojbject
    and attaches that function to a client.

    Parameters
    ----------
    query_class: TypeAlias
        Pydantic class used to serialize the query parameters

    response_model_class: TypeAlias = BaseModel,
        Pydantic class used to serialize the return value

    query: str
        http query

    query_suffix: str
        suffix of query specifying the property in question

    results_key: str | None
        Used to grab part of the response

    Returns
    -------
    the_function: Callable
        Function that invokeds a get method on DB ojbject
    """

    def general_query_function(
        obj: CMClient,
        row_id: int,
        **kwargs: Any,
    ) -> response_model_class:
        full_query = f"{query}/{row_id}/{query_suffix}"
        params = query_class(**kwargs).model_dump()
        results = obj.client.get(full_query, params=params).raise_for_status().json()
        if results_key is None:
            return TypeAdapter(response_model_class).validate_python(results)
        return TypeAdapter(response_model_class).validate_python(results[results_key])  # pragma: no cover

    return general_query_function
