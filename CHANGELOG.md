# Changelog

## 2026-07-28

- Add `start.sh` to launch the local app (venv + optional UI build + uvicorn).
- Connect paths: auto-detected values show as read-only with Change (remove redundant Use detected).
- Distill Convert preview: playlists collapse by default; open for filename-first track details (no dual full-path tables).
- Add Scan & heal for missing tracks: index music root by filename and rematch before convert.
- Increase UI type scale (18px body) across Connect / Select / Convert.
- Simplify UI to Connect / Select / Convert tabs with playlist multi-select.
- Redesign UI into a two-pane conversion workspace (cool booth palette, clearer task flow).
- Fix Rekordbox `master.db` open: pass the database *file* to pyrekordbox (not the folder), so playlist trees load from the live library.
- Initial project scaffold: FastAPI backend, React frontend, planning docs.
- Serato `.crate` TLV reader/writer with `%%` hierarchy encoding.
- Rekordbox XML playlist reader/writer; optional master.db playlist listing.
- Bidirectional convert API with dry-run, path checks, and crate backups.
- Local web UI for connect → browse → preview → convert.
