"""
Admin Endpoints

Error log management — read and clear the persistent error log.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from app.core.logging import ERROR_LOG_FILE
from app.core.security import get_current_user_id

router = APIRouter()


@router.get("/error-log", response_class=PlainTextResponse)
async def get_error_log(
    lines: int = Query(200, ge=1, le=5000),
    _user_id: str = Depends(get_current_user_id),
) -> str:
    """Return the last N lines of the error log file."""
    if not ERROR_LOG_FILE.exists():
        return ""
    text = ERROR_LOG_FILE.read_text(encoding="utf-8", errors="replace")
    all_lines = text.splitlines()
    return "\n".join(all_lines[-lines:])


@router.delete("/error-log")
async def clear_error_log(
    _user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    """Truncate the error log file after review."""
    if ERROR_LOG_FILE.exists():
        ERROR_LOG_FILE.write_text("", encoding="utf-8")
    return {"status": "cleared"}
