"""python for client API for managing Group tables"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import pause
from pydantic import TypeAdapter, ValidationError

from .. import db, models
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient

# Template specialization
# Specify the pydantic model for Group
ResponseModelClass = models.Queue
# Specify the pydantic model from making new Groups
CreateModelClass = models.QueueCreate
# Specify the pydantic model from updating rows
UpdateModelClass = models.QueueUpdate
# Specify the associated database table
DbClass = db.Queue

# Construct derived templates
router_string = f"{DbClass.class_string}"


class CMQueueClient:
    """Interface for accessing remote cm-service to manipulate Queue Tables"""

    def __init__(self, parent: CMClient) -> None:
        self._client = parent.client

    @property
    def client(self) -> httpx.Client:
        """Return the httpx.Client"""
        return self._client

    # Add functions to the client class
    get_rows = wrappers.get_rows_no_parent_function(ResponseModelClass, f"{router_string}/list")

    get_row = wrappers.get_row_function(ResponseModelClass, f"{router_string}/get")

    # get_row_by_fullname =

    create = wrappers.create_row_function(
        ResponseModelClass,
        CreateModelClass,
        f"{router_string}/create",
    )

    update = wrappers.update_row_function(
        ResponseModelClass,
        UpdateModelClass,
        f"{router_string}/update",
    )

    delete = wrappers.delete_row_function(f"{router_string}/delete")

    def sleep_time(
        self,
        row_id: int,
    ) -> int:
        """Check how long to sleep based on what is running

        Parameters
        ----------
        row_id: int
            ID of the Queue row in question

        Returns
        -------
        sleep_time: int
            Time to sleep before next call to process (in seconds)
        """
        results = self._client.get(f"{router_string}/sleep_time/{row_id}").json()
        try:
            return TypeAdapter(int).validate_json(results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def process(
        self,
        row_id: int,
    ) -> bool:
        """Process associated element

        Parameters
        ----------
        row_id: int
            ID of the Queue row in question

        Returns
        -------
        can_continue: bool
            True if processing can continue
        """
        results = self._client.get(f"{router_string}/process/{row_id}").json()
        try:
            return TypeAdapter(bool).validate_json(results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def pause_until_next_check(
        self,
        row_id: int,
    ) -> None:
        """Sleep until the next time to check associated element

        Parameters
        ----------
        row_id: int
            ID of the Queue row in question
        """
        now = datetime.now()
        try:
            queue = self.get_row(row_id)
            sleep_time = self.sleep_time(row_id)
            wait_time = min(sleep_time, queue.interval)
            delta_t = timedelta(seconds=wait_time)
            next_check = queue.time_updated + delta_t
        except Exception as msg:  # pylint: disable=broad-exception-caught
            print(f"failed to compute next_check time, making best guess: {msg}")
            sleep_time = 300
            wait_time = 300
            delta_t = timedelta(seconds=sleep_time)
            next_check = now + delta_t
        print(now, sleep_time, wait_time, delta_t, next_check)
        if now < next_check:
            print("pausing")
            pause.until(next_check)

    def daemon(
        self,
        row_id: int,
    ) -> None:
        """Run client-side daemon on a queued element

        Parameters
        ----------
        row_id: int
            ID of the Queue row in question
        """
        can_continue = True
        while can_continue:
            self.pause_until_next_check(row_id)
            try:
                can_continue = self.process(row_id)
            except Exception as msg:  # pylint: disable=broad-exception-caught
                print(f"Caught exception in process: {msg}, continuing")
                try:
                    self.update(row_id, time_updated=datetime.now())
                except Exception as msg2:  # pylint: disable=broad-exception-caught
                    print(f"Failed to modify time_updated: {msg2}, continuing")
                can_continue = True
