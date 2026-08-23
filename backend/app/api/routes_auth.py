"""
HR authentication: register, login (email OR mobile number), and OTP-based
password reset. Candidate-facing routes are untouched - candidates never
log in, they use a mailed token (see routes_submissions.py).

Note: OTP delivery only goes through email (the only delivery channel
this app has - no SMS provider integrated). Logging in via mobile number
is fully supported; receiving the reset OTP via SMS is not - the OTP is
always emailed to the account's email address, regardless of which
identifier was used to request the reset. Flagging this rather than
pretending SMS delivery exists.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.auth.jwt_tokens import create_access_token
from app.infrastructure.auth.otp import generate_otp, hash_otp, verify_otp
from app.infrastructure.auth.password_hashing import hash_password, verify_password
from app.infrastructure.db.database import get_session
from app.infrastructure.db.models import UserORM
from app.infrastructure.email.email_sender import get_email_sender
from app.infrastructure.email.templates import OTP_EMAIL_BODY, OTP_EMAIL_SUBJECT

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = get_logger(__name__)


def _to_user_response(user: UserORM) -> UserResponse:
    return UserResponse(id=user.id, name=user.name, email=user.email, mobile_number=user.mobile_number, role=user.role)


async def _find_by_identifier(session: AsyncSession, identifier: str) -> UserORM | None:
    """Identifier can be an email OR a mobile number - both are unique
    columns, so a single OR query covers login regardless of which one
    the user typed."""
    result = await session.execute(select(UserORM).where(or_(UserORM.email == identifier, UserORM.mobile_number == identifier)))
    return result.scalar_one_or_none()


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    existing = await _find_by_identifier(session, body.email)
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    if body.mobile_number:
        existing_mobile = await _find_by_identifier(session, body.mobile_number)
        if existing_mobile is not None:
            raise HTTPException(status_code=409, detail="An account with this mobile number already exists.")

    user = UserORM(name=body.name, email=body.email, mobile_number=body.mobile_number, password_hash=hash_password(body.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)

    settings = get_settings()
    token = create_access_token(user.id, settings)
    logger.info("New HR account registered: %s", user.email)
    return TokenResponse(access_token=token, user=_to_user_response(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    user = await _find_by_identifier(session, body.identifier)
    if user is None or not verify_password(body.password, user.password_hash):
        # Same error for "no such user" and "wrong password" - never leak
        # which one it was, that's an account-enumeration hole.
        raise HTTPException(status_code=401, detail="Incorrect email/mobile number or password.")

    settings = get_settings()
    token = create_access_token(user.id, settings)
    logger.info("HR login: %s", user.email)
    return TokenResponse(access_token=token, user=_to_user_response(user))


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(body: ForgotPasswordRequest, session: AsyncSession = Depends(get_session)) -> ForgotPasswordResponse:
    """Always returns the same success message whether or not the
    identifier matches an account - prevents attackers from using this
    endpoint to discover which emails/numbers are registered."""

    settings = get_settings()
    generic_message = "If an account exists for that email/mobile number, a reset code has been sent."

    user = await _find_by_identifier(session, body.identifier)
    if user is None:
        logger.info("Forgot-password requested for unknown identifier (no email sent, generic response returned)")
        return ForgotPasswordResponse(message=generic_message)

    otp = generate_otp()
    user.reset_otp_hash = hash_otp(otp)
    user.reset_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expire_minutes)
    await session.commit()

    email_sender = get_email_sender(settings)
    email_sender.send(
        to_email=user.email,
        subject=OTP_EMAIL_SUBJECT,
        body=OTP_EMAIL_BODY.format(name=user.name, otp=otp, expire_minutes=settings.otp_expire_minutes),
    )
    logger.info("Password reset OTP sent to %s", user.email)
    return ForgotPasswordResponse(message=generic_message)


@router.post("/reset-password", response_model=ForgotPasswordResponse)
async def reset_password(body: ResetPasswordRequest, session: AsyncSession = Depends(get_session)) -> ForgotPasswordResponse:
    user = await _find_by_identifier(session, body.identifier)
    if user is None or user.reset_otp_hash is None or user.reset_otp_expires_at is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code.")

    expires_at = user.reset_otp_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)  # SQLite tzinfo round-trip, same issue as elsewhere in this app

    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code.")
    if not verify_otp(body.otp, user.reset_otp_hash):
        raise HTTPException(status_code=400, detail="Invalid or expired reset code.")

    user.password_hash = hash_password(body.new_password)
    user.reset_otp_hash = None
    user.reset_otp_expires_at = None
    await session.commit()
    logger.info("Password reset completed for %s", user.email)
    return ForgotPasswordResponse(message="Password reset successfully. You can now log in with your new password.")
