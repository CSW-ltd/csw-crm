"""GPS ulanishlari (PR-B), API tomoni: manba yaratish, «Ulash» havolasi, tokenni shifrlab saqlash, sinxronlashni so'rash.
API SmartGPS'ga HECH QACHON chiqmaydi — tokenni tekshirish va sinxronlashni gps-worker bajaradi (30 soniya ichida)."""
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secretbox
from app.core.config import get_settings
from app.core.errors import AppError, invalid, not_found
from app.db.base import utcnow
from app.gps import tokens
from app.gps.client import login_url, valid_token
from app.models import AppSetting, District, Geozone, GeozoneGroup, GpsSource, GpsSyncLog, User, VehicleLink
from app.services import situation

SYSTEMS = ("smartgps", "wialon")
HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+(:\d{2,5})?$")
WORKER_ALIVE_S = 120


def _server(raw: str) -> str:
    """Faqat host (https). Lokal/test muhitda http://host:port ham (soxta SmartGPS uchun)."""
    s = (raw or "").strip().rstrip("/").lower()
    if s.startswith("https://"):
        s = s[8:]
    if s.startswith("http://"):
        if get_settings().app_env == "production":
            raise invalid("gps_bad_server", "Server manzili https bo'lishi kerak")
        return s
    if not HOST_RE.match(s):
        raise invalid("gps_bad_server", "Server manzili noto'g'ri (masalan: gps.example.uz)")
    return s


async def _get(db: AsyncSession, source_id: int) -> GpsSource:
    src = await db.get(GpsSource, source_id)
    if not src:
        raise not_found("GPS ulanishi")
    return src


async def _district(db: AsyncSession, district_id: int | None) -> int | None:
    if district_id is None:
        return None
    d = await db.get(District, district_id)
    if not d or not d.is_active:
        raise invalid("district_inactive", "Tuman topilmadi yoki faol emas")
    return d.id


def _iso(d: datetime | None) -> str | None:
    return d.isoformat(timespec="seconds") if d else None


async def overview(db: AsyncSession) -> dict:
    row = await db.get(AppSetting, "gps_worker_seen")
    seen = datetime.fromisoformat(row.value) if row else None
    from sqlalchemy import func
    zones = dict((await db.execute(select(Geozone.source_id, func.count()).where(Geozone.is_active.is_(True))
                                   .group_by(Geozone.source_id))).all())
    groups = dict((await db.execute(select(GeozoneGroup.source_id, func.count()).where(GeozoneGroup.is_active.is_(True))
                                    .group_by(GeozoneGroup.source_id))).all())
    links = dict((await db.execute(select(VehicleLink.source_id, func.count()).group_by(VehicleLink.source_id))).all())
    districts = {d.id: d.name for d in (await db.execute(select(District))).scalars()}
    out = []
    for s in (await db.execute(select(GpsSource).order_by(GpsSource.id))).scalars():
        last = (await db.execute(select(GpsSyncLog).where(GpsSyncLog.source_id == s.id).order_by(GpsSyncLog.id.desc()).limit(1))).scalar_one_or_none()
        out.append({"id": s.id, "system": s.system, "server": s.server, "account": s.account, "district_id": s.district_id,
                    "district": districts.get(s.district_id), "unit_group": s.unit_group, "is_active": s.is_active,
                    "token_status": s.token_status if s.token_enc else "none", "token_user": s.token_user,
                    "token_set_at": _iso(s.token_set_at), "backup_account": s.backup_account,
                    "backup_token_status": tokens.status(s, "backup"), "backup_token_user": s.backup_token_user,
                    "backup_token_set_at": _iso(s.backup_token_set_at), "active_slot": tokens.active(s),
                    "token_checked_at": _iso(s.token_checked_at), "alert_state": s.alert_state or "ok", "sync_requested": s.sync_requested_at is not None,
                    "last_sync_at": _iso(s.last_sync_at), "last_error": s.last_error, "zones": zones.get(s.id, 0),
                    "groups": groups.get(s.id, 0), "vehicles_linked": links.get(s.id, 0),
                    "last_stats": json.loads(last.stats) if last and last.stats else None})
    alive = bool(seen and utcnow() - seen < timedelta(seconds=WORKER_ALIVE_S))
    return {"worker": {"seen_at": _iso(seen), "alive": alive, "enabled": get_settings().gps_worker_enabled},
            "encryption_ready": secretbox.available(), "sources": out}


async def create(db: AsyncSession, actor: User, system: str, server: str, account: str, district_id: int | None,
                 unit_group: str | None) -> GpsSource:
    if system not in SYSTEMS:
        raise invalid("gps_bad_system", "Tizim: smartgps yoki wialon")
    server, account = _server(server), (account or "").strip()
    if not account:
        raise invalid("gps_account_required", "SmartGPS akkaunt (login) nomini kiriting")
    exists = (await db.execute(select(GpsSource).where(GpsSource.server == server, GpsSource.account == account))).scalar_one_or_none()
    if exists:
        raise AppError(409, "gps_source_exists", "Bu server va akkaunt uchun ulanish allaqachon bor")
    src = GpsSource(system=system, server=server, account=account[:100], district_id=await _district(db, district_id),
                    unit_group=(unit_group or "").strip()[:150] or None, token_status="none", is_active=True)
    db.add(src)
    await db.flush()
    situation.activity(db, "act_gps_connect", f"GPS ulanishi qo'shildi: {server} ({account})", params={"server": server},
                       actor_id=actor.id, district_id=src.district_id)
    await db.commit()
    return src


async def update(db: AsyncSession, source_id: int, data: dict) -> GpsSource:
    src = await _get(db, source_id)
    if "district_id" in data:
        src.district_id = await _district(db, data["district_id"])
    if "unit_group" in data:
        src.unit_group = (data["unit_group"] or "").strip()[:150] or None
    if "account" in data and data["account"] and data["account"].strip() != src.account:
        src.account = data["account"].strip()[:100]
        if src.token_enc:
            src.token_status = "pending"  # token egasi qayta tekshiriladi
        if src.backup_token_enc and not src.backup_account:
            src.backup_token_status = "pending"
    if "backup_account" in data:
        acc = (data["backup_account"] or "").strip()[:100] or None
        if acc != src.backup_account:
            src.backup_account = acc
            if src.backup_token_enc:
                src.backup_token_status = "pending"
    if "is_active" in data and data["is_active"] is not None:
        src.is_active = bool(data["is_active"])
    await db.commit()
    return src


def connect_url(src: GpsSource, redirect: str, request_host: str | None) -> str:
    """SmartGPS login sahifasi havolasi. redirect — shu admin sahifasining o'zi bo'lishi kerak (boshqa saytga token ketmasin)."""
    u = urlparse(redirect or "")
    local = u.hostname in ("localhost", "127.0.0.1")
    if u.scheme not in ("https", "http") or (u.scheme == "http" and not local) or not u.netloc:
        raise invalid("gps_bad_redirect", "Qaytish manzili noto'g'ri")
    if request_host and u.netloc.lower() != request_host.lower():
        raise invalid("gps_bad_redirect", "Qaytish manzili shu sayt bo'lishi kerak")
    path = u.path.rstrip("/")
    if not (path.endswith(f"/gps-callback/{src.id}") or path.endswith(f"/gps-callback/{src.id}/backup")):
        raise invalid("gps_bad_redirect", "Qaytish manzili noto'g'ri")
    return login_url(src.server, redirect)


def _slot(slot: str) -> str:
    if slot not in tokens.SLOTS:
        raise invalid("gps_bad_slot", "Token turi: main yoki backup")
    return slot


async def set_token(db: AsyncSession, actor: User, source_id: int, token: str, slot: str = "main") -> GpsSource:
    """Tokenni shifrlab saqlaydi (parol emas — SmartGPS «Ulash» sahifasi bergan faqat o'qish tokeni). Tekshiruv — worker'da."""
    src = await _get(db, source_id)
    slot, token = _slot(slot), (token or "").strip()
    if not valid_token(token):
        raise invalid("gps_bad_token", "Token noto'g'ri ko'rinishda")
    if not secretbox.available():
        raise AppError(503, "gps_encryption_off", "GPS_ENC_KEY sozlanmagan — token saqlanmaydi")
    tokens.set_slot(src, slot, token_enc=secretbox.encrypt(token), status_="pending", user=None, set_at=utcnow())
    if slot == "main" or tokens.status(src, "main") != "ok":
        src.sync_requested_at = utcnow()
    src.last_error = None
    label = "zaxira tokeni" if slot == "backup" else "tokeni"
    situation.activity(db, "act_gps_connect", f"GPS {label} yangilandi: {src.server} ({tokens.account(src, slot)})",
                       params={"server": src.server, "slot": slot}, actor_id=actor.id, district_id=src.district_id)
    await db.commit()
    return src


async def clear_token(db: AsyncSession, actor: User, source_id: int, slot: str = "main") -> GpsSource:
    src = await _get(db, source_id)
    slot = _slot(slot)
    tokens.set_slot(src, slot, token_enc=None, status_="none", user=None)
    tokens.pick_active(src)
    if not tokens.has_any(src):
        src.sync_requested_at = None
    src.alert_state = tokens.state(src)  # admin o'zi o'chirdi — ogohlantirish emas
    label = "zaxira tokeni" if slot == "backup" else "tokeni"
    situation.activity(db, "act_gps_connect", f"GPS {label} o'chirildi: {src.server} ({tokens.account(src, slot)})",
                       params={"server": src.server, "slot": slot}, actor_id=actor.id, district_id=src.district_id)
    await db.commit()
    return src


async def request_sync(db: AsyncSession, source_id: int) -> GpsSource:
    src = await _get(db, source_id)
    if not tokens.has_any(src):
        raise invalid("gps_not_connected", "Avval SmartGPS'ga ulang")
    src.sync_requested_at = utcnow()
    await db.commit()
    return src


async def logs(db: AsyncSession, source_id: int, limit: int = 20) -> list[dict]:
    await _get(db, source_id)
    rows = (await db.execute(select(GpsSyncLog).where(GpsSyncLog.source_id == source_id).order_by(GpsSyncLog.id.desc()).limit(limit))).scalars()
    return [{"id": r.id, "started_at": _iso(r.started_at), "finished_at": _iso(r.finished_at), "ok": r.ok,
             "stats": json.loads(r.stats) if r.stats else None, "error": r.error} for r in rows]
