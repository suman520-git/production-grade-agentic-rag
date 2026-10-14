import math
import time

from fastapi import Depends, HTTPException, Request
from limits import RateLimitItemPerMinute
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

from backend.config import settings
from backend.security import require_api_key


storage = MemoryStorage()

limiter = FixedWindowRateLimiter(storage)

request_limit = RateLimitItemPerMinute(
    settings.rate_limit_per_minute
)


def enforce_rate_limit(
    request: Request,
    authenticated: None = Depends(require_api_key),
):
    client_ip = (
        request.client.host
        if request.client is not None
        else "unknown"
    )

    # The same IP shares one counter across application endpoints.
    identifiers = ("application_requests", client_ip)

    if not limiter.hit(request_limit, *identifiers):
        window = limiter.get_window_stats(
            request_limit,
            *identifiers,
        )

        retry_after = max(
            1,
            math.ceil(window.reset_time - time.time()),
        )

        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
            headers={
                "Retry-After": str(retry_after),
            },
        )