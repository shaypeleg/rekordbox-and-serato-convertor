"""Shared domain models for playlist trees and track references."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Side(StrEnum):
    """Library side for conversion."""

    REKORDBOX = "rekordbox"
    SERATO = "serato"


class NodeKind(StrEnum):
    """Tree node type."""

    FOLDER = "folder"
    PLAYLIST = "playlist"


class TrackRef(BaseModel):
    """Reference to a track file on disk."""

    path_absolute: str | None = None
    path_relative: str | None = None
    missing: bool = False
    title: str | None = None
    artist: str | None = None


class PlaylistNode(BaseModel):
    """Folder or playlist in a library tree."""

    id: str
    name: str
    kind: NodeKind
    path: list[str] = Field(default_factory=list)
    track_count: int = 0
    children: list[PlaylistNode] = Field(default_factory=list)
    tracks: list[TrackRef] | None = None


class LibraryPaths(BaseModel):
    """Connected library roots."""

    rekordbox_path: str | None = None
    rekordbox_kind: str | None = None  # "master.db" | "xml"
    serato_path: str | None = None
    music_root: str | None = None


class DetectedLibraries(BaseModel):
    """Auto-detected default library locations."""

    rekordbox_candidates: list[str] = Field(default_factory=list)
    serato_candidates: list[str] = Field(default_factory=list)
    music_root_candidates: list[str] = Field(default_factory=list)


class ConnectRequest(BaseModel):
    """Request to connect library paths."""

    rekordbox_path: str | None = None
    serato_path: str | None = None
    music_root: str | None = None


class ConvertDirection(StrEnum):
    """Conversion direction."""

    REKORDBOX_TO_SERATO = "rekordbox_to_serato"
    SERATO_TO_REKORDBOX = "serato_to_rekordbox"


class ConvertRequest(BaseModel):
    """Dry-run or apply conversion for selected playlists."""

    direction: ConvertDirection
    playlist_ids: list[str]
    dry_run: bool = True
    output_xml_path: str | None = None
    heal_missing: bool = False


class ConvertTrackPreview(BaseModel):
    """Single track mapping in a conversion preview."""

    source_path: str
    destination_path: str | None = None
    missing: bool = False
    healed: bool = False


class ConvertPlaylistPreview(BaseModel):
    """Preview for one playlist/crate conversion."""

    source_id: str
    source_name: str
    source_path: list[str]
    destination_name: str
    track_count: int
    missing_count: int
    healed_count: int = 0
    tracks: list[ConvertTrackPreview] = Field(default_factory=list)
    backup_path: str | None = None
    written_path: str | None = None


class HealSummary(BaseModel):
    """Aggregate heal-scan statistics."""

    scanned_files: int = 0
    attempted: int = 0
    healed: int = 0
    still_missing: int = 0
    ambiguous: int = 0
    scan_roots: list[str] = Field(default_factory=list)


class ConvertResult(BaseModel):
    """Result of dry-run or apply."""

    direction: ConvertDirection
    dry_run: bool
    playlists: list[ConvertPlaylistPreview]
    message: str = ""
    heal: HealSummary | None = None


PlaylistNode.model_rebuild()
