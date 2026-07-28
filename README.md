# DJ Playlist Converter

Local web app to convert **Rekordbox playlists ↔ Serato crates** by mapping track
file paths and folder hierarchy. Hot cues that already live in your audio files
are left alone and typically show up in both apps automatically.

## Requirements

- Python 3.11+
- Node.js 18+ (for the UI)
- Rekordbox and/or Serato installed on this machine
- Close **Serato** before writing crates

## Setup

```bash
cd "/path/to/DJ app converter"
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .

cd frontend && npm install && npm run build && cd ..
```

## Run

Terminal 1 — API (serves built UI from `frontend/dist` when present):

```bash
source venv/bin/activate
PYTHONPATH=src uvicorn dj_converter.main:app --reload --port 8000
```

Open http://127.0.0.1:8000

Dev UI with hot reload (optional):

```bash
# API as above, then:
cd frontend && npm run dev
```

Open http://127.0.0.1:5173 (proxies `/api` to the backend).

## Usage

1. **Connect** — paste or use detected paths for Rekordbox (`master.db` or XML)
   and Serato (`~/Music/_Serato_`).
2. **Browse** — pick a playlist or crate (folders convert all child playlists).
3. **Preview** — check path mappings and missing files.
4. **Apply**
   - Rekordbox → Serato: writes `.crate` files under `_Serato_/Subcrates/`
     (nested folders use `%%` in the filename). Re-open Serato.
   - Serato → Rekordbox: writes an XML file. In Rekordbox use
     **File → Import → rekordbox xml**, then import the playlist.

## Tests

```bash
source venv/bin/activate
PYTHONPATH=src pytest src/dj_converter -v
ruff check src
```

## Notes

- Audio files are never moved or copied — only playlist/crate membership.
- Existing destination crates are backed up under `_Serato_/Backups/dj-converter/`.
- Streaming-only tracks without local files will appear as missing.
- Writing directly into encrypted Rekordbox `master.db` is out of scope for v1.
