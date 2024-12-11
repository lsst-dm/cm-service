from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import yaml
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from ..common.errors import CMYamlParseError
from ..common.utils import yaml_safe_load
from .base import Base
from .row import RowMixin

if TYPE_CHECKING:
    pass


class ScriptTemplate(Base, RowMixin):
    """Database table to manage script templates

    A 'ScriptTemplate' is a template that gets used to create a bash script
    """

    __tablename__ = "script_template"
    class_string = "script_template"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True)
    data: Mapped[dict | list | None] = mapped_column(type_=JSON)

    col_names_for_table = ["id", "name"]

    @hybrid_property
    def fullname(self) -> str:
        """Maps name to fullname for consistency"""
        return self.name

    def __repr__(self) -> str:
        return f"ScriptTemplate {self.id}: {self.fullname} {self.data}"

    @classmethod
    async def get_create_kwargs(
        cls,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> dict:
        name = kwargs["name"]

        return {
            "name": name,
            "data": kwargs.get("data", None),
        }

    @classmethod
    async def load(  # pylint: disable=too-many-arguments
        cls,
        session: async_scoped_session,
        name: str,
        file_path: str,
    ) -> ScriptTemplate:
        """Load a ScriptTemplate from a file

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        name: str,
            Name for the ScriptTemplate

        file_path
            Path to the file

        Returns
        -------
        script_template : `ScriptTemplate`
            Newly created `ScriptTemplate`
        """
        full_file_path = os.path.abspath(os.path.expandvars(file_path))
        if not os.path.exists(full_file_path):
            raise CMYamlParseError(f"Script template does not exist at path {file_path}")
        try:
            data = await run_in_threadpool(yaml_safe_load, full_file_path)
        except yaml.YAMLError as yaml_error:
            raise CMYamlParseError(f"Error parsing YAML file: {yaml_error}") from yaml_error
        except Exception as e:
            raise CMYamlParseError(f"{e}") from e
        return await cls.create_row(session, name=name, data=data)

    async def update_from_file(
        self,
        session: async_scoped_session,
        name: str,
        file_path: str,
    ) -> ScriptTemplate:
        """Update a ScriptTemplate from a file

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        name: str,
            Name for the ScriptTemplate

        file_path
            Path to the file

        Returns
        -------
        script_template : `ScriptTemplate`
            Newly updated `ScriptTemplate`
        """
        full_file_path = os.path.abspath(os.path.expandvars(file_path))
        if not os.path.exists(full_file_path):
            raise CMYamlParseError(f"Script template does not exist at path {file_path}")

        try:
            data = await run_in_threadpool(yaml_safe_load, full_file_path)
        except yaml.YAMLError as yaml_error:
            raise CMYamlParseError(
                f"Error parsing YAML file at {file_path}; throws {yaml_error}"
            ) from yaml_error
        except Exception as e:
            raise CMYamlParseError(f"{e}") from e
        return await self.update_values(session, name=name, data=data)
