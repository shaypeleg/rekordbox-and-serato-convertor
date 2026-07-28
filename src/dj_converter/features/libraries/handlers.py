"""Library detection and connection handlers."""

from __future__ import annotations

from pathlib import Path

from dj_converter.models import (
    ConnectRequest,
    DetectedLibraries,
    LibraryPaths,
)
from dj_converter.paths import default_music_roots
from dj_converter.rekordbox.library import (
    default_rekordbox_candidates,
    detect_rekordbox_kind,
)
from dj_converter.session import get_paths, set_paths


def default_serato_candidates() -> list[str]:
    """Return likely `_Serato_` folder locations."""
    home = Path.home()
    candidates = [
        home / "Music" / "_Serato_",
        home / "Documents" / "_Serato_",
    ]
    # External volumes
    volumes = Path("/Volumes")
    if volumes.is_dir():
        for vol in volumes.iterdir():
            candidates.append(vol / "_Serato_")
            candidates.append(vol / "Music" / "_Serato_")
    return [str(c) for c in candidates if c.is_dir()]


def detect_libraries() -> DetectedLibraries:
    """Auto-detect Rekordbox and Serato library locations."""
    return DetectedLibraries(
        rekordbox_candidates=default_rekordbox_candidates(),
        serato_candidates=default_serato_candidates(),
        music_root_candidates=default_music_roots(),
    )


def connect_libraries(request: ConnectRequest) -> LibraryPaths:
    """
    Validate and store library paths.

    Raises:
        ValueError: If a provided path is invalid
    """
    current = get_paths()
    rb_path = request.rekordbox_path or current.rekordbox_path
    sr_path = request.serato_path or current.serato_path
    music_root = request.music_root or current.music_root

    rb_kind = None
    if rb_path:
        p = Path(rb_path).expanduser()
        if not p.exists():
            raise ValueError(f"Rekordbox path does not exist: {rb_path}")
        rb_kind = detect_rekordbox_kind(p)
        rb_path = str(p.resolve())

    if sr_path:
        p = Path(sr_path).expanduser()
        if not p.is_dir():
            raise ValueError(f"Serato path is not a directory: {sr_path}")
        sr_path = str(p.resolve())

    if music_root:
        p = Path(music_root).expanduser()
        if not p.exists():
            raise ValueError(f"Music root does not exist: {music_root}")
        music_root = str(p.resolve())

    return set_paths(
        LibraryPaths(
            rekordbox_path=rb_path,
            rekordbox_kind=rb_kind,
            serato_path=sr_path,
            music_root=music_root,
        )
    )


"""
=== FILE FLOW DOCUMENTATION ===

Functionality: Detect default DJ library locations and validate connections.

Flow:
1. Probe common macOS paths for master.db and _Serato_
2. Validate user-provided paths
3. Store in session

Main Entry Point: detect_libraries, connect_libraries

Dependencies:
- dj_converter.rekordbox.library
- dj_converter.session
"""
