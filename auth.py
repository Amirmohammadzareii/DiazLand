# -*- coding: utf-8 -*-
"""
احراز هویت دیازلند — هش رمز با pbkdf2 و session با کوکی امضاشده (itsdangerous).
SECRET_KEY فقط از متغیر محیطی خوانده می‌شود، هرگز هاردکد نمی‌شود.
"""

import os
import hashlib
import hmac
import secrets

from itsdangerous import BadSignature, URLSafeTimedSerializer

# کلید امضای session — باید از env بیاید
SECRET_KEY = os.environ.get("SECRET_KEY", "")

# نام کوکی session
SESSION_COOKIE = "diazland_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # ۳۰ روز

# تعداد تکرار pbkdf2
PBKDF2_ITERATIONS = 200_000


def _serializer():
    """ساخت سریالایزر امضاشده."""
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY تنظیم نشده است — آن را در متغیر محیطی بگذارید.")
    return URLSafeTimedSerializer(SECRET_KEY, salt="diazland-session")


def hash_password(password: str) -> str:
    """هش رمز با pbkdf2_hmac (sha256) و salt تصادفی."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """بررسی رمز در برابر هش ذخیره‌شده."""
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def make_session(user_id: int) -> str:
    """ساخت توکن session امضاشده برای کاربر."""
    return _serializer().dumps({"uid": user_id})


def read_session(token: str):
    """خواندن user_id از توکن امضاشده؛ در صورت نامعتبر بودن None."""
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE)
        return data.get("uid")
    except (BadSignature, Exception):
        return None
