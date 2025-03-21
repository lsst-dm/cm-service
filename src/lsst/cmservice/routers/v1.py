from fastapi import APIRouter

from . import (
    actions,
    campaigns,
    groups,
    jobs,
    loaders,
    pipetask_error_types,
    pipetask_errors,
    product_sets,
    queues,
    script_dependencies,
    script_errors,
    scripts,
    spec_blocks,
    specifications,
    step_dependencies,
    steps,
    task_sets,
    wms_task_reports,
)

router = APIRouter(
    prefix="/v1",
)

router.include_router(loaders.router)
router.include_router(actions.router)

router.include_router(campaigns.router)
router.include_router(steps.router)
router.include_router(groups.router)
router.include_router(jobs.router)
router.include_router(scripts.router)

router.include_router(specifications.router)
router.include_router(spec_blocks.router)

router.include_router(pipetask_error_types.router)
router.include_router(pipetask_errors.router)
router.include_router(script_errors.router)

router.include_router(task_sets.router)
router.include_router(product_sets.router)
router.include_router(wms_task_reports.router)

router.include_router(script_dependencies.router)
router.include_router(step_dependencies.router)
router.include_router(queues.router)
