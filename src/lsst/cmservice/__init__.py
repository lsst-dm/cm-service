"""LSST Namespace package, pkgutil-style"""
# This package, ``lsst.cmservice`` is a workspace root package and should not
# be used as an installation target. Instead, use one of the workspace members
# from ``packages/*`` instead.

import pkgutil

__path__ = pkgutil.extend_path(__path__, __name__)
__version__ = "0.5.0"
