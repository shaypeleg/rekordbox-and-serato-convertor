"""
Heal missing playlist track paths by scanning a music root for matching filenames.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from dj_converter.models import PlaylistNode, TrackRef

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".aiff",
    ".aif",
    ".flac",
    ".m4a",
    ".aac",
    ".ogg",
    ".alac",
    ".wma",
}


@dataclass
class HealStats:
    """Summary of a heal pass."""

    scanned_files: int = 0
    attempted: int = 0
    healed: int = 0
    still_missing: int = 0
    ambiguous: int = 0
    scan_roots: list[str] = field(default_factory=list)


class HealError(Exception):
    """Raised when healing cannot run."""


def build_filename_index(roots: list[str | Path]) -> tuple[dict[str, list[str]], int]:
    """
    Walk music roots and index audio files by lowercase basename.

    Args:
        roots: Directories to scan

    Returns:
        (index, total_file_count)
    """
    index: dict[str, list[str]] = {}
    count = 0
    seen_roots: set[str] = set()

    for root in roots:
        path = Path(root).expanduser()
        if not path.exists():
            continue
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        if resolved in seen_roots:
            continue
        seen_roots.add(resolved)

        if path.is_file():
            _add_to_index(index, path)
            count += 1
            continue

        for file_path in path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            # Skip Serato / Pioneer analysis folders
            parts_lower = {p.lower() for p in file_path.parts}
            if "_serato_" in parts_lower or "pioneer" in parts_lower:
                continue
            _add_to_index(index, file_path)
            count += 1

    return index, count


def _add_to_index(index: dict[str, list[str]], file_path: Path) -> None:
    key = file_path.name.lower()
    try:
        abs_path = str(file_path.resolve())
    except OSError:
        abs_path = str(file_path)
    bucket = index.setdefault(key, [])
    if abs_path not in bucket:
        bucket.append(abs_path)


def _score_candidate(candidate: str, original: str | None) -> tuple[int, int, str]:
    """
    Score a candidate path against the original missing path.

    Higher is better. Tie-break with shorter path, then lexical order.
    """
    if not original:
        return (0, -len(candidate), candidate)

    cand = Path(candidate)
    orig = Path(original)
    score = 0
    if cand.name.lower() == orig.name.lower():
        score += 10
    # Shared parent folder names
    cand_parents = {p.lower() for p in cand.parts[:-1]}
    orig_parents = {p.lower() for p in orig.parts[:-1]}
    score += len(cand_parents & orig_parents)
    # Prefer same extension
    if cand.suffix.lower() == orig.suffix.lower():
        score += 2
    return (score, -len(candidate), candidate)


def resolve_missing_path(
    original: str | None,
    filename_hint: str | None,
    index: dict[str, list[str]],
) -> tuple[str | None, bool]:
    """
    Find a replacement absolute path for a missing track.

    Returns:
        (path_or_none, was_ambiguous)
    """
    name = None
    if original:
        name = Path(original).name
    elif filename_hint:
        name = Path(filename_hint).name
    if not name:
        return None, False

    candidates = index.get(name.lower(), [])
    if not candidates:
        # Try stem match across index (rare; only exact basename failed)
        stem = Path(name).stem.lower()
        stem_hits: list[str] = []
        for key, paths in index.items():
            if Path(key).stem == stem:
                stem_hits.extend(paths)
        candidates = stem_hits

    if not candidates:
        return None, False
    if len(candidates) == 1:
        return candidates[0], False

    ranked = sorted(candidates, key=lambda c: _score_candidate(c, original), reverse=True)
    best = ranked[0]
    second = ranked[1]
    # Ambiguous if top two scores equal
    ambiguous = _score_candidate(best, original)[0] == _score_candidate(second, original)[0]
    return best, ambiguous


def heal_playlists(
    playlists: list[PlaylistNode],
    music_root: str | None,
    extra_roots: list[str] | None = None,
) -> tuple[list[PlaylistNode], HealStats]:
    """
    Rematch missing track paths under music_root (and optional extra roots).

    Mutates track refs on copies of the playlist nodes.

    Args:
        playlists: Selected playlist nodes with tracks
        music_root: Primary scan root (required for healing)
        extra_roots: Additional directories to include in the index

    Returns:
        (healed_playlists, stats)
    """
    roots: list[str] = []
    if music_root:
        roots.append(music_root)
    if extra_roots:
        roots.extend(extra_roots)
    if not roots:
        raise HealError(
            "Set a Music root on the Connect tab before scanning to heal missing files."
        )

    index, scanned = build_filename_index(roots)
    stats = HealStats(scanned_files=scanned, scan_roots=[str(Path(r).expanduser()) for r in roots])

    healed_playlists: list[PlaylistNode] = []
    for pl in playlists:
        new_tracks: list[TrackRef] = []
        for t in pl.tracks or []:
            abs_path = t.path_absolute
            is_missing = not abs_path or not Path(abs_path).expanduser().is_file()
            if not is_missing:
                new_tracks.append(t.model_copy())
                continue

            stats.attempted += 1
            hint = t.path_relative or t.title
            found, ambiguous = resolve_missing_path(abs_path, hint, index)
            if found and Path(found).is_file():
                stats.healed += 1
                if ambiguous:
                    stats.ambiguous += 1
                new_tracks.append(
                    TrackRef(
                        path_absolute=found,
                        path_relative=t.path_relative,
                        title=t.title or Path(found).stem,
                        artist=t.artist,
                        missing=False,
                    )
                )
            else:
                stats.still_missing += 1
                new_tracks.append(t.model_copy(update={"missing": True}))

        healed_playlists.append(
            pl.model_copy(
                update={
                    "tracks": new_tracks,
                    "track_count": len(new_tracks),
                }
            )
        )

    logger.info(
        "Heal scan: scanned=%s attempted=%s healed=%s still_missing=%s ambiguous=%s",
        stats.scanned_files,
        stats.attempted,
        stats.healed,
        stats.still_missing,
        stats.ambiguous,
    )
    return healed_playlists, stats


"""
=== FILE FLOW DOCUMENTATION ===

Functionality: Scan music folders and rematch missing playlist tracks by filename.

Flow:
1. Index audio files under music_root by basename
2. For each missing track, find best filename match
3. Prefer candidates sharing parent folder names with the original path
4. Return updated playlists and heal statistics

Main Entry Point: heal_playlists

Dependencies:
- pathlib
- dj_converter.models.TrackRef / PlaylistNode
"""
