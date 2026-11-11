"""Socket.IO server: jonli yangilanishlar.

Xonalar:
  managers          — admin va manager
  gps:{district_id} — shu tuman GPS xodimlari
  gps:all           — tumani belgilanmagan GPS xodimlari
  driver:{user_id}  — haydovchining o'zi
  user:{user_id}    — har bir xodimning shaxsiy xonasi
"""
from http.cookies import SimpleCookie

import socketio

from app.core.config import get_settings
from app.core.portals import host_allows
from app.core.security import ACCESS, decode_token

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=get_settings().cors_list)


@sio.event
async def connect(sid, environ, auth):
    token = (auth or {}).get("token")
    if not token:
        cookie = SimpleCookie(environ.get("HTTP_COOKIE", ""))
        token = cookie["access_token"].value if "access_token" in cookie else None
    data = decode_token(token, ACCESS) if token else None
    if not data:
        return False  # ulanish rad etiladi
    role, uid = data["role"], data["sub"]
    if not host_allows(environ.get("HTTP_HOST"), role):
        return False  # boshqa rol portali (ROLE_HOSTS)
    await sio.enter_room(sid, f"user:{uid}")
    if role in ("admin", "manager"):
        await sio.enter_room(sid, "managers")
    if role == "admin":
        await sio.enter_room(sid, "admins")  # Vaziyat paneli
    if role in ("manager", "accountant"):
        # Vaziyat paneli: faqat o'z tumanlari hodisalari jonli keladi
        for d in await _user_districts(uid):
            await sio.enter_room(sid, f"sit:{d}")
    elif role == "gps":
        # Tuman foydalanuvchining o'zidan olinadi (mijoz yubormaydi) — yangi qizil karta jonli tushishi uchun
        district = await _user_district(uid)
        await sio.enter_room(sid, f"gps:{district}" if district else "gps:all")
    elif role == "driver":
        await sio.enter_room(sid, f"driver:{uid}")
    elif role == "operator":
        await sio.enter_room(sid, "operators")  # o'zi ochgan arizalar holati jonli
    elif role == "legal":
        await sio.enter_room(sid, "legal")      # yangi murojaatlar navbati
    return True


async def _user_district(uid) -> int | None:
    from app.db.session import SessionLocal
    from app.models import User
    try:
        async with SessionLocal() as db:
            u = await db.get(User, int(uid))
            return u.district_id if u else None
    except Exception:  # noqa: BLE001 — baza vaqtincha yo'q bo'lsa umumiy xonaga
        return None


async def _user_districts(uid) -> list[int]:
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models import UserDistrict
    try:
        async with SessionLocal() as db:
            return list((await db.execute(select(UserDistrict.district_id).where(UserDistrict.user_id == int(uid)))).scalars())
    except Exception:  # noqa: BLE001
        return []


async def emit_request_updated(payload: dict) -> None:
    rooms = ["managers", "operators", "legal", "gps:all", f"gps:{payload['district_id']}"]
    if payload.get("driver_id"):
        rooms.append(f"driver:{payload['driver_id']}")
    await sio.emit("request:updated", payload, room=rooms)


async def emit_driver_location(payload: dict) -> None:
    await sio.emit("driver:location", payload, room=["managers", "gps:all", f"gps:{payload['district_id']}"])


async def emit_situation(payload: dict) -> None:
    """Vaziyat paneli: admin — hammasi; manager va buxgalter — o'z tumanlari (faoliyat jurnali jonli yuborilmaydi)."""
    rooms = ["admins"] + ([f"sit:{payload['district_id']}"] if payload.get("district_id") else [])
    await sio.emit("situation:new", payload, room=rooms)


async def emit_notification(user_id: int, payload: dict) -> None:
    """Shaxsiy bildirishnoma — faqat shu xodimning xonasiga."""
    await sio.emit("notification:new", payload, room=f"user:{user_id}")


async def emit_appeal_updated(payload: dict) -> None:
    """Murojaat yaratildi/ko'rib chiqildi: yuridik bo'lim navbati va operator ekrani."""
    await sio.emit("appeal:updated", payload, room=["legal", "operators", "managers"])

