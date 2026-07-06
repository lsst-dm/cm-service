"""Module implements an audit-logging middleware.

If any route has added an audit log sequence to the request state, this
middleware will write the audit log entries to the database after the route has
completed successfully. The database action is deferred to a `BackgroundTask`.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, assert_never

from fastapi import Request, Response
from starlette.background import BackgroundTask, BackgroundTasks
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from lsst.cmservice.models.db.audit import AuditLog

from ..db.session import db_session_dependency


@dataclass
class AuditLogCollector:
    """Collector class for audit log middleware."""

    logs: list[AuditLog] = field(default_factory=list)

    def add(self, log: AuditLog) -> None:
        """Add an audit log entry to the collector"""
        self.logs.append(log)

    def __bool__(self) -> bool:
        """Return True if log entries are present"""
        return bool(self.logs)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Middleware to write audit log entries to the database after a route has
    completed successfully."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.audit = AuditLogCollector()
        response = await call_next(request)

        # middleware ends early if the route has not added an audit entry
        if not request.state.audit:
            return response

        match response.background:
            case None:
                response.background = BackgroundTasks()

            case BackgroundTasks():
                pass

            case BackgroundTask() as task:
                tasks = BackgroundTasks()
                tasks.tasks.append(task)
                response.background = tasks

            case _ as unreachable:
                assert_never(unreachable)

        response.background.add_task(serialize_audit, request.state.audit)

        return response


async def serialize_audit(collector: AuditLogCollector) -> None:
    """Serializes the collection of audit logs by writing to the database."""
    if TYPE_CHECKING:
        assert db_session_dependency.sessionmaker is not None

    async with db_session_dependency.sessionmaker() as session:
        session.add_all(collector.logs)
        await session.commit()
