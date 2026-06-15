import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import get_settings


def constant_time_equals(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return False
    return hmac.compare_digest(left, right)


admin_api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)


async def require_admin_api_key(api_key: str | None = Security(admin_api_key_header)) -> None:
    expected = get_settings().admin_api_key
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin API key is not configured")
    if not constant_time_equals(api_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin API key")
