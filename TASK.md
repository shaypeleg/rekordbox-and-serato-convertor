# TASK.md

## Active

- [x] 2026-07-28 — Scaffold project (PLANNING, package, FastAPI, Vite React)
- [x] 2026-07-28 — Serato `.crate` TLV read/write + `%%` hierarchy + tests
- [x] 2026-07-28 — Rekordbox XML / optional master.db playlist tree + XML writer
- [x] 2026-07-28 — Path normalization, dry-run convert API, backups
- [x] 2026-07-28 — Connect / browse / preview / convert web UI
- [x] 2026-07-28 — README, CHANGELOG, pytest validation

## Discovered During Work

- [x] 2026-07-28 — Distill Convert preview: collapsed playlist rows by default; filename-first track list
- [x] 2026-07-28 — Connect: Change path instead of Use detected when auto-filled
- [x] 2026-07-28 — Add simple `start.sh` launcher
- [x] 2026-07-28 — Update project README for current UI and workflow
- Crate filenames must sanitize `/` — otherwise nested dirs break `list_crates` glob
- Serato → Rekordbox writes XML for import (safer than encrypted master.db writes)
