"""Authenticated image downloads; no directory listing or arbitrary file types."""
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()


def evidence_file(directory, filename):
    if '..' in filename or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:jpg|jpeg|png|webp)', filename, re.I):
        raise HTTPException(404, 'Evidence not found.')
    root = Path(directory).resolve()
    path = (root / filename).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(404, 'Evidence not found.')
    return path


@router.get('/screenshots/{filename:path}')
def download_evidence(filename: str):
    from config import settings
    path = evidence_file(settings.SCREENSHOT_DIR, filename)
    mime = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}[path.suffix.lower()]
    return FileResponse(path, media_type=mime)
