from fastapi import APIRouter

from .. import db, models
from . import wrappers

response_model_class = models.Dependency
create_model_class = models.DependencyCreate
db_class = db.ScriptDependency
tag_string = "Script Dependencies"


router = APIRouter(
    prefix=f"/{db_class.class_string}",
    tags=[tag_string],
)


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
