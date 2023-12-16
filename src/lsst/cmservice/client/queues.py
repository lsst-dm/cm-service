"""python for client API for managing Group tables"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import pause
from pydantic import ValidationError, parse_obj_as

from .. import db, models
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient

# Template specialization
# Specify the pydantic model for Group
response_model_class = models.Queue
# Specify the pydantic model from making new Groups
create_model_class = models.QueueCreate
# Specify the associated database table
db_class = db.Queue

# Construct derived templates
router_string = f"{db_class.class_string}"


class CMQueueClient:
    """Interface for accessing remote cm-service to manipulate Queue Tables"""

    def __init__(self, parent: CMClient) -> None:
        self._client = parent.client

    @property
    def client(self) -> httpx.Client:
        return self._client

    # Add functions to the client class
    get_rows = wrappers.get_rows_no_parent_function(response_model_class, f"{router_string}/list")

    get_row = wrappers.get_row_function(response_model_class, f"{router_string}/get")

    # get_row_by_fullname =

    create = wrappers.create_row_function(
        response_model_class,
        create_model_class,
        f"{router_string}/create",
    )

    update = wrappers.update_row_function(
        response_model_class,
        f"{router_string}/update",
    )

    delete = wrappers.delete_row_function(f"{router_string}/delete")

    def sleep_time(
        self,
        row_id: int,
    ) -> int:
        results = self._client.get(f"{router_string}/sleep_time/{row_id}").json()
        try:
            return parse_obj_as(int, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def process(
        self,
        row_id: int,
    ) -> bool:
        results = self._client.get(f"{router_string}/process/{row_id}").json()
        try:
            return parse_obj_as(bool, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def pause_until_next_check(
        self,
        row_id: int,
    ) -> None:
        queue = self.get_row(row_id)
        sleep_time = self.sleep_time(row_id)
        wait_time = min(sleep_time, queue.interval)
        delta_t = timedelta(seconds=wait_time)
        next_check = queue.time_updated + delta_t
        now = datetime.now()
        print(now, sleep_time, wait_time, next_check)
        if now < next_check:
            print("pausing")
            pause.until(next_check)

    def daemon(
        self,
        row_id: int,
    ) -> None:
        can_continue = True
        while can_continue:
            self.pause_until_next_check(row_id)
            try:
                can_continue = self.process(row_id)
            except Exception:  # pylint: disable=broad-exception-caught
                can_continue = True
