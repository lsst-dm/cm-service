import os

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.handlers import functions, interface

from .util_functions import cleanup, delete_all_rows


@pytest.mark.asyncio()
async def test_error_match_db(engine: AsyncEngine) -> None:
    """Test error matching in pipetask_error_type.match.

    Correctly match a real error to the error_type database and fail to match a
    fake error which is not in the database.
    """

    logger = structlog.get_logger(__name__)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        specification = await interface.load_specification(session, "examples/empty_config.yaml")
        check2 = await specification.get_block(session, "campaign")
        assert check2.name == "campaign"

        # Here we list an error which we will insert into the database table.
        known_error = {
            "error_source": "manifest",
            "error_flavor": "configuration",
            "error_action": "review",
            "task_name": "skyObjectMean",
            "diagnostic_message": "The error message from a regular pipetask error",
        }
        # First we want to make a row of the database table for the error.
        e1 = await db.PipetaskErrorType.create_row(
            session,
            **known_error,
        )

        assert e1.fullname == f"{e1.task_name}#{e1.diagnostic_message}", "Bad fullname"

        dummy = await db.PipetaskErrorType.get_row_by_fullname(session, e1.fullname)
        assert dummy.fullname == e1.fullname

        # Assert that the error we just put in the database will match with
        # itself
        assert e1.match(
            known_error["task_name"],
            known_error["diagnostic_message"],
        ), "Known error does not match to its value stored in the database"

        # Here we test that the same error with a different pipetask name will
        # not match. Let's consider the same error, but on task "isr"

        assert (
            e1.match("isr", known_error["diagnostic_message"]) is False
        ), "Failure to identify non-matching pipetask name"

        # Here we test that the same pipetask name but different error does not
        # match.
        assert (
            e1.match(known_error["task_name"], "A different error message") is False
        ), "Failure to identify separate errors with the same associated pipetask"

        # Here we test that a different valid PipetaskError does not match to
        # the wrong PipetaskErrorType
        assert (
            e1.match(
                "subtractImages",
                """Ghoulies and ghosties and long-legged
                    beasties and things that go bump in the night.""",
            )
            is False
        ), "Incorrectly marked unknown error as known"

        # Here we test that match doesn't return true for an empty error
        assert e1.match("", "") is False, "Matched known error to empty strings"

        # using the interface
        matched = await functions.match_pipetask_error(
            session,
            known_error["task_name"],
            known_error["diagnostic_message"],
        )
        assert matched is not None, "interface.match_pipetask_error failed"

        not_matched = await functions.match_pipetask_error(
            session,
            "bad",
            known_error["diagnostic_message"],
        )
        assert not_matched is None

        matched = await functions.match_pipetask_error(
            session,
            known_error["task_name"],
            "bad",
        )
        assert not_matched is None

        await delete_all_rows(session, db.PipetaskErrorType)
        await cleanup(session)


@pytest.mark.asyncio()
async def test_error_type_db(engine: AsyncEngine) -> None:
    """Test `error_type` db table."""

    logger = structlog.get_logger(__name__)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        specification = await interface.load_specification(session, "examples/empty_config.yaml")
        check2 = await specification.get_block(session, "campaign")
        assert check2.name == "campaign"

        # Check UNIQUE constraint
        # Make a PipetaskErrorType to test with
        error = {
            "error_source": "manifest",
            "error_flavor": "pipelines",
            "error_action": "fail",
            "task_name": "task",
            "diagnostic_message": "message",
        }
        # Try to create a PipetaskErrorType twice with the same diagnostic
        # message- pipetask combination Note: currently PipetaskErrorType only
        # lists the diagnostic message as unique but we should really be making
        #       sure it is the combination of the message with the pipetask.
        #       There exist some diagnostic messages which arise from different
        #       tasks.
        e1 = await db.PipetaskErrorType.create_row(
            session,
            **error,
        )
        with pytest.raises(IntegrityError):
            e1 = await db.PipetaskErrorType.create_row(
                session,
                **error,
            )

        # Make sure we can read the same values out of the PipetaskErrorType
        # database that we just put in it and that the id is right
        check = await db.PipetaskErrorType.get_row(session, e1.id)
        assert check.task_name == e1.task_name
        assert check.diagnostic_message == e1.diagnostic_message

        assert check.id == e1.id

        # Check that we have actually created a PipetaskErrorType by putting
        # one in the database
        errors = await db.PipetaskErrorType.get_rows(session)
        n_errors = len(errors)
        assert n_errors >= 1

        # Check that we can delete rows from the PipetaskErrorType database
        await db.PipetaskErrorType.delete_row(session, e1.id)
        errors = await db.PipetaskErrorType.get_rows(session)
        assert len(errors) == n_errors - 1

        await delete_all_rows(session, db.PipetaskErrorType)
        await cleanup(session)
