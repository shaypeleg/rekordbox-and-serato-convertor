"""Conversion service: Rekordbox ↔ Serato playlist membership."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from dj_converter.heal import HealError, HealStats, heal_playlists
from dj_converter.models import (
    ConvertDirection,
    ConvertPlaylistPreview,
    ConvertRequest,
    ConvertResult,
    ConvertTrackPreview,
    HealSummary,
    NodeKind,
    PlaylistNode,
    TrackRef,
)
from dj_converter.paths import annotate_missing, from_serato_relative, to_serato_relative
from dj_converter.rekordbox.library import (
    collect_playlists,
    find_playlist_by_id,
    read_playlist_tree,
    write_rekordbox_xml,
)
from dj_converter.serato.crate import filename_from_hierarchy, subcrates_dir, write_crate
from dj_converter.serato.tree import build_serato_tree, find_serato_playlist
from dj_converter.session import get_paths


class ConvertError(Exception):
    """Raised when conversion cannot proceed."""


def _load_source_tree(direction: ConvertDirection) -> list[PlaylistNode]:
    paths = get_paths()
    if direction == ConvertDirection.REKORDBOX_TO_SERATO:
        if not paths.rekordbox_path:
            raise ConvertError("Rekordbox library is not connected")
        return read_playlist_tree(paths.rekordbox_path)
    if not paths.serato_path:
        raise ConvertError("Serato library is not connected")
    return build_serato_tree(paths.serato_path, paths.music_root)


def _resolve_selected(tree: list[PlaylistNode], playlist_ids: list[str]) -> list[PlaylistNode]:
    selected: list[PlaylistNode] = []
    for pid in playlist_ids:
        node = find_playlist_by_id(tree, pid) or find_serato_playlist(tree, pid)
        if node is None:
            raise ConvertError(f"Playlist not found: {pid}")
        if node.kind == NodeKind.FOLDER:
            selected.extend(collect_playlists(node))
        else:
            selected.append(node)
    seen: set[str] = set()
    unique: list[PlaylistNode] = []
    for pl in selected:
        if pl.id in seen:
            continue
        seen.add(pl.id)
        unique.append(pl)
    return unique


def _healed_path_set(
    before: list[PlaylistNode], after: list[PlaylistNode]
) -> set[str]:
    """Absolute paths that were missing before and exist after healing."""
    healed: set[str] = set()
    before_by_id = {p.id: p for p in before}
    for pl_after in after:
        pl_before = before_by_id.get(pl_after.id)
        if pl_before is None:
            continue
        before_tracks = pl_before.tracks or []
        after_tracks = pl_after.tracks or []
        for t_b, t_a in zip(before_tracks, after_tracks, strict=False):
            was_missing = annotate_missing(t_b.path_absolute) or t_b.missing
            now_ok = t_a.path_absolute and not annotate_missing(t_a.path_absolute)
            if was_missing and now_ok and t_a.path_absolute:
                healed.add(t_a.path_absolute)
    return healed


def preview_rekordbox_to_serato(
    playlists: list[PlaylistNode],
    music_root: str | None,
    healed_paths: set[str] | None = None,
) -> list[ConvertPlaylistPreview]:
    """Build previews for RB → Serato."""
    healed_paths = healed_paths or set()
    previews: list[ConvertPlaylistPreview] = []
    for pl in playlists:
        tracks_preview: list[ConvertTrackPreview] = []
        missing = 0
        healed_count = 0
        for t in pl.tracks or []:
            abs_path = t.path_absolute
            missing_flag = annotate_missing(abs_path)
            is_healed = bool(abs_path and abs_path in healed_paths and not missing_flag)
            if missing_flag:
                missing += 1
            if is_healed:
                healed_count += 1
            rel = to_serato_relative(abs_path, music_root) if abs_path else None
            tracks_preview.append(
                ConvertTrackPreview(
                    source_path=abs_path or "(missing)",
                    destination_path=rel,
                    missing=missing_flag,
                    healed=is_healed,
                )
            )
        dest_name = filename_from_hierarchy(pl.path or [pl.name])
        previews.append(
            ConvertPlaylistPreview(
                source_id=pl.id,
                source_name=pl.name,
                source_path=pl.path,
                destination_name=dest_name,
                track_count=len(tracks_preview),
                missing_count=missing,
                healed_count=healed_count,
                tracks=tracks_preview[:50],
            )
        )
    return previews


def preview_serato_to_rekordbox(
    playlists: list[PlaylistNode],
    healed_paths: set[str] | None = None,
) -> list[ConvertPlaylistPreview]:
    """Build previews for Serato → RB XML."""
    healed_paths = healed_paths or set()
    previews: list[ConvertPlaylistPreview] = []
    for pl in playlists:
        tracks_preview: list[ConvertTrackPreview] = []
        missing = 0
        healed_count = 0
        for t in pl.tracks or []:
            abs_path = t.path_absolute
            missing_flag = t.missing or annotate_missing(abs_path)
            is_healed = bool(abs_path and abs_path in healed_paths and not missing_flag)
            if missing_flag:
                missing += 1
            if is_healed:
                healed_count += 1
            tracks_preview.append(
                ConvertTrackPreview(
                    source_path=t.path_relative or abs_path or "(missing)",
                    destination_path=abs_path,
                    missing=missing_flag,
                    healed=is_healed,
                )
            )
        dest_name = "/".join(pl.path) if pl.path else pl.name
        previews.append(
            ConvertPlaylistPreview(
                source_id=pl.id,
                source_name=pl.name,
                source_path=pl.path,
                destination_name=f"{dest_name}.xml section",
                track_count=len(tracks_preview),
                missing_count=missing,
                healed_count=healed_count,
                tracks=tracks_preview[:50],
            )
        )
    return previews


def apply_rekordbox_to_serato(
    playlists: list[PlaylistNode],
    serato_path: str,
    music_root: str | None,
    healed_paths: set[str] | None = None,
) -> list[ConvertPlaylistPreview]:
    """Write .crate files into Serato Subcrates with backups."""
    sub = subcrates_dir(serato_path)
    backup_root = (
        Path(serato_path)
        / "Backups"
        / "dj-converter"
        / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    backup_root.mkdir(parents=True, exist_ok=True)

    previews = preview_rekordbox_to_serato(playlists, music_root, healed_paths)
    by_id = {p.source_id: p for p in previews}

    for pl in playlists:
        dest_name = filename_from_hierarchy(pl.path or [pl.name])
        dest = sub / dest_name
        if dest.exists():
            shutil.copy2(dest, backup_root / dest_name)

        rel_paths: list[str] = []
        for t in pl.tracks or []:
            if t.path_absolute and not annotate_missing(t.path_absolute):
                rel_paths.append(to_serato_relative(t.path_absolute, music_root))
            elif t.path_relative:
                rel_paths.append(t.path_relative)

        write_crate(dest, rel_paths)
        preview = by_id[pl.id]
        preview.written_path = str(dest)
        preview.backup_path = str(backup_root)
        preview.track_count = len(rel_paths)

    return previews


def apply_serato_to_rekordbox(
    playlists: list[PlaylistNode],
    output_xml_path: str,
    healed_paths: set[str] | None = None,
) -> list[ConvertPlaylistPreview]:
    """Write Rekordbox XML for Import Playlist."""
    dest = Path(output_xml_path).expanduser()
    if dest.exists():
        backup = dest.with_suffix(
            dest.suffix + f".bak-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        )
        shutil.copy2(dest, backup)
        backup_path = str(backup)
    else:
        backup_path = None

    for pl in playlists:
        enriched: list[TrackRef] = []
        for t in pl.tracks or []:
            abs_path = t.path_absolute
            if abs_path is None and t.path_relative:
                abs_path = from_serato_relative(t.path_relative)
            enriched.append(
                TrackRef(
                    path_absolute=abs_path,
                    path_relative=t.path_relative,
                    title=t.title or (Path(abs_path).stem if abs_path else None),
                    artist=t.artist,
                    missing=annotate_missing(abs_path),
                )
            )
        pl.tracks = enriched

    write_rekordbox_xml(dest, playlists)
    previews = preview_serato_to_rekordbox(playlists, healed_paths)
    for p in previews:
        p.written_path = str(dest.resolve())
        p.backup_path = backup_path
        p.destination_name = dest.name
    return previews


def _maybe_heal(
    playlists: list[PlaylistNode],
    heal_missing: bool,
    music_root: str | None,
) -> tuple[list[PlaylistNode], HealStats | None, set[str]]:
    """Optionally heal missing tracks; return playlists, stats, healed path set."""
    if not heal_missing:
        return playlists, None, set()
    try:
        healed, stats = heal_playlists(playlists, music_root)
    except HealError as exc:
        raise ConvertError(str(exc)) from exc
    healed_paths = _healed_path_set(playlists, healed)
    return healed, stats, healed_paths


def _heal_summary(stats: HealStats | None) -> HealSummary | None:
    if stats is None:
        return None
    return HealSummary(
        scanned_files=stats.scanned_files,
        attempted=stats.attempted,
        healed=stats.healed,
        still_missing=stats.still_missing,
        ambiguous=stats.ambiguous,
        scan_roots=stats.scan_roots,
    )


def _heal_message(stats: HealStats | None, base: str) -> str:
    if stats is None:
        return base
    heal_bits = (
        f"Heal scan: {stats.scanned_files} files indexed, "
        f"{stats.healed}/{stats.attempted} rematched"
    )
    if stats.still_missing:
        heal_bits += f", {stats.still_missing} still missing"
    if stats.ambiguous:
        heal_bits += f", {stats.ambiguous} ambiguous (best guess used)"
    return f"{heal_bits}. {base}"


def run_convert(request: ConvertRequest) -> ConvertResult:
    """
    Dry-run or apply a conversion.

    Args:
        request: ConvertRequest with direction and playlist ids

    Returns:
        ConvertResult with previews and optional written paths
    """
    paths = get_paths()
    tree = _load_source_tree(request.direction)
    playlists = _resolve_selected(tree, request.playlist_ids)
    if not playlists:
        raise ConvertError("No playlists selected")

    playlists, heal_stats, healed_paths = _maybe_heal(
        playlists, request.heal_missing, paths.music_root
    )
    heal_model = _heal_summary(heal_stats)

    if request.direction == ConvertDirection.REKORDBOX_TO_SERATO:
        if request.dry_run:
            previews = preview_rekordbox_to_serato(
                playlists, paths.music_root, healed_paths
            )
            return ConvertResult(
                direction=request.direction,
                dry_run=True,
                playlists=previews,
                heal=heal_model,
                message=_heal_message(
                    heal_stats,
                    "Dry run: no files written. Close Serato before applying.",
                ),
            )
        if not paths.serato_path:
            raise ConvertError("Serato library is not connected")
        previews = apply_rekordbox_to_serato(
            playlists, paths.serato_path, paths.music_root, healed_paths
        )
        return ConvertResult(
            direction=request.direction,
            dry_run=False,
            playlists=previews,
            heal=heal_model,
            message=_heal_message(
                heal_stats,
                "Crates written. Re-open Serato to see them in the library.",
            ),
        )

    if request.dry_run:
        previews = preview_serato_to_rekordbox(playlists, healed_paths)
        return ConvertResult(
            direction=request.direction,
            dry_run=True,
            playlists=previews,
            heal=heal_model,
            message=_heal_message(
                heal_stats,
                "Dry run: no XML written. Apply to create an importable Rekordbox XML.",
            ),
        )
    out = request.output_xml_path
    if not out:
        base = Path(paths.serato_path or Path.home() / "Music")
        out = str(Path(base).parent / "dj-converter-export.xml")
    previews = apply_serato_to_rekordbox(playlists, out, healed_paths)
    return ConvertResult(
        direction=request.direction,
        dry_run=False,
        playlists=previews,
        heal=heal_model,
        message=_heal_message(
            heal_stats,
            (
                f"XML written to {out}. In Rekordbox: File → Import → "
                "rekordbox xml, then Import Playlist."
            ),
        ),
    )


"""
=== FILE FLOW DOCUMENTATION ===

Functionality: Preview and apply bidirectional playlist/crate conversion,
optionally healing missing files via music-root filename scan.

Flow:
1. Load source tree from connected library
2. Resolve selected playlist ids
3. Optional heal scan rematches missing paths
4. Dry-run preview or write crates/XML with backups

Main Entry Point: run_convert
"""
