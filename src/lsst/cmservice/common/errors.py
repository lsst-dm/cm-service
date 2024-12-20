"""cm-service specific error types"""

from typing import Any, TypeVar

from sqlalchemy.exc import IntegrityError

T = TypeVar("T")


class CMBashCheckError(KeyError):
    """Raised when bash checking fails"""


class CMBashSubmitError(RuntimeError):
    """Raised when bash submisison fails"""


class CMBadFullnameError(ValueError):
    """Raised when a fullname is badly formed"""


class CMBadStateTransitionError(ValueError):
    """Raised when requesting a bad transition states for a Node"""


class CMBadExecutionMethodError(RuntimeError):
    """Raised when requesting a bed execution method for a Node"""


class CMBadParameterTypeError(TypeError):
    """Raised when a parameter is of the wrong type"""


class CMBadHandlerTypeError(TypeError):
    """Raised when the specified handler type is not a valid type"""


class CMBadEnumError(ValueError):
    """Raised when an enum value isn't handled in a switch"""


class CMIDMismatchError(ValueError):
    """Raised when there is an ID mismatch between row IDs"""


class CMIntegrityError(IntegrityError):  # pylint: disable=too-many-ancestors
    """Raise when catching a sqlalchemy.exc.IntegrityError"""


class CMMissingNodeUrlError(ValueError):
    """Raised when a URL needed by a Node does not exist"""


class CMMissingScriptInputError(KeyError):
    """Raised when a script is missing an input in needs"""


class CMMissingRowCreateInputError(KeyError):
    """Raised when command to create a row is missing an input"""


class CMMissingFullnameError(KeyError):
    """Raised when no row matches the requested fullname"""


class CMMissingIDError(KeyError):
    """Raised when no row matches the requested ID"""


class CMResolveCollectionsError(KeyError):
    """Raised when the collection name resolution fails"""


class CMSlurmSubmitError(RuntimeError):
    """Raised when slurm submisison fails"""


class CMSlurmCheckError(KeyError):
    """Raised when slurm checking fails"""


class CMHTCondorSubmitError(RuntimeError):
    """Raised when htcondor submission fails"""


class CMHTCondorCheckError(KeyError):
    """Raised when htcondor checking fails"""


class CMNoButlerError(RuntimeError):
    """Raised when no butler is present"""


class CMButlerCallError(RuntimeError):
    """Raised when a call to butler fails"""


class CMSpecficiationError(KeyError):
    """Raised when Specification calls out an non-existing fragement"""


class CMTooFewAcceptedJobsError(KeyError):
    """Raised when no jobs of the same name are accepted"""


class CMTooManyAcceptedJobsError(KeyError):
    """Raised when more that one job of the same name is accepted"""


class CMTooManyActiveScriptsError(KeyError):
    """Raised when more that one script of the same name is active"""


class CMYamlParseError(KeyError):
    """Raised when parsing a yaml file fails"""


def test_type_and_raise(object: Any, expected_type: type[T], var_name: str) -> T:
    if not isinstance(object, expected_type):
        raise CMBadParameterTypeError(f"{var_name} expected type {expected_type} got {type(object)}")
    return object
