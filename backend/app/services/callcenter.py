"""Call-center: ariza ochish (takroriy ariza tasdig'i bilan), bekor qilish, 72 soatlik muddat, birinchi murojaatlar.

Ariza ochilishi bilan tumanning GPS xodimi ro'yxatiga jonli tushadi (request:updated). Korxona bazada bo'lmasa operator
"birinchi murojaat" yuboradi — yuridik bo'lim korxona kartasini (va shartnomani) yaratadi, ariza avtomatik ochiladi.
"""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import realtime
from app.core.errors import conflict, invalid, not_found
from app.db.base import utcnow
from app.models import Appeal, Customer, District, OrderForm, Request, User
from app.models.enums import OPEN_STATUSES, AppealStatus, RequestStatus, SituationLevel, WasteType
from app.repositories import customers as customers_repo
from app.repositories import requests as req_repo
from app.schemas import AppealAcceptIn, AppealIn, ContractIn, RequestCreateIn
from app.services import access, customer_service, events, situation
from app.services.normalize import format_phone

NORM_HOURS = 72


def _open(q):
    return q.where(Request.status.in_([RequestStatus(s) for s in OPEN_STATUSES]))


async def open_for_customer(db: AsyncSession, actor: User, customer_id: int) -> list[Request]:
    cust = await db.get(Customer, customer_id)
    if not cust:
        raise not_found("customer")
    access.check_scope(actor, cust.district_id)
    q = _open(select(Request).where(Request.customer_id == customer_id)).order_by(Request.created_at.desc())
    return list((await db.execute(req_repo._with_details(q))).scalars())


async def create_request(db: AsyncSession, actor: User, body: RequestCreateIn) -> Request:
    cust = await customers_repo.get(db, body.customer_id)
    if not cust:
        raise not_found("customer")
    access.check_scope(actor, cust.district_id)
    open_reqs = await open_for_customer(db, actor, cust.id)
    if open_reqs and not body.confirm_repeat:
        raise conflict("open_request_exists",
                       f"Bu korxonada ochiq ariza bor: {', '.join(r.number or str(r.id) for r in open_reqs)}. Qayta ariza sifatida belgilaysizmi?")
    return await _new_request(db, actor, cust, body, repeat_of=open_reqs[0] if open_reqs else None)


async def _new_request(db: AsyncSession, actor: User, cust: Customer, body, repeat_of: Request | None = None,
                       commit: bool = True) -> Request:
    now = utcnow()
    req = Request(customer_id=cust.id, contract=cust.active_contract(), district_id=cust.district_id, status=RequestStatus.new,
                  waste_type=body.waste_type, volume_estimate=body.volume_estimate, preferred_time=body.preferred_time,
                  note=(body.note or "").strip() or None, source=body.source, caller_name=(body.caller_name or "").strip() or None,
                  caller_phone=format_phone(body.caller_phone), created_by_id=actor.id, due_at=now + timedelta(hours=NORM_HOURS),
                  is_repeat=repeat_of is not None, repeat_of_id=repeat_of.id if repeat_of else None)
    db.add(req)
    await db.flush()
    req.number = f"M-{req.id:06d}"
    events.record(db, req, actor.id, f"qayta ariza ({repeat_of.number})" if repeat_of else None)
    if commit:
        await db.commit()
        await events.broadcast(req)
    return await req_repo.by_id(db, req.id)


async def cancel_request(db: AsyncSession, actor: User, request_id: int, reason: str) -> Request:
    req = await req_repo.by_id(db, request_id, lock=True)
    if not req:
        raise not_found("request")
    access.check_scope(actor, req.district_id)
    if req.status != RequestStatus.new:
        raise conflict("request_not_new", "Faqat hali biriktirilmagan arizani bekor qilish mumkin")
    req.status = RequestStatus.cancelled
    req.cancel_reason = reason.strip()
    req.finished_at = utcnow()
    events.record(db, req, actor.id, f"bekor qilindi: {req.cancel_reason}")
    await db.commit()
    await events.broadcast(req)
    return req


async def list_requests(db: AsyncSession, actor: User, *, district_id: int | None, status: RequestStatus | None, mine: bool,
                        overdue: bool, q: str | None, limit: int, offset: int, date_from: datetime | None = None,
                        date_to: datetime | None = None, waste_type: WasteType | None = None,
                        repeat: bool = False, stage: str | None = None, hours: int | None = None) -> tuple[list[Request], int]:
    cond = []
    if hours:
        cond.append(Request.created_at >= utcnow() - timedelta(hours=hours))
    black_edge = utcnow() - timedelta(hours=NORM_HOURS)
    red_st = [RequestStatus.new, RequestStatus.printing]
    if stage == "red":
        cond += [Request.status.in_(red_st), Request.created_at > black_edge]
    elif stage == "black":
        cond += [Request.status.in_(red_st), Request.created_at <= black_edge]
    elif stage == "yellow":
        cond.append(Request.status.in_([RequestStatus.assigned, RequestStatus.enroute, RequestStatus.onsite, RequestStatus.failed]))
    elif stage == "green":
        cond.append(Request.status.in_([RequestStatus.done, RequestStatus.suspect]))
    if date_from:
        cond.append(Request.created_at >= date_from)
    if date_to:
        cond.append(Request.created_at < date_to)
    if waste_type:
        cond.append(Request.waste_type == waste_type)
    if repeat:
        cond.append(Request.is_repeat.is_(True))
    s = access.scope(actor)
    if s is not None:
        cond.append(Request.district_id.in_(s or {-1}))
    if district_id:
        cond.append(Request.district_id == district_id)
    if status:
        cond.append(Request.status == status)
    if mine:
        cond.append(Request.created_by_id == actor.id)
    if overdue:
        cond += [Request.status.in_([RequestStatus(x) for x in OPEN_STATUSES]), Request.due_at < utcnow()]
    if q and q.strip():
        like = f"%{q.strip()}%"
        up = q.strip().upper()
        cond.append(Request.number.ilike(like)
                    | Request.customer_id.in_(select(Customer.id).where(Customer.name.ilike(like) | (Customer.code == up)
                                                                        | (Customer.stir == q.strip())))
                    | Request.id.in_(select(OrderForm.request_id).where(OrderForm.number == q.strip())))
    total = (await db.execute(select(func.count()).select_from(Request).where(*cond))).scalar_one()
    order = (Request.finished_at.desc(),) if stage == "green" else (Request.assigned_at.asc(),) if stage == "yellow" else ()
    rows = (await db.execute(req_repo._with_details(select(Request).where(*cond).order_by(*order, Request.created_at.desc())
                                                    .limit(limit).offset(offset)))).scalars()
    return list(rows), total


async def check_overdue(db: AsyncSession) -> int:
    """Muddati (72 soat) o'tgan, hali bajarilmagan arizalar — admin Vaziyat paneliga bir marta ogohlantirish."""
    q = _open(select(Request).where(Request.due_at < utcnow(), Request.overdue_notified.is_(False))) \
        .options(selectinload(Request.customer))
    rows = list((await db.execute(q)).scalars())
    names = {d.id: d.name for d in (await db.execute(select(District))).scalars()}
    for r in rows:
        r.overdue_notified = True
        hours = int((utcnow() - r.created_at).total_seconds() // 3600)
        situation.add(db, SituationLevel.warning, "request_overdue",
                      f"Muddati o'tdi: {r.number} «{r.customer.name}» ({names.get(r.district_id, '')}) — {hours} soat, bajarilmagan",
                      params={"number": r.number, "customer": r.customer.name, "hours": hours}, district_id=r.district_id,
                      ref=("request", r.id))
    await situation.commit(db)
    return len(rows)


# --- birinchi murojaatlar ---
async def _appeal_broadcast(a: Appeal) -> None:
    await realtime.emit_appeal_updated({"id": a.id, "number": a.number, "status": a.status.value, "district_id": a.district_id,
                                        "created_by_id": a.created_by_id})


async def create_appeal(db: AsyncSession, actor: User, body: AppealIn) -> Appeal:
    d = await db.get(District, body.district_id)
    if not d or not d.is_active:
        raise not_found("district")
    access.check_scope(actor, d.id)
    a = Appeal(**body.model_dump(exclude={"caller_phone"}), caller_phone=format_phone(body.caller_phone), created_by_id=actor.id)
    a.org_name = a.org_name.strip()
    db.add(a)
    await db.flush()
    a.number = f"MR-{a.id:06d}"
    await db.commit()
    await _appeal_broadcast(a)
    return a


async def create_new_company(db: AsyncSession, actor: User, body) -> Appeal:
    """Yangi korxona: karta "shartnoma kutilmoqda" holatida ochiladi, maxsus raqam beriladi va telefonga SMS ketadi.
    Murojaat yuridik bo'lim navbatiga tushadi; shartnoma bo'lmaguncha GPS ko'rmaydi."""
    from app.models import CustomerContact
    from app.repositories import customers as cust_repo
    from app.services import sms
    from app.services.customer_import import next_fixed_no_start
    from app.services.customer_service import stir_taken
    from app.services.normalize import key, phone_digits
    if len(phone_digits(body.phone)) != 9:
        raise invalid("bad_phone", "Telefon raqami 9 xonali bo'lishi kerak (masalan, 94 512 11 16)")
    other = await cust_repo.by_stir(db, body.stir)
    if other:
        raise stir_taken(other)
    district_id = body.district_id
    if district_id is None:
        own = access.scope(actor)
        if own is None or len(own) != 1:
            raise invalid("district_required", "Tumanni tanlang")
        district_id = next(iter(own))
    d = await db.get(District, district_id)
    if not d or not d.is_active:
        raise not_found("district")
    access.check_scope(actor, d.id)
    phone = format_phone(body.phone)
    name = f"Yangi korxona (STIR {body.stir})"
    cust = Customer(fixed_no=f"A-{await next_fixed_no_start(db):04d}", name=name, name_key=key(name), district_id=d.id,
                    stir=body.stir, phone=phone, source="call")
    db.add(cust)
    await db.flush()
    db.add(CustomerContact(customer_id=cust.id, name=body.contact_name.strip(), phone=phone))
    a = Appeal(district_id=d.id, org_name=name, stir=body.stir, caller_name=body.contact_name.strip(), caller_phone=phone,
               waste_type=body.waste_type, created_by_id=actor.id, customer_id=cust.id)
    db.add(a)
    await db.flush()
    a.number = f"MR-{a.id:06d}"
    code = cust.code
    await db.commit()
    sms.send_later(phone, f"Korxonangiz maxsus raqami: {code}. Chiqindi olib ketish uchun murojaat qilganda shu raqamni ayting. "
                          "Bu raqamni boshqa hech kimga aytmang.")
    await _appeal_broadcast(a)
    return a


async def list_appeals(db: AsyncSession, actor: User, status: AppealStatus | None, mine: bool) -> list[Appeal]:
    q = select(Appeal).order_by(Appeal.created_at.desc()).limit(200)
    s = access.scope(actor)
    if s is not None:
        q = q.where(Appeal.district_id.in_(s or {-1}))
    if status:
        q = q.where(Appeal.status == status)
    if mine:
        q = q.where(Appeal.created_by_id == actor.id)
    return list((await db.execute(q)).scalars())


async def _pending_appeal(db: AsyncSession, actor: User, appeal_id: int) -> Appeal:
    a = await db.get(Appeal, appeal_id, with_for_update=True)
    if not a:
        raise not_found("appeal")
    access.check_scope(actor, a.district_id)
    if a.status != AppealStatus.new:
        raise conflict("appeal_not_new", "Bu murojaat allaqachon ko'rib chiqilgan")
    return a


async def _check_contract(db: AsyncSession, c: ContractIn | None) -> None:
    if c is None:
        return
    if c.valid_to < c.valid_from:
        raise invalid("bad_dates", "Tugash sanasi boshlanish sanasidan oldin bo'lmasin")
    if await customers_repo.contract_by_number(db, c.number.strip()):
        raise conflict("contract_number_taken", "Bu raqamli shartnoma bor")


async def accept_appeal(db: AsyncSession, actor: User, appeal_id: int, body: AppealAcceptIn) -> Appeal:
    """Korxona kartasi (+ shartnoma) → ariza (murojaatdagi buyurtma) → murojaat yopiladi. Kartani yaratishdan oldin hammasi tekshiriladi."""
    a = await _pending_appeal(db, actor, appeal_id)
    if body.customer.district_id != a.district_id:
        access.check_scope(actor, body.customer.district_id)
    await _check_contract(db, body.contract)
    if a.customer_id:  # operator ochgan "shartnoma kutilmoqda" kartasi — to'ldiriladi
        from app.schemas import CustomerUpdateIn
        data = {k: v for k, v in body.customer.model_dump(exclude={"district_id"}).items() if v not in (None, "")}
        cust = await customer_service.update(db, a.customer_id, CustomerUpdateIn(**data), actor)
    else:
        cust = await customer_service.create(db, body.customer, actor)
    if body.contract:
        cust = await customer_service.add_contract(db, cust.id, body.contract, actor)
    a = await db.get(Appeal, appeal_id)
    req = await _new_request(db, actor, cust, a, commit=False)
    a.status, a.reviewed_by_id, a.reviewed_at = AppealStatus.accepted, actor.id, utcnow()
    a.customer_id, a.request_id = cust.id, req.id
    await db.commit()
    await events.broadcast(req)
    await _appeal_broadcast(a)
    return a


async def reject_appeal(db: AsyncSession, actor: User, appeal_id: int, reason: str) -> Appeal:
    a = await _pending_appeal(db, actor, appeal_id)
    a.status, a.reviewed_by_id, a.reviewed_at, a.reject_reason = AppealStatus.rejected, actor.id, utcnow(), reason.strip()
    await db.commit()
    await _appeal_broadcast(a)
    return a


async def request_detail(db: AsyncSession, actor: User, request_id: int) -> dict:
    """Ariza kartasi: korxona, haydovchi, kim ochgan va holatlar tarixi."""
    from app.models import RequestEvent
    req = await req_repo.by_id(db, request_id)
    if not req:
        raise not_found("request")
    access.check_scope(actor, req.district_id)
    names = {u.id: u.full_name for u in (await db.execute(select(User))).scalars()}
    events = (await db.execute(select(RequestEvent).where(RequestEvent.request_id == req.id).order_by(RequestEvent.id))).scalars()
    await req_repo.mark_seen(db, actor.id, [req.id])
    return {"req": req, "driver_name": names.get(req.driver_id), "created_by_name": names.get(req.created_by_id),
            "events": [{"status": e.status, "note": e.note, "actor_name": names.get(e.actor_id), "created_at": e.created_at} for e in events]}


async def stage_summary(db: AsyncSession, actor: User, hours: int, district_id: int | None = None) -> dict:
    since = utcnow() - timedelta(hours=hours)
    q = select(Request.status, Request.created_at).where(Request.created_at >= since, Request.status != RequestStatus.cancelled)
    s = access.scope(actor)
    if s is not None:
        q = q.where(Request.district_id.in_(s or {-1}))
    if district_id:
        q = q.where(Request.district_id == district_id)
    black_edge = utcnow() - timedelta(hours=NORM_HOURS)
    out = {"hours": hours, "red": 0, "black": 0, "yellow": 0, "green": 0}
    for st, created in (await db.execute(q)).all():
        v = st.value
        if v in ("new", "printing"):
            out["black" if created <= black_edge else "red"] += 1
        elif v in ("done", "suspect"):
            out["green"] += 1
        else:
            out["yellow"] += 1
    return out
