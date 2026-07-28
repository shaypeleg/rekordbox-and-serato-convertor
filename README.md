# DJ Playlist Converter

Local web app to convert **Rekordbox playlists ↔ Serato crates** by mapping track
file paths and folder hierarchy. Audio files are never moved or copied. Hot cues
that already live in your audio tags are left alone and usually show up in both
apps when they point at the same files.

Repo: [github.com/shaypeleg/rekordbox-and-serato-convertor](https://github.com/shaypeleg/rekordbox-and-serato-convertor)

## What it does

| Direction | Reads | Writes |
|-----------|--------|--------|
| Rekordbox → Serato | `master.db` (preferred) or exported XML | `_Serato_/Subcrates/*.crate` (`%%` nested folders) |
| Serato → Rekordbox | `_Serato_/Subcrates/*.crate` | Rekordbox XML for **File → Import → rekordbox xml** |

Also:

- Auto-detects common Rekordbox / Serato / Music paths on this Mac
- Multi-select playlists (folders select everything inside)
- Dry-run preview before writing
- Backs up existing crates before overwrite
- **Heal** — rescan your Music root by filename when tracks show as missing

## Requirements

- macOS (paths and library locations are Mac-oriented)
- Python 3.11+
- Node.js 18+ (to build the UI once)
- Rekordbox and/or Serato on this machine
- Close **Serato** before applying crates

## Setup (once)

```bash
git clone https://github.com/shaypeleg/rekordbox-and-serato-convertor.git
cd rekordbox-and-serato-convertor

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .

cd frontend && npm install && npm run build && cd ..
```

## Run

```bash
./start.sh
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

- Custom port: `PORT=8080 ./start.sh`
- If `frontend/dist` is missing, `start.sh` builds the UI first

Manual start:

```bash
source venv/bin/activate
PYTHONPATH=src uvicorn dj_converter.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend hot reload (optional)

With the API running:

```bash
cd frontend && npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173) (proxies `/api` to the backend).

## Usage

1. **Connect** — confirm detected Rekordbox (`master.db` or XML), Serato
   (`_Serato_`), and Music root. Use **Change** only if you need another path.
   Choose direction (Rekordbox → Serato or reverse), then **Load**.
2. **Select** — check one or more playlists/crates. Folders select children.
3. **Convert** — dry-run first. Uncheck any playlist you do not want to import
   (e.g. heal failed). Expand a row only if you want track detail. If files are
   missing, set Music root and use **Heal**, then apply. After a successful
   write you get a confirmation with the next step for Serato or Rekordbox.

### After apply

- **Rekordbox → Serato:** reopen Serato so crates refresh.
- **Serato → Rekordbox:** writes an XML file (default
  `~/Music/dj-converter-export.xml`). Rekordbox does **not** import it
  automatically:
  1. Preferences → **Advanced → Database** → **rekordbox xml → Imported Library**
     → Browse to that XML file
  2. Preferences → **View → Layout** → enable **rekordbox xml**
  3. In the browser tree open **rekordbox xml → Playlists**, then drag the
     playlist into your **Playlists** folder

## Project layout

```
src/dj_converter/   FastAPI app, Serato/Rekordbox modules, convert + heal
frontend/           Vite + React UI (built into frontend/dist)
start.sh            Launch script
PLANNING.md         Architecture notes
```

## Tests

```bash
source venv/bin/activate
PYTHONPATH=src pytest src/dj_converter -v
ruff check src
```

## Safety & limits

- Playlist/crate membership only — not cues, beatgrids, or smart-playlist rules
- Destination crates are backed up under `_Serato_/Backups/dj-converter/`
- Streaming-only tracks without local files stay missing
- Does **not** write into encrypted Rekordbox `master.db` (XML import only)
