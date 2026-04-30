import asyncio
from typing import Any

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.base import STATE_RUNNING, BaseJobStore, BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from ..config import config
from .logging import LOGGER

logger = LOGGER.bind(module=__name__)


class Scheduler:
    """A class wrapping an async `apscheduler` for use with the FastAPI and
    CM Daemon event loop.
    """

    job_defaults: dict[str, Any]
    jobstores: dict[str, BaseJobStore]
    scheduler: BaseScheduler
    heartbeat_interval_seconds: int = 60

    def __init__(self, app: FastAPI):
        self.app = app
        self.jobstores = {"default": MemoryJobStore()}
        self.job_defaults = config.scheduler.model_dump(by_alias=True)
        self.scheduler = AsyncIOScheduler(jobstores=self.jobstores, job_defaults=self.job_defaults)

    @classmethod
    async def trigger(cls, cron: str) -> CronTrigger:
        """Construct a trigger instance from the given cron string"""
        return CronTrigger.from_crontab(cron)

    async def scheduler_task(self) -> None:
        """A coro that is meant to be used with `asyncio.create_task` to
        establish and maintain a perpetual reference to the scheduler under-
        lying this class instance.

        This task will only return if the scheduler is no longer running.
        """
        # Start the scheduler
        self.app.state.scheduler = self
        logger.debug("Starting scheduler")
        self.scheduler.start()

        try:
            while True:
                if not self.scheduler.running:
                    raise RuntimeError("Scheduler stopped unexpectedly.")
                elif self.scheduler.state != STATE_RUNNING:
                    msg = f"Scheduler in failed state: {self.scheduler.state}"
                    raise RuntimeError(msg)
                await asyncio.sleep(self.heartbeat_interval_seconds)

        except asyncio.CancelledError:
            logger.info("Shutting down scheduler")
            self.scheduler.shutdown()
            raise
