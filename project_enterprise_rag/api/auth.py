from __future__ import annotations

from fastapi import Header, HTTPException, status

from services.job_service import verify_api_key


AUTH_HEADER = "X-API-Key"


def require_api_key(x_api_key: str | None = Header(default=None, alias=AUTH_HEADER)) -> str:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_type": "auth_error", "message": f"Missing {AUTH_HEADER} header."},
        )

    if not verify_api_key(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_type": "auth_error", "message": "Invalid API key."},
        )

    return x_api_key
