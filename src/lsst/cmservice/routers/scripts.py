from fastapi import APIRouter, Depends
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..common.enums import StatusEnum
from . import wrappers

response_model_class = models.Script
create_model_class = models.ScriptCreate
db_class = db.Script
class_string = "script"
tag_string = "Scripts"


router = APIRouter(
    prefix=f"/{class_string}s",
    tags=[tag_string],
)


get_rows = wrappers.get_rows_function(router, response_model_class, db_class, class_string)
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
get_spec_block = wrappers.get_node_spec_block_function(router, db_class, class_string)
get_specification = wrappers.get_node_specification_function(router, db_class, class_string)
get_parent = wrappers.get_node_parent_function(router, models.Production, db_class, class_string)
get_resolved_collections = wrappers.get_node_resolved_collections_function(router, db_class, class_string)
get_collections = wrappers.get_node_collections_function(router, db_class, class_string)
get_child_config = wrappers.get_node_child_config_function(router, db_class, class_string)
get_data_dict = wrappers.get_node_data_dict_function(router, db_class, class_string)
get_spec_aliases = wrappers.get_node_spec_aliases_function(router, db_class, class_string)
update_collections = wrappers.update_node_collections_function(
    router,
    response_model_class,
    db_class,
    class_string,
)
update_child_config = wrappers.update_node_child_config_function(
    router,
    response_model_class,
    db_class,
    class_string,
)
update_data_dict = wrappers.update_node_data_dict_function(
    router,
    response_model_class,
    db_class,
    class_string,
)
update_spec_aliases = wrappers.update_node_spec_aliases_function(
    router,
    response_model_class,
    db_class,
    class_string,
)
accept = wrappers.get_node_accept_function(router, response_model_class, db_class, class_string)
reject = wrappers.get_node_reject_function(router, response_model_class, db_class, class_string)
reset = wrappers.get_node_reset_function(router, response_model_class, db_class, class_string)
process = wrappers.get_node_process_function(router, response_model_class, db_class, class_string)
run_check = wrappers.get_node_run_check_function(router, response_model_class, db_class, class_string)


@router.put(
    "/set_status/{row_id}/",
    response_model=response_model_class,
    summary=f"Set the status of a {class_string}",
)
async def update_row_status(
    row_id: int,
    status: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db_class:
    result = await db_class.update_row(session, row_id, status=StatusEnum(status))
    await session.commit()
    return result
