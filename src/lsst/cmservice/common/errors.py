"""cm-service specific error types"""

from typing import Any

from sqlalchemy.exc import IntegrityError


class CMCheckError(KeyError):
    """Raised when script checking fails"""


class CMBashCheckError(CMCheckError):
    """Raised when bash checking fails"""


class CMHTCondorCheckError(CMCheckError):
    """Raised when htcondor checking fails"""


class CMSlurmCheckError(CMCheckError):
    """Raised when slurm checking fails"""


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


class CMIntegrityError(IntegrityError):
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


class CMSubmitError(RuntimeError):
    """Raised when a submission fails"""


class CMHTCondorSubmitError(CMSubmitError):
    """Raised when htcondor submission fails"""


class CMSlurmSubmitError(CMSubmitError):
    """Raised when slurm submission fails"""


class CMBashSubmitError(CMSubmitError):
    """Raised when bash submission fails"""


class CMNoButlerError(RuntimeError):
    """Raised when no butler is present"""


class CMButlerCallError(RuntimeError):
    """Raised when a call to butler fails"""


class CMSpecificationError(KeyError):
    """Raised when Specification calls out a non-existing fragment"""


class CMTooFewAcceptedJobsError(KeyError):
    """Raised when no jobs of the same name are accepted"""


class CMTooManyAcceptedJobsError(KeyError):
    """Raised when more that one job of the same name is accepted"""


class CMTooManyActiveScriptsError(KeyError):
    """Raised when more that one script of the same name is active"""


class CMYamlParseError(KeyError):
    """Raised when parsing a yaml file fails"""


class CMInvalidGroupingError(Exception):
    """Raised when group splitting fails"""


def test_type_and_raise[T](object: Any, expected_type: type[T], var_name: str) -> T:
    if not isinstance(object, expected_type):
        raise CMBadParameterTypeError(f"{var_name} expected type {expected_type} got {type(object)}")
    return object
