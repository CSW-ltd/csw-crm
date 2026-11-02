"""GPS xodimi qizil kartaga mashina biriktiradi: haydovchi — bugungi ish jadvalidan, buyurtma varaqasi yaratiladi (sariq)."""
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import conflict, forbidden, invalid, not_found
from app.db.base import utcnow
from app.models import Request, User, Vehicle
from app.models.enums import RequestStatus
from app.repositories import requests as req_repo
from app.services import access, events, naryad, order_forms, schedule


async def assign(db: AsyncSession, gps_user: User, request_id: int, vehicle_id: int) -> Request:
    req = await req_repo.by_id(db, request_id, lock=True)
    if not req:
        raise not_found("request")
    if not access.in_scope(gps_user, req.district_id):
        raise forbidden("Bu ariza sizning tumaningizga tegishli emas")
    if req.status != RequestStatus.new:
        raise conflict("request_not_new", "Ariza allaqachon biriktirilgan")
    # Amaldagi shartnoma bo'lmasa mashina yuborilmaydi
    if req.customer.missing_fields:
        raise conflict("customer_incomplete", "Korxonada amaldagi shartnoma yo'q")
    if req.contract is None or req.contract.customer_id != req.customer_id or not _in_force(req.contract):
        req.contract = req.customer.active_contract()
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle or not vehicle.is_active:
        raise not_found("vehicle")
    if vehicle.district_id != req.district_id:
        raise invalid("district_mismatch", "Mashina faqat o'z tumanidagi arizaga biriktiriladi")
    plan = await schedule.for_vehicle_today(db, vehicle.id)
    if not plan or not plan.driver_id:
        raise conflict("vehicle_not_scheduled", "Bu mashina bugungi ish jadvalida haydovchi bilan yo'q")
    req.naryad_no = await naryad.next_number(db, req.district_id)
    req.vehicle, req.driver = vehicle, plan.driver  # munosabat orqali: javobda darhol ko'rinadi
    # Varaqa printerdan chiqqani tasdiqlanmaguncha murojaat qizil (printing); sariqqa — order_forms.confirm_printed
    req.status = RequestStatus.printing
    req.assigned_at = utcnow()
    form = await order_forms.create_for(db, req, gps_user)
    events.record(db, req, gps_user.id, f"{vehicle.plate} · {plan.driver.full_name} · varaqa {form.number} — chop etilishi kutilmoqda")
    await db.commit()
    await events.broadcast(req)
    return await req_repo.by_id(db, req.id)


def _in_force(contract) -> bool:
    today = date.today()
    return contract.is_active and contract.valid_from <= today <= contract.valid_to
