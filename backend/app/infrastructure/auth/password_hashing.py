"""
Password hashing - bcrypt directly (no passlib wrapper needed for one
algorithm). Also used to hash OTPs before storing them, so a raw OTP is
never sitting in the database even for the few minutes it's valid.
"""

from __future__ import annotations

import bcrypt


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed hash (shouldn't happen with data we wrote ourselves,
        # but never let a bad hash crash the login attempt into a 500).
        return False
