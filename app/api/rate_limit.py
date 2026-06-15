from collections import defaultdict, deque
from time import monotonic

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


_buckets: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(request: Request, channel: str) -> None:
    settings = get_settings()
    limit = settings.webhook_rate_limit_per_minute
    if limit <= 0:
        return

    client_host = request.client.host if request.client else "unknown"
    key = f"{channel}:{client_host}"
    now = monotonic()
    bucket = _buckets[key]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Webhook rate limit exceeded")
    bucket.append(now)

