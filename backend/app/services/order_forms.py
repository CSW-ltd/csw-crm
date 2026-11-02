"""Buyurtma varaqasi: mashina biriktirish → chop etish (GPS) → skan + maxfiy kod + kub/tur (legal) → yashil.

Firibgarlikka qarshi:
  * maxfiy 7 belgili kod faqat chop etilgan PDF'da bo'ladi; bazada HMAC xeshi, hech bir API javobida ko'rinmaydi;
  * GPS varaqani bir marta chop etadi — qayta chop etish manager ruxsati bilan, yangi kod beriladi, eskisi bekor bo'ladi;
  * kod 3 marta noto'g'ri kiritilsa varaqa bloklanadi, Vaziyat paneliga ogohlantirish; blokni manager ochadi.
"""
import hashlib
import hmac
import secrets
from decimal import Decimal
from uuid import uuid4

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, conflict, forbidden, invalid, not_found
from app.db.base import utcnow
from app.models import District, OrderForm, Provider, Request, User
from app.models.enums import RequestStatus, SituationLevel
from app.repositories import requests as req_repo
from app.services import access, events, situation
from app.services.storage import Storage

CODE_ALPHABET = "ABCDEFGHJKLMNPRSTUVWXYZ23456789"  # O/0, I/1, Q yo'q
CODE_LEN = 7
MAX_ATTEMPTS = 3
SCAN_TYPES = {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}
WASTE_KINDS = ("solid", "liquid")


def _secret() -> bytes:
    s = get_settings()
    return (s.order_code_secret or ("order-code:" + s.jwt_secret)).encode()


def normalize_code(code: str) -> str:
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def hash_code(code: str) -> str:
    return hmac.new(_secret(), normalize_code(code).encode(), hashlib.sha256).hexdigest()


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LEN))


async def create_for(db: AsyncSession, req: Request, actor: User) -> OrderForm:
    """Mashina biriktirilganda chaqiriladi (commit — chaqiruvchida). Raqam: 7 xonali tartib raqami.
    Bitta murojaatga bitta varaqa: mavjud bo'lsa (yopilmagan) — o'sha raqam saqlanadi."""
    existing = (await db.execute(select(OrderForm).where(OrderForm.request_id == req.id))).scalar_one_or_none()
    if existing:
        req.order_form = existing
        return existing
    form = OrderForm(request_id=req.id, created_by_id=actor.id)
    req.order_form = form
    db.add(form)
    await db.flush()
    form.number = f"{form.id:07d}"
    return form


async def _form(db: AsyncSession, user: User, form_id: int, lock: bool = False) -> tuple[OrderForm, Request]:
    form = await db.get(OrderForm, form_id, with_for_update=lock)
    if not form:
        raise not_found("order_form")
    req = await req_repo.by_id(db, form.request_id, lock=lock)
    access.check_scope(user, req.district_id)
    return form, req


async def provider_name(db: AsyncSession, district_id: int) -> str:
    d = await db.get(District, district_id)
    p = (await db.execute(select(Provider).where(Provider.region_id == d.region_id))).scalar_one_or_none() if d else None
    return p.name if p else ""


async def paper(db: AsyncSession, user: User, form_id: int) -> dict:
    """Varaqaning qog'oz ko'rinishi uchun ma'lumot (maxfiy kodsiz)."""
    form, req = await _form(db, user, form_id)
    return {"form": brief(form), "request_number": req.number, "provider": await provider_name(db, req.district_id),
            "customer": {"name": req.customer.name, "code": req.customer.code, "address": req.customer.address},
            "vehicle": {"plate": req.vehicle.plate, "model": req.vehicle.model} if req.vehicle else None,
            "driver_name": req.driver.full_name if req.driver else None, "assigned_at": req.assigned_at,
            "waste_type": req.waste_type.value,
            # printerdan chiqqani tasdiqlanmagan: qizil kartada; manual_confirm — tumanda agentsiz rejim
            "awaiting_print": req.status == RequestStatus.printing,
            "needs_reprint": needs_reprint(form, req),
            "manual_confirm": bool((d := await db.get(District, req.district_id)) and d.print_manual_confirm)}


def brief(f: OrderForm | None) -> dict | None:
    if f is None:
        return None
    return {"id": f.id, "number": f.number, "printed": f.print_count > 0, "print_count": f.print_count, "printed_at": f.printed_at,
            "reprint_allowed": f.reprint_allowed, "locked": f.locked, "attempts_left": max(0, MAX_ATTEMPTS - f.attempts),
            "has_scan": bool(f.scan_key), "verified": f.verified_at is not None, "closed_at": f.closed_at, "closed_via": f.closed_via,
            "volume_m3": float(f.volume_m3) if f.volume_m3 is not None else None, "waste_kind": f.waste_kind,
            "print_confirmed": f.print_confirmed_at is not None, "print_confirm_via": f.print_confirm_via}


async def print_pdf(db: AsyncSession, user: User, form_id: int) -> tuple[bytes, str]:
    """PDF (ikki qism, ikkalasida ham maxfiy kod). Bir marta; qayta — manager ruxsati bilan, yangi kod."""
    from app.services.order_form_pdf import render
    form, req = await _form(db, user, form_id, lock=True)
    if form.closed_at:
        raise conflict("order_closed", "Murojaat yopilgan")
    # Printerdan chiqqani tasdiqlanmaguncha (status printing) — o'sha raqam bilan erkin qayta chop etiladi
    if form.print_count > 0 and not form.reprint_allowed and req.status != RequestStatus.printing:
        raise conflict("already_printed", "Varaqa allaqachon chop etilgan. Qayta chop etish uchun manager ruxsati kerak")
    code = new_code()
    reprint = form.print_count > 0
    form.code_hash = hash_code(code)
    form.print_count += 1
    form.printed_at, form.printed_by_id = utcnow(), user.id
    form.reprint_allowed = False
    form.attempts, form.locked, form.verified_at, form.verified_by_id = 0, False, None, None
    data = await paper(db, user, form_id)
    pdf = await run_in_threadpool(render, data, code)
    events.record(db, req, user.id, f"buyurtma varaqasi {form.number} chop etildi" + (f" (qayta, {form.print_count}-marta)" if reprint else ""))
    situation.activity(db, "act_form_printed", f"Varaqa chop etildi: {form.number} ({req.number}), {form.print_count}-marta",
                       params={"form": form.number, "number": req.number, "count": form.print_count}, district_id=req.district_id,
                       actor_id=user.id, ref=("request", req.id))
    await db.commit()
    return pdf, form.number


async def allow_reprint(db: AsyncSession, user: User, form_id: int) -> OrderForm:
    form, req = await _form(db, user, form_id, lock=True)
    if form.closed_at:
        raise conflict("order_closed", "Murojaat yopilgan")
    form.reprint_allowed = True
    events.record(db, req, user.id, f"varaqa {form.number}: qayta chop etishga ruxsat berildi")
    situation.add(db, SituationLevel.info, "order_reprint", f"Varaqani qayta chop etishga ruxsat: {form.number} ({req.number})",
                  params={"form": form.number, "number": req.number}, district_id=req.district_id, actor_id=user.id,
                  ref=("request", req.id))
    await situation.commit(db)
    return form


async def unlock(db: AsyncSession, user: User, form_id: int) -> OrderForm:
    form, req = await _form(db, user, form_id, lock=True)
    form.locked, form.attempts = False, 0
    events.record(db, req, user.id, f"varaqa {form.number}: blok ochildi")
    await db.commit()
    return form


async def upload_scan(db: AsyncSession, storage: Storage, user: User, form_id: int, data: bytes, content_type: str) -> OrderForm:
    form, req = await _form(db, user, form_id, lock=True)
    _open_for_close(form, req)
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype not in SCAN_TYPES:
        raise invalid("bad_scan", "Skan formati: JPG, PNG yoki PDF")
    limit = get_settings().max_upload_mb * 1024 * 1024
    if not data or len(data) > limit:
        raise invalid("file_too_large", f"Fayl bo'sh yoki {get_settings().max_upload_mb} MB dan katta")
    key = f"order-forms/{form.id}/scan-{uuid4().hex}.{SCAN_TYPES[ctype]}"
    await run_in_threadpool(storage.put, key, data, ctype)
    form.scan_key, form.scan_content_type = key, ctype
    await db.commit()
    return form


async def scan_file(db: AsyncSession, storage: Storage, user: User, form_id: int) -> tuple[bytes, str]:
    form, _ = await _form(db, user, form_id)
    if not form.scan_key:
        raise not_found("scan")
    return await run_in_threadpool(storage.get, form.scan_key), form.scan_content_type or "application/octet-stream"


def _open_for_close(form: OrderForm, req: Request) -> None:
    if form.closed_at or req.status in (RequestStatus.done, RequestStatus.suspect, RequestStatus.cancelled):
        raise conflict("order_closed", "Murojaat allaqachon yopilgan")
    if not form.print_count:
        raise conflict("not_printed", "Varaqa hali chop etilmagan")


async def verify(db: AsyncSession, user: User, form_id: int, code: str) -> dict:
    """Maxfiy kodni tekshiradi; to'g'ri bo'lsa forma avtomatik to'ladigan ma'lumotni qaytaradi."""
    form, req = await _form(db, user, form_id, lock=True)
    _open_for_close(form, req)
    if form.locked:
        raise AppError(423, "order_locked", "Varaqa bloklangan: kod 3 marta noto'g'ri kiritildi. Manager blokni ochishi kerak")
    if not form.scan_key:
        raise conflict("scan_required", "Avval varaqaning skanini biriktiring")
    if not form.code_hash or not hmac.compare_digest(form.code_hash, hash_code(code)):
        form.attempts += 1
        left = MAX_ATTEMPTS - form.attempts
        if left <= 0:
            form.locked = True
            situation.add(db, SituationLevel.warning, "order_locked",
                          f"Buyurtma varaqasi bloklandi: {form.number} ({req.number} «{req.customer.name}») — kod 3 marta noto'g'ri, "
                          f"kirituvchi: {user.full_name}",
                          params={"form": form.number, "number": req.number, "customer": req.customer.name, "user": user.full_name},
                          district_id=req.district_id, actor_id=user.id, ref=("request", req.id))
            await situation.commit(db)
            raise AppError(423, "order_locked", "Kod 3 marta noto'g'ri kiritildi — varaqa bloklandi. Manager blokni ochishi kerak")
        await db.commit()
        raise AppError(422, "bad_order_code", f"Kod noto'g'ri. Qolgan urinishlar: {left}", {"attempts_left": left})
    form.verified_at, form.verified_by_id, form.attempts = utcnow(), user.id, 0
    await db.commit()
    return await paper(db, user, form_id)


async def close(db: AsyncSession, user: User, form_id: int, volume_m3: Decimal, waste_kind: str) -> Request:
    form, req = await _form(db, user, form_id, lock=True)
    _open_for_close(form, req)
    if not form.scan_key:
        raise conflict("scan_required", "Avval varaqaning skanini biriktiring")
    if not form.verified_at:
        raise conflict("code_required", "Avval maxfiy kodni kiriting")
    if volume_m3 is None or volume_m3 <= 0:
        raise invalid("volume_required", "Kubni kiriting")
    if waste_kind not in WASTE_KINDS:
        raise invalid("waste_kind_required", "Chiqindi turini belgilang")
    now = utcnow()
    form.volume_m3, form.waste_kind = volume_m3, waste_kind
    form.closed_at, form.closed_by_id, form.closed_via = now, user.id, "form"
    req.status, req.finished_at = RequestStatus.done, now
    events.record(db, req, user.id, f"buyurtma varaqasi {form.number} bo'yicha yopildi: {volume_m3} m³")
    situation.activity(db, "act_form_closed", f"Murojaat varaqa bilan yopildi: {req.number}, varaqa {form.number}, {volume_m3} m³",
                       params={"number": req.number, "form": form.number, "volume": float(volume_m3)}, district_id=req.district_id,
                       actor_id=user.id, ref=("request", req.id))
    await db.commit()
    await events.broadcast(req)
    return await req_repo.by_id(db, req.id)


def close_by_act(form: OrderForm | None, driver_id: int, volume_m3: Decimal) -> None:
    """Planshetda dalolatnoma yakunlansa varaqa ham yopilgan hisoblanadi (commit — chaqiruvchida)."""
    if form and not form.closed_at:
        form.closed_at, form.closed_by_id, form.closed_via, form.volume_m3 = utcnow(), driver_id, "act", volume_m3


def needs_reprint(form: OrderForm, req: Request) -> bool:
    """Qayta biriktirilgan (printing): qog'ozda eski mashina — yangi biriktirishdan keyin chop etilmagan."""
    return bool(req.status == RequestStatus.printing and form.printed_at and req.assigned_at and form.printed_at < req.assigned_at)


async def confirm_printed(db: AsyncSession, user: User, form_id: int, via: str) -> Request:
    """Varaqa printerdan chiqdi: murojaat qizildan sariqqa (biriktirilgan) o'tadi, haydovchiga vazifa ko'rinadi.
    via="agent" — printer agenti (PR #20), via="manual" — faqat tumanda agentsiz rejim yoqilgan bo'lsa."""
    form, req = await _form(db, user, form_id, lock=True)
    if req.status != RequestStatus.printing:
        raise conflict("not_printing", "Murojaat varaqa chop etilishini kutmayapti")
    if not form.print_count or needs_reprint(form, req):
        raise conflict("not_printed", "Varaqa hali chop etilmagan (qayta biriktirilgandan keyin yangi mashina bilan chop eting)")
    if via == "manual":
        d = await db.get(District, req.district_id)
        if not d or not d.print_manual_confirm:
            raise forbidden("Bu tumanda varaqa faqat printer agenti orqali tasdiqlanadi")
    form.print_confirmed_at, form.print_confirmed_by_id, form.print_confirm_via = utcnow(), user.id, via
    req.status = RequestStatus.assigned
    events.record(db, req, user.id, f"varaqa {form.number} printerdan chiqdi ({'agent' if via == 'agent' else 'qo‘lda tasdiq'})")
    situation.activity(db, "act_print_confirmed", f"Varaqa printerdan chiqdi: {form.number} ({req.number}) — {'printer agenti' if via == 'agent' else 'qo‘lda tasdiq'}",
                       params={"form": form.number, "number": req.number, "via": via}, district_id=req.district_id, actor_id=user.id,
                       ref=("request", req.id))
    await db.commit()
    await events.broadcast(req)
    return await req_repo.by_id(db, req.id)
