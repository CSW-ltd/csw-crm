from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

ACCESS = "access"
REFRESH = "refresh"
MFA = "mfa"  # paroldan keyin, 2FA kodigacha (5 daqiqa); sessiya bermaydi
MFA_TOKEN_MINUTES = 5


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_token(user_id: int, role: str, token_type: str) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    ttl = (timedelta(minutes=s.access_token_minutes) if token_type == ACCESS
           else timedelta(minutes=MFA_TOKEN_MINUTES) if token_type == MFA else timedelta(days=s.refresh_token_days))
    payload = {"sub": str(user_id), "role": role, "type": token_type, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_token(token: str, expected_type: str) -> dict | None:
    s = get_settings()
    try:
        data = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    if data.get("type") != expected_type:
        return None
    return data
