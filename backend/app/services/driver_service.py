"""Haydovchi oqimi: yo'lga chiqish → rasmlar → dalolatnoma → yakunlash yoki bajarib bo'lmadi."""
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app import realtime
from app.core.errors import conflict, invalid, not_found
from app.db.base import utcnow
from app.models import Act, ActFile, Request, User
from app.models.enums import (
    FailReason,
    FileKind,
    LocationStatus,
    RequestStatus,
    SituationLevel,
)
from app.repositories import requests as req_repo
from app.repositories import settings as settings_repo
from app.services import events, situation
from app.services.files import UploadedImage
from app.services.geo import distance_m, valid_coords
from app.services.storage import Storage


async def _own_request(db: AsyncSession, driver: User, request_id: int, lock: bool = False) -> Request:
    req = await req_repo.by_id(db, request_id, lock=lock)
    if not req or req.driver_id != driver.id:
        raise not_found("request")
    return req


async def set_enroute(db: AsyncSession, driver: User, request_id: int) -> Request:
    req = await _own_request(db, driver, request_id, lock=True)
    if req.status != RequestStatus.assigned:
        raise conflict("bad_status", "Ariza \"biriktirilgan\" holatida emas")
    req.status = RequestStatus.enroute
    events.record(db, req, driver.id)
    await db.commit()
    await events.broadcast(req)
    return req


async def upload_file(db: AsyncSession, storage: Storage, driver: User, request_id: int,
                      kind: FileKind, image: UploadedImage, lat: float | None, lng: float | None,
                      accuracy_m: int | None = None) -> ActFile:
    req = await _own_request(db, driver, request_id, lock=True)
    if req.status not in (RequestStatus.enroute, RequestStatus.onsite):
        raise conflict("bad_status", "Rasmni faqat yo'lda yoki joyida yuklash mumkin")
    files = await req_repo.files_for(db, req.id)
    if kind == FileKind.before:
        if lat is None or lng is None or not valid_coords(lat, lng):
            raise invalid("gps_required", "\"Oldin\" rasmi uchun GPS joylashuv kerak")
    elif FileKind.before not in files:
        raise conflict("before_photo_first", "Avval \"oldin\" rasmini yuklang")
    if kind == FileKind.after and (lat is None or lng is None):
        raise invalid("gps_required", "\"Keyin\" rasmi uchun GPS joylashuv kerak")

    key = f"requests/{req.id}/{kind.value}-{uuid4().hex}.{image.ext}"
    await run_in_threadpool(storage.put, key, image.data, image.content_type)
    row = files.get(kind)  # qayta olish mumkin: oxirgisi saqlanadi
    if row:
        row.storage_key, row.content_type, row.size_bytes, row.lat, row.lng = key, image.content_type, len(image.data), lat, lng
        row.accuracy_m = accuracy_m
    else:
        row = ActFile(request_id=req.id, kind=kind, storage_key=key, content_type=image.content_type,
                      size_bytes=len(image.data), lat=lat, lng=lng, accuracy_m=accuracy_m, uploaded_by_id=driver.id)
        db.add(row)
    if kind == FileKind.before and req.status == RequestStatus.enroute:
        req.status = RequestStatus.onsite
        events.record(db, req, driver.id)
    await db.commit()
    await events.broadcast(req)
    return row


async def report_location(db: AsyncSession, driver: User, lat: float, lng: float) -> None:
    if not valid_coords(lat, lng):
        raise invalid("bad_coords", "Koordinatalar noto'g'ri")
    # Smenasiz: haydovchining bugungi jadvaldagi mashinasi joylashuvi yangilanadi (GPS-monitoring ulanmaguncha)
    from app.services import schedule
    plan = await schedule.for_driver_today(db, driver.id)
    if plan:
        await schedule.set_position(db, plan.vehicle_id, lat, lng, None, "tablet")
    await db.commit()
    await realtime.emit_driver_location({"driver_id": driver.id, "district_id": driver.district_id,
                                         "lat": lat, "lng": lng, "at": utcnow().isoformat()})


@dataclass
class CompleteInput:
    containers: int
    volume_m3: Decimal
    note: str
    lat: float
    lng: float


REQUIRED_FILES = (FileKind.before, FileKind.after, FileKind.face, FileKind.sign)


async def complete(db: AsyncSession, driver: User, request_id: int, data: CompleteInput) -> tuple[Request, Act]:
    """Dalolatnoma tekshiruvi. Tizimdan: sana, davlat raqami, haydovchi, avtonaryad, shartnoma, korxona maxsus raqami."""
    req = await _own_request(db, driver, request_id, lock=True)
    if req.status != RequestStatus.onsite:
        raise conflict("bad_status", "Ariza \"joyida\" holatida emas")
    missing: list[str] = []
    files = await req_repo.files_for(db, req.id)
    missing += [f"file:{k.value}" for k in REQUIRED_FILES if k not in files]
    if data.containers is None or data.containers < 1:
        missing.append("containers")
    if data.volume_m3 is None or data.volume_m3 <= 0:
        missing.append("volume_m3")
    if not (data.note or "").strip():
        missing.append("note")
    if not valid_coords(data.lat, data.lng):
        missing.append("gps")
    if not req.naryad_no:
        missing.append("naryad_no")
    if not req.contract:
        missing.append("contract")
    if missing:
        raise invalid("act_incomplete", "Dalolatnoma to'liq emas: " + ", ".join(missing))

    radius = await settings_repo.radius_for_district(db, req.district_id)
    cust = req.customer
    note = None
    first_visit = False
    if cust.location_status == LocationStatus.confirmed and cust.lat is not None and cust.lng is not None:
        dist = distance_m(cust.lat, cust.lng, data.lat, data.lng)
        in_radius = dist <= radius
        if not in_radius:
            note = f"radiusdan tashqarida: {dist} m"
    else:
        # Koordinata tasdiqlanmagan: radius tekshirilmaydi. Birinchi tashrif nuqtasi Manager tasdiqiga yuboriladi.
        dist = in_radius = None
        if cust.location_status == LocationStatus.none:
            cust.lat, cust.lng, cust.location_status = data.lat, data.lng, LocationStatus.pending
            first_visit = True
            note = "birinchi tashrif: koordinata Manager tasdiqini kutmoqda"
    act = Act(request_id=req.id, containers=data.containers, volume_m3=data.volume_m3, note=data.note.strip(),
              lat=data.lat, lng=data.lng, distance_m=dist, radius_m=radius, in_radius=in_radius,
              vehicle_plate=req.vehicle.plate if req.vehicle else "",
              completed_at=utcnow())
    db.add(act)
    req.status = RequestStatus.suspect if in_radius is False else RequestStatus.done
    req.finished_at = act.completed_at
    from app.services.order_forms import close_by_act
    close_by_act(req.order_form, driver.id, data.volume_m3)  # planshetda yakunlangan — varaqa ham yopiladi (yashil)
    events.record(db, req, driver.id, note)
    situation.activity(db, "act_act_completed", f"Haydovchi dalolatnoma bilan yakunladi: {req.number} «{cust.name}», {data.volume_m3} m³",
                       params={"number": req.number, "customer": cust.name, "volume": float(data.volume_m3 or 0)},
                       district_id=req.district_id, actor_id=driver.id, ref=("request", req.id))
    if in_radius is False:
        situation.add(db, SituationLevel.warning, "act_suspect",
                      f"Shubhali dalolatnoma: {req.number} «{cust.name}» — korxonadan {dist} m uzoqda yopildi (radius {radius} m)",
                      params={"number": req.number, "customer": cust.name, "distance": dist, "radius": radius, "driver": driver.full_name},
                      district_id=req.district_id, actor_id=driver.id, ref=("request", req.id))
    elif first_visit:
        situation.add(db, SituationLevel.info, "location_pending",
                      f"Koordinata tasdiqni kutmoqda: «{cust.name}» ({cust.fixed_no}) — birinchi tashrif {req.number}",
                      params={"customer": cust.name, "fixed_no": cust.fixed_no, "number": req.number},
                      district_id=req.district_id, actor_id=driver.id, ref=("customer", cust.id))
    await situation.commit(db)
    await events.broadcast(req)
    return req, act


async def fail(db: AsyncSession, driver: User, request_id: int, reason: FailReason, note: str | None) -> Request:
    """Bajarib bo'lmadi: ariza va shartnoma yopilmaydi, Manager nazoratiga o'tadi."""
    req = await _own_request(db, driver, request_id, lock=True)
    if req.status not in (RequestStatus.enroute, RequestStatus.onsite):
        raise conflict("bad_status", "Faqat yo'lda yoki joyidagi arizani bekor qilish mumkin")
    req.status = RequestStatus.failed
    req.fail_reason = reason
    req.fail_note = (note or "").strip() or None
    req.finished_at = utcnow()
    events.record(db, req, driver.id, reason.value)
    situation.add(db, SituationLevel.warning, "request_failed",
                  f"Bajarib bo'lmadi: {req.number} «{req.customer.name}» — sabab: {reason.value}"
                  + (f", izoh: {req.fail_note}" if req.fail_note else ""),
                  params={"number": req.number, "customer": req.customer.name, "reason": reason.value, "note": req.fail_note,
                          "driver": driver.full_name},
                  district_id=req.district_id, actor_id=driver.id, ref=("request", req.id))
    await situation.commit(db)
    await events.broadcast(req)
    return req
