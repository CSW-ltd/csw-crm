"""Kunlik sinxronlash (PR-B): SmartGPS/Wialon → CRM. Geozonalar (xesh bilan), geozona guruhlari, mashina ↔ GPS obyekti.
FAQAT O'QISH: client.py faqat o'qish buyruqlarini yuboradi. Mahallalar bu yerda o'zgarmaydi (qamrov bosqichida).

Xavfsizlik:
- token: faol (asosiy/zaxira), rad etilsa ikkinchisi — app/gps/tokens.py;
- token egasi `gps_sources.account` bo'lishi kerak (boshqa akkaunt tokeni rad etiladi);
- token o'zgartirish huquqiga ega bo'lsa — rad etiladi (faqat 0x300);
- SmartGPS'dan geozona kelmasa (huquq yo'q, server xatosi) — CRM'dagi geozonalar o'chirilmaydi."""
import hashlib
import json
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secretbox
from app.db.base import utcnow
from app.gps import tokens
from app.gps.client import GpsError, WialonClient
from app.models import Geozone, GeozoneGroup, GpsSource, GpsSyncLog
from app.services import situation
from app.services.gps.importer import Zone, link_vehicles, upsert_zones, zone_from_wialon
from app.services.gps.names import mfy_key

F_BASE, F_ZONES, F_ZGROUPS = 0x1, 0x1000, 0x100000


def _key(s: str | None) -> str:
    return mfy_key(s or "") or (s or "").strip().lower()


async def _upsert_groups(db: AsyncSession, source_id: int, groups: dict[tuple[int, int], tuple[str, list[int]]]) -> dict:
    existing = {(g.ext_resource_id, g.ext_id): g for g in
                (await db.execute(select(GeozoneGroup).where(GeozoneGroup.source_id == source_id))).scalars()}
    n = {"new": 0, "changed": 0, "deactivated": 0}
    for k, (name, zns) in groups.items():
        h = hashlib.sha256(json.dumps([name, zns], ensure_ascii=False).encode()).hexdigest()
        g = existing.get(k)
        if g is None:
            db.add(GeozoneGroup(source_id=source_id, ext_resource_id=k[0], ext_id=k[1], name=name[:200], zone_ids=json.dumps(zns),
                                hash=h, is_active=True))
            n["new"] += 1
        elif g.hash != h or not g.is_active:
            g.name, g.zone_ids, g.hash, g.is_active = name[:200], json.dumps(zns), h, True
            n["changed"] += 1
    for k, g in existing.items():
        if k not in groups and g.is_active:
            g.is_active = False
            n["deactivated"] += 1
    return n


async def _units(c: WialonClient, unit_group: str | None) -> tuple[dict[int, str], bool]:
    """GPS obyektlari {id: nom}. unit_group berilsa — faqat shu guruh a'zolari. Qaytaradi: (obyektlar, guruh topildimi)."""
    units = {int(u["id"]): str(u.get("nm") or "") for u in await c.search("avl_unit", F_BASE) if u.get("id") is not None}
    if not unit_group:
        return units, True
    want = _key(unit_group)
    grp = next((g for g in await c.search("avl_unit_group", F_BASE) if _key(g.get("nm")) == want), None)
    if not grp:
        return {}, False
    members = {int(x) for x in grp.get("u") or []}
    return {i: n for i, n in units.items() if i in members}, True


async def _fetch(c: WialonClient, unit_group: str | None) -> tuple[list, dict, dict, dict[int, str], bool]:
    zones: dict[tuple[int, int], Zone] = {}
    groups: dict[tuple[int, int], tuple[str, list[int]]] = {}
    resources = await c.search("avl_resource", F_BASE | F_ZONES | F_ZGROUPS)
    for res in resources:
        rid = int(res["id"])
        ids = sorted(int(k) for k in (res.get("zl") or {}))
        for z in await c.zone_data(rid, ids) if ids else []:
            zz = zone_from_wialon(z, rid)
            if zz:
                zones[(zz.res, zz.ext)] = zz
        for g in (res.get("zg") or {}).values():
            if g.get("id") is not None and g.get("n"):
                groups[(rid, int(g["id"]))] = (str(g["n"]).strip(), sorted(int(x) for x in g.get("zns") or []))
    units, group_found = await _units(c, unit_group)
    return resources, zones, groups, units, group_found


async def sync_source(db: AsyncSession, src: GpsSource, *, transport=None) -> GpsSyncLog:
    """Bitta manbani sinxronlaydi. Natija gps_sync_log'ga va manbaning holatiga yoziladi (commit qilinadi).
    Token: avval faol, u rad etilsa — ikkinchisi (shu aylanishning o'zida); o'ligi belgilanadi va adminlar ogohlantiriladi."""
    log = GpsSyncLog(source_id=src.id, started_at=utcnow())
    db.add(log)
    stats: dict = {}
    try:
        slots = tokens.candidates(src)
        if not slots:
            raise GpsError("Ishlaydigan token yo'q — admin «Ulash» qilsin" + (f" ({src.last_error})" if src.last_error else ""))
        fetched = None
        for i, slot in enumerate(slots):
            token = secretbox.decrypt(tokens.enc(src, slot) or "")
            authed = False
            try:
                if not token:
                    raise GpsError("Token ochilmadi (GPS_ENC_KEY o'zgarganmi?) — qayta «Ulash» kerak", 8)
                async with WialonClient(src.server, transport=transport) as c:
                    user = await tokens.verify(c, token, tokens.account(src, slot))
                    tokens.set_slot(src, slot, status_="ok", **({"user": user} if user else {}))
                    authed = True
                    fetched = await _fetch(c, src.unit_group)
                break
            except GpsError as e:  # tarmoq xatosida token o'zgarmaydi — keyingi safar qayta uriniladi
                if authed or not e.auth:
                    raise
                tokens.mark_dead(src, slot, e)
                if i == len(slots) - 1:
                    raise
        resources, zones, groups, units, group_found = fetched
        active = (await db.execute(select(func.count()).where(Geozone.source_id == src.id, Geozone.is_active.is_(True)))).scalar_one()
        if not zones and active:
            raise GpsError("SmartGPS'dan birorta geozona kelmadi — CRM'dagi geozonalar o'zgartirilmadi")
        zn, _ = await upsert_zones(db, src.id, zones)
        gn = await _upsert_groups(db, src.id, groups)
        linked = await link_vehicles(db, src.id, src.district_id, units) if src.district_id and group_found else 0
        stats = {"resources": len(resources), "zones": len(zones), **{f"zones_{k}": v for k, v in zn.items()},
                 "groups": len(groups), **{f"groups_{k}": v for k, v in gn.items()}, "units": len(units),
                 "vehicles_linked": linked, "unit_group_found": group_found}
        log.ok = True
        src.last_error = None if group_found else f"Mashinalar guruhi «{src.unit_group}» SmartGPS'da topilmadi"
    except GpsError as e:  # bazaga yozish faqat barcha ma'lumot olingandan keyin — bu yerda yarim yozilgan narsa yo'q
        log.error = str(e)[:500]
        src.last_error = log.error
    log.finished_at = src.last_sync_at = utcnow()
    src.sync_requested_at = None
    log.stats = json.dumps(stats, ensure_ascii=False) if stats else None
    situation.activity(db, "act_gps_sync", (f"GPS sinxronlandi: {src.server} — geozona {stats.get('zones', 0)} (yangi {stats.get('zones_new', 0)}, "
                                            f"o'zgargan {stats.get('zones_changed', 0)}, o'chgan {stats.get('zones_deactivated', 0)}), "
                                            f"mashina bog'lanishi {stats.get('vehicles_linked', 0)}") if log.ok
                       else f"GPS sinxronlash xatosi: {src.server} — {log.error}",
                       params={"server": src.server, "ok": log.ok, **stats}, district_id=src.district_id)
    await tokens.settle(db, src)
    await db.commit()
    return log


def local_now(now: datetime | None = None) -> datetime:
    """Toshkent vaqti (UTC+5, yozgi vaqt yo'q), naive."""
    from datetime import timedelta
    return (now or utcnow()) + timedelta(hours=5)


def due(src: GpsSource, now: datetime, sync_time: str) -> bool:
    """Sinxronlash kerakmi: so'ralgan, yangi token, yoki bugungi kunlik vaqt o'tgan va bugun hali sinxronlanmagan."""
    if not src.is_active or not tokens.has_any(src):
        return False
    if src.sync_requested_at is not None or tokens.any_status(src, "pending"):
        return True
    if not tokens.any_status(src, "ok"):
        return False
    loc = local_now(now)
    try:
        h, m = (int(x) for x in sync_time.split(":"))
    except ValueError:
        h, m = 5, 30
    if (loc.hour, loc.minute) < (h, m):
        return False
    return src.last_sync_at is None or local_now(src.last_sync_at).date() < loc.date()
