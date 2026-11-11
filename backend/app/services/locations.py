"""Korxona joylashuvini GPS tasdiqlaydi (2026-11-11 qarori): legal shartnomada ixtiyoriy kiritgan nuqta/geofence/kadastr
yoki umuman kiritilmagan joylashuv — GPS navbatida. Faqat «Tasdiqlash» va «O'zgartirish» (izoh majburiy); o'zgartirilsa —
izoh GPS xodimi F.I.Sh. bilan Vaziyat paneliga va shartnomani kiritgan legal'ning bildirishnomalariga tushadi."""
import json

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import invalid, not_found
from app.db.base import utcnow
from app.models import Contract, Customer, User
from app.models.enums import LocationStatus, SituationLevel
from app.services import access, notifications, situation
from app.services.geo import coords_error, distance_m, geofence_error

QUEUE_STATUSES = ("signed", "returned", "approved", "draft")  # shartnomasi bor korxonalar (loyiha ham)


def geofence_of(c: Customer) -> dict | None:
    try:
        return json.loads(c.geofence) if c.geofence else None
    except ValueError:
        return None


async def _last_contract(db: AsyncSession, customer_id: int) -> Contract | None:
    q = (select(Contract).where(Contract.customer_id == customer_id, Contract.status.in_(QUEUE_STATUSES))
         .order_by(Contract.id.desc()).limit(1))
    return (await db.execute(q)).scalar_one_or_none()


async def queue(db: AsyncSession, actor: User) -> list[dict]:
    """Tasdiqlanmagan joylashuvlar (o'z tumanlari): legal kiritgan (kutilmoqda) yoki umuman yo'q («to'ldirish kerak»)."""
    has_contract = select(Contract.id).where(Contract.customer_id == Customer.id, Contract.status.in_(QUEUE_STATUSES)).exists()
    q = select(Customer).where(Customer.location_status != LocationStatus.confirmed, has_contract).order_by(Customer.id.desc()).limit(500)
    s = access.scope(actor)
    if s is not None:
        q = q.where(Customer.district_id.in_(s or {-1}))
    out = []
    for c in (await db.execute(q)).scalars():
        ct = await _last_contract(db, c.id)
        author = await db.get(User, ct.created_by_id) if ct and ct.created_by_id else None
        out.append({"customer": brief(c), "contract": {"id": ct.id, "number": ct.display_number, "status": ct.status} if ct else None,
                    "entered_by": author.full_name if author else None,
                    "state": "missing" if c.lat is None or c.lng is None else "pending"})
    return out


def brief(c: Customer) -> dict:
    return {"id": c.id, "name": c.name, "code": c.code, "stir": c.stir, "district_id": c.district_id, "lat": c.lat, "lng": c.lng,
            "geofence": geofence_of(c), "cadastre": c.cadastre, "legal_address": c.legal_address, "is_rented": c.is_rented,
            "location_status": c.location_status.value, "location_source": c.location_source}


class ConfirmIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    geofence: dict
    cadastre: str | None = Field(None, max_length=40)
    comment: str | None = Field(None, max_length=500)


async def confirm(db: AsyncSession, actor: User, customer_id: int, body: ConfirmIn) -> dict:
    """«Tasdiqlash» — o'zgarishsiz; «O'zgartirish» — nuqta/geofence/kadastr farq qilsa izoh majburiy."""
    c = await db.get(Customer, customer_id, with_for_update=True)
    if not c:
        raise not_found("customer")
    access.check_scope(actor, c.district_id)
    if code := coords_error(body.lat, body.lng):
        raise invalid(f"coords_{code}", "Koordinata noto'g'ri")
    if code := geofence_error(body.geofence):
        raise invalid(code, "Geofence noto'g'ri (radius 10–3000 m yoki 3+ nuqtali poligon)")
    cad = (body.cadastre or "").strip() or None
    old_gf = geofence_of(c)
    moved = c.lat is None or c.lng is None or distance_m(c.lat, c.lng, body.lat, body.lng) > 1
    # Legal'ning ma'lumoti o'zgardi: nuqta siljidi, legal chizgan geofence boshqacha yoki kadastr boshqa (geofence qo'shish — o'zgarish emas)
    changed = moved or (old_gf is not None and old_gf != body.geofence) or (cad is not None and c.cadastre is not None and cad != c.cadastre)
    had_legal = c.lat is not None and c.lng is not None and c.location_source == "legal"
    comment = (body.comment or "").strip()
    if changed and had_legal and len(comment) < 3:
        raise invalid("comment_required", "Legal kiritgan joylashuv o'zgartirildi — izoh majburiy")
    c.lat, c.lng, c.geofence = body.lat, body.lng, json.dumps(body.geofence)
    if cad is not None:
        c.cadastre = cad
    c.location_status, c.location_source = LocationStatus.confirmed, "gps"
    c.location_confirmed_by_id, c.location_confirmed_at = actor.id, utcnow()
    ct = await _last_contract(db, c.id)
    num = ct.display_number if ct else "—"
    if changed and had_legal:
        params = {"customer": c.name, "contract": num, "comment": comment, "gps": actor.full_name}
        situation.add(db, SituationLevel.info, "location_changed",
                      f"GPS joylashuvni o'zgartirdi: {num} «{c.name}» — {actor.full_name}: {comment}",
                      params=params, district_id=c.district_id, actor_id=actor.id, ref=("customer", c.id))
        if ct and ct.created_by_id and ct.created_by_id != actor.id:
            notifications.add(db, ct.created_by_id, "location_changed",
                              f"{actor.full_name} joylashuvni o'zgartirdi: {num} «{c.name}» — {comment}",
                              params=params, actor_id=actor.id, ref=("customer", c.id))
    else:
        situation.activity(db, "act_location_confirmed", f"GPS joylashuvni tasdiqladi: {num} «{c.name}»",
                           params={"customer": c.name, "contract": num}, district_id=c.district_id, actor_id=actor.id,
                           ref=("customer", c.id))
    await situation.commit(db)
    await notifications.publish(db)
    return brief(c)
