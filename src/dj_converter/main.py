"""FastAPI application entry point."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from dj_converter.features.convert.service import ConvertError, run_convert
from dj_converter.features.libraries.handlers import connect_libraries, detect_libraries
from dj_converter.features.source.handlers import SourceError, get_playlist_detail, get_source_tree
from dj_converter.models import ConnectRequest, ConvertRequest, Side
from dj_converter.session import get_paths

app = FastAPI(title="DJ Playlist Converter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


@app.get("/api/libraries/detect")
def api_detect_libraries() -> dict:
    """Detect default Rekordbox/Serato paths on this machine."""
    return detect_libraries().model_dump()


@app.get("/api/libraries/status")
def api_library_status() -> dict:
    """Return currently connected library paths."""
    return get_paths().model_dump()


@app.post("/api/libraries/connect")
def api_connect_libraries(body: ConnectRequest) -> dict:
    """Validate and connect library paths."""
    try:
        return connect_libraries(body).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/source/tree")
def api_source_tree(side: Side) -> list[dict]:
    """Return nested playlist/crate tree for a side."""
    try:
        nodes = get_source_tree(side)
    except SourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    # Omit heavy track payloads from tree listing
    slim = []
    for n in nodes:
        slim.append(_slim_node(n))
    return slim


def _slim_node(node) -> dict:
    data = node.model_dump()
    data["tracks"] = None
    data["children"] = [_slim_node(c) for c in node.children]
    return data


@app.get("/api/source/playlist/{playlist_id}")
def api_playlist_detail(playlist_id: str, side: Side) -> dict:
    """Return playlist detail including tracks."""
    try:
        return get_playlist_detail(side, playlist_id).model_dump()
    except SourceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/convert")
def api_convert(body: ConvertRequest) -> dict:
    """Dry-run or apply conversion (dry_run flag on body)."""
    try:
        return run_convert(body).model_dump()
    except ConvertError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/convert/apply")
def api_convert_apply(body: ConvertRequest) -> dict:
    """Force apply conversion (dry_run ignored / set False)."""
    body = body.model_copy(update={"dry_run": False})
    try:
        return run_convert(body).model_dump()
    except ConvertError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Serve built frontend if present
_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        """Serve SPA index for non-API routes."""
        index = _FRONTEND_DIST / "index.html"
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


"""
=== FILE FLOW DOCUMENTATION ===

Functionality: HTTP API and optional static SPA hosting for the converter.

Flow:
1. Library detect/connect endpoints
2. Source tree and playlist detail
3. Convert dry-run and apply
4. Serve frontend dist when built

Main Entry Point: app (uvicorn dj_converter.main:app)

Dependencies:
- fastapi
- feature handlers for libraries, source, convert
"""
