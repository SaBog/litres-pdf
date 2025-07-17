# litres/config/__init__.py

from .logging import logger, setup_logging
from .settings import app_settings

__all__ = [
    'setup_logging',
    'logger',
    'app_settings'
]