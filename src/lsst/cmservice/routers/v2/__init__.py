from fastapi import APIRouter

from . import (
    campaigns,
    manifests,
)

router = APIRouter(
    prefix="/v2",
)

router.include_router(campaigns.router)
router.include_router(manifests.router)
