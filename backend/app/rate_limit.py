"""Rate limiting. Redis-backed via slowapi, keyed by authenticated user when
available, otherwise by client IP. Default ceiling is applied via middleware;
stricter per-route limits are set by decorator on sensitive endpoints.
"""
from fastapi import Request
from jose import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()


def identity_key(request: Request) -> str:
    """Rate-limit key: `user:<uuid>` if a valid JWT cookie is present,
    else `ip:<remote-address>`. Expired JWTs are still keyed by user so a
    replay doesn't get a fresh bucket."""
    token = request.cookies.get("ca_token")
    if token:
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": False},
            )
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=identity_key,
    storage_uri=settings.redis_url,
    default_limits=["120/minute"],
)
