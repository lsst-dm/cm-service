"""Model library describing the runtime data model of a Library Manifest for a
processing site or facility.
"""

from . import LibraryManifest, ManifestSpec


class FacilitySpec(ManifestSpec): ...


class FacilityManifest(LibraryManifest[FacilitySpec]): ...
