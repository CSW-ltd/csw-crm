"""GPS eksport importi (PR-A): csw-gps-agent `gps_eksport.py` natijasi zip ko'rinishida.

Zip ichida (papka nomi muhim emas):
  geojson/*.geojson        — akkauntdagi barcha geozonalar (chiziq = tayoqcha, poligon, doira), GeoJSON [lng, lat]
  mfy_xarita/<tuman>.json  — qamrov skripti ko'radigan mahalla ↔ tayoqcha va chegara, tuman mashinalari

Ikki bosqich: `analyze` (dry-run — bazaga yozmaydi) va `apply`. Har bo'lim (tuman) CRM tumaniga admin tomonidan qo'lda
bog'lanadi (`mapping`). Qayta import: geozona (source, resurs, id) + xesh bo'yicha — o'zgargani yangilanadi, yo'qolgani
is_active=False (o'chirilmaydi); ikkinchi importda o'zgarish 0. Mashina avtomatik yaratilmaydi."""
import hashlib
import io
import json
import zipfile
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, invalid
from app.models import District, Geozone, GpsSource, Mahalla, MahallaGeozone, User, Vehicle, VehicleLink
from app.services import situation
from app.services.gps.names import match_unit, mfy_key

MAX_ZIP = 10 * 1024 * 1024  # nginx cheklovi 12 MB — zip'ga faqat geojson/ va mfy_xarita/ papkalari kiritiladi
MAX_UNZIPPED = 200 * 1024 * 1024
KINDS = {"LineString": "line", "Polygon": "polygon", "Point": "circle"}


@dataclass
class Zone:
    res: int
    ext: int
    kind: str
    name: str | None
    width: float | None
    radius: float | None
    coords: list
    color: str | None
    hash: str = ""
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)  # min_lat, max_lat, min_lng, max_lng


@dataclass
class Bundle:
    server: str
    account: str
    zones: dict[tuple[int, int], Zone] = field(default_factory=dict)
    sections: list[dict] = field(default_factory=list)


def _num(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _zone(feat: dict) -> Zone | None:
    g, p = feat.get("geometry") or {}, feat.get("properties") or {}
    kind = KINDS.get(g.get("type"))
    try:
        res, ext = int(p["resurs_id"]), int(p["id"])
    except (KeyError, TypeError, ValueError):
        return None
    c = g.get("coordinates")
    if not kind or not c:
        return None
    coords = c[0] if kind == "polygon" else c
    pts = [coords] if kind == "circle" else coords
    try:
        lngs, lats = [float(q[0]) for q in pts], [float(q[1]) for q in pts]
    except (TypeError, ValueError, IndexError):
        return None
    z = Zone(res, ext, kind, (str(p.get("nom") or "")[:200] or None), _num(p.get("kenglik_m")), _num(p.get("radius_m")),
             coords, (str(p.get("rang") or "")[:9] or None))
    z.bbox = (min(lats), max(lats), min(lngs), max(lngs))
    z.hash = hashlib.sha256(json.dumps([z.kind, z.coords, z.width, z.radius, z.name, z.color], ensure_ascii=False,
                                       separators=(",", ":")).encode()).hexdigest()
    return z


def _color(c) -> str:
    try:
        return "#%06x" % (int(c) & 0xFFFFFF)
    except (TypeError, ValueError):
        return "#3388ff"


def zone_from_wialon(z: dict, resource_id: int) -> Zone | None:
    """Wialon `resource/get_zone_data` (flags 0x1F) natijasidan Zone — gps_eksport.py bilan aynan bir xil GeoJSON va xesh
    (zip importi va jonli sinxron bir-birini «o'zgardi» deb ko'rmasligi uchun)."""
    pts = [[p["x"], p["y"]] for p in z.get("p") or [] if "x" in p and "y" in p]
    t = z.get("t")
    if not pts:
        return None
    if t == 1:
        geom = {"type": "LineString", "coordinates": pts if len(pts) > 1 else pts * 2}
    elif t == 2:
        geom = {"type": "Polygon", "coordinates": [pts + ([pts[0]] if pts[0] != pts[-1] else [])]}
    elif t == 3:
        geom = {"type": "Point", "coordinates": pts[0]}
    else:
        return None
    props = {"resurs_id": resource_id, "id": z.get("id"), "nom": z.get("n"), "kenglik_m": z.get("w") if t == 1 else None,
             "radius_m": (z.get("p") or [{}])[0].get("r") if t == 3 else None, "rang": _color(z.get("c"))}
    return _zone({"geometry": geom, "properties": props})


async def upsert_zones(db: AsyncSession, source_id: int, zones: dict[tuple[int, int], Zone]) -> tuple[dict, dict]:
    """Geozonalarni xesh bo'yicha yangilaydi; ro'yxatda yo'qlari is_active=False. Qaytaradi: (sonlar, {kalit: geozone.id})."""
    existing = {(g.ext_resource_id, g.ext_id): g for g in (await db.execute(select(Geozone).where(Geozone.source_id == source_id))).scalars()}
    n = {"new": 0, "changed": 0, "deactivated": 0}
    for k, z in zones.items():
        g = existing.get(k)
        if g is None:
            g = Geozone(source_id=source_id, ext_resource_id=z.res, ext_id=z.ext)
            db.add(g)
            existing[k] = g
            n["new"] += 1
        elif g.hash == z.hash and g.is_active:
            continue
        else:
            n["changed"] += 1
        g.kind, g.name, g.width_m, g.radius_m, g.color, g.hash, g.is_active = z.kind, z.name, z.width, z.radius, z.color, z.hash, True
        g.coords = json.dumps(z.coords, separators=(",", ":"))
        g.min_lat, g.max_lat, g.min_lng, g.max_lng = z.bbox
    for k, g in existing.items():
        if k not in zones and g.is_active:
            g.is_active = False
            n["deactivated"] += 1
    await db.flush()
    return n, {k: g.id for k, g in existing.items() if k in zones}


def read_zip(content: bytes) -> Bundle:
    if len(content) > MAX_ZIP:
        raise AppError(413, "import_too_large", "Zip 10 MB dan katta — faqat geojson/ va mfy_xarita/ papkalarini qo'shing")
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise invalid("import_bad_zip", "Fayl zip emas yoki buzilgan")
    names = [i for i in zf.infolist() if not i.is_dir()]
    gj = [i for i in names if i.filename.lower().endswith(".geojson") and "/geojson/" in f"/{i.filename}".replace("\\", "/")]
    mx = [i for i in names if i.filename.lower().endswith(".json") and "/mfy_xarita/" in f"/{i.filename}".replace("\\", "/")]
    if sum(i.file_size for i in gj + mx) > MAX_UNZIPPED:
        raise AppError(413, "import_too_large", "Zip ichidagi fayllar juda katta")
    if not mx:
        raise invalid("import_no_mfy_map", "Zip ichida mfy_xarita/<tuman>.json topilmadi (agentning yangi gps_eksport.py si kerak)")
    if not gj:
        raise invalid("import_no_zones", "Zip ichida geojson/*.geojson topilmadi")
    try:
        maps = [json.loads(zf.read(i).decode("utf-8-sig")) for i in mx]
        feats = [f for i in gj for f in (json.loads(zf.read(i).decode("utf-8-sig")).get("features") or [])]
    except (ValueError, UnicodeDecodeError, AttributeError):
        raise invalid("import_bad_json", "Zip ichidagi JSON fayl o'qilmadi")
    accounts = {(str(m.get("tizim") or ""), str(m.get("akkaunt") or "")) for m in maps}
    if len(accounts) != 1 or not all(next(iter(accounts))):
        raise invalid("import_mixed_accounts", "Bitta zip — bitta GPS akkaunti bo'lishi kerak")
    server, account = next(iter(accounts))
    b = Bundle(server=server[:120], account=account[:100])
    for f in feats:
        if (f.get("properties") or {}).get("tizim") not in (None, server):
            continue
        z = _zone(f)
        if z:
            b.zones[(z.res, z.ext)] = z
    for m in sorted(maps, key=lambda x: str(x.get("tuman") or "")):
        mahallas = []
        for x in m.get("mahallalar") or []:
            key = str(x.get("kalit") or "") or mfy_key(x.get("nomi"))
            if not key:
                continue
            sticks = [(int(r), int(i)) for r, i in (x.get("tayoqchalar") or [])]
            ch = x.get("chegara")
            mahallas.append({"name": str(x.get("nomi") or key)[:150], "key": key[:150], "sticks": sticks,
                             "boundary": (int(ch[0]), int(ch[1])) if ch else None})
        units = {int(u["id"]): str(u.get("nomi") or "") for u in (m.get("mashinalar") or []) if u.get("id") is not None}
        b.sections.append({"tuman": str(m.get("tuman") or "—"), "mahallas": mahallas, "units": units})
    return b


async def _source(db: AsyncSession, b: Bundle) -> GpsSource | None:
    return (await db.execute(select(GpsSource).where(GpsSource.server == b.server, GpsSource.account == b.account))).scalar_one_or_none()


async def _suggest_district(db: AsyncSession, src: GpsSource | None, keys: list[str]) -> int | None:
    """Oldingi importdagi bog'lanish: shu akkauntning shu kalitli mahallalari ko'p bo'lgan tuman."""
    if not src or not keys:
        return None
    rows = (await db.execute(select(Mahalla.district_id).where(Mahalla.source_id == src.id, Mahalla.name_key.in_(keys)))).scalars().all()
    return Counter(rows).most_common(1)[0][0] if rows else None


def _vehicle_matches(units: dict[int, str], vehicles: list[Vehicle]) -> tuple[dict[int, int], list[str]]:
    """vehicle_id → unit_id (bitta unit faqat bitta mashinaga). Qaytaradi: moslar va topilmagan CRM mashinalari."""
    out, used, missing = {}, set(), []
    for v in vehicles:
        uid = match_unit(units, v.plate)
        if uid is None or uid in used:
            missing.append(v.plate)
            continue
        used.add(uid)
        out[v.id] = uid
    return out, missing


async def link_vehicles(db: AsyncSession, source_id: int, district_id: int, units: dict[int, str]) -> int:
    """Tumanning faol CRM mashinalari ↔ GPS obyektlari (davlat raqami bo'yicha). Mashina yaratilmaydi. Qaytaradi: o'zgargan bog'lanishlar."""
    vehicles = list((await db.execute(select(Vehicle).where(Vehicle.district_id == district_id, Vehicle.is_active.is_(True)))).scalars())
    matched, _ = _vehicle_matches(units, vehicles)
    links = {l.ext_unit_id: l for l in (await db.execute(select(VehicleLink).where(VehicleLink.source_id == source_id))).scalars()}
    vids, n = {v.id for v in vehicles}, 0
    for l in list(links.values()):  # shu tuman mashinasining eski (endi mos kelmagan) bog'lanishi
        if l.vehicle_id in vids and matched.get(l.vehicle_id) != l.ext_unit_id:
            await db.delete(l)
            links.pop(l.ext_unit_id)
    for vid, uid in matched.items():
        l = links.get(uid)
        if l is None:
            db.add(VehicleLink(vehicle_id=vid, source_id=source_id, ext_unit_id=uid, ext_name=units[uid][:150], has_gps=True))
            n += 1
        elif l.vehicle_id != vid or l.ext_name != units[uid][:150]:
            l.vehicle_id, l.ext_name = vid, units[uid][:150]
            n += 1
    return n


async def analyze(db: AsyncSession, b: Bundle, mapping: dict[str, int] | None = None) -> dict:
    """Dry-run: geozona o'zgarishlari va har bo'lim (tuman) bo'yicha sonlar. Bazaga yozmaydi."""
    mapping = mapping or {}
    src = await _source(db, b)
    old = {}
    if src:
        old = {(g.ext_resource_id, g.ext_id): (g.hash, g.is_active) for g in
               (await db.execute(select(Geozone).where(Geozone.source_id == src.id))).scalars()}
    new = sum(1 for k in b.zones if k not in old)
    changed = sum(1 for k, z in b.zones.items() if k in old and (old[k][0] != z.hash or not old[k][1]))
    gone = sum(1 for k, (_, act) in old.items() if act and k not in b.zones)
    kinds = Counter(z.kind for z in b.zones.values())
    districts = {d.id: d for d in (await db.execute(select(District))).scalars()}
    sections = []
    for s in b.sections:
        sticks = {k for m in s["mahallas"] for k in m["sticks"]}
        did = mapping.get(s["tuman"])
        vehicles = []
        if did:
            vehicles = list((await db.execute(select(Vehicle).where(Vehicle.district_id == did, Vehicle.is_active.is_(True))
                                              .order_by(Vehicle.plate))).scalars())
        matched, missing = _vehicle_matches(s["units"], vehicles)
        linked_units = set(matched.values())
        sections.append({
            "tuman": s["tuman"], "district_id": did, "district": districts[did].name if did in districts else None,
            "suggested_district_id": await _suggest_district(db, src, [m["key"] for m in s["mahallas"]]),
            "mahallas": len(s["mahallas"]), "sticks": len(sticks),
            "boundaries": sum(1 for m in s["mahallas"] if m["boundary"]),
            "no_boundary": [m["name"] for m in s["mahallas"] if not m["boundary"]][:100],
            "missing_zones": sum(1 for m in s["mahallas"] for k in m["sticks"] + ([m["boundary"]] if m["boundary"] else [])
                                 if k not in b.zones),
            "units": len(s["units"]), "vehicles_matched": len(matched),
            "vehicles_missing": missing[:100],  # CRM'da bor, GPS'da topilmadi
            "units_unmatched": [nm for uid, nm in sorted(s["units"].items()) if uid not in linked_units][:100] if did else [],
        })
    return {"server": b.server, "account": b.account, "source_id": src.id if src else None,
            "zones": {"total": len(b.zones), "line": kinds.get("line", 0), "polygon": kinds.get("polygon", 0),
                      "circle": kinds.get("circle", 0), "new": new, "changed": changed, "deactivated": gone},
            "sections": sections}


async def apply(db: AsyncSession, actor: User, b: Bundle, mapping: dict[str, int]) -> dict:
    """Import: manba, geozonalar (xesh bilan), bog'langan bo'limlar uchun mahallalar, tayoqcha/chegara va mashina bog'lanishi."""
    tumans = {s["tuman"] for s in b.sections}
    mapping = {k: int(v) for k, v in (mapping or {}).items() if v and k in tumans}
    if not mapping:
        raise invalid("district_required", "Kamida bitta bo'lim uchun CRM tumanini tanlang")
    if len(set(mapping.values())) != len(mapping):
        raise invalid("district_twice", "Bitta CRM tumani ikki bo'limga tanlangan")
    for did in mapping.values():
        d = await db.get(District, did)
        if not d or not d.is_active:
            raise invalid("district_inactive", "Tuman topilmadi yoki faol emas")
    report = await analyze(db, b, mapping)

    src = await _source(db, b)
    if not src:
        src = GpsSource(system="smartgps" if "smartgps" in b.server.lower() else "wialon", server=b.server, account=b.account)
        db.add(src)
        await db.flush()
    # --- geozonalar
    _, zid = await upsert_zones(db, src.id, b.zones)

    # --- bo'limlar (tumanlar)
    stats = {"mahallas_created": 0, "mahallas_updated": 0, "mahallas_deactivated": 0, "links_changed": 0, "vehicles_linked": 0}
    for s in b.sections:
        did = mapping.get(s["tuman"])
        if not did:
            continue
        rows = {m.name_key: m for m in (await db.execute(select(Mahalla).where(Mahalla.district_id == did))).scalars()}
        seen = set()
        for x in s["mahallas"]:
            m = rows.get(x["key"])
            if m is None:
                m = Mahalla(district_id=did, name=x["name"], name_key=x["key"], source_id=src.id, is_active=True)
                db.add(m)
                rows[x["key"]] = m
                stats["mahallas_created"] += 1
            elif m.name != x["name"] or not m.is_active or m.source_id != src.id:
                m.name, m.is_active, m.source_id = x["name"], True, src.id
                stats["mahallas_updated"] += 1
            seen.add(x["key"])
        for key, m in rows.items():
            if key not in seen and m.source_id == src.id and m.is_active:
                m.is_active = False
                stats["mahallas_deactivated"] += 1
        await db.flush()
        for x in s["mahallas"]:
            m = rows[x["key"]]
            want = {(zid[k], "stick") for k in x["sticks"] if k in zid}
            if x["boundary"] and x["boundary"] in zid:
                want.add((zid[x["boundary"]], "boundary"))
            have = {(r.geozone_id, r.role) for r in (await db.execute(select(MahallaGeozone).where(MahallaGeozone.mahalla_id == m.id))).scalars()}
            if want != have:
                await db.execute(delete(MahallaGeozone).where(MahallaGeozone.mahalla_id == m.id))
                db.add_all([MahallaGeozone(mahalla_id=m.id, geozone_id=g, role=r) for g, r in sorted(want)])
                stats["links_changed"] += 1
        # --- mashinalar
        stats["vehicles_linked"] += await link_vehicles(db, src.id, did, s["units"])
    z = report["zones"]
    situation.activity(db, "act_gps_import", f"GPS geozonalari import qilindi: {b.server} — geozona {z['total']} (yangi {z['new']}, "
                                             f"o'zgargan {z['changed']}, o'chgan {z['deactivated']}), tumanlar {len(mapping)}",
                       params={"server": b.server, **z, "districts": len(mapping), **stats}, actor_id=actor.id)
    await db.commit()
    return {**report, "applied": True, "source_id": src.id, "stats": stats}


async def summary(db: AsyncSession) -> dict:
    """Tumanlar bo'yicha: faol mahallalar, tayoqchalar, chegarasi bor/yo'q, GPS'ga bog'langan mashinalar; manbalar."""
    from sqlalchemy import func
    districts = {d.id: d.name for d in (await db.execute(select(District))).scalars()}
    mah = (await db.execute(select(Mahalla.district_id, func.count()).where(Mahalla.is_active.is_(True)).group_by(Mahalla.district_id))).all()
    q = (select(Mahalla.district_id, MahallaGeozone.role, func.count(func.distinct(MahallaGeozone.geozone_id)))
         .join(MahallaGeozone, MahallaGeozone.mahalla_id == Mahalla.id).join(Geozone, Geozone.id == MahallaGeozone.geozone_id)
         .where(Mahalla.is_active.is_(True), Geozone.is_active.is_(True)).group_by(Mahalla.district_id, MahallaGeozone.role))
    links = {(d, r): n for d, r, n in (await db.execute(q)).all()}
    veh = dict((await db.execute(select(Vehicle.district_id, func.count(func.distinct(VehicleLink.vehicle_id)))
                                 .join(VehicleLink, VehicleLink.vehicle_id == Vehicle.id).group_by(Vehicle.district_id))).all())
    rows = [{"district_id": d, "district": districts.get(d), "mahallas": n, "sticks": links.get((d, "stick"), 0),
             "boundaries": links.get((d, "boundary"), 0), "vehicles_linked": veh.get(d, 0)} for d, n in mah]
    srcs = []
    for s in (await db.execute(select(GpsSource).order_by(GpsSource.id))).scalars():
        n, last = (await db.execute(select(func.count(), func.max(Geozone.updated_at))
                                    .where(Geozone.source_id == s.id, Geozone.is_active.is_(True)))).one()
        srcs.append({"id": s.id, "system": s.system, "server": s.server, "account": s.account, "zones": n, "updated_at": last})
    return {"districts": sorted(rows, key=lambda r: r["district"] or ""), "sources": srcs}
