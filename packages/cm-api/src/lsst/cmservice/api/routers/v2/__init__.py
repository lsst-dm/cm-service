from fastapi import APIRouter

from . import (
    activity_log,
    campaigns,
    edges,
    manifests,
    nodes,
)

router = APIRouter(
    prefix="/v2",
)

router.include_router(activity_log.router)
router.include_router(campaigns.router)
router.include_router(edges.router)
router.include_router(manifests.router)
router.include_router(nodes.router)
