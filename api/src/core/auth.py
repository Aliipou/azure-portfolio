"""Azure Entra ID JWT validation + RBAC dependencies."""

from __future__ import annotations

import json
import time
from functools import lru_cache
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.config import settings
from src.models.enums import UserRole
from src.models.schemas import UserClaims

_bearer = HTTPBearer(auto_error=False)

# JWKS cache: (keys, fetched_at)
_jwks_cache: tuple[list[dict[str, Any]], float] | None = None
_JWKS_TTL = 86400  # 24 hours


@lru_cache(maxsize=1)
def _jwks_uri() -> str:
    return (
        f"https://login.microsoftonline.com/{settings.azure_tenant_id}"
        "/discovery/v2.0/keys"
    )


async def _get_jwks() -> list[dict[str, Any]]:
    global _jwks_cache
    now = time.time()
    if _jwks_cache and now - _jwks_cache[1] < _JWKS_TTL:
        return _jwks_cache[0]
    async with httpx.AsyncClient() as client:
        resp = await client.get(_jwks_uri(), timeout=10)
        resp.raise_for_status()
        keys: list[dict[str, Any]] = resp.json()["keys"]
    _jwks_cache = (keys, now)
    return keys


def _decode_dev_user(header_value: str) -> UserClaims:
    """Parse X-Dev-User header for local development."""
    data = json.loads(header_value)
    roles = [UserRole(r) for r in data.get("roles", [])]
    return UserClaims(
        sub=data.get("sub", "dev-user"),
        email=data.get("email", "dev@local"),
        roles=roles,
        tenant_id=data.get("tenant_id", "dev-tenant"),
        name=data.get("name", "Dev User"),
    )


async def verify_token(token: str) -> UserClaims:
    """Validate JWT from Azure Entra ID and extract claims."""
    try:
        keys = await _get_jwks()
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        key = next((k for k in keys if k.get("kid") == kid), None)
        if key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown key ID")

        payload: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.azure_client_id or None,
            options={"verify_aud": bool(settings.azure_client_id)},
        )

        roles_raw: list[str] = payload.get("roles", [])
        roles = [UserRole(r) for r in roles_raw if r in UserRole.__members__.values()]

        return UserClaims(
            sub=payload["sub"],
            email=payload.get("email") or payload.get("preferred_username"),
            roles=roles,
            tenant_id=payload.get("tid"),
            name=payload.get("name"),
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UserClaims:
    """FastAPI dependency: extract and validate user identity."""
    # Dev mode: accept X-Dev-User header
    if settings.dev_mode:
        dev_header = request.headers.get("X-Dev-User")
        if dev_header:
            try:
                return _decode_dev_user(dev_header)
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid X-Dev-User header: {exc}",
                ) from exc

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await verify_token(credentials.credentials)


def require_role(*roles: UserRole):
    """Dependency factory: enforce at least one of the given roles."""
    async def _check(user: UserClaims = Depends(get_current_user)) -> UserClaims:
        if not any(r in user.roles for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {[r.value for r in roles]}",
            )
        return user
    return _check
