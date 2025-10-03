"""LSST Namespace package, pkgutil-style"""

import pkgutil

__path__ = pkgutil.extend_path(__path__, __name__)
