# migrations/__init__.py

from .sqlite_to_json import migrate_database

__all__ = ["migrate_database"]