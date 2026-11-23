"""Admin 2FA (TOTP, RFC 6238): kalitni shifrlash, kodni tekshirish, QR va zaxira kodlar.

Kalit bazada Fernet bilan shifrlangan (TOTP_ENC_KEY .env'da) — baza zaxirasi sizsa ham kod yaratib bo'lmaydi.
Bitta kod qayta ishlatilmaydi: oxirgi qabul qilingan vaqt qadami (`totp_last_step`) saqlanadi.
"""
import base64
import hashlib
import hmac
import io
import secrets
import time

import pyotp
import segno
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

ISSUER = "CSW"
STEP = 30
BACKUP_CODES = 10
_BACKUP_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # o'xshash belgilarsiz (0/o, 1/l/i)


class TotpKeyError(ValueError):
    pass


def check_key(key: str) -> None:
    if not key:
        raise TotpKeyError("TOTP_ENC_KEY bo'sh — admin 2FA uchun kerak (README: Fernet kaliti yaratish)")
    try:
        Fernet(key.encode())
    except (ValueError, TypeError):
        raise TotpKeyError("TOTP_ENC_KEY Fernet kaliti emas (32 bayt, urlsafe base64)") from None


def _fernet() -> Fernet:
    s = get_settings()
    if s.totp_enc_key:
        return Fernet(s.totp_enc_key.encode())
    # Lokal/testlar: JWT_SECRET'dan olinadi (prod'da check_production kalitni majburiy qiladi)
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("totp:" + s.jwt_secret).encode()).digest()))


def new_secret() -> str:
    return pyotp.random_base32()


def encrypt(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def provisioning_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=ISSUER)


def qr_svg(uri: str) -> str:
    buf = io.BytesIO()
    segno.make(uri, error="m").save(buf, kind="svg", scale=5, border=2, xmldecl=False, svgns=True)
    return buf.getvalue().decode()


def match_step(secret: str, code: str, last_step: int | None, now: float | None = None) -> int | None:
    """To'g'ri kodning vaqt qadami (±1 qadam soat farqi uchun) yoki None. last_step va undan oldingilari rad etiladi."""
    code = "".join(c for c in code if c.isdigit())
    if len(code) != 6:
        return None
    totp = pyotp.TOTP(secret)
    current = int((now if now is not None else time.time()) // STEP)
    for step in (current, current - 1, current + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(totp.at(step * STEP), code):
            return step
    return None


def new_backup_codes() -> list[str]:
    """10 ta bir martalik kod, ko'rinishi `abcd-efgh`."""
    def one() -> str:
        raw = "".join(secrets.choice(_BACKUP_ALPHABET) for _ in range(8))
        return f"{raw[:4]}-{raw[4:]}"
    return [one() for _ in range(BACKUP_CODES)]


def normalize_backup(code: str) -> str:
    return "".join(c for c in code.lower() if c.isalnum())


def hash_backup(code: str) -> str:
    """HMAC-SHA256, kalit TOTP_ENC_KEY'dan: faqat baza sizsa, kodlarni tanlab topib bo'lmaydi."""
    s = get_settings()
    key = hashlib.sha256(("backup:" + (s.totp_enc_key or s.jwt_secret)).encode()).digest()
    return hmac.new(key, normalize_backup(code).encode(), hashlib.sha256).hexdigest()
