"""Storage providers."""

from app.storage.base import StorageProvider
from app.storage.local import LocalStorage

__all__ = ["LocalStorage", "StorageProvider"]
