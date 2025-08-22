"""Provide a common application root logger."""

import structlog
from safir.logging import configure_logging

from ..config import config

configure_logging(profile=config.logging.profile, log_level=config.logging.level, name=config.logging.handle)

LOGGER = structlog.get_logger(config.logging.handle)
