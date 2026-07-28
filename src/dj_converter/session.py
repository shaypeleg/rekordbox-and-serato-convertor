"""In-memory session state for connected libraries."""

from __future__ import annotations

from threading import Lock

from dj_converter.models import LibraryPaths

_lock = Lock()
_paths = LibraryPaths()


def get_paths() -> LibraryPaths:
    """Return a copy of current library paths."""
    with _lock:
        return _paths.model_copy()


def set_paths(paths: LibraryPaths) -> LibraryPaths:
    """Update connected library paths."""
    global _paths
    with _lock:
        _paths = paths.model_copy()
        return _paths.model_copy()


def clear_paths() -> None:
    """Reset connected paths."""
    global _paths
    with _lock:
        _paths = LibraryPaths()
