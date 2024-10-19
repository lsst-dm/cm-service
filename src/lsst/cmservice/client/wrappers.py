from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeAlias, TypeVar

from pydantic import BaseModel, TypeAdapter

from .. import models

if TYPE_CHECKING:
    from .client import CMClient

RMC = TypeVar("RMC", bound=BaseModel)
CMC = TypeVar("CMC", bound=BaseModel)
UMC = TypeVar("UMC", bound=BaseModel)
QC = TypeVar("QC", bound=BaseModel)
RT = TypeVar("RT")


def get_rows_no_parent_function(
    response_model_class: TypeAlias = RMC,
    query: str = "",
) -> Callable:
    """Return a function that gets all the rows from a table
    and attaches that function to a client.

    This version will provide a function that always returns
    all the rows

    Parameters
    ----------
    response_model_class: TypeAlias
        Pydantic class used to serialize the return value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that return all the rows for the table in question
    """

    def get_rows(obj: CMClient) -> list[RMC]:
        results: list[RMC] = []
        params = {"skip": 0}
        while (paged_results := obj.client.get(query, params=params).raise_for_status().json()) != []:
            results.extend(TypeAdapter(list[response_model_class]).validate_python(paged_results))
            params["skip"] += len(paged_results)
        return results

    return get_rows


def get_rows_function(
    response_model_class: TypeAlias = RMC,
    query: str = "",
) -> Callable:
    """Return a function that gets all the rows from a table
    and attaches that function to a client.

    This version will provide a function which can be filtered
    based on the id of the parent node.

    Parameters
    ----------
    response_model_class: TypeAlias
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
    ) -> list[RMC]:
        results: list[RMC] = []
        params: dict[str, Any] = {"skip": 0}
        if parent_id:
            params["parent_id"] = parent_id
        if parent_name:
            params["parent_name"] = parent_name
        while (paged_results := obj.client.get(query, params=params).raise_for_status().json()) != []:
            results.extend(TypeAdapter(list[response_model_class]).validate_python(paged_results))
            params["skip"] += len(paged_results)
        return results

    return get_rows


def get_row_function(
    response_model_class: TypeAlias = RMC,
    query: str = "",
) -> Callable:
    """Return a function that gets a single row from a table (by ID)
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias
        Pydantic class used to serialize the return value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that returns a single row from a table by ID
    """

    def row_get(obj: CMClient, row_id: int) -> response_model_class:
        full_query = f"{query}/{row_id}"
        result = obj.client.get(full_query).raise_for_status().json()
        return response_model_class.model_validate(result)

    return row_get


def create_row_function(
    response_model_class: TypeAlias = RMC,
    create_model_class: TypeAlias = CMC,
    query: str = "",
) -> Callable:
    """Return a function that creates a single row in a table
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias
        Pydantic class used to serialize the return value

    create_model_class: TypeAlias
        Pydantic class used to serialize the inputs value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that returns a single row from a table by ID
    """

    def row_create(obj: CMClient, **kwargs: Any) -> response_model_class:
        params = create_model_class(**kwargs)
        result = obj.client.post(query, content=params.json()).raise_for_status().json()
        return response_model_class.validate_model(result)

    return row_create


def update_row_function(
    response_model_class: TypeAlias = RMC,
    update_model_class: TypeAlias = UMC,
    query: str = "",
) -> Callable:
    """Return a function that updates a single row in a table
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias
        Pydantic class used to serialize the return value

    update_model_class: TypeAlias
        Pydantic class used to serialize the input values

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that updates a row from a table by ID
    """

    def row_update(obj: CMClient, row_id: int, **kwargs: Any) -> response_model_class:
        params = update_model_class(**kwargs)
        full_query = f"{query}/{row_id}"
        results = obj.client.put(f"{full_query}", content=params.json())
        if results.status_code != 200:
            raise ValueError(f"Server returned {results} on PUT call to {full_query}.")

        try:
            return parse_obj_as(response_model_class, results.json())
        except ValidationError as msg:
            print(results)
            raise ValueError(f"Bad response: {results}") from msg

    return row_update


def delete_row_function(query: str = "") -> Callable:
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

    def row_delete(obj: CMClient, row_id: int) -> None:
        full_query = f"{query}/{row_id}"
        obj.client.delete(full_query).raise_for_status()

    return row_delete


def get_row_by_fullname_function(
    response_model_class: TypeAlias = RMC,
    query: str = "",
) -> Callable:
    """Return a function that gets a single row from a table (by fullname)
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias
        Pydantic class used to serialize the return value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that returns a single row from a table by fullname
    """

    def get_row_by_fullname(obj: CMClient, fullname: str) -> response_model_class:
        params = models.FullnameQuery(fullname=fullname)
        result = obj.client.get(query, params=params.model_dump()).raise_for_status().json()
        return response_model_class.validate_python(result)

    return get_row_by_fullname


def get_row_by_name_function(
    response_model_class: TypeAlias = RMC,
    query: str = "",
) -> Callable:
    """Return a function that gets a single row from a table (by name)
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias
        Pydantic class used to serialize the return value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that returns a single row from a table by name
    """

    def get_row_by_name(obj: CMClient, name: str) -> RMC | None:
        params = models.NameQuery(name=name)
        result = obj.client.get(query, params=params.model_dump()).raise_for_status().json()
        return response_model_class.validate_python(result)

    return get_row_by_name


def get_node_property_function(
    response_type: TypeAlias = RT,
    query: str = "",
    query_suffix: str = "",
) -> Callable:
    """Return a function that gets a property of a single row of a table
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: TypeAlias
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

    def get_node_property(obj: CMClient, row_id: int) -> response_type:
        results = obj.client.get(f"{query}/{row_id}/{query_suffix}").raise_for_status().json()
        return results

    return get_node_property


def get_node_property_by_fullname_function(
    response_type: TypeAlias = RT,
    query: str = "",
) -> Callable:
    """Return a function that gets a property of a single row of a table
    and attaches that function to a client.

    Parameters
    ----------
    response_type: TypeAlias
        Pydantic class used to serialize the return value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that returns a property of a single row from a table by name
    """

    def get_node_property_by_fullname(obj: CMClient, fullname: str) -> response_type:
        params = models.FullnameQuery(fullname=fullname)
        results = obj.client.get(query, params=params.model_dump()).raise_for_status().json()
        return results

    return get_node_property_by_fullname


def get_node_post_query_function(
    response_model_class: type[RMC],
    query_class: type[QC],
    query: str = "",
    query_suffix: str = "",
) -> Callable:
    """Return a function that invokeds a post method on DB ojbject
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: type
        Pydantic class used to serialize the return value

    query_class: type[bound=BaseModel]
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

    def node_update(obj: CMClient, row_id: int, **kwargs: Any) -> RMC:
        params = query_class(**kwargs)
        results = (
            obj.client.post(f"{query}/{row_id}/{query_suffix}", content=params.json())
            .raise_for_status()
            .json()
        )
        return results

    return node_update


def get_node_post_no_query_function(
    response_model_class: type[RMC],
    query: str = "",
    query_suffix: str = "",
) -> Callable:
    """Return a function that invokeds a post method on DB ojbject
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: type
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

    def node_update(obj: CMClient, row_id: int) -> RMC:
        results = obj.client.post(f"{query}/{row_id}/{query_suffix}").raise_for_status().json()
        return results

    return node_update


def get_job_property_function(
    response_model_class: type[RMC],
    query: str = "",
) -> Callable:
    """Return a function that invokes a query
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: type
        Pydantic class used to serialize the return value

    query: str
        http query

    Returns
    -------
    the_function: Callable
        Function that invokes a query
    """

    def get_job_property(
        obj: CMClient,
        fullname: str,
    ) -> list[RMC]:
        params = models.FullnameQuery(fullname=fullname)
        results = obj.client.get(query, params=params.model_dump()).raise_for_status().json()
        return results

    return get_job_property


def get_general_post_function(
    query_class: type[QC],
    response_model_class: type[RMC],
    query: str = "",
    results_key: str | None = None,
) -> Callable:
    """Return a function that invokeds a post method on DB ojbject
    and attaches that function to a client.

    Parameters
    ----------
    response_model_class: type
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

    def general_post_function(obj: CMClient, **kwargs: Any) -> RMC:
        params = query_class(**kwargs)
        results = obj.client.post(query, content=params.json()).raise_for_status().json()
        return results

    return general_post_function


def get_general_query_function(
    query_class: TypeAlias = QC,
    response_model_class: TypeAlias = RMC,
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

    response_model_class: TypeAlias
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

    def general_query_function(obj: CMClient, row_id: int, **kwargs: Any) -> response_model_class:
        params = query_class(**kwargs)
        results = (
            obj.client.get(f"{query}/{row_id}/{query_suffix}", params=params.model_dump())
            .raise_for_status()
            .json()
        )
        return TypeAdapter(list[response_model_class]).validate_python(results)

    return general_query_function
