"""Unit tests for path normalization."""

from __future__ import annotations

from pathlib import Path

from dj_converter.paths import annotate_missing, from_serato_relative, to_serato_relative


def test_to_serato_relative_strips_root() -> None:
    """Expected: absolute POSIX path becomes drive-relative."""
    assert to_serato_relative("/Users/dj/Music/a.mp3") == "Users/dj/Music/a.mp3"


def test_from_serato_relative_with_music_root(tmp_path: Path) -> None:
    """Expected: filename under music_root resolves when absolute missing."""
    track = tmp_path / "track.mp3"
    track.write_bytes(b"x")
    resolved = from_serato_relative("Users/nobody/Music/track.mp3", str(tmp_path))
    assert Path(resolved) == track.resolve()


def test_annotate_missing_empty() -> None:
    """Failure: empty path is missing."""
    assert annotate_missing(None) is True
    assert annotate_missing("") is True
