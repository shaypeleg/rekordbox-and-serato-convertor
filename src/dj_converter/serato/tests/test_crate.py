"""Unit tests for Serato .crate TLV format."""

from __future__ import annotations

from pathlib import Path

import pytest

from dj_converter.serato.crate import (
    CrateError,
    build_crate_bytes,
    filename_from_hierarchy,
    hierarchy_from_filename,
    list_crates,
    parse_records,
    read_crate_tracks,
    write_crate,
)


def test_roundtrip_crate_tracks(tmp_path: Path) -> None:
    """Expected: written paths are read back unchanged."""
    tracks = [
        "Music/Artist/Album/01 Song.mp3",
        "Downloads/Another Track.wav",
    ]
    crate_path = tmp_path / "Test Crate.crate"
    write_crate(crate_path, tracks)
    assert read_crate_tracks(crate_path) == tracks


def test_hierarchy_encoding() -> None:
    """Expected: folder path encodes with %% separator."""
    name = filename_from_hierarchy(["Groove and Funk", "70s Groove Disco"])
    assert name == "Groove and Funk%%70s Groove Disco.crate"
    assert hierarchy_from_filename(name) == ["Groove and Funk", "70s Groove Disco"]


def test_hierarchy_empty_raises() -> None:
    """Failure: empty path cannot become a crate name."""
    with pytest.raises(CrateError):
        filename_from_hierarchy([])


def test_parse_version_record() -> None:
    """Edge: crate starts with version string record."""
    data = build_crate_bytes([])
    records = parse_records(data)
    assert records[0][0] == "vrsn"
    assert "Serato" in records[0][1]


def test_list_crates_nested(tmp_path: Path) -> None:
    """Expected: Subcrates folder is scanned with hierarchy."""
    serato = tmp_path / "_Serato_"
    sub = serato / "Subcrates"
    sub.mkdir(parents=True)
    write_crate(sub / "Hip Hop%%July.crate", ["a.mp3", "b.mp3"])
    crates = list_crates(serato)
    assert len(crates) == 1
    assert crates[0]["hierarchy"] == ["Hip Hop", "July"]
    assert crates[0]["track_count"] == 2
