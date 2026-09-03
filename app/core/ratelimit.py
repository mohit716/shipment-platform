import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings


class SlidingWindowLimiter:
    """Counts attempts per key inside a moving time window.

    A sliding window rather than a fixed one: with fixed buckets a caller can
    make the full allowance at 11:59:59 and the full allowance again at
    12:00:00, so a limit of five per minute permits ten in two seconds. Keeping
    the timestamps and discarding the expired ones costs a little memory and
    removes the edge entirely.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> bool:
        """Record an attempt and report whether it is within the allowance."""
        now = time.monotonic()
        window = self.hits[key]

        # Drop everything that has aged out before counting.
        while window and now - window[0] > self.window:
            window.popleft()

        if len(window) >= self.limit:
            return False

        window.append(now)
        return True

    def retry_after(self, key: str) -> int:
        """Seconds until the oldest attempt in the window expires."""
        window = self.hits.get(key)
        if not window:
            return 0
        return max(1, int(self.window - (time.monotonic() - window[0])))

    def reset(self) -> None:
        self.hits.clear()


# In process, so each API instance counts separately. Behind two replicas the
# effective limit doubles. That is an accepted trade for now and the reason the
# counter is behind a small class: moving it to Redis, which every instance
# shares, changes this file and nothing else.
login_limiter = SlidingWindowLimiter(
    limit=settings.login_rate_limit,
    window_seconds=settings.login_rate_limit_window_seconds,
)


def client_key(request: Request) -> str:
    """Identify the caller for rate limiting purposes.

    Behind a proxy the socket address is the proxy, so every user would share
    one bucket. X-Forwarded-For is honoured only when the deployment says it is
    behind a trusted proxy: the header is trivially spoofed, and trusting it
    unconditionally lets an attacker have a fresh allowance per request.
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_login_rate_limit(request: Request) -> None:
    """Reject a caller who has attempted to log in too many times."""
    key = client_key(request)
    if login_limiter.check(key):
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many login attempts. Try again shortly.",
        # Tells a well behaved client when to come back rather than leaving it
        # to guess, which usually means retrying immediately.
        headers={"Retry-After": str(login_limiter.retry_after(key))},
    )
