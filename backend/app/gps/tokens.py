"""GPS token chidamliligi (0028): asosiy va zaxira token, har soatlik tekshiruv, avtomatik o'tish, ogohlantirish.

- Parol hech qachon saqlanmaydi: ikkala token ham SmartGPS'ning o'z «Ulash» sahifasidan olinadi (faqat o'qish, 0x300), shifrlangan.
- Zaxira token boshqa akkauntdan bo'lishi mumkin (`backup_account`, bo'sh bo'lsa — asosiy akkaunt): bitta akkauntning hamma
  tokenlari o'chirilsa ham zaxira yashab qoladi.
- Worker har soatda (yangi token — darhol) har bir tokenni tekshiradi. Tarmoq xatosida token «o'lik» deb belgilanmaydi — faqat
  SmartGPS rad etsa (xato 1/4/7/8), egasi mos kelmasa yoki huquqi faqat o'qish bo'lmasa.
- Faol token o'lsa worker o'zi ikkinchisiga o'tadi; asosiysi qayta ulansa — unga qaytadi.
- Ogohlantirish faqat holat yomonlashganda (takrorlanmaydi): Vaziyat paneli + barcha faol adminlarga bildirishnoma («Ulash» havolasi).
  Dispatch xodimi tokenni ham, bu bildirishnomani ham ko'rmaydi.

Bu modul faqat gps-worker'da tarmoqqa chiqadi (check_*); pick_active/state — API tomonida ham ishlatiladi (tarmoqsiz)."""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secretbox
from app.db.base import utcnow
from app.gps.client import GpsError, WialonClient, is_read_only
from app.models import GpsSource, User
from app.models.enums import Role, SituationLevel
from app.services import notifications, situation

SLOTS = ("main", "backup")
CHECK_EVERY = timedelta(hours=1)
LABEL = {"main": "Asosiy token", "backup": "Zaxira token"}
_F = {"main": ("token_enc", "token_status", "token_user", "token_set_at"),
      "backup": ("backup_token_enc", "backup_token_status", "backup_token_user", "backup_token_set_at")}


def enc(src: GpsSource, slot: str) -> str | None:
    return getattr(src, _F[slot][0])


def status(src: GpsSource, slot: str) -> str:
    return (getattr(src, _F[slot][1]) or "none") if enc(src, slot) else "none"


def account(src: GpsSource, slot: str) -> str:
    return (src.backup_account or src.account) if slot == "backup" else src.account


def set_slot(src: GpsSource, slot: str, *, token_enc: str | None = ..., status_: str | None = None, user: str | None = ...,
             set_at: datetime | None = ...) -> None:
    f_enc, f_st, f_user, f_at = _F[slot]
    if token_enc is not ...:
        setattr(src, f_enc, token_enc)
    if status_ is not None:
        setattr(src, f_st, status_)
    if user is not ...:
        setattr(src, f_user, user)
    if set_at is not ...:
        setattr(src, f_at, set_at)


def has_any(src: GpsSource) -> bool:
    return any(enc(src, s) for s in SLOTS)


def any_status(src: GpsSource, st: str) -> bool:
    return any(status(src, s) == st for s in SLOTS)


def active(src: GpsSource) -> str:
    return src.active_slot if src.active_slot in SLOTS else "main"


def candidates(src: GpsSource) -> list[str]:
    """Sinxron/jonli so'rovlar uchun tokenlar tartibi: avval faol, keyin ikkinchisi; o'liklari tashlab ketiladi."""
    a = active(src)
    return [s for s in (a, *(x for x in SLOTS if x != a)) if enc(src, s) and status(src, s) in ("ok", "pending")]


def pick_active(src: GpsSource) -> None:
    """Asosiysi ishlasa — asosiy; bo'lmasa ishlaydigan zaxira. Ishlaydigan token yo'q bo'lsa — o'zgarmaydi."""
    ok = [s for s in SLOTS if status(src, s) == "ok"]
    if "main" in ok:
        src.active_slot = "main"
    elif ok:
        src.active_slot = ok[0]


def state(src: GpsSource) -> str:
    """ok | d:main | d:backup (bitta o'lik, ikkinchisi ishlaydi yoki tekshirilmoqda) | down (ishlaydigan token yo'q)."""
    dead = [s for s in SLOTS if status(src, s) == "invalid"]
    alive = [s for s in SLOTS if status(src, s) in ("ok", "pending")]
    if not dead:
        return "ok"
    if not alive:
        return "down"
    return f"d:{dead[0]}"


async def verify(c: WialonClient, token: str, owner: str) -> str:
    """Login + egasi + faqat o'qish huquqi. Qaytaradi: SmartGPS foydalanuvchi nomi. Rad etilsa — GpsError (auth kodi bilan)."""
    user = await c.login(token)
    if owner and user and user.strip().lower() != owner.strip().lower():
        raise GpsError(f"Token «{user}» akkauntiga tegishli, bu ulanish «{owner}» uchun", 8)
    if not is_read_only(await c.token_access(token)):
        raise GpsError("Token o'zgartirish huquqiga ega — faqat o'qish (0x300) token kerak", 7)
    return user


def mark_dead(src: GpsSource, slot: str, err: GpsError) -> None:
    set_slot(src, slot, status_="invalid")
    src.last_error = f"{LABEL[slot]}: {err}"[:500]


async def check_slot(src: GpsSource, slot: str, *, transport=None) -> bool | None:
    """True — ishlaydi, False — o'lik (belgilandi), None — tekshirib bo'lmadi (tarmoq), holat o'zgarmaydi."""
    token = secretbox.decrypt(enc(src, slot) or "")
    try:
        if not token:
            raise GpsError("Token ochilmadi (GPS_ENC_KEY o'zgarganmi?) — qayta «Ulash» kerak", 8)
        async with WialonClient(src.server, transport=transport, timeout=60, retry_delay=2) as c:
            user = await verify(c, token, account(src, slot))
    except GpsError as e:
        if e.auth:
            mark_dead(src, slot, e)
            return False
        return None
    set_slot(src, slot, status_="ok", **({"user": user} if user else {}))
    return True


def need_check(src: GpsSource, now: datetime) -> bool:
    if not src.is_active or not has_any(src):
        return False
    if any_status(src, "pending"):
        return True
    return src.token_checked_at is None or now - src.token_checked_at >= CHECK_EVERY


async def check_source(db: AsyncSession, src: GpsSource, *, transport=None) -> None:
    """Har soatlik tekshiruv: har bir token, keyin faol tokenni tanlash va ogohlantirish. Commit qiladi."""
    for slot in SLOTS:
        if enc(src, slot):
            await check_slot(src, slot, transport=transport)
    src.token_checked_at = utcnow()
    await settle(db, src)
    await db.commit()


async def _admins(db: AsyncSession) -> list[int]:
    return list((await db.execute(select(User.id).where(User.role == Role.admin, User.is_active.is_(True)))).scalars())


async def settle(db: AsyncSession, src: GpsSource) -> None:
    """Faol tokenni tanlaydi va holat o'zgargan bo'lsa ogohlantiradi (commit chaqiruvchida).
    Yomonlashdi (ok → d:*, d:x → d:y, * → down) — Vaziyat paneli + adminlarga bildirishnoma; yaxshilandi — faoliyat jurnali."""
    pick_active(src)
    old, new = src.alert_state or "ok", state(src)
    if old == new:
        return
    src.alert_state = new
    ref = ("gps_source", src.id)
    if new == "ok" or (old == "down" and new.startswith("d:")):
        situation.activity(db, "act_gps_token_ok", f"GPS tokeni tiklandi: {src.server} ({src.account})",
                           params={"server": src.server, "account": src.account}, district_id=src.district_id, ref=ref)
        return
    dead = [s for s in SLOTS if status(src, s) == "invalid"]
    params = {"server": src.server, "account": ", ".join(dict.fromkeys(account(src, s) for s in dead))}
    if new == "down":
        kind, level = "gps_token_down", SituationLevel.error
        msg = f"GPS ma'lumoti to'xtadi: {src.server} ({params['account']}) — ishlaydigan token yo'q, admin «Ulash» qilsin"
    else:
        kind, level = "gps_token_dead", SituationLevel.warning
        msg = f"GPS tokeni yaroqsiz: {src.server} ({params['account']}) — zaxira tokenga o'tildi, admin «Ulash» qilsin"
    situation.add(db, level, kind, msg, params=params, district_id=src.district_id, ref=ref)
    for uid in await _admins(db):
        notifications.add(db, uid, kind, msg, params=params, ref=ref)
