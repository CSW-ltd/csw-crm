"""Bazada saqlanadigan tashqi tokenlarni (SmartGPS/Wialon) shifrlash — Fernet, kalit GPS_ENC_KEY (.env).
Baza zaxirasi sizib chiqsa ham token o'qilmaydi. Lokal/testlarda kalit bo'sh bo'lsa JWT_SECRET'dan olinadi."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class KeyError_(ValueError):
    pass


def check_key(key: str, name: str = "GPS_ENC_KEY") -> None:
    if not key:
        raise KeyError_(f"{name} bo'sh — GPS ulanishi uchun kerak (deploy/README: Fernet kaliti yaratish)")
    try:
        Fernet(key.encode())
    except (ValueError, TypeError):
        raise KeyError_(f"{name} Fernet kaliti emas (32 bayt, urlsafe base64)") from None


def _fernet() -> Fernet:
    s = get_settings()
    if s.gps_enc_key:
        return Fernet(s.gps_enc_key.encode())
    if s.app_env == "production":
        raise KeyError_("GPS_ENC_KEY bo'sh — GPS ulanishi o'chiq")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("gps:" + s.jwt_secret).encode()).digest()))


def available() -> bool:
    try:
        _fernet()
        return True
    except KeyError_:
        return False


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, KeyError_):
        return None
