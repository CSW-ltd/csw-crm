"""Admin 2FA (TOTP): ulash, tekshirish, zaxira kodlar, qayta o'rnatish.

Oqim: /auth/login parol to'g'ri bo'lsa admin uchun sessiya bermaydi — `mfa_required` xatosi (details: mode, mfa_token).
mode="setup" — /auth/2fa/setup (QR) → /auth/2fa/enable (kod) → zaxira kodlar + sessiya.
mode="verify" — /auth/2fa/verify (TOTP yoki zaxira kod) → sessiya.
Noto'g'ri kod parol bilan umumiy hisoblagichga qo'shiladi (auth_service.register_failure).
"""
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import totp
from app.core.config import get_settings
from app.core.errors import AppError, conflict, invalid, not_found
from app.core.portals import check_portal
from app.core.security import MFA, create_token, decode_token
from app.db.base import utcnow
from app.models import User, UserBackupCode
from app.models.enums import Role, SituationLevel
from app.repositories import users as users_repo
from app.services import situation
from app.services.auth_service import check_not_locked, register_failure

W = SituationLevel.warning


def challenge(user: User) -> AppError:
    """Parol to'g'ri, endi 2FA kerak: frontend shu xato tafsilotlaridan keyingi qadamni oladi."""
    mode = "verify" if user.totp_enabled else "setup"
    return AppError(401, "mfa_required", "Ikki bosqichli tekshiruv kodi kerak",
                    details={"mode": mode, "mfa_token": create_token(user.id, user.role.value, MFA)})


async def _from_token(db: AsyncSession, token: str, host: str | None) -> User:
    data = decode_token(token, MFA) if token else None
    user = await users_repo.by_id(db, int(data["sub"])) if data else None
    if not user or not user.is_active or not get_settings().role_active(user.role.value):
        raise AppError(401, "mfa_expired", "Kod kiritish vaqti tugadi — qaytadan kiring")
    check_portal(host, user.role.value)
    check_not_locked(user)
    return user


async def setup(db: AsyncSession, token: str, host: str | None) -> dict:
    user = await _from_token(db, token, host)
    if user.totp_enabled:
        raise conflict("mfa_already_enabled", "2FA allaqachon ulangan")
    secret = totp.new_secret()  # har chaqiruvda yangi: eski QR yaroqsiz bo'ladi
    user.totp_secret_enc = totp.encrypt(secret)
    user.totp_last_step = None
    await db.commit()
    uri = totp.provisioning_uri(secret, user.username)
    return {"secret": secret, "uri": uri, "qr_svg": totp.qr_svg(uri)}


async def _bad_code(db: AsyncSession, user: User) -> AppError:
    await register_failure(db, user)
    return AppError(422, "mfa_invalid_code", "Kod noto'g'ri yoki eskirgan")


def _success(user: User) -> None:
    user.failed_logins = 0
    user.locked_until = None


async def _replace_backup_codes(db: AsyncSession, user: User) -> list[str]:
    await db.execute(delete(UserBackupCode).where(UserBackupCode.user_id == user.id))
    codes = totp.new_backup_codes()
    db.add_all([UserBackupCode(user_id=user.id, code_hash=totp.hash_backup(c)) for c in codes])
    return codes


async def enable(db: AsyncSession, token: str, code: str, host: str | None) -> tuple[User, list[str]]:
    user = await _from_token(db, token, host)
    if user.totp_enabled:
        raise conflict("mfa_already_enabled", "2FA allaqachon ulangan")
    secret = totp.decrypt(user.totp_secret_enc) if user.totp_secret_enc else None
    if not secret:
        raise conflict("mfa_setup_required", "Avval QR kodni oling")
    step = totp.match_step(secret, code, None)
    if step is None:
        raise await _bad_code(db, user)
    user.totp_enabled = True
    user.totp_last_step = step
    _success(user)
    codes = await _replace_backup_codes(db, user)
    situation.add(db, SituationLevel.info, "mfa_enabled", f"2FA ulandi: {user.full_name} ({user.username})",
                  params={"name": user.full_name, "username": user.username}, actor_id=user.id, ref=("user", user.id))
    await situation.commit(db)
    return user, codes


async def verify(db: AsyncSession, token: str, code: str, host: str | None) -> User:
    user = await _from_token(db, token, host)
    if not user.totp_enabled:
        raise conflict("mfa_setup_required", "2FA ulanmagan — qaytadan kiring")
    digits = "".join(c for c in code if c.isdigit())
    if len(digits) == 6 and len(totp.normalize_backup(code)) == 6:
        secret = totp.decrypt(user.totp_secret_enc or "")
        step = totp.match_step(secret, digits, user.totp_last_step) if secret else None
        if step is None:
            raise await _bad_code(db, user)
        user.totp_last_step = step
        _success(user)
        await db.commit()
        return user
    row = (await db.execute(select(UserBackupCode).where(
        UserBackupCode.user_id == user.id, UserBackupCode.code_hash == totp.hash_backup(code),
        UserBackupCode.used_at.is_(None)))).scalar_one_or_none()
    if not row:
        raise await _bad_code(db, user)
    row.used_at = utcnow()
    _success(user)
    left = await remaining_backup_codes(db, user.id)  # autoflush: ishlatilgan kod allaqachon hisobdan chiqqan
    situation.add(db, W, "mfa_backup_used", f"Zaxira kod bilan kirildi: {user.full_name} ({user.username}), qolgan kodlar: {left}",
                  params={"name": user.full_name, "username": user.username, "left": left}, actor_id=user.id, ref=("user", user.id))
    await situation.commit(db)
    return user


async def remaining_backup_codes(db: AsyncSession, user_id: int) -> int:
    return (await db.execute(select(func.count()).select_from(UserBackupCode).where(
        UserBackupCode.user_id == user_id, UserBackupCode.used_at.is_(None)))).scalar_one()


def _clear(user: User) -> None:
    user.totp_secret_enc = None
    user.totp_enabled = False
    user.totp_last_step = None


async def reset(db: AsyncSession, actor: User | None, user_id: int, reason: str) -> User:
    """Boshqa admin (yoki serverdagi CLI, actor=None) 2FA'ni qayta o'rnatadi: keyingi kirishda QR qaytadan.
    Eski sessiyalar refresh'da rad etiladi (2FA ulanmagan admin refresh qila olmaydi)."""
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise invalid("mfa_reason_required", "Sababini yozing (kamida 3 belgi)")
    user = await users_repo.by_id(db, user_id)
    if not user:
        raise not_found("user")
    if actor is not None and actor.id == user.id:
        raise conflict("cannot_reset_own_2fa", "O'z 2FA'ingizni qayta o'rnata olmaysiz — boshqa admin qiladi")
    if user.role != Role.admin and not user.totp_secret_enc:
        raise conflict("mfa_not_enabled", "Bu xodimda 2FA yo'q")
    _clear(user)
    await db.execute(delete(UserBackupCode).where(UserBackupCode.user_id == user.id))
    who = "server (CLI)" if actor is None else f"{actor.full_name} ({actor.username})"
    situation.add(db, W, "mfa_reset", f"2FA qayta o'rnatildi: {user.full_name} ({user.username}) — {who}. Sabab: {reason}",
                  params={"name": user.full_name, "username": user.username, "by": who, "reason": reason},
                  actor_id=actor.id if actor else None, ref=("user", user.id))
    await situation.commit(db)
    return await users_repo.by_id(db, user.id)
