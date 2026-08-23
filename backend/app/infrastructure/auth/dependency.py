"""
FastAPI dependency guarding HR-facing routes. Candidate-facing routes
(routes_submissions.py) deliberately do NOT use this - candidates
authenticate via their mailed token instead, not a login.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.auth.jwt_tokens import InvalidTokenError, decode_access_token
from app.infrastructure.db.database import get_session
from app.infrastructure.db.models import UserORM

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> UserORM:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated - missing bearer token.")

    settings = get_settings()
    try:
        user_id = decode_access_token(credentials.credentials, settings)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    user = await session.get(UserORM, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists.")
    return user
