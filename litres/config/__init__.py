# litres/config/__init__.py

from .logging import setup_logging, logger
from .settings import app_settings

__all__ = [
    'setup_logging',
    'logger',
    'app_settings'
]