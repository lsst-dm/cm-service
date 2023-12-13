import json
from collections.abc import Callable, Sequence
from typing import Any, TypeAlias

import click
import yaml
from pydantic import BaseModel
from tabulate import tabulate

from ..client.client import CMClient
from ..common.enums import StatusEnum
from . import options


def _output_pydantic_object(
    model: BaseModel,
    output: options.OutputEnum | None,
    col_names: list[str] | None = None,
) -> None:
    match output:
        case options.OutputEnum.json:
            click.echo(json.dumps(model.dict(), indent=4))
        case options.OutputEnum.yaml:
            click.echo(yaml.dump(model.dict()))
        case _:
            assert col_names
            the_table = [[getattr(model, col_) for col_ in col_names]]
            click.echo(tabulate(the_table, headers=col_names, tablefmt="plain"))


def _output_pydantic_list(
    models: Sequence[BaseModel],
    output: options.OutputEnum | None,
    col_names: Sequence[str] | None = None,
) -> None:
    the_table = []
    for model_ in models:
        match output:
            case options.OutputEnum.json:
                click.echo(json.dumps(model_.dict(), indent=4))
            case options.OutputEnum.yaml:
                click.echo(yaml.dump(model_.dict()))
            case _:
                assert col_names
                the_table.append([str(getattr(model_, col_)) for col_ in col_names])
    match output:
        case options.OutputEnum.json:
            pass
        case options.OutputEnum.yaml:
            pass
        case _:
            assert col_names
            click.echo(tabulate(the_table, headers=col_names, tablefmt="plain"))


def _output_dict(
    the_dict: dict,
    output: options.OutputEnum | None,
) -> None:
    match output:
        case options.OutputEnum.json:
            click.echo(json.dumps(the_dict, indent=4))
        case options.OutputEnum.yaml:
            click.echo(yaml.dump(the_dict))
        case _:
            for key, val in the_dict.items():
                click.echo(f"{key}: {val}")


def get_list_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    @group_command(name="list", help="list dem rows")
    @options.cmclient()
    @options.output()
    def get_rows(
        client: CMClient,
        output: options.OutputEnum | None,
    ) -> None:
        """List the existing rows"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.get_rows()
        _output_pydantic_list(result, output, db_class.col_names_for_table)

    return get_rows


def get_row_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    @group_command(name="all")
    @options.cmclient()
    @options.row_id()
    @options.output()
    def get_row(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
    ) -> None:
        """Get a single row"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.get_row(row_id)
        _output_pydantic_object(result, output, db_class.col_names_for_table)

    return get_row


def get_create_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    @group_command(name="create")
    @options.cmclient()
    @options.name()
    @options.parent_name()
    @options.spec_block_name()
    @options.data()
    @options.child_config()
    @options.collections()
    @options.spec_aliases()
    @options.handler()
    @options.output()
    def create(
        client: CMClient,
        output: options.OutputEnum | None,
        **kwargs: Any,
    ) -> None:
        """Create a new row"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.create(**kwargs)
        _output_pydantic_object(result, output, db_class.col_names_for_table)

    return create


def get_update_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    @group_command(name="all")
    @options.cmclient()
    @options.row_id()
    @options.name()
    @options.parent_name()
    @options.spec_block_name()
    @options.data()
    @options.child_config()
    @options.collections()
    @options.spec_aliases()
    @options.handler()
    @options.output()
    def update(
        client: CMClient,
        output: options.OutputEnum | None,
        row_id: int,
        **kwargs: Any,
    ) -> None:
        """Update an existing row"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.update(row_id, **kwargs)
        _output_pydantic_object(result, output, db_class.col_names_for_table)

    return update


def get_delete_command(
    group_command: Callable,
    sub_client_name: str,
) -> Callable:
    @group_command(name="delete")
    @options.cmclient()
    @options.row_id()
    def delete(
        client: CMClient,
        row_id: int,
    ) -> None:
        """Delete a row"""
        sub_client = getattr(client, sub_client_name)
        sub_client.delete(row_id)

    return delete


def get_spec_block_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    @group_command(name="get_spec_block")
    @options.cmclient()
    @options.row_id()
    @options.output()
    def get_spec_block(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
    ) -> None:
        """Get the SpecBlock associated to a Node"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.get_spec_block(row_id)
        _output_pydantic_object(result, output, db_class.col_names_for_table)

    return get_spec_block


def get_specification_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command(name="specification")
    @options.cmclient()
    @options.row_id()
    @options.output()
    def get_specification(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
    ) -> None:
        """Get the Specification associated to a Node"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.get_specification(row_id)
        _output_pydantic_object(result, output, db_class.col_names_for_table)

    return get_specification


def get_resolved_collections_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command(name="resolved_collections")
    @options.cmclient()
    @options.row_id()
    @options.output()
    def get_resolved_collections(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
    ) -> None:
        """Get the resovled collection for a partiuclar node"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.get_resolved_collections(row_id)
        _output_dict(result, output)

    return get_resolved_collections


def get_collections_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command(name="collections")
    @options.cmclient()
    @options.row_id()
    @options.output()
    def get_collections(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
    ) -> None:
        """Get the collection parameters for a partiuclar node"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.get_collections(row_id)
        _output_dict(result, output)

    return get_collections


def get_child_config_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command(name="child_config")
    @options.cmclient()
    @options.row_id()
    @options.output()
    def get_child_config(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
    ) -> None:
        """Get the child_config parameters for a partiuclar node"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.get_child_config(row_id)
        _output_dict(result, output)

    return get_child_config


def get_data_dict_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command(name="data_dict")
    @options.cmclient()
    @options.row_id()
    @options.output()
    def get_data_dict(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
    ) -> None:
        """Get the data_dict parameters for a partiuclar node"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.get_data_dict(row_id)
        _output_dict(result, output)

    return get_data_dict


def get_spec_aliases_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command(name="spec_alias")
    @options.cmclient()
    @options.row_id()
    @options.output()
    def get_spec_aliases(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
    ) -> None:
        """Get the spec_aliases parameters for a partiuclar node"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.get_spec_aliases(row_id)
        _output_dict(result, output)

    return get_spec_aliases


def get_update_status_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command(name="status")
    @options.cmclient()
    @options.row_id()
    @options.output()
    @options.status()
    def update_status(
        client: CMClient,
        row_id: int,
        status: StatusEnum,
        output: options.OutputEnum | None,
    ) -> None:
        """Update the status of a particular Node"""
        sub_client = getattr(client, sub_client_name)
        status = sub_client.update_status(
            row_id=row_id,
            status=status,
        )
        _output_dict({"status": status}, output)

    return update_status


def get_update_collections_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command(name="collections")
    @options.cmclient()
    @options.row_id()
    @options.output()
    @options.update_dict()
    def update_collections(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
        **kwargs: Any,
    ) -> None:
        """Update collections configuration of particular Node"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.update_collections(
            row_id=row_id,
            **kwargs,
        )
        _output_dict(result, output)

    return update_collections


def get_update_child_config_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command(name="child_config")
    @options.cmclient()
    @options.row_id()
    @options.output()
    @options.update_dict()
    def update_child_config(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
        **kwargs: Any,
    ) -> None:
        """Update child_config configuration of particular Node"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.update_child_config(
            row_id=row_id,
            **kwargs,
        )
        _output_dict(result, output)

    return update_child_config


def get_update_data_dict_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command(name="data_dict")
    @options.cmclient()
    @options.row_id()
    @options.output()
    @options.update_dict()
    def update_data_dict(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
        **kwargs: Any,
    ) -> None:
        """Update data_dict configuration of particular Node"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.update_data_dict(
            row_id=row_id,
            **kwargs,
        )
        _output_dict(result, output)

    return update_data_dict


def get_update_spec_aliases_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command(name="spec_aliases")
    @options.cmclient()
    @options.row_id()
    @options.output()
    @options.update_dict()
    def update_spec_aliases(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
        **kwargs: Any,
    ) -> None:
        """Update spec_aliases configuration of particular Node"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.update_spec_aliases(
            row_id=row_id,
            **kwargs,
        )
        _output_dict(result, output)

    return update_spec_aliases


def get_action_process_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command()
    @options.cmclient()
    @options.row_id()
    @options.fake_status()
    @options.output()
    def process(
        client: CMClient,
        row_id: int,
        fake_status: StatusEnum | None,
        output: options.OutputEnum | None,
    ) -> None:
        """Process a node"""
        sub_client = getattr(client, sub_client_name)
        changed, status = sub_client.process(
            row_id=row_id,
            fake_status=fake_status,
        )
        _output_dict({"changed": changed, "status": status}, output)

    return process


def get_action_run_check_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    assert db_class

    @group_command(name="run_check")
    @options.cmclient()
    @options.row_id()
    @options.output()
    def run_check(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
    ) -> None:
        """Check the status of a node"""
        sub_client = getattr(client, sub_client_name)
        changed, status = sub_client.run_check(row_id=row_id)
        _output_dict({"changed": changed, "status": status}, output)

    return run_check


def get_action_accept_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    @group_command(name="accept")
    @options.cmclient()
    @options.row_id()
    @options.output()
    def accept(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
    ) -> None:
        """Mark a node as accepted"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.accept(row_id=row_id)
        _output_pydantic_object(result, output, db_class.col_names_for_table)

    return accept


def get_action_reject_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    @group_command(name="reject")
    @options.cmclient()
    @options.row_id()
    @options.output()
    def reject(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
    ) -> None:
        """Mark a node as rejected"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.reject(row_id=row_id)
        _output_pydantic_object(result, output, db_class.col_names_for_table)

    return reject


def get_action_reset_command(
    group_command: Callable,
    sub_client_name: str,
    db_class: TypeAlias,
) -> Callable:
    @group_command(name="reset")
    @options.cmclient()
    @options.row_id()
    @options.output()
    def reset(
        client: CMClient,
        row_id: int,
        output: options.OutputEnum | None,
    ) -> None:
        """Reset the status of a node"""
        sub_client = getattr(client, sub_client_name)
        result = sub_client.reset(row_id=row_id)
        _output_pydantic_object(result, output, db_class.col_names_for_table)

    return reset
