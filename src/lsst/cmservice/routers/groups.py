from fastapi import APIRouter

from .. import db, models
from . import wrappers

response_model_class = models.Group
create_model_class = models.GroupCreate
db_class = db.Group
tag_string = "Groups"


router = APIRouter(
    prefix=f"/{db_class.class_string}",
    tags=[tag_string],
)


get_rows = wrappers.get_rows_function(router, response_model_class, db_class)
get_row = wrappers.get_row_function(router, response_model_class, db_class)
get_row_by_fullname = wrappers.get_row_function(router, response_model_class, db_class)
post_row = wrappers.post_row_function(
    router,
    response_model_class,
    create_model_class,
    db_class,
)
delete_row = wrappers.delete_row_function(router, db_class)
update_row = wrappers.put_row_function(router, response_model_class, db_class)
get_spec_block = wrappers.get_node_spec_block_function(router, db_class)
get_specification = wrappers.get_node_specification_function(router, db_class)
get_parent = wrappers.get_node_parent_function(router, models.Production, db_class)
get_resolved_collections = wrappers.get_node_resolved_collections_function(router, db_class)
get_collections = wrappers.get_node_collections_function(router, db_class)
get_child_config = wrappers.get_node_child_config_function(router, db_class)
get_data_dict = wrappers.get_node_data_dict_function(router, db_class)
get_spec_aliases = wrappers.get_node_spec_aliases_function(router, db_class)
update_collections = wrappers.update_node_collections_function(
    router,
    response_model_class,
    db_class,
)
update_child_config = wrappers.update_node_child_config_function(
    router,
    response_model_class,
    db_class,
)
update_data_dict = wrappers.update_node_data_dict_function(
    router,
    response_model_class,
    db_class,
)
update_spec_aliases = wrappers.update_node_spec_aliases_function(
    router,
    response_model_class,
    db_class,
)
accept = wrappers.get_node_accept_function(router, response_model_class, db_class)
reject = wrappers.get_node_reject_function(router, response_model_class, db_class)
reset = wrappers.get_node_reset_function(router, response_model_class, db_class)
process = wrappers.get_node_process_function(router, response_model_class, db_class)
run_check = wrappers.get_node_run_check_function(router, response_model_class, db_class)
