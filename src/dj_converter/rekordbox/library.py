"""
Rekordbox playlist reading (XML / master.db) and XML writing for import.
"""

from __future__ import annotations

import hashlib
import logging
import urllib.parse
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from dj_converter.models import NodeKind, PlaylistNode, TrackRef

logger = logging.getLogger(__name__)


class RekordboxError(Exception):
    """Raised when Rekordbox library cannot be read or written."""


def _file_url_to_path(location: str) -> str:
    """Convert file:// URL (Rekordbox Location) to a filesystem path."""
    if location.startswith("file://localhost"):
        location = location.replace("file://localhost", "file://", 1)
    if location.startswith("file://"):
        parsed = urllib.parse.urlparse(location)
        path = urllib.parse.unquote(parsed.path)
        # Windows file:///C:/...
        if path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        return path
    return urllib.parse.unquote(location)


def _path_to_file_url(path: str) -> str:
    """Convert absolute path to Rekordbox-style file URL."""
    abs_path = Path(path).resolve()
    # file://localhost/Users/...
    return "file://localhost" + urllib.parse.quote(str(abs_path))


def detect_rekordbox_kind(path: Path | str) -> str:
    """
    Detect whether path is master.db, XML, or unsupported.

    Returns:
        'master.db' | 'xml'
    """
    p = Path(path)
    name = p.name.lower()
    if name == "master.db" or name.endswith(".db"):
        return "master.db"
    if name.endswith(".xml"):
        return "xml"
    raise RekordboxError(f"Unrecognized Rekordbox library path: {path}")


def default_rekordbox_candidates() -> list[str]:
    """Return likely Rekordbox library locations on this machine."""
    home = Path.home()
    candidates = [
        home / "Library" / "Pioneer" / "rekordbox" / "master.db",
        home / "Library" / "Pioneer" / "rekordbox6" / "master.db",
        home / "Library" / "Pioneer" / "rekordbox7" / "master.db",
    ]
    return [str(c) for c in candidates if c.is_file()]


def read_playlist_tree_from_xml(xml_path: Path | str) -> list[PlaylistNode]:
    """
    Build playlist tree from a Rekordbox XML export.

    Args:
        xml_path: Path to DJ_PLAYLISTS XML file

    Returns:
        Top-level playlist/folder nodes
    """
    path = Path(xml_path)
    tree = ET.parse(path)
    root = tree.getroot()
    collection: dict[str, TrackRef] = {}
    coll = root.find("COLLECTION")
    if coll is not None:
        for track_el in coll.findall("TRACK"):
            track_id = track_el.get("TrackID") or ""
            location = track_el.get("Location") or ""
            abs_path = _file_url_to_path(location) if location else None
            collection[track_id] = TrackRef(
                path_absolute=abs_path,
                title=track_el.get("Name"),
                artist=track_el.get("Artist"),
                missing=bool(abs_path) and not Path(abs_path).is_file(),
            )

    playlists_el = root.find("PLAYLISTS")
    if playlists_el is None:
        return []

    def walk_node(node_el: ET.Element, parent_path: list[str]) -> PlaylistNode | None:
        name = node_el.get("Name") or "Untitled"
        # Skip root "ROOT" wrapper name sometimes used
        node_type = node_el.get("Type")
        # Type 0 = folder, Type 1 = playlist (Pioneer XML)
        kind = NodeKind.FOLDER if node_type == "0" else NodeKind.PLAYLIST
        current_path = parent_path if name == "ROOT" and not parent_path else [*parent_path, name]
        if name == "ROOT" and not parent_path:
            current_path = []

        children_nodes: list[PlaylistNode] = []
        tracks: list[TrackRef] = []

        for child in list(node_el):
            if child.tag == "NODE":
                child_node = walk_node(child, current_path if current_path else parent_path)
                if child_node is not None:
                    children_nodes.append(child_node)
            elif child.tag == "TRACK":
                key = child.get("Key") or ""
                ref = collection.get(key)
                if ref is None:
                    tracks.append(TrackRef(path_absolute=None, missing=True))
                else:
                    tracks.append(ref.model_copy())

        display_name = name if name != "ROOT" else "Playlists"
        node_id_src = "/".join(current_path) if current_path else display_name
        node_id = "rb:" + hashlib.sha1(node_id_src.encode()).hexdigest()[:16]

        if name == "ROOT" and not parent_path:
            return PlaylistNode(
                id=node_id,
                name=display_name,
                kind=NodeKind.FOLDER,
                path=[],
                track_count=sum(c.track_count for c in children_nodes),
                children=children_nodes,
            )

        if kind == NodeKind.PLAYLIST:
            return PlaylistNode(
                id=node_id,
                name=name,
                kind=NodeKind.PLAYLIST,
                path=current_path,
                track_count=len(tracks),
                tracks=tracks,
                children=[],
            )

        return PlaylistNode(
            id=node_id,
            name=name,
            kind=NodeKind.FOLDER,
            path=current_path,
            track_count=sum(c.track_count for c in children_nodes),
            children=children_nodes,
        )

    top = playlists_el.find("NODE")
    if top is None:
        return []
    root_node = walk_node(top, [])
    if root_node is None:
        return []
    # Return children of ROOT for a cleaner tree
    if root_node.name in ("ROOT", "Playlists") and root_node.children:
        return root_node.children
    return [root_node]


def read_playlist_tree_from_db(db_path: Path | str) -> list[PlaylistNode]:
    """
    Read playlist tree from encrypted Rekordbox master.db via pyrekordbox.

    Args:
        db_path: Path to master.db

    Returns:
        Top-level playlist/folder nodes

    Raises:
        RekordboxError: If database cannot be opened
    """
    try:
        from pyrekordbox import Rekordbox6Database
    except ImportError as exc:
        raise RekordboxError("pyrekordbox is required to read master.db") from exc

    path = Path(db_path).expanduser().resolve()
    if path.is_dir():
        candidate = path / "master.db"
        if not candidate.is_file():
            raise RekordboxError(f"No master.db found in directory: {path}")
        path = candidate
    if not path.is_file():
        raise RekordboxError(f"Rekordbox database file not found: {path}")

    # Reason: pyrekordbox `path` must be the master.db *file*; passing the
    # directory makes db_dir resolve to Pioneer/ and fails to open the DB.
    try:
        db = Rekordbox6Database(path=str(path))
    except Exception as exc:  # noqa: BLE001 — surface decrypt/path errors
        raise RekordboxError(
            f"Could not open Rekordbox database at {path}: {exc}. "
            "Close Rekordbox completely (including rekordboxAgent) and retry, "
            "or connect an exported XML file instead."
        ) from exc

    try:
        return _tree_from_pyrekordbox_db(db)
    finally:
        try:
            db.close()
        except Exception:  # noqa: BLE001
            pass


def _is_root_parent(parent_id: Any) -> bool:
    """Return True if ParentID denotes a top-level playlist/folder."""
    if parent_id is None:
        return True
    return str(parent_id).lower() in {"root", "0", ""}


def _tree_from_pyrekordbox_db(db: Any) -> list[PlaylistNode]:
    """Build PlaylistNode tree from an open Rekordbox6Database."""
    content_by_id: dict[Any, TrackRef] = {}
    try:
        for content in db.get_content():
            folder_path = getattr(content, "FolderPath", None) or getattr(
                content, "file_path", None
            )
            abs_path = str(folder_path) if folder_path else None
            cid = getattr(content, "ID", None)
            content_by_id[cid] = TrackRef(
                path_absolute=abs_path,
                title=getattr(content, "Title", None) or getattr(content, "title", None),
                artist=getattr(content, "ArtistName", None)
                or getattr(getattr(content, "Artist", None), "Name", None),
                missing=bool(abs_path) and not Path(abs_path).is_file(),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load content from master.db: %s", exc)
        raise RekordboxError(f"Failed to read tracks from master.db: {exc}") from exc

    playlists = list(db.get_playlist())
    nodes_by_id: dict[Any, dict[str, Any]] = {}
    for pl in playlists:
        pid = str(getattr(pl, "ID", ""))
        attr = getattr(pl, "Attribute", 0)
        # Attribute -128 = cloud/trial sync placeholders; skip
        if attr == -128:
            continue
        parent_raw = getattr(pl, "ParentID", None)
        parent_id = None if _is_root_parent(parent_raw) else str(parent_raw)
        nodes_by_id[pid] = {
            "obj": pl,
            "name": getattr(pl, "Name", None) or "Untitled",
            "parent_id": parent_id,
            "is_folder": attr == 1,
            "seq": getattr(pl, "Seq", 0) or 0,
        }

    def tracks_for_playlist(pl_obj: Any) -> list[TrackRef]:
        tracks: list[TrackRef] = []
        try:
            songs = list(db.get_playlist_songs(PlaylistID=getattr(pl_obj, "ID", None)))
        except Exception:  # noqa: BLE001
            songs = []
        for song in songs:
            cid = getattr(song, "ContentID", None) or getattr(song, "content_id", None)
            if cid in content_by_id:
                tracks.append(content_by_id[cid].model_copy())
            else:
                tracks.append(TrackRef(missing=True))
        return tracks

    def build(pid: Any, parent_path: list[str]) -> PlaylistNode:
        meta = nodes_by_id[pid]
        name = meta["name"]
        current_path = [*parent_path, name]
        child_ids = [
            cid for cid, m in nodes_by_id.items() if m["parent_id"] == pid and cid != pid
        ]
        child_ids.sort(key=lambda c: nodes_by_id[c]["seq"])

        is_folder = meta["is_folder"] or bool(child_ids)
        pl_tracks: list[TrackRef] = []
        if not is_folder:
            pl_tracks = tracks_for_playlist(meta["obj"])

        node_id = "rb:" + hashlib.sha1("/".join(current_path).encode()).hexdigest()[:16]
        if is_folder:
            children = [build(cid, current_path) for cid in child_ids]
            return PlaylistNode(
                id=node_id,
                name=name,
                kind=NodeKind.FOLDER,
                path=current_path,
                track_count=sum(c.track_count for c in children),
                children=children,
            )
        return PlaylistNode(
            id=node_id,
            name=name,
            kind=NodeKind.PLAYLIST,
            path=current_path,
            track_count=len(pl_tracks),
            tracks=pl_tracks,
        )

    root_ids = [
        pid
        for pid, meta in nodes_by_id.items()
        if meta["parent_id"] is None or meta["parent_id"] not in nodes_by_id
    ]
    root_ids.sort(key=lambda c: nodes_by_id[c]["seq"])
    return [build(pid, []) for pid in root_ids]


def read_playlist_tree(path: Path | str) -> list[PlaylistNode]:
    """
    Read playlist tree from XML or master.db.

    Args:
        path: Library path

    Returns:
        Top-level nodes
    """
    kind = detect_rekordbox_kind(path)
    if kind == "xml":
        return read_playlist_tree_from_xml(path)
    return read_playlist_tree_from_db(path)


def find_playlist_by_id(nodes: list[PlaylistNode], playlist_id: str) -> PlaylistNode | None:
    """Depth-first search for a playlist/folder by id."""
    for node in nodes:
        if node.id == playlist_id:
            return node
        found = find_playlist_by_id(node.children, playlist_id)
        if found is not None:
            return found
    return None


def collect_playlists(node: PlaylistNode) -> list[PlaylistNode]:
    """Collect all playlist leaves under a node (inclusive if playlist)."""
    if node.kind == NodeKind.PLAYLIST:
        return [node]
    result: list[PlaylistNode] = []
    for child in node.children:
        result.extend(collect_playlists(child))
    return result


def write_rekordbox_xml(
    output_path: Path | str,
    playlists: list[PlaylistNode],
    product_name: str = "DJ Playlist Converter",
) -> Path:
    """
    Write a Rekordbox-importable XML file containing the given playlists.

    Args:
        output_path: Destination .xml path
        playlists: Playlist nodes (must include tracks)
        product_name: PRODUCT Name attribute

    Returns:
        Written path
    """
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Collect unique tracks
    track_ids: dict[str, int] = {}
    track_list: list[TrackRef] = []
    next_id = 1

    def ensure_track(ref: TrackRef) -> int:
        nonlocal next_id
        key = ref.path_absolute or ref.path_relative or f"missing-{next_id}"
        if key not in track_ids:
            track_ids[key] = next_id
            track_list.append(ref)
            next_id += 1
        return track_ids[key]

    for pl in playlists:
        for t in pl.tracks or []:
            ensure_track(t)

    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
    ET.SubElement(root, "PRODUCT", Name=product_name, Version="0.1.0", Company="local")
    coll = ET.SubElement(root, "COLLECTION", Entries=str(len(track_list)))
    for ref in track_list:
        key = ref.path_absolute or ref.path_relative or f"missing-{id(ref)}"
        tid = track_ids[key]
        loc = _path_to_file_url(ref.path_absolute) if ref.path_absolute else ""
        ET.SubElement(
            coll,
            "TRACK",
            TrackID=str(tid),
            Name=ref.title or Path(ref.path_absolute or "Unknown").stem,
            Artist=ref.artist or "",
            Location=loc,
        )

    playlists_el = ET.SubElement(root, "PLAYLISTS")
    root_node = ET.SubElement(
        playlists_el,
        "NODE",
        Type="0",
        Name="ROOT",
        Count="0",
    )

    # Build nested folder nodes so hierarchy survives XML round-trip
    folder_index: dict[tuple[str, ...], ET.Element] = {(): root_node}

    def ensure_folder(parts: list[str]) -> ET.Element:
        key = tuple(parts)
        if key in folder_index:
            return folder_index[key]
        parent = ensure_folder(parts[:-1])
        folder_el = ET.SubElement(
            parent,
            "NODE",
            Type="0",
            Name=parts[-1],
            Count="0",
        )
        folder_index[key] = folder_el
        parent.set("Count", str(len(list(parent))))
        return folder_el

    for pl in playlists:
        tracks = pl.tracks or []
        path_parts = pl.path or [pl.name]
        folder_parts = path_parts[:-1]
        pl_name = path_parts[-1] if path_parts else pl.name
        parent_el = ensure_folder(folder_parts)
        pl_node = ET.SubElement(
            parent_el,
            "NODE",
            Name=pl_name,
            Type="1",
            KeyType="0",
            Entries=str(len(tracks)),
        )
        parent_el.set("Count", str(len(list(parent_el))))
        for ref in tracks:
            tid = ensure_track(ref)
            ET.SubElement(pl_node, "TRACK", Key=str(tid))

    root_node.set("Count", str(len(list(root_node))))

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(dest, encoding="UTF-8", xml_declaration=True)
    return dest


"""
=== FILE FLOW DOCUMENTATION ===

Functionality: Read Rekordbox playlist trees from XML or master.db and write
importable XML playlists.

Flow:
1. Detect library kind (xml vs master.db)
2. Parse collection + playlist hierarchy into PlaylistNode tree
3. Optionally write selected playlists to Rekordbox XML for import

Main Entry Point: read_playlist_tree, write_rekordbox_xml, find_playlist_by_id

Dependencies:
- pyrekordbox: optional master.db access
- xml.etree: XML parse/write

Example Usage:
  from dj_converter.rekordbox.library import read_playlist_tree
  nodes = read_playlist_tree("~/export.xml")
"""
