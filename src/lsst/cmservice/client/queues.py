from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import pause
from pydantic import ValidationError, parse_obj_as

from .. import models
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient


class CMQueueClient:
    """Interface for accessing remote cm-service."""

    def __init__(self, parent: CMClient) -> None:
        self._client = parent.client

    @property
    def client(self) -> httpx.Client:
        return self._client

    create = wrappers.create_row_function(models.Queue, models.QueueCreate, "queues")

    update = wrappers.update_row_function(models.Queue, "queues")

    delete = wrappers.delete_row_function("queues")

    get = wrappers.get_row_function(models.Queue, "queues")

    def sleep_time(
        self,
        row_id: int,
    ) -> int:
        results = self._client.get(f"queues/sleep_time/{row_id}").json()
        try:
            return parse_obj_as(int, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def process(
        self,
        row_id: int,
    ) -> bool:
        results = self._client.get(f"queues/process/{row_id}").json()
        try:
            return parse_obj_as(bool, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def pause_until_next_check(
        self,
        row_id: int,
    ) -> None:
        queue = self.get(row_id)
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
