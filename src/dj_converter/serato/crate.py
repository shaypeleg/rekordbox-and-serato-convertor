"""
Serato .crate binary format (TLV) reader and writer.

Format (Mixxx / reverse-engineered):
  [4-byte ASCII tag][4-byte big-endian length][payload]
  Nested records use tags starting with 'o'.
  Text uses UTF-16 big-endian for t*/p*/vrsn tags.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

CRATE_VERSION = "1.0/Serato ScratchLive Crate"
HIERARCHY_SEP = "%%"


class CrateError(Exception):
    """Raised when a crate file cannot be parsed or written."""


def _encode_tag(tag: str, payload: bytes) -> bytes:
    """Encode a single TLV record."""
    tag_bytes = tag.encode("ascii")
    if len(tag_bytes) != 4:
        raise CrateError(f"Tag must be 4 ASCII bytes, got {tag!r}")
    return tag_bytes + struct.pack(">I", len(payload)) + payload


def _encode_utf16(text: str) -> bytes:
    """Encode text as UTF-16 big-endian without BOM."""
    return text.encode("utf-16-be")


def _decode_utf16(data: bytes) -> str:
    """Decode UTF-16 big-endian text."""
    return data.decode("utf-16-be")


def parse_records(data: bytes, offset: int = 0, end: int | None = None) -> list[tuple[str, Any]]:
    """
    Parse concatenated TLV records from a byte buffer.

    Args:
        data: Full crate bytes
        offset: Start offset
        end: Exclusive end offset (defaults to len(data))

    Returns:
        List of (tag, value) where value is str, int, bytes, or nested list
    """
    if end is None:
        end = len(data)
    records: list[tuple[str, Any]] = []
    pos = offset
    while pos + 8 <= end:
        tag = data[pos : pos + 4].decode("ascii", errors="replace")
        length = struct.unpack(">I", data[pos + 4 : pos + 8])[0]
        pos += 8
        if pos + length > end:
            raise CrateError(f"Truncated record {tag!r} at {pos - 8}")
        payload = data[pos : pos + length]
        pos += length
        records.append((tag, _decode_payload(tag, payload)))
    return records


def _decode_payload(tag: str, payload: bytes) -> Any:
    """Decode payload based on tag prefix conventions."""
    if tag.startswith("o"):
        return parse_records(payload)
    if tag in ("vrsn",) or tag.startswith("t") or tag.startswith("p"):
        return _decode_utf16(payload)
    if tag.startswith("u"):
        if len(payload) >= 4:
            return struct.unpack(">I", payload[:4])[0]
        return payload
    if tag.startswith("s"):
        if len(payload) >= 4:
            return struct.unpack(">i", payload[:4])[0]
        return payload
    if tag.startswith("b"):
        return payload[0] if payload else 0
    return payload


def encode_records(records: list[tuple[str, Any]]) -> bytes:
    """Encode a list of (tag, value) records to crate bytes."""
    chunks: list[bytes] = []
    for tag, value in records:
        chunks.append(_encode_value(tag, value))
    return b"".join(chunks)


def _encode_value(tag: str, value: Any) -> bytes:
    """Encode one tagged value."""
    if tag.startswith("o"):
        if not isinstance(value, list):
            raise CrateError(f"Nested tag {tag!r} requires a list")
        return _encode_tag(tag, encode_records(value))
    if tag in ("vrsn",) or tag.startswith("t") or tag.startswith("p"):
        if not isinstance(value, str):
            raise CrateError(f"Text tag {tag!r} requires a str")
        return _encode_tag(tag, _encode_utf16(value))
    if tag.startswith("u"):
        return _encode_tag(tag, struct.pack(">I", int(value)))
    if tag.startswith("s"):
        return _encode_tag(tag, struct.pack(">i", int(value)))
    if tag.startswith("b"):
        return _encode_tag(tag, bytes([int(value) & 0xFF]))
    if isinstance(value, bytes):
        return _encode_tag(tag, value)
    raise CrateError(f"Unsupported value for tag {tag!r}: {type(value)}")


def read_crate_tracks(path: Path | str) -> list[str]:
    """
    Read relative track paths from a .crate file.

    Args:
        path: Path to .crate file

    Returns:
        List of drive-relative track paths (as stored in ptrk)
    """
    data = Path(path).read_bytes()
    records = parse_records(data)
    tracks: list[str] = []
    for tag, value in records:
        if tag == "otrk" and isinstance(value, list):
            for nested_tag, nested_val in value:
                if nested_tag == "ptrk" and isinstance(nested_val, str):
                    tracks.append(nested_val)
    return tracks


def build_crate_bytes(track_paths: list[str]) -> bytes:
    """
    Build a minimal valid .crate file from relative track paths.

    Args:
        track_paths: Drive-relative paths (no leading slash / drive letter root)

    Returns:
        Binary crate content
    """
    records: list[tuple[str, Any]] = [("vrsn", CRATE_VERSION)]
    # Column view metadata (minimal set Serato expects)
    for col in ("song", "artist", "bpm", "key", "length"):
        records.append(("ovct", [("tvcn", col), ("tvcw", "0")]))
    for rel in track_paths:
        records.append(("otrk", [("ptrk", rel)]))
    return encode_records(records)


def write_crate(path: Path | str, track_paths: list[str]) -> Path:
    """
    Write a .crate file.

    Args:
        path: Destination .crate path
        track_paths: Drive-relative track paths

    Returns:
        Written path
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(build_crate_bytes(track_paths))
    return dest


def hierarchy_from_filename(filename: str) -> list[str]:
    """
    Decode Serato crate hierarchy from filename.

    Example:
        'Groove and Funk%%70s Groove Disco.crate'
        -> ['Groove and Funk', '70s Groove Disco']
    """
    stem = Path(filename).stem
    if not stem:
        return []
    return stem.split(HIERARCHY_SEP)


def filename_from_hierarchy(path_parts: list[str]) -> str:
    """
    Encode playlist folder path as Serato crate filename.

    Args:
        path_parts: Nested names, e.g. ['Hip Hop RnB', 'Hip Hop July 2026']

    Returns:
        Filename including .crate suffix
    """
    if not path_parts:
        raise CrateError("Cannot build crate filename from empty path")
    safe: list[str] = []
    for part in path_parts:
        # Reason: /, \, and %% would break Serato flat Subcrates filenames
        cleaned = part.replace(HIERARCHY_SEP, "_").replace("/", "-").replace("\\", "-").strip()
        if cleaned:
            safe.append(cleaned)
    if not safe:
        raise CrateError("Cannot build crate filename from empty path")
    return HIERARCHY_SEP.join(safe) + ".crate"


def list_crates(serato_root: Path | str) -> list[dict[str, Any]]:
    """
    List crates under a Serato library root.

    Looks in Subcrates/ and Crates/ (legacy).

    Args:
        serato_root: Path to `_Serato_` folder

    Returns:
        List of dicts with keys: filename, path, hierarchy, track_count
    """
    root = Path(serato_root)
    dirs = [root / "Subcrates", root / "SubCrates", root / "Crates"]
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for crate_file in sorted(d.glob("*.crate")):
            key = crate_file.name.lower()
            if key in seen:
                continue
            seen.add(key)
            try:
                tracks = read_crate_tracks(crate_file)
            except CrateError:
                tracks = []
            results.append(
                {
                    "filename": crate_file.name,
                    "path": str(crate_file),
                    "hierarchy": hierarchy_from_filename(crate_file.name),
                    "track_count": len(tracks),
                    "tracks": tracks,
                }
            )
    return results


def subcrates_dir(serato_root: Path | str) -> Path:
    """Return the preferred Subcrates directory, creating it if needed."""
    root = Path(serato_root)
    for name in ("Subcrates", "SubCrates"):
        candidate = root / name
        if candidate.is_dir():
            return candidate
    dest = root / "Subcrates"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


"""
=== FILE FLOW DOCUMENTATION ===

Functionality: Parse and write Serato ScratchLive/DJ .crate binary files and
encode nested playlist folders via %% in filenames.

Flow:
1. Parse TLV records (tag + length + payload) from .crate bytes
2. Extract ptrk paths from otrk nested records
3. Build crate bytes from a list of relative paths
4. Map folder hierarchy to/from %%-separated filenames

Main Entry Point: read_crate_tracks, write_crate, list_crates, filename_from_hierarchy

Dependencies:
- struct: binary packing
- pathlib: filesystem paths

Example Usage:
  from dj_converter.serato.crate import write_crate, list_crates
  write_crate("/Music/_Serato_/Subcrates/Funk.crate", ["Music/track.mp3"])
"""
