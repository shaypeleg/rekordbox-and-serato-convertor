# PLANNING.md — DJ Playlist Converter

## Goal

Local web app that converts **Rekordbox playlists ↔ Serato crates** by mapping
track file paths and folder hierarchy. Hot cues typically live in audio file
tags and transfer automatically when both apps point at the same files.

## Architecture

- **Backend:** Python FastAPI (`src/dj_converter/`) on localhost
- **Frontend:** Vite + React SPA in `frontend/`, served by FastAPI in production
- **Vertical slices:** `features/libraries`, `features/source`, `features/convert`
- **Format modules:** `serato/` (`.crate` TLV), `rekordbox/` (XML + optional master.db)

## Data model

Canonical playlist:

```
PlaylistNode { id, name, kind: folder|playlist, path[], children?, track_count, tracks? }
TrackRef { path_absolute?, path_relative?, missing: bool }
```

## Conversion rules

| Direction | Read | Write |
|-----------|------|-------|
| Rekordbox → Serato | `master.db` (preferred) or XML | `_Serato_/Subcrates/*.crate` with `%%` hierarchy |
| Serato → Rekordbox | `_Serato_/Subcrates/*.crate` | Rekordbox XML for manual Import Playlist |

## Safety

- Never move/copy audio files
- Backup destination crates before overwrite
- Prefer dry-run before apply
- Close Serato before writing crates; import XML in Rekordbox for reverse

## Out of scope (v1)

- Cue/beatgrid database rewriting
- Streaming-only tracks without local files
- Smart playlist rule translation
- Direct encrypted Rekordbox `master.db` writes
