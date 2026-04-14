"""
Shared slowapi rate limiter.

Import `limiter` here; wire it into the app in main.py:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

Endpoints opt in with:
    @limiter.limit("30/minute")
    async def endpoint(request: Request, ...):
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
