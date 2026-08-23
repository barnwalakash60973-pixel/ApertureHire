"""
OTP generation for password reset. 6-digit numeric code, hashed before
storage (same bcrypt hashing as passwords - never store a raw OTP).
"""

from __future__ import annotations

import secrets

from app.infrastructure.auth.password_hashing import hash_password, verify_password


def generate_otp() -> str:
    """6-digit numeric OTP, cryptographically random (not `random` module)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    return hash_password(otp)


def verify_otp(otp: str, otp_hash: str) -> bool:
    return verify_password(otp, otp_hash)
