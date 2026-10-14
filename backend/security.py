import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from backend.config import settings


api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
)


def require_api_key(
    provided_key: str | None = Security(api_key_header),
):
    expected_key = settings.app_api_key.get_secret_value()

    if provided_key is None or not secrets.compare_digest(
        provided_key.encode("utf-8"),
        expected_key.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key.",
            headers={"WWW-Authenticate": "APIKey"},
        )