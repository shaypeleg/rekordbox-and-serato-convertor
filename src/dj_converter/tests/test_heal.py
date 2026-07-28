"""Tests for missing-file heal scanner."""

from __future__ import annotations

from pathlib import Path

import pytest

from dj_converter.heal import HealError, heal_playlists, resolve_missing_path
from dj_converter.models import NodeKind, PlaylistNode, TrackRef


def test_heal_finds_moved_file(tmp_path: Path) -> None:
    """Expected: missing track rematched by filename under music root."""
    music = tmp_path / "Music"
    nested = music / "Library" / "Funk"
    nested.mkdir(parents=True)
    track = nested / "Groove Hit.mp3"
    track.write_bytes(b"ID3")

    pl = PlaylistNode(
        id="rb:1",
        name="Funk",
        kind=NodeKind.PLAYLIST,
        path=["Funk"],
        track_count=1,
        tracks=[
            TrackRef(
                path_absolute=str(tmp_path / "Old" / "Groove Hit.mp3"),
                title="Groove Hit",
                missing=True,
            )
        ],
    )
    healed, stats = heal_playlists([pl], str(music))
    assert stats.healed == 1
    assert stats.still_missing == 0
    assert healed[0].tracks is not None
    assert healed[0].tracks[0].path_absolute == str(track.resolve())
    assert healed[0].tracks[0].missing is False


def test_heal_requires_music_root() -> None:
    """Failure: healing without a music root raises."""
    pl = PlaylistNode(
        id="rb:1",
        name="X",
        kind=NodeKind.PLAYLIST,
        path=["X"],
        tracks=[TrackRef(path_absolute="/nope/a.mp3", missing=True)],
    )
    with pytest.raises(HealError):
        heal_playlists([pl], None)


def test_resolve_prefers_matching_parent() -> None:
    """Edge: when multiple files share a name, prefer shared folder names."""
    index = {
        "track.mp3": [
            "/Volumes/A/Downloads/track.mp3",
            "/Volumes/A/Music/HipHop/track.mp3",
        ]
    }
    found, ambiguous = resolve_missing_path(
        "/OldDrive/Music/HipHop/track.mp3",
        None,
        index,
    )
    assert found == "/Volumes/A/Music/HipHop/track.mp3"
    assert ambiguous is False
