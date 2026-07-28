"""Path normalization between absolute paths and Serato drive-relative paths."""

from __future__ import annotations

from pathlib import Path


def default_music_roots() -> list[str]:
    """Likely music root directories on this machine."""
    home = Path.home()
    candidates = [home / "Music", home / "music", Path("/Volumes")]
    return [str(c) for c in candidates if c.exists()]


def to_serato_relative(absolute_path: str, music_root: str | None = None) -> str:
    """
    Convert an absolute filesystem path to a Serato-style relative path.

    Serato stores paths relative to the drive/volume root (no leading slash).

    Args:
        absolute_path: Absolute track path
        music_root: Optional hint (reserved for future remapping)

    Returns:
        Relative path with forward slashes
    """
    _ = music_root
    p = Path(absolute_path).expanduser()
    try:
        resolved = p.resolve()
    except OSError:
        resolved = p

    parts = resolved.parts
    if resolved.is_absolute() and parts and parts[0] == "/":
        rel = "/".join(parts[1:])
    else:
        rel = "/".join(parts[1:]) if len(parts) > 1 else str(resolved)
    return rel.replace("\\", "/")


def from_serato_relative(relative_path: str, music_root: str | None = None) -> str:
    """
    Resolve a Serato relative path to an absolute path.

    Args:
        relative_path: Path as stored in .crate
        music_root: Optional music directory to search when absolute path missing

    Returns:
        Absolute path string (may not exist)
    """
    rel = relative_path.replace("\\", "/").lstrip("/")
    abs_path = Path("/") / rel
    if abs_path.is_file():
        return str(abs_path.resolve())

    if music_root:
        mr = Path(music_root).expanduser()
        # Direct join if relative is under music folder name
        joined = mr / rel
        if joined.is_file():
            return str(joined.resolve())
        # Filename match inside music root
        name = Path(rel).name
        by_name = mr / name
        if by_name.is_file():
            return str(by_name.resolve())
        # If relative includes the music root tail (e.g. Users/x/Music/a.mp3)
        mr_abs = str(mr.resolve()).lstrip("/")
        if rel.startswith(mr_abs):
            candidate = Path("/") / rel
            return str(candidate)
        suffix = rel.split(mr.name + "/", 1)
        if len(suffix) == 2:
            candidate = mr / suffix[1]
            if candidate.is_file():
                return str(candidate.resolve())

    return str(abs_path)


def annotate_missing(absolute_path: str | None) -> bool:
    """Return True if path is missing or empty."""
    if not absolute_path:
        return True
    return not Path(absolute_path).expanduser().is_file()


"""
=== FILE FLOW DOCUMENTATION ===

Functionality: Convert between absolute filesystem paths and Serato
drive-relative crate paths; detect missing files.

Flow:
1. Strip volume root for Serato relative form
2. Rehydrate absolute path from relative + optional music root
3. Check file existence

Main Entry Point: to_serato_relative, from_serato_relative, annotate_missing
"""
