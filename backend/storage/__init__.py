"""
Storage Layer - Persist and retrieve metrics

Implements the storage interface needed by analytics module.
Supports in-memory, SQLite persistent, and tiered hot/cold backends.
"""

from .interface import StorageBackend, get_metric_series, configure_storage, get_storage
from .memory_storage import InMemoryStorage

__all__ = [
    "StorageBackend",
    "get_metric_series",
    "configure_storage",
    "get_storage",
    "InMemoryStorage",
]

# Lazy imports for optional backends to avoid import errors
# when their dependencies haven't been resolved yet.
# Use: from backend.storage.sqlite_storage import SQLiteStorage
# Use: from backend.storage.tiered_storage import TieredStorageBackend
