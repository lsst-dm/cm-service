from fastapi import APIRouter

from .. import db, models
from . import wrappers

response_model_class = models.Dependency
create_model_class = models.DependencyCreate
db_class = db.StepDependency
class_string = "step_dependency"
tag_string = "Step Dependencies"


router = APIRouter(
    prefix="/step_dependencies",
    tags=[tag_string],
)


get_rows = wrappers.get_rows_no_parent_function(router, response_model_class, db_class, class_string)
get_row = wrappers.get_row_function(router, response_model_class, db_class, class_string)
post_row = wrappers.post_row_function(
    router,
    response_model_class,
    create_model_class,
    db_class,
    class_string,
)
delete_row = wrappers.delete_row_function(router, db_class, class_string)
update_row = wrappers.put_row_function(router, response_model_class, db_class, class_string)
