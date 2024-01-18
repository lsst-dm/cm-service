"""http routers for managing SpecBlockAssociation tables"""
from fastapi import APIRouter

from .. import db, models
from . import wrappers

# Template specialization
# Specify the pydantic model for the table
response_model_class = models.SpecBlockAssociation
# Specify the pydantic model from making new rows
create_model_class = models.SpecBlockAssociationCreate
# Specify the associated database table
db_class = db.SpecBlockAssociation
# Specify the tag in the router documentation
tag_string = "SpecBlockAssociations"


# Build the router
router = APIRouter(
    prefix=f"/{db_class.class_string}",
    tags=[tag_string],
)


# Attach functions to the router
get_rows = wrappers.get_rows_no_parent_function(router, response_model_class, db_class)
get_row = wrappers.get_row_function(router, response_model_class, db_class)
post_row = wrappers.post_row_function(
    router,
    response_model_class,
    create_model_class,
    db_class,
)
delete_row = wrappers.delete_row_function(router, db_class)
update_row = wrappers.put_row_function(router, response_model_class, db_class)