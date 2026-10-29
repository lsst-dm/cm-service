"""cm-service specific error types"""


class CMNoButlerError(RuntimeError):
    """Raised when no butler is present"""


class CMButlerCallError(RuntimeError):
    """Raised when a call to butler fails"""


class CMInvalidGroupingError(RuntimeError):
    """Raised when group splitting fails"""


class CMNoSuchManifestError(RuntimeError):
    """Raised when a Manifest cannot be found in the database."""
