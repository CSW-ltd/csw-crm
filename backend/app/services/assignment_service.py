"""GPS xodimi qizil kartaga mashina biriktiradi: haydovchi — bugungi ish jadvalidan, buyurtma varaqasi yaratiladi (sariq)."""
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import conflict, forbidden, invalid, not_found
from app.db.base import utcnow
from app.models import Request, User, Vehicle
from app.models.enums import RequestStatus, SituationLevel
from app.repositories import requests as req_repo
from app.services import access, events, naryad, order_forms, schedule, situation


async def assign(db: AsyncSession, gps_user: User, request_id: int, vehicle_id: int) -> Request:
    req = await req_repo.by_id(db, request_id, lock=True)
    if not req:
        raise not_found("request")
    if not access.in_scope(gps_user, req.district_id):
        raise forbidden("Bu ariza sizning tumaningizga tegishli emas")
    # Varaqa printerdan chiqqani tasdiqlanmaguncha (printing) boshqa mashinaga qayta biriktirish mumkin — raqam o'zgarmaydi
    reassign = req.status == RequestStatus.printing
    if req.status != RequestStatus.new and not reassign:
        raise conflict("request_not_new", "Ariza allaqachon biriktirilgan")
    old_plate = req.vehicle.plate if reassign and req.vehicle else None
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
    if not req.naryad_no:
        req.naryad_no = await naryad.next_number(db, req.district_id)
    req.vehicle, req.driver = vehicle, plan.driver  # munosabat orqali: javobda darhol ko'rinadi
    # Varaqa printerdan chiqqani tasdiqlanmaguncha murojaat qizil (printing); sariqqa — order_forms.confirm_printed
    req.status = RequestStatus.printing
    req.assigned_at = utcnow()
    form = await order_forms.create_for(db, req, gps_user)
    note = f"{vehicle.plate} · {plan.driver.full_name} · varaqa {form.number} — chop etilishi kutilmoqda"
    events.record(db, req, gps_user.id, f"qayta biriktirildi ({old_plate} → {vehicle.plate}): {note}" if reassign else note)
    if reassign:
        # Managerga (o'z tumani) va adminga jonli ogohlantirish
        situation.add(db, SituationLevel.warning, "request_reassigned",
                      f"Qayta biriktirildi: {req.number} {old_plate} → {vehicle.plate} · {plan.driver.full_name}, varaqa {form.number}",
                      params={"number": req.number, "plate": vehicle.plate, "old_plate": old_plate, "driver": plan.driver.full_name,
                              "form": form.number, "gps": gps_user.full_name}, district_id=req.district_id, actor_id=gps_user.id,
                      ref=("request", req.id))
    else:
        situation.activity(db, "act_assigned", f"Mashina biriktirildi: {req.number} → {vehicle.plate} · {plan.driver.full_name}, varaqa {form.number}",
                           params={"number": req.number, "plate": vehicle.plate, "driver": plan.driver.full_name, "form": form.number},
                           district_id=req.district_id, actor_id=gps_user.id, ref=("request", req.id))
    await situation.commit(db)
    await events.broadcast(req)
    return await req_repo.by_id(db, req.id)


def _in_force(contract) -> bool:
    today = date.today()
    return contract.is_active and contract.valid_from <= today <= contract.valid_to
