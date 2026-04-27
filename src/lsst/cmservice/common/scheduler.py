import asyncio
from datetime import UTC
from typing import assert_never

import apscheduler.events
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger
from cron_converter import Cron
from fastapi import FastAPI

from lsst.cmservice.models.lib.logging import LOGGER

from ..config import config

logger = LOGGER.bind(module=__name__)

SCHEDULER_EVENTS = (
    apscheduler.events.EVENT_SCHEDULER_STARTED
    | apscheduler.events.EVENT_SCHEDULER_SHUTDOWN
    | apscheduler.events.EVENT_SCHEDULER_PAUSED
    | apscheduler.events.EVENT_SCHEDULER_RESUMED
)
"""Collection of scheduler-related events for observation."""

JOB_EVENTS = (
    apscheduler.events.EVENT_JOB_ERROR
    | apscheduler.events.EVENT_JOB_EXECUTED
    | apscheduler.events.EVENT_JOB_MISSED
)
"""Collection of job-related events for observation."""


class Scheduler:
    """A class wrapping an async `apscheduler` for use with the FastAPI and
    CM Daemon event loop.
    """

    scheduler: BaseScheduler
    sentinel: asyncio.Event

    def __init__(self, app: FastAPI, sentinel: asyncio.Event):
        self.app = app
        self.sentinel = sentinel
        self.scheduler = AsyncIOScheduler(
            timezone=UTC, jobstores={}, job_defaults=config.scheduler.model_dump(by_alias=True)
        )

        match config.scheduler.jobstore_type:
            case "memory":
                self.scheduler.add_jobstore(MemoryJobStore(), alias="default")
            case "sqlalchemy":
                self.configure_postgres_jobstore()
            case _ as unreachable:
                raise RuntimeError("Requested jobstore type not supported.")
                assert_never(unreachable)

    @classmethod
    def normalize_cron_string(cls, cron: str) -> str:
        """Replaces day-of-week numbers with names in a cron string."""
        # WORKAROUND for APScheduler 3.x, which uses 0=monday indexed weekdays
        # - easiest way to deal with this is to always use the weekday names
        #   instead of numbers when providing a cron string to a CronTrigger
        # NOTE
        # - Apscheduler does not support "around the bend" ranges, so a dow
        #   expression like "sun-tues" produces an error.
        return str(Cron(cron, {"output_weekday_names": True}))

    @classmethod
    async def trigger(cls, cron: str | list[str]) -> BaseTrigger:
        """Construct a trigger instance from the given cron string or strings.

        If multiple crons are given, the resulting trigger is the OR combo
        of the triggers.

        Parameters
        ----------
        cron: str | list[str]
            A valid cron expression string, or a list of these strings.
        """

        match cron:
            case str():
                return CronTrigger.from_crontab(cls.normalize_cron_string(cron), timezone=UTC)
            case list():
                return OrTrigger(
                    triggers=[
                        CronTrigger.from_crontab(cls.normalize_cron_string(c), timezone=UTC) for c in cron
                    ]
                )
            case _ as unreachable:
                assert_never(unreachable)
                raise RuntimeError("Invalid cron input for trigger.")

    @property
    def is_running(self) -> bool:
        """Scheduler status wrapper method."""
        return all(
            [
                self.scheduler.running,
                not self.sentinel.is_set(),
            ]
        )

    async def scheduler_task(self) -> None:
        """A coro that is meant to be used with `asyncio.create_task` to
        establish and maintain a perpetual reference to the scheduler under-
        lying this class instance.

        This task will only return if the scheduler is no longer running.
        """
        # Start the scheduler
        self.app.state.scheduler = self
        logger.debug("Starting scheduler")
        self.scheduler.add_listener(self.scheduler_event_handler, mask=SCHEDULER_EVENTS)
        self.scheduler.add_listener(self.job_event_handler, mask=JOB_EVENTS)

        try:
            self.scheduler.start()
            logger.info("Started scheduler")
            # The sentinel event will be set by a scheduler event on shutdown
            await self.sentinel.wait()
            logger.info("App is shutting down")
        except asyncio.CancelledError:
            logger.info("Scheduler task has been cancelled")
            raise
        except Exception:
            logger.exception("Exception raised in Scheduler")
            raise
        finally:
            logger.info("Shutting down scheduler")
            self.scheduler.shutdown(wait=True)
            logger.info("Shut down scheduler")

    def scheduler_event_handler(self, event: apscheduler.events.SchedulerEvent) -> None:
        """Callback handler for scheduler events."""
        match event.code:
            case apscheduler.events.EVENT_SCHEDULER_SHUTDOWN:
                logger.warning("Scheduler has shutdown", code=event.code, alias=event.alias)
            case _:
                logger.info("Scheduler event received", code=event.code, alias=event.alias)

    @classmethod
    def job_event_handler(cls, event: apscheduler.events.JobEvent) -> None:
        """Callback handler for scheduler job-related events."""
        # NOTE event listeners may not be async in apscheduler 3.x
        # TODO integrate with notification system(s)
        logger.info("Scheduler Job event received", code=event.code, alias=event.alias)

    def configure_postgres_jobstore(self) -> None:
        """Helper method to create a jobstore for a postgresql database."""
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
        from sqlalchemy import make_url

        # NOTE apscheduler 3.x does not support async engines, so we need to
        # provide it a URL for it to create its own engine. In 4.x, when
        # released, it should be possible to share the async engine between
        # tasks.
        if isinstance(config.db.url, str):
            url = make_url(config.db.url)
        if config.db.password is not None:
            url = url.set(password=config.db.password.get_secret_value())

        self.scheduler.add_jobstore(
            SQLAlchemyJobStore(
                url=url,
                tablename=config.scheduler.jobstore_table_name,
                tableschema=config.db.table_schema,
            ),
            alias="default",
        )
