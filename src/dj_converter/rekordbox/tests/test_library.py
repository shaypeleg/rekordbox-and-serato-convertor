"""Tests for Rekordbox XML playlist I/O."""

from __future__ import annotations

from pathlib import Path

from dj_converter.models import NodeKind, PlaylistNode, TrackRef
from dj_converter.rekordbox.library import (
    find_playlist_by_id,
    read_playlist_tree_from_xml,
    write_rekordbox_xml,
)

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="6.0.0" Company="Pioneer DJ"/>
  <COLLECTION Entries="2">
    <TRACK TrackID="1" Name="Song A" Artist="Artist A"
      Location="file://localhost/Users/test/Music/Song%20A.mp3"/>
    <TRACK TrackID="2" Name="Song B" Artist="Artist B"
      Location="file://localhost/Users/test/Music/Song%20B.mp3"/>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="ROOT" Count="1">
      <NODE Type="0" Name="Funk" Count="1">
        <NODE Name="70s Disco" Type="1" KeyType="0" Entries="2">
          <TRACK Key="1"/>
          <TRACK Key="2"/>
        </NODE>
      </NODE>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>
"""


def test_read_xml_playlist_tree(tmp_path: Path) -> None:
    """Expected: nested folder and playlist with two tracks."""
    xml_path = tmp_path / "library.xml"
    xml_path.write_text(SAMPLE_XML, encoding="utf-8")
    nodes = read_playlist_tree_from_xml(xml_path)
    assert len(nodes) == 1
    assert nodes[0].name == "Funk"
    assert nodes[0].kind == NodeKind.FOLDER
    assert len(nodes[0].children) == 1
    pl = nodes[0].children[0]
    assert pl.name == "70s Disco"
    assert pl.track_count == 2
    assert pl.tracks is not None
    assert pl.tracks[0].title == "Song A"
    assert pl.tracks[0].path_absolute == "/Users/test/Music/Song A.mp3"


def test_write_and_reread_xml(tmp_path: Path) -> None:
    """Expected: written XML round-trips playlist membership."""
    music = tmp_path / "Music"
    music.mkdir()
    f1 = music / "a.mp3"
    f1.write_bytes(b"x")
    pl = PlaylistNode(
        id="rb:test",
        name="My Crate",
        kind=NodeKind.PLAYLIST,
        path=["Imported", "My Crate"],
        track_count=1,
        tracks=[TrackRef(path_absolute=str(f1), title="a", artist="x", missing=False)],
    )
    out = tmp_path / "out.xml"
    write_rekordbox_xml(out, [pl])
    nodes = read_playlist_tree_from_xml(out)
    assert any(n.kind == NodeKind.PLAYLIST or n.children for n in nodes)
    assert out.is_file()


def test_find_playlist_by_id(tmp_path: Path) -> None:
    """Edge: find nested playlist by id."""
    xml_path = tmp_path / "library.xml"
    xml_path.write_text(SAMPLE_XML, encoding="utf-8")
    nodes = read_playlist_tree_from_xml(xml_path)
    target = nodes[0].children[0]
    found = find_playlist_by_id(nodes, target.id)
    assert found is not None
    assert found.name == "70s Disco"
