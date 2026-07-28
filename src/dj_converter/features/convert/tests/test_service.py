"""Integration tests for conversion service."""

from __future__ import annotations

from pathlib import Path

from dj_converter.features.convert.service import run_convert
from dj_converter.models import (
    ConvertDirection,
    ConvertRequest,
    LibraryPaths,
    NodeKind,
    PlaylistNode,
    TrackRef,
)
from dj_converter.rekordbox.library import write_rekordbox_xml
from dj_converter.serato.crate import list_crates, read_crate_tracks, write_crate
from dj_converter.session import set_paths


def test_rekordbox_xml_to_serato_crate(tmp_path: Path) -> None:
    """Expected: playlist becomes a %% crate with relative paths."""
    music = tmp_path / "Users" / "dj" / "Music"
    music.mkdir(parents=True)
    track = music / "funk.mp3"
    track.write_bytes(b"ID3")

    # Build XML via writer then convert
    pl = PlaylistNode(
        id="rb:funk",
        name="70s Disco",
        kind=NodeKind.PLAYLIST,
        path=["Groove and Funk", "70s Disco"],
        track_count=1,
        tracks=[TrackRef(path_absolute=str(track), title="funk", missing=False)],
    )
    xml_path = tmp_path / "rb.xml"
    write_rekordbox_xml(xml_path, [pl])

    serato = tmp_path / "_Serato_"
    serato.mkdir()
    set_paths(
        LibraryPaths(
            rekordbox_path=str(xml_path),
            rekordbox_kind="xml",
            serato_path=str(serato),
            music_root=str(music),
        )
    )

    # Need real id from parsed tree
    from dj_converter.rekordbox.library import read_playlist_tree_from_xml

    nodes = read_playlist_tree_from_xml(xml_path)
    # Writer puts playlist name as joined path under ROOT
    leaf = None

    def find_leaf(ns):
        nonlocal leaf
        for n in ns:
            if n.kind == NodeKind.PLAYLIST:
                leaf = n
                return
            find_leaf(n.children)

    find_leaf(nodes)
    assert leaf is not None

    result = run_convert(
        ConvertRequest(
            direction=ConvertDirection.REKORDBOX_TO_SERATO,
            playlist_ids=[leaf.id],
            dry_run=False,
        )
    )
    assert result.dry_run is False
    assert len(result.playlists) == 1
    crates = list_crates(serato)
    assert len(crates) == 1
    assert "Groove" in crates[0]["filename"] or "70s" in crates[0]["filename"]
    tracks = read_crate_tracks(crates[0]["path"])
    assert any("funk.mp3" in t for t in tracks)


def test_serato_to_rekordbox_xml(tmp_path: Path) -> None:
    """Expected: crate converts to importable XML."""
    music = tmp_path / "Users" / "dj" / "Music"
    music.mkdir(parents=True)
    track = music / "hip.mp3"
    track.write_bytes(b"ID3")

    serato = tmp_path / "_Serato_"
    sub = serato / "Subcrates"
    sub.mkdir(parents=True)
    # Path as Serato stores it (relative to volume root)
    write_crate(sub / "Hip Hop%%July.crate", ["Users/dj/Music/hip.mp3"])

    # Make from_serato_relative work: path /Users/dj/Music won't exist;
    # put a real file at tmp_path simulation — use music_root join fallback
    set_paths(
        LibraryPaths(
            serato_path=str(serato),
            music_root=str(music),
        )
    )

    from dj_converter.serato.tree import build_serato_tree

    tree = build_serato_tree(str(serato), str(music))
    leaf = None

    def find_leaf(ns):
        nonlocal leaf
        for n in ns:
            if n.kind == NodeKind.PLAYLIST:
                leaf = n
                return
            find_leaf(n.children)

    find_leaf(tree)
    assert leaf is not None

    out_xml = tmp_path / "export.xml"
    result = run_convert(
        ConvertRequest(
            direction=ConvertDirection.SERATO_TO_REKORDBOX,
            playlist_ids=[leaf.id],
            dry_run=False,
            output_xml_path=str(out_xml),
        )
    )
    assert out_xml.is_file()
    assert result.playlists[0].written_path is not None


def test_dry_run_does_not_write(tmp_path: Path) -> None:
    """Failure/edge: dry_run leaves Subcrates empty."""
    music = tmp_path / "Music"
    music.mkdir()
    track = music / "a.mp3"
    track.write_bytes(b"x")
    pl = PlaylistNode(
        id="rb:x",
        name="Solo",
        kind=NodeKind.PLAYLIST,
        path=["Solo"],
        track_count=1,
        tracks=[TrackRef(path_absolute=str(track), missing=False)],
    )
    xml_path = tmp_path / "rb.xml"
    write_rekordbox_xml(xml_path, [pl])
    serato = tmp_path / "_Serato_"
    serato.mkdir()
    set_paths(
        LibraryPaths(
            rekordbox_path=str(xml_path),
            rekordbox_kind="xml",
            serato_path=str(serato),
        )
    )
    from dj_converter.rekordbox.library import read_playlist_tree_from_xml

    nodes = read_playlist_tree_from_xml(xml_path)
    leaf = nodes[0] if nodes[0].kind == NodeKind.PLAYLIST else nodes[0].children[0]
    run_convert(
        ConvertRequest(
            direction=ConvertDirection.REKORDBOX_TO_SERATO,
            playlist_ids=[leaf.id],
            dry_run=True,
        )
    )
    assert list_crates(serato) == []
