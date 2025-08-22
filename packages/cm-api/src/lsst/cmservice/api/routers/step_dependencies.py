"""http routers for managing StepDependency tables"""

from fastapi import APIRouter

from lsst.cmservice.core import db, models

from . import wrappers

# Template specialization
# Specify the pydantic model for the table
ResponseModelClass = models.Dependency
# Specify the pydantic model from making new rows
CreateModelClass = models.DependencyCreate
# Specify the associated database table
DbClass = db.StepDependency


# Build the router
router = APIRouter(
    prefix=f"/{DbClass.class_string}",
    tags=["step dependencies"],
)


# Attach functions to the router
get_rows = wrappers.get_rows_no_parent_function(router, ResponseModelClass, DbClass)
get_row = wrappers.get_row_function(router, ResponseModelClass, DbClass)
post_row = wrappers.post_row_function(
    router,
    ResponseModelClass,
    CreateModelClass,
    DbClass,
)
delete_row = wrappers.delete_row_function(router, DbClass)
