from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.portals import check_portal
from app.core.security import hash_password, verify_password
from app.db.base import utcnow
from app.models import User
from app.models.enums import Role, SituationLevel
from app.repositories import users as users_repo
from app.services import situation


def mfa_required(user: User) -> bool:
    return user.role == Role.admin and get_settings().admin_2fa_on


def check_not_locked(user: User) -> None:
    if user.locked_until and user.locked_until > utcnow():
        m = get_settings().login_lock_minutes
        raise AppError(423, "account_locked", f"Juda ko'p xato urinish. {m} daqiqadan keyin qayta urinib ko'ring")


async def register_failure(db: AsyncSession, user: User) -> None:
    """Noto'g'ri parol yoki 2FA kodi — umumiy hisoblagich: login_max_attempts xatodan keyin blok (commit qiladi)."""
    s = get_settings()
    user.failed_logins += 1
    if user.failed_logins >= s.login_max_attempts:
        user.locked_until = utcnow() + timedelta(minutes=s.login_lock_minutes)
        user.failed_logins = 0
        situation.add(db, SituationLevel.warning, "account_locked",
                      f"«{user.username}» akkaunti {s.login_lock_minutes} daqiqaga bloklandi: "
                      f"{s.login_max_attempts} marta noto'g'ri parol yoki kod kiritildi",
                      params={"username": user.username, "minutes": s.login_lock_minutes, "attempts": s.login_max_attempts},
                      district_id=user.district_id, ref=("user", user.id))
    await situation.commit(db)


async def login(db: AsyncSession, username: str, password: str, host: str | None = None) -> User:
    s = get_settings()
    user = await users_repo.by_username(db, username.strip().lower())
    bad = AppError(401, "invalid_credentials", "Login yoki parol noto'g'ri")
    if user and user.approval_status == "pending" and verify_password(password, user.password_hash):
        raise AppError(403, "account_pending", "Hisobingiz admin tasdig'ini kutmoqda")
    if not user or not user.is_active:
        raise bad
    check_not_locked(user)
    if not verify_password(password, user.password_hash):
        await register_failure(db, user)
        raise bad
    if not mfa_required(user):
        # 2FA'li adminda hisoblagich faqat kod to'g'ri bo'lganda tozalanadi — aks holda parol qayta kiritilib,
        # kodni cheksiz tanlash mumkin bo'lardi
        user.failed_logins = 0
    user.locked_until = None
    await db.commit()
    if not s.role_active(user.role.value):
        raise AppError(403, "role_inactive", "Bu rol hozircha faol emas — tizimga kirish keyingi bosqichda ochiladi")
    # Portal (subdomen) faqat parol to'g'ri bo'lgandan keyin tekshiriladi — login borligi oshkor bo'lmasin
    check_portal(host, user.role.value)
    return user


MIN_PASSWORD = 8


def check_password_strength(password: str) -> None:
    # Frontend'dagi talablar ro'yxati bilan bir xil: kamida 8 belgi, kamida bitta harf va bitta raqam
    if len(password) < MIN_PASSWORD or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise AppError(422, "weak_password", f"Parol kamida {MIN_PASSWORD} belgi bo'lib, harf va raqam aralash bo'lishi kerak")


async def change_password(db: AsyncSession, user: User, current: str, new: str) -> User:
    if not verify_password(current, user.password_hash):
        raise AppError(422, "wrong_current_password", "Joriy parol noto'g'ri")
    if current == new:
        raise AppError(422, "same_password", "Yangi parol eskisidan farq qilishi kerak")
    check_password_strength(new)
    user.password_hash = hash_password(new)
    user.must_change_password = False
    await db.commit()
    return user
