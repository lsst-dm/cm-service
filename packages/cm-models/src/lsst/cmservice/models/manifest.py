import warnings

from .manifests import LibraryManifest as LibraryManifest
from .manifests.artifact import ArtifactManifest as ArtifactManifest
from .manifests.bps import BpsManifest as BpsManifest
from .manifests.butler import ButlerManifest as ButlerManifest
from .manifests.facility import FacilityManifest as FacilityManifest
from .manifests.lsst import LsstManifest as LsstManifest
from .manifests.steps import StepManifest as StepManifest
from .manifests.wms import WmsManifest as WmsManifest

warnings.warn(
    "lsst.cmservice.models.manifest is deprecated, use .model.manifests instead", DeprecationWarning
)
