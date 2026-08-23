"""
JWT issuance and verification for HR login sessions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import Settings


class InvalidTokenError(Exception):
    pass


def create_access_token(user_id: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> str:
    """Returns the user_id encoded in the token, or raises InvalidTokenError."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as e:
        raise InvalidTokenError(str(e)) from e

    user_id = payload.get("sub")
    if not user_id:
        raise InvalidTokenError("Token has no subject.")
    return user_id
