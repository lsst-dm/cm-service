"""http routers for managing ScriptTemplateAssociation tables"""
from fastapi import APIRouter

from .. import db, models
from . import wrappers

# Template specialization
# Specify the pydantic model for the table
ResponseModelClass = models.ScriptTemplateAssociation
# Specify the pydantic model from making new rows
CreateModelClass = models.ScriptTemplateAssociationCreate
# Specify the associated database table
DbClass = db.ScriptTemplateAssociation
# Specify the tag in the router documentation
TAG_STRING = "ScriptTemplateAssociations"


# Build the router
router = APIRouter(
    prefix=f"/{DbClass.class_string}",
    tags=[TAG_STRING],
)


# Attach functions to the router
get_rows = wrappers.get_rows_no_parent_function(router, ResponseModelClass, DbClass)
get_row = wrappers.get_row_function(router, ResponseModelClass, DbClass)
get_row_by_fullname = wrappers.get_row_by_fullname_function(router, ResponseModelClass, DbClass)

post_row = wrappers.post_row_function(
    router,
    ResponseModelClass,
    CreateModelClass,
    DbClass,
)
delete_row = wrappers.delete_row_function(router, DbClass)
