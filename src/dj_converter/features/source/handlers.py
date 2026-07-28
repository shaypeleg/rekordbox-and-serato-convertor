"""Source library tree handlers."""

from __future__ import annotations

from dj_converter.models import PlaylistNode, Side
from dj_converter.rekordbox.library import (
    RekordboxError,
    find_playlist_by_id,
    read_playlist_tree,
)
from dj_converter.serato.tree import build_serato_tree, find_serato_playlist
from dj_converter.session import get_paths


class SourceError(Exception):
    """Raised when source tree cannot be loaded."""


def get_source_tree(side: Side) -> list[PlaylistNode]:
    """
    Load playlist/crate tree for the given side.

    Args:
        side: rekordbox or serato

    Returns:
        Top-level nodes (without full track lists for folders)
    """
    paths = get_paths()
    if side == Side.REKORDBOX:
        if not paths.rekordbox_path:
            raise SourceError("Rekordbox library is not connected")
        try:
            return read_playlist_tree(paths.rekordbox_path)
        except RekordboxError as exc:
            raise SourceError(str(exc)) from exc
    if not paths.serato_path:
        raise SourceError("Serato library is not connected")
    return build_serato_tree(paths.serato_path, paths.music_root)


def get_playlist_detail(side: Side, playlist_id: str) -> PlaylistNode:
    """
    Return a single playlist node including tracks.

    Raises:
        SourceError: If not found
    """
    tree = get_source_tree(side)
    node = find_playlist_by_id(tree, playlist_id)
    if node is None:
        node = find_serato_playlist(tree, playlist_id)
    if node is None:
        raise SourceError(f"Playlist not found: {playlist_id}")
    return node


"""
=== FILE FLOW DOCUMENTATION ===

Functionality: Expose source playlist trees for API browsing.

Flow:
1. Read connected paths from session
2. Load Rekordbox or Serato tree
3. Resolve a playlist by id for detail view

Main Entry Point: get_source_tree, get_playlist_detail
"""
