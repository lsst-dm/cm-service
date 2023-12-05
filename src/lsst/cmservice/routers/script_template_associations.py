from fastapi import APIRouter

from .. import db, models
from . import wrappers

response_model_class = models.ScriptTemplateAssociation
create_model_class = models.ScriptTemplateAssociationCreate
db_class = db.ScriptTemplateAssociation
class_string = "script_template_association"
tag_string = "ScriptTemplateAssociations"


router = APIRouter(
    prefix=f"/{class_string}s",
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
