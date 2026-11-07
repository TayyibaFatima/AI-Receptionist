import uuid

from fastapi import Header, HTTPException


def get_session_id(x_session_id: str | None = Header(default=None)) -> uuid.UUID:
    """The visitor's session key, sent by the frontend in the X-Session-ID header."""
    if not x_session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header is required.")
    try:
        return uuid.UUID(x_session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Session-ID must be a valid UUID.")
