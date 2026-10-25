"""Storage download endpoint (serves persisted output files).

Serves stored artifacts (e.g. rendered clips) to authenticated callers.
This is the real backing for the frontend's ``download_url``. Path
traversal is prevented by the StorageProvider's own validation.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from app.api.deps import get_storage, require_auth
from app.storage.base import StorageProvider

router = APIRouter(prefix="/storage", tags=["storage"])

AuthDep = Depends(require_auth)


@router.get("/{path:path}", summary="Download a stored artifact")
def download_artifact(
    request: Request,
    path: str,
    _: None = AuthDep,
) -> FileResponse:
    storage: StorageProvider = get_storage(request)
    try:
        local_path = storage.path_for(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid storage path") from exc
    if not Path(local_path).is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(
        str(local_path),
        media_type="video/mp4",
        filename=Path(path).name,
    )
