"""cm-service specific error types"""


class BashSubmitError(KeyError):
    """Raised when bash submisison fails"""


class BadStateTransitionError(ValueError):
    """Raised when requesting a bad transition states for a Node"""


class BadExecutionMethodError(ValueError):
    """Raised when requesting a bed execution method for a Node"""


class MissingNodeUrlError(ValueError):
    """Raised when a URL needed by a Node does not exist"""


class MissingScriptInputError(KeyError):
    """Raised when a script is missing an input in needs"""


class ResolveCollectionsError(KeyError):
    """Raised when the collection name resolution fails"""


class SlurmSubmitError(KeyError):
    """Raised when slurm submisison fails"""


class YamlParseError(KeyError):
    """Raised when parsing a yaml file fails"""
