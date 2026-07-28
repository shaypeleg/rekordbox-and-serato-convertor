"""Build playlist trees from Serato crates."""

from __future__ import annotations

import hashlib

from dj_converter.models import NodeKind, PlaylistNode, TrackRef
from dj_converter.paths import annotate_missing, from_serato_relative
from dj_converter.serato.crate import list_crates


def build_serato_tree(serato_root: str, music_root: str | None = None) -> list[PlaylistNode]:
    """
    Build a nested folder/playlist tree from Serato %% crate filenames.

    Args:
        serato_root: Path to `_Serato_` directory
        music_root: Optional music root for resolving paths

    Returns:
        Top-level folder/playlist nodes
    """
    crates = list_crates(serato_root)
    # Insert into nested dict tree
    root_children: dict[str, dict] = {}

    def ensure(path_parts: list[str]) -> dict:
        cursor = root_children
        for part in path_parts:
            if part not in cursor:
                cursor[part] = {"_children": {}, "_crate": None}
            cursor = cursor[part]["_children"] if part in cursor else cursor
        # Re-walk to return node dict
        node = root_children
        parent = None
        name = ""
        for part in path_parts:
            parent = node
            name = part
            if part not in node:
                node[part] = {"_children": {}, "_crate": None}
            node = node  # noqa: B018 — keep structure clear
            entry = parent[part]
            node = entry["_children"]
        return parent[name] if parent is not None else {}

    # Simpler approach: nest explicitly
    forest: dict[str, dict] = {}

    for crate in crates:
        hierarchy: list[str] = crate["hierarchy"]
        if not hierarchy:
            continue
        cursor = forest
        for i, part in enumerate(hierarchy):
            if part not in cursor:
                cursor[part] = {"_children": {}, "_meta": None}
            if i == len(hierarchy) - 1:
                cursor[part]["_meta"] = crate
            cursor = cursor[part]["_children"]

    def to_nodes(tree: dict, parent_path: list[str]) -> list[PlaylistNode]:
        nodes: list[PlaylistNode] = []
        for name, entry in sorted(tree.items()):
            current_path = [*parent_path, name]
            children_tree = entry.get("_children") or {}
            meta = entry.get("_meta")
            node_id = "sr:" + hashlib.sha1("/".join(current_path).encode()).hexdigest()[:16]

            child_nodes = to_nodes(children_tree, current_path)
            if meta is not None and not child_nodes:
                tracks = [
                    TrackRef(
                        path_relative=rel,
                        path_absolute=from_serato_relative(rel, music_root),
                        missing=annotate_missing(from_serato_relative(rel, music_root)),
                    )
                    for rel in meta.get("tracks") or []
                ]
                nodes.append(
                    PlaylistNode(
                        id=node_id,
                        name=name,
                        kind=NodeKind.PLAYLIST,
                        path=current_path,
                        track_count=len(tracks),
                        tracks=tracks,
                    )
                )
            elif meta is not None and child_nodes:
                # Rare: same name as folder and crate — expose crate as playlist child
                tracks = [
                    TrackRef(
                        path_relative=rel,
                        path_absolute=from_serato_relative(rel, music_root),
                        missing=annotate_missing(from_serato_relative(rel, music_root)),
                    )
                    for rel in meta.get("tracks") or []
                ]
                pl_id = node_id + ":pl"
                child_nodes.insert(
                    0,
                    PlaylistNode(
                        id=pl_id,
                        name=name,
                        kind=NodeKind.PLAYLIST,
                        path=current_path,
                        track_count=len(tracks),
                        tracks=tracks,
                    ),
                )
                nodes.append(
                    PlaylistNode(
                        id=node_id,
                        name=name,
                        kind=NodeKind.FOLDER,
                        path=current_path,
                        track_count=sum(c.track_count for c in child_nodes),
                        children=child_nodes,
                    )
                )
            else:
                nodes.append(
                    PlaylistNode(
                        id=node_id,
                        name=name,
                        kind=NodeKind.FOLDER,
                        path=current_path,
                        track_count=sum(c.track_count for c in child_nodes),
                        children=child_nodes,
                    )
                )
        return nodes

    return to_nodes(forest, [])


def find_serato_playlist(nodes: list[PlaylistNode], playlist_id: str) -> PlaylistNode | None:
    """Find a node by id in Serato tree."""
    for node in nodes:
        if node.id == playlist_id:
            return node
        found = find_serato_playlist(node.children, playlist_id)
        if found is not None:
            return found
    return None


"""
=== FILE FLOW DOCUMENTATION ===

Functionality: Convert flat Serato crate list with %% names into a nested
PlaylistNode tree for the UI.

Flow:
1. list_crates under _Serato_
2. Nest by hierarchy segments
3. Resolve relative paths to absolute and flag missing files

Main Entry Point: build_serato_tree

Dependencies:
- dj_converter.serato.crate
- dj_converter.paths

Example Usage:
  from dj_converter.serato.tree import build_serato_tree
  tree = build_serato_tree("~/Music/_Serato_")
"""
