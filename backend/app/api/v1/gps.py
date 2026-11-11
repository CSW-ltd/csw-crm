"""GPS xodimi: kunlik ish jadvali, qizil kartalar (biriktirilmagan arizalar), mashina biriktirish va buyurtma varaqasi."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, require_perm, require_roles
from app.core.errors import invalid
from app.models import User
from app.models.enums import Role
from app.repositories import requests as req_repo
from app.schemas import AssignIn, RequestOut
from app.services import assignment_service, locations, schedule

router = APIRouter(prefix="/gps", tags=["gps"])
Gps = Depends(require_roles(Role.gps, Role.admin))


def _district(user: User, district_id: int | None) -> int:
    d = user.district_id or district_id
    if not d:
        raise invalid("district_required", "district_id kerak")
    return d


class ScheduleRowIn(BaseModel):
    vehicle_id: int
    driver_id: int | None = None
    service: str = Field("legal", pattern="^(legal|individual)$")
    mahallas: str | None = Field(None, max_length=500)


class ScheduleIn(BaseModel):
    rows: list[ScheduleRowIn] = Field(max_length=200)


@router.get("/schedule")
async def get_schedule(day: date | None = None, district_id: int | None = Query(None), user: User = Gps, db: AsyncSession = DB) -> dict:
    d = _district(user, district_id)
    from sqlalchemy import select
    from app.models import User as U, Vehicle
    day = day or schedule.today()
    vehicles = (await db.execute(select(Vehicle).where(Vehicle.district_id == d, Vehicle.is_active).order_by(Vehicle.plate))).scalars()
    drivers = (await db.execute(select(U).where(U.role == Role.driver, U.district_id == d, U.is_active).order_by(U.full_name))).scalars()
    return {"day": day, "district_id": d, "rows": [schedule.row_out(r) for r in await schedule.day_rows(db, d, day)],
            "vehicles": [{"id": v.id, "plate": v.plate, "model": v.model} for v in vehicles],
            "drivers": [{"id": u.id, "full_name": u.full_name, "phone": u.phone} for u in drivers]}


@router.put("/schedule")
async def put_schedule(body: ScheduleIn, day: date | None = None, district_id: int | None = Query(None), user: User = Gps,
                       db: AsyncSession = DB) -> list[dict]:
    d = _district(user, district_id)
    rows = await schedule.save_day(db, user, d, day or schedule.today(), [r.model_dump() for r in body.rows])
    return [schedule.row_out(r) for r in rows]


@router.post("/schedule/copy")
async def copy_schedule(from_day: date, day: date | None = None, district_id: int | None = Query(None), user: User = Gps,
                        db: AsyncSession = DB) -> list[dict]:
    d = _district(user, district_id)
    rows = await schedule.copy_day(db, user, d, day or schedule.today(), from_day)
    return [schedule.row_out(r) for r in rows]


@router.get("/requests", response_model=list[RequestOut])
async def new_requests(district_id: int | None = Query(None), user: User = Gps, db: AsyncSession = DB):
    """Qizil kartalar: biriktirilmagan arizalar (yangisi tepada); `seen` — shu xodim ko'rganmi."""
    # Shartnomasiz korxonalar murojaatlari GPS'ga umuman ko'rinmaydi
    rows = [r for r in await req_repo.new_in_district(db, user.district_id or district_id) if not r.customer.missing_fields]
    seen = await req_repo.seen_ids(db, user.id, [r.id for r in rows])
    out = []
    for r in rows:
        item = RequestOut.model_validate(r)
        item.seen = r.id in seen
        out.append(item)
    return out


@router.get("/requests/{request_id}/vehicles")
async def vehicle_options(request_id: int, user: User = Gps, db: AsyncSession = DB) -> dict:
    return await schedule.vehicle_options(db, user, request_id)


@router.post("/requests/{request_id}/assign", response_model=RequestOut)
async def assign(request_id: int, body: AssignIn, user: User = Gps, db: AsyncSession = DB):
    return await assignment_service.assign(db, user, request_id, body.vehicle_id)


# --- Joylashuvni tasdiqlash (faqat GPS; legal kiritgani yoki umuman yo'q) ---
Locator = Depends(require_perm("customers.location_confirm"))


@router.get("/locations")
async def location_queue(user: User = Locator, db: AsyncSession = DB) -> list[dict]:
    """Tasdiqlanmagan joylashuvlar: shartnoma raqami, korxona, legal kiritgan nuqta/geofence/kadastr («missing» — kiritilmagan)."""
    return await locations.queue(db, user)


@router.post("/locations/{customer_id}/confirm")
async def location_confirm(customer_id: int, body: locations.ConfirmIn, user: User = Locator, db: AsyncSession = DB) -> dict:
    """«Tasdiqlash» yoki «O'zgartirish» (legal kiritganidan farq qilsa izoh majburiy) — nuqta + geofence majburiy."""
    return await locations.confirm(db, user, customer_id, body)
