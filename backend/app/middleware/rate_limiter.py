"""
Simple in-memory rate limiter middleware for Module 8 sensitive endpoints.
For production, replace with Redis-backed implementation.
"""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Token-bucket rate limiter for sensitive endpoints."""
    
    SENSITIVE_PREFIXES = ["/api/review", "/review"]
    MAX_REQUESTS = 60  # per window
    WINDOW_SECONDS = 60
    
    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._counters: dict[str, list[float]] = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in self.SENSITIVE_PREFIXES):
            return await call_next(request)
        
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip and request.client:
            client_ip = request.client.host
        if not client_ip:
            client_ip = "unknown"
        
        now = datetime.now(timezone.utc).timestamp()
        window_start = now - self.window_seconds
        self._counters[client_ip] = [
            t for t in self._counters[client_ip] if t > window_start
        ]
        
        if len(self._counters[client_ip]) >= self.max_requests:
            logger.warning("Rate limit exceeded for IP %s on %s", client_ip, path)
            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(self.window_seconds)},
            )
        
        self._counters[client_ip].append(now)
        return await call_next(request)
