# web/__init__.py

from .gui import MigrationGUI

# Expose GUI components
__all__ = ["MigrationGUI"]

# Log GUI initialization
import logging
logging.info("Web GUI components initialized")