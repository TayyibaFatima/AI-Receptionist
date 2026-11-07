"""Small in-memory rate limiter (per client IP). See README 'Security limitations':
for multiple server instances use a shared store such as Redis."""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int = 60):
        self.max_calls, self.window = max_calls, window_seconds
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.max_calls:
                raise HTTPException(status_code=429, detail="Too many messages. Please wait a moment and try again.")
            q.append(now)

    def reset(self) -> None:
        with self.lock:
            self.hits.clear()


chat_limiter = RateLimiter(get_settings().chat_rate_limit_per_minute)


def chat_rate_limit(request: Request) -> None:
    # Behind a proxy (FastAPI Cloud) the real client IP is the first X-Forwarded-For entry.
    forwarded = request.headers.get("x-forwarded-for", "")
    key = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    chat_limiter.check(key)
