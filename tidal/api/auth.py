"""Bearer-token auth for operator endpoints."""

from __future__ import annotations

from dataclasses import dataclass
import secrets

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tidal.config import Settings

security = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class OperatorIdentity:
    operator_id: str
    token: str


def resolve_operator_tokens(settings: Settings) -> dict[str, str]:
    if settings.tidal_api_operator_tokens:
        return dict(settings.tidal_api_operator_tokens)
    if settings.tidal_api_token:
        return {"default": settings.tidal_api_token}
    return {}


def authenticate_operator(
    credentials: HTTPAuthorizationCredentials | None,
    settings: Settings,
) -> OperatorIdentity:
    tokens = resolve_operator_tokens(settings)
    if not tokens:
        raise HTTPException(status_code=503, detail="API operator tokens are not configured")
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token required")
    for operator_id, token in tokens.items():
        if secrets.compare_digest(token, credentials.credentials):
            return OperatorIdentity(operator_id=operator_id, token=token)
    raise HTTPException(status_code=401, detail="Invalid bearer token")

