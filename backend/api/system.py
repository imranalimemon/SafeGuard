from fastapi import APIRouter, HTTPException, Query
from config import settings
from logging_setup import tail_logs

router = APIRouter()

@router.get('/api/system/logs')
def system_logs(limit: int = Query(default=100, ge=1, le=250)):
    try:
        return {'lines': tail_logs(settings.LOG_DIR, limit), 'timezone': 'UTC', 'rotation': '2 MB per file; four backups'}
    except OSError:
        raise HTTPException(503, 'System log is unavailable.') from None
