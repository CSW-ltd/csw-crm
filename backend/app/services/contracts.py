"""«Yangi shartnoma» jarayoni (legal → buxgalter).

draft (forma saqlandi, ichki raqam berildi; hujjat PDF/DOCX)
  → signed   (legal «Imzolandi»: elektron — platforma + ID; qog'oz — skan ixtiyoriy). Shu paytdan FAOL: murojaat ochiladi, GPS ko'radi.
  → approved (buxgalter tasdiqladi — faktura va debitorga kiradi)
signed → returned (buxgalter izoh bilan qaytardi; faol qoladi, hisobga kirmaydi) → legal tuzatadi → signed (qayta yuborildi)
"""
import json
import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, PrivateAttr
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.errors import AppError, conflict, invalid, not_found
from app.db.base import utcnow
from app.models import Contract, ContractEvent, Customer, District, Provider, User
from app.models.enums import ContractType, LocationStatus
from app.services import access, billing, contract_templates, tariffs
from app.services.geo import coords_error
from app.services.billing import local_day
from app.services.customer_service import _check_stir
from app.services.invoice_pdf import words_uz
from app.services.normalize import format_phone, phone_digits
from app.services.storage import Storage

VAT = Decimal("12")
LIVE = ("signed", "returned", "approved")  # faol shartnoma holatlari
PLATFORMS = ("didox", "hujjat", "soliq", "other")
SCAN_TYPES = {"application/pdf": "pdf"}  # imzolangan nusxa / asl hujjat — faqat PDF
NEW_BADGE_DAYS = 30  # GPS kartasida «Yangi shartnoma» belgisi


class Requisites(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    stir: str | None = Field(None, max_length=9)
    director: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=30)
    legal_address: str | None = Field(None, max_length=255)
    address: str | None = Field(None, max_length=255)
    bank: str | None = Field(None, max_length=150)
    mfo: str | None = Field(None, max_length=5)
    account: str | None = Field(None, max_length=20)
    oked: str | None = Field(None, max_length=10)
    cadastre: str | None = Field(None, max_length=40)
    is_rented: bool = False  # obyekt ijarada (shartnoma 10.3-bandi)
    # Obyekt koordinatasi (majburiy): yurist kiritsa — «kutilmoqda», haydovchi tashrifi yoki manager tasdiqlaydi
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)


class ExistingMeta(BaseModel):
    """Mavjud (tizimdan oldin imzolangan) shartnoma: qo'shimcha maydonlar."""
    number: str | None = Field(None, max_length=40)
    signed_on: date | None = None
    platform: str | None = Field(None, pattern="^(didox|hujjat|soliq|other)$")
    platform_id: str | None = Field(None, max_length=40)


class ContractDraftIn(BaseModel):
    customer_id: int
    requisites: Requisites
    type: ContractType = ContractType.by_volume
    price: Decimal | None = Field(None, ge=0, max_digits=14, decimal_places=2)
    annual_volume: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    annual_trips: int | None = Field(None, ge=0, le=100000)
    valid_from: date | None = None
    valid_to: date | None = None
    place: str | None = Field(None, max_length=100)
    sign_method: str = Field("electronic", pattern="^(electronic|paper)$")
    existing: ExistingMeta | None = None  # bo'lsa — «Mavjud shartnomani kiritish»
    price_reason: str | None = Field(None, max_length=255)  # mavjud shartnoma: narx ta'rifdan farq qilsa — sababi (majburiy)
    _tariff: Decimal | None = PrivateAttr(None)  # validate() to'ldiradi: boshlanish sanasidagi ta'rif


def manual_price_allowed(actor: User, existing_src: bool) -> bool:
    """Mavjud shartnomada (qo'lda/Excel) kub narxini legal o'zi kiritadi — «customers.existing_price» ruxsati bilan."""
    return existing_src and actor.can("customers.existing_price")


def price_differs(price, tariff) -> bool:
    return tariff is None or price is None or Decimal(str(price)) != Decimal(str(tariff))


# --- hisob ---
def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def months_between(a: date, b: date) -> int:
    """01.03 — 31.12 → 10 oy (boshlanish va tugash oylari ham hisoblanadi)."""
    return max(1, (b.year - a.year) * 12 + b.month - a.month + 1)


def totals(ctype: ContractType, price: Decimal | None, volume: Decimal | None, trips: int | None, vf: date | None, vt: date | None) -> dict:
    """Jadval qatori: miqdor, birlik, narx (QQSsiz), qiymat (QQSsiz), QQS 12% (ichida), jami (QQS bilan). Narx — QQS bilan kiritiladi."""
    price = Decimal(str(price or 0))
    if ctype == ContractType.per_trip:
        qty, unit = Decimal(trips or 0), "reys"
    elif ctype == ContractType.monthly:
        qty, unit = Decimal(months_between(vf, vt) if vf and vt and vt >= vf else 0), "oy"
    elif ctype == ContractType.one_off:
        qty, unit = Decimal(1), "xizmat"
    else:
        qty, unit = Decimal(str(volume or 0)), "kub. metr"
    total = _q(qty * price)
    vat = _q(total * VAT / (100 + VAT))
    return {"qty": qty, "unit": unit, "unit_net": _q(price * 100 / (100 + VAT)), "net": total - vat, "vat": vat, "total": total, "price": price}


def money_words(v: Decimal) -> str:
    w = words_uz(int(v))
    return f"{w[:1].upper()}{w[1:]} so‘m {int((v % 1) * 100):02d} tiyin"


def _fmt(v: Decimal, dec=2) -> str:
    return f"{v:,.{dec}f}".replace(",", " ")


# --- tekshirish ---
def _err(field: str, code: str) -> dict:
    return {"field": field, "code": code}


async def _overlap(db: AsyncSession, customer_id: int, vf: date, vt: date, own_id: int | None) -> Contract | None:
    q = select(Contract).where(Contract.customer_id == customer_id, Contract.status.in_(LIVE), Contract.is_active.is_(True),
                               Contract.valid_from <= vt, Contract.valid_to >= vf)
    if own_id:
        q = q.where(Contract.id != own_id)
    return (await db.execute(q.limit(1))).scalar_one_or_none()


async def validate(db: AsyncSession, actor: User, body: ContractDraftIn, own_id: int | None = None,
                   existing_src: bool = False) -> tuple[Customer, list[dict]]:
    cust = await db.get(Customer, body.customer_id)
    if not cust:
        raise not_found("customer")
    access.check_scope(actor, cust.district_id)
    r, errs = body.requisites, []
    if not r.stir or not re.fullmatch(r"\d{9}", r.stir):
        errs.append(_err("stir", "stir"))
    else:
        try:
            await _check_stir(db, r.stir, cust.id)
        except AppError:
            errs.append(_err("stir", "stir_taken"))
    for f in ("director", "legal_address", "bank"):
        if not (getattr(r, f) or "").strip():
            errs.append(_err(f, "required"))
    if len(phone_digits(r.phone or "")) != 9:
        errs.append(_err("phone", "phone"))
    if not r.account or not re.fullmatch(r"\d{20}", r.account):
        errs.append(_err("account", "account"))
    if not r.mfo or not re.fullmatch(r"\d{5}", r.mfo):
        errs.append(_err("mfo", "mfo"))
    if r.oked and not re.fullmatch(r"\d{4,5}", r.oked):
        errs.append(_err("oked", "oked"))
    ex = body.existing
    if body.type != ContractType.by_volume and not ex:
        errs.append(_err("type", "type_volume_only"))  # yangi shartnoma — faqat kub (ta'rif); reys/oylik — mavjud shartnomani kiritishda
    existing_src = existing_src or ex is not None
    if body.type == ContractType.by_volume:
        # Narx — davlat ta'rifi (shartnoma boshlanish sanasidagi, tuman → viloyat). Mavjud shartnomada (ruxsat bilan) legal eski narxni
        # o'zi kiritadi; ta'rifdan farq qilsa (yoki o'sha sanaga ta'rif yo'q bo'lsa) — sababi majburiy.
        tariff = await tariffs.price_for(db, cust.district_id, body.valid_from or local_day(utcnow()))
        body._tariff = tariff
        if manual_price_allowed(actor, existing_src):
            if not body.price or body.price <= 0:
                errs.append(_err("price", "required"))
            elif price_differs(body.price, tariff) and len((body.price_reason or "").strip()) < 3:
                errs.append(_err("price_reason", "required"))
        else:
            body.price = tariff
            if not body.price:
                errs.append(_err("price", "no_tariff"))
    elif not body.price or body.price <= 0:
        errs.append(_err("price", "required"))
    if ex:
        num, pid = (ex.number or "").strip(), (ex.platform_id or "").strip() or None
        if not num:
            errs.append(_err("number", "required"))
        elif (await db.execute(select(Contract.id).where(Contract.number == num, Contract.id != (own_id or -1)))).first():
            errs.append(_err("number", "number_taken"))
        if not ex.signed_on:
            errs.append(_err("signed_on", "required"))
        elif ex.signed_on > local_day(utcnow()):
            errs.append(_err("signed_on", "future"))
        if body.sign_method == "electronic" and not pid:
            errs.append(_err("platform_id", "required"))
        if pid and (await db.execute(select(Contract.id).where(Contract.platform_id == pid, Contract.id != (own_id or -1)))).first():
            errs.append(_err("platform_id", "platform_id_taken"))
    if body.type == ContractType.by_volume and not (body.annual_volume and body.annual_volume > 0):
        errs.append(_err("annual_volume", "required"))
    if body.type == ContractType.per_trip and not body.annual_trips:
        errs.append(_err("annual_trips", "required"))
    if not body.valid_from:
        errs.append(_err("valid_from", "required"))
    if not body.valid_to:
        errs.append(_err("valid_to", "required"))
    if body.valid_from and body.valid_to:
        if body.valid_to < body.valid_from:
            errs.append(_err("valid_to", "bad_dates"))
        elif (body.valid_to - body.valid_from).days > 5 * 366:
            errs.append(_err("valid_to", "too_long"))
        elif await _overlap(db, cust.id, body.valid_from, body.valid_to, own_id):
            errs.append(_err("valid_from", "overlap"))
    if not (body.place or "").strip():
        errs.append(_err("place", "required"))
    if code := coords_error(r.lat, r.lng):
        errs.append(_err("coords", code))
    return cust, errs


async def check(db: AsyncSession, actor: User, body: ContractDraftIn, own_id: int | None = None) -> dict:
    existing_src = False
    if own_id:
        own = await db.get(Contract, own_id)
        existing_src = bool(own and own.source in ("manual", "import"))
    _, errs = await validate(db, actor, body, own_id, existing_src)
    t = totals(body.type, body.price, body.annual_volume, body.annual_trips, body.valid_from, body.valid_to)
    return {"ok": not errs, "errors": errs, "totals": {"qty": float(t["qty"]), "unit": t["unit"], "net": float(t["net"]), "vat": float(t["vat"]),
                                                      "total": float(t["total"]), "words": money_words(t["total"]),
                                                      "price": float(body.price) if body.price else None,
                                                      "tariff": float(body._tariff) if body._tariff else None}}


def _raise(errs: list[dict]) -> None:
    if errs:
        raise AppError(422, "contract_invalid", "Shartnoma ma'lumotlarida xato bor", {"errors": errs})


# --- raqam ---
async def _provider(db: AsyncSession, district_id: int) -> Provider | None:
    d = await db.get(District, district_id)
    return (await db.execute(select(Provider).where(Provider.region_id == d.region_id))).scalar_one_or_none() if d else None


async def next_number(db: AsyncSession, prefix_code: str, year: int) -> str:
    prefix = f"{prefix_code}-{year}/"
    rows = (await db.execute(select(Contract.number).where(Contract.number.like(f"{prefix}%")))).scalars().all()
    # o'chirilgan (arxiv) loyihalarning raqamlari ham qayta berilmaydi
    rows += [x.split(" / ")[0] for x in (await db.execute(select(Contract.archived_number)
                                                           .where(Contract.archived_number.like(f"{prefix}%")))).scalars().all()]
    n = max([int(x[len(prefix):]) for x in rows if x[len(prefix):].isdigit()] or [0]) + 1
    return f"{prefix}{n:05d}"


# --- saqlash ---
def _apply_location(cust: Customer, lat: float | None, lng: float | None) -> None:
    """Yurist kiritgan nuqta o'zgargan bo'lsa — «kutilmoqda» (manba legal); o'zgarmagan bo'lsa maqom saqlanadi."""
    if lat is None or lng is None:
        return
    same = cust.lat is not None and cust.lng is not None and abs(cust.lat - lat) < 1e-6 and abs(cust.lng - lng) < 1e-6
    if not same:
        cust.lat, cust.lng = lat, lng
        cust.location_status, cust.location_source = LocationStatus.pending, "legal"


def _apply(cust: Customer, ct: Contract, body: ContractDraftIn) -> None:
    r = body.requisites
    cust.name = r.name.strip()
    cust.stir = r.stir
    cust.phone = format_phone(r.phone)
    for f in ("director", "legal_address", "address", "bank", "mfo", "account", "oked", "cadastre"):
        setattr(cust, f, (getattr(r, f) or "").strip() or None)
    cust.is_rented = r.is_rented
    _apply_location(cust, r.lat, r.lng)
    ct.draft_data = None
    ct.type, ct.price, ct.annual_volume, ct.annual_trips = body.type, body.price, body.annual_volume, body.annual_trips
    ct.valid_from, ct.valid_to, ct.place, ct.sign_method = body.valid_from, body.valid_to, (body.place or "").strip(), body.sign_method
    if body.type == ContractType.by_volume and ct.source in ("manual", "import"):
        ct.tariff_price = body._tariff
        ct.price_reason = ((body.price_reason or "").strip() or None) if price_differs(body.price, body._tariff) else None
    else:
        ct.tariff_price = ct.price_reason = None


def _event(ct: Contract, actor: User, action: str, comment: str | None = None) -> None:
    ct.events.append(ContractEvent(actor_id=actor.id, action=action, comment=comment))


async def create(db: AsyncSession, actor: User, body: ContractDraftIn) -> Contract:
    cust, errs = await validate(db, actor, body)
    _raise(errs)
    prov = await _provider(db, cust.district_id)
    number = await next_number(db, prov.code if prov else "SH", body.valid_from.year)
    ct = Contract(customer_id=cust.id, number=number, status="draft", is_active=False, created_by_id=actor.id, events=[],
                  type=body.type, valid_from=body.valid_from, valid_to=body.valid_to)
    _apply(cust, ct, body)
    _event(ct, actor, "created")
    db.add(ct)
    await db.commit()
    return await get(db, actor, ct.id)


async def create_existing(db: AsyncSession, storage: Storage, actor: User, body: ContractDraftIn,
                          file: tuple[bytes, str, str] | None = None) -> Contract:
    """Mavjud (tizimdan oldin imzolangan) shartnoma: yangi shartnoma bilan bir xil to'liq ma'lumot (rekvizitlar, shartlar)
    + raqam, imzolangan sana, platforma ID. Asl hujjatning PDF'i majburiy: PDF yuklanmaguncha «Tugallanmagan» (skan kutilmoqda),
    yuklangach buxgalter tasdig'iga («Tasdiq kutilmoqda», faol)."""
    if not body.existing:
        raise invalid("existing_required", "Mavjud shartnoma ma'lumotlari yo'q")
    cust, errs = await validate(db, actor, body)
    _raise(errs)
    ex = body.existing
    pid = (ex.platform_id or "").strip() or None
    ct = Contract(customer_id=cust.id, number=(ex.number or "").strip(), status="draft", is_active=False, created_by_id=actor.id, events=[],
                  type=body.type, valid_from=body.valid_from, valid_to=body.valid_to, source="manual", signed_on=ex.signed_on,
                  platform=(ex.platform or "other") if pid else None, platform_id=pid)
    _apply(cust, ct, body)
    _event(ct, actor, "imported")
    db.add(ct)
    await db.flush()
    log(db, ct, cust, actor, "act_contract_imported", f"Mavjud shartnoma kiritildi: {ct.display_number} «{cust.name}» — PDF kutilmoqda"
        + _price_note(ct))
    if file:
        await _put_scan(storage, ct, file)
        _promote_existing(db, ct, cust, actor)
    await db.commit()
    return await get(db, actor, ct.id)


def _price_note(ct: Contract) -> str:
    if not ct.price_reason:
        return ""
    tariff = _fmt(Decimal(str(ct.tariff_price)), 0) if ct.tariff_price is not None else "yo'q"
    return f"; narx qo'lda: {_fmt(Decimal(str(ct.price)), 0)} (ta'rif {tariff}) — {ct.price_reason}"


def awaiting_scan(ct: Contract) -> bool:
    """Imzolangan nusxa (PDF) kutilmoqda: mavjud shartnoma PDF'siz yoki qog'oz imzoli loyiha (raqam berilgan, tekshirilgan)."""
    return ct.status == "draft" and bool(ct.number) and not ct.draft_data and (ct.source in ("manual", "import") or ct.sign_method == "paper")


def _promote_existing(db: AsyncSession, ct: Contract, cust: Customer, actor: User) -> None:
    """Mavjud shartnomaning PDF'i yuklandi → buxgalter tasdig'iga (faol)."""
    ct.status, ct.is_active, ct.signed_at = "signed", True, utcnow()
    _event(ct, actor, "signed")
    log(db, ct, cust, actor, "act_contract_signed", f"Mavjud shartnoma PDF'i yuklandi, buxgalteriyaga yuborildi: {ct.display_number} «{cust.name}»")


def log(db: AsyncSession, ct: Contract, cust: Customer, actor: User, kind: str, text: str, comment: str | None = None) -> None:
    from app.services import situation
    situation.activity(db, kind, text + (f" — {comment}" if comment else ""),
                       params={"contract": ct.display_number, "customer": cust.name, "comment": comment},
                       district_id=cust.district_id, actor_id=actor.id, ref=("customer", cust.id))


async def _own(db: AsyncSession, actor: User, contract_id: int, lock: bool = False, fresh: bool = False) -> Contract:
    q = select(Contract).where(Contract.id == contract_id).options(selectinload(Contract.customer), selectinload(Contract.events))
    if fresh:  # commit'dan keyin: korxona rekvizitlari va tarix yangidan o'qiladi (actor obyekti tegilmaydi)
        q = q.execution_options(populate_existing=True)
    if lock:
        q = q.with_for_update()
    ct = (await db.execute(q)).scalar_one_or_none()
    if not ct or ct.status == "deleted":
        raise not_found("contract")
    access.check_scope(actor, ct.customer.district_id)
    return ct


async def get(db: AsyncSession, actor: User, contract_id: int) -> Contract:
    return await _own(db, actor, contract_id, fresh=True)


async def update(db: AsyncSession, actor: User, contract_id: int, body: ContractDraftIn) -> Contract:
    ct = await _own(db, actor, contract_id, lock=True)
    if ct.status not in ("draft", "returned"):
        raise conflict("contract_locked", "Shartnoma imzolangan — faqat buxgalter qaytarsa o'zgartiriladi")
    body.customer_id = ct.customer_id
    cust, errs = await validate(db, actor, body, own_id=ct.id, existing_src=ct.source in ("manual", "import"))
    _raise(errs)
    _apply(cust, ct, body)
    if not ct.number:  # tugallanmagan loyiha — raqam tekshiruvdan o'tgach beriladi
        prov = await _provider(db, cust.district_id)
        ct.number = await next_number(db, prov.code if prov else "SH", body.valid_from.year)
    _event(ct, actor, "edited")
    log(db, ct, cust, actor, "act_contract_saved", f"Shartnoma ma'lumotlari saqlandi: {ct.display_number} «{cust.name}»" + _price_note(ct))
    await db.commit()
    return await get(db, actor, ct.id)


async def start(db: AsyncSession, actor: User, customer_id: int) -> Contract:
    """Usta: korxona tanlangan zahoti tugallanmagan loyiha (raqamsiz) — «Tugallanmagan shartnomalar»da qoladi."""
    cust = await db.get(Customer, customer_id)
    if not cust:
        raise not_found("customer")
    access.check_scope(actor, cust.district_id)
    today = local_day(utcnow())
    ct = Contract(customer_id=cust.id, number=None, status="draft", is_active=False, created_by_id=actor.id, events=[],
                  type=ContractType.by_volume, valid_from=today, valid_to=date(today.year, 12, 31))
    _event(ct, actor, "created")
    db.add(ct)
    await db.flush()
    log(db, ct, cust, actor, "act_contract_started", f"Yangi shartnoma boshlandi: «{cust.name}»")
    await db.commit()
    return await get(db, actor, ct.id)


async def save_draft(db: AsyncSession, actor: User, contract_id: int, body: ContractDraftIn) -> Contract:
    """Usta yopilganda yoki «Orqaga»: forma tekshiruvsiz saqlanadi (korxona kartasiga emas — loyihaga)."""
    ct = await _own(db, actor, contract_id, lock=True)
    if ct.status not in ("draft", "returned"):
        raise conflict("contract_locked", "Shartnoma imzolangan")
    ct.draft_data = body.model_dump_json(exclude={"customer_id"})
    if body.valid_from and body.valid_to and body.valid_to >= body.valid_from:
        ct.valid_from, ct.valid_to = body.valid_from, body.valid_to
    if body.annual_volume is not None:
        ct.annual_volume = body.annual_volume
    await db.commit()
    return await get(db, actor, ct.id)


DELETE_REASON_MIN = 5


async def delete_draft(db: AsyncSession, actor: User, contract_id: int, reason: str | None) -> None:
    """Tugallanmagan shartnomani o'chirish — faqat izoh bilan. Yozuv arxivga («deleted»): ro'yxat, sanoq va hisobga kirmaydi;
    raqam va platforma ID bo'shatiladi (xato kiritilgan mavjud shartnomani to'g'ri qayta kiritish uchun), eskisi archived_number'da.
    Vaziyat paneliga ogohlantirish (admin va tuman manageri)."""
    from app.models.enums import SituationLevel
    from app.services import situation
    reason = (reason or "").strip()
    if len(reason) < DELETE_REASON_MIN:
        raise invalid("reason_required", f"O'chirish sababini yozing (kamida {DELETE_REASON_MIN} belgi)")
    ct = await _own(db, actor, contract_id, lock=True)
    if ct.status != "draft":
        raise conflict("contract_locked", "Faqat tugallanmagan shartnomani o'chirish mumkin")
    cust = ct.customer
    district = await db.get(District, cust.district_id)
    label = ct.display_number or "raqamsiz loyiha"
    ct.archived_number = " / ".join(x for x in (ct.number, ct.platform_id) if x) or None
    ct.number = ct.platform_id = None
    ct.status, ct.is_active, ct.deleted_at, ct.delete_reason = "deleted", False, utcnow(), reason
    _event(ct, actor, "deleted", reason)
    situation.add(db, SituationLevel.warning, "contract_deleted",
                  f"Shartnoma o'chirildi: {label} «{cust.name}» ({district.name if district else '—'}) — {reason}",
                  params={"contract": label, "customer": cust.name, "district": district.name if district else None, "comment": reason,
                          "contract_id": ct.id},
                  district_id=cust.district_id, actor_id=actor.id, ref=("customer", cust.id))
    await situation.commit(db)


async def sign(db: AsyncSession, storage: Storage, actor: User, contract_id: int, signed_on: date, method: str,
               platform: str | None, platform_id: str | None, file: tuple[bytes, str, str] | None) -> Contract:
    ct = await _own(db, actor, contract_id, lock=True)
    if ct.status not in ("draft", "returned"):
        raise conflict("contract_locked", "Shartnoma allaqachon imzolangan")
    if not ct.number or ct.draft_data:
        raise conflict("contract_incomplete", "Avval ma'lumotlarni tekshirib, saqlang")
    if method not in ("electronic", "paper"):
        raise invalid("bad_sign_method", "Imzo usuli: elektron yoki qog'oz")
    if signed_on > local_day(utcnow()):
        raise invalid("bad_dates", "Imzolangan sana kelajakda bo'lmasin")
    pid = (platform_id or "").strip() or None
    if method == "electronic":
        if platform not in PLATFORMS or not pid:
            raise invalid("platform_required", "Elektron imzoda platforma va hujjat ID kiritiladi")
        dup = (await db.execute(select(Contract.id).where(Contract.platform_id == pid, Contract.id != ct.id))).first()
        if dup:
            raise conflict("platform_id_taken", "Bu platforma ID boshqa shartnomada bor")
    if method == "paper" and not file and not ct.scan_key:
        # Qog'ozda: imzolangan nusxaning skani (PDF) yuklanmaguncha «Tugallanmagan»da qoladi
        raise invalid("scan_required_paper", "Qog'ozda imzolangan shartnomaning skanini (PDF) yuklang")
    if file:
        await _put_scan(storage, ct, file)
    was_returned = ct.status == "returned"
    ct.status, ct.is_active, ct.signed_on, ct.sign_method = "signed", True, signed_on, method
    ct.platform, ct.platform_id = (platform if method == "electronic" else None), (pid if method == "electronic" else None)
    ct.signed_at, ct.return_comment = utcnow(), None
    _event(ct, actor, "resubmitted" if was_returned else "signed")
    log(db, ct, ct.customer, actor, "act_contract_signed", f"Shartnoma imzolandi, buxgalteriyaga yuborildi: {ct.display_number} «{ct.customer.name}»"
        + (" (qayta)" if was_returned else ""))
    await db.commit()
    return await get(db, actor, ct.id)


async def _put_scan(storage: Storage, ct: Contract, file: tuple[bytes, str, str]) -> None:
    data, ctype, name = file
    ctype = (ctype or "").split(";")[0].strip().lower()
    if ctype not in SCAN_TYPES:
        raise invalid("bad_scan", "Fayl faqat PDF bo'lsin")
    if not data or len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise invalid("file_too_large", f"Fayl bo'sh yoki {get_settings().max_upload_mb} MB dan katta")
    key = f"contracts/{ct.id}/{uuid4().hex}.{SCAN_TYPES[ctype]}"
    await run_in_threadpool(storage.put, key, data, ctype)
    ct.scan_key, ct.scan_type, ct.scan_name = key, ctype, (name or "")[:150] or None


async def attach_scan(db: AsyncSession, storage: Storage, actor: User, contract_id: int, file: tuple[bytes, str, str]) -> Contract:
    ct = await _own(db, actor, contract_id, lock=True)
    await _put_scan(storage, ct, file)
    if ct.status == "draft" and ct.source in ("manual", "import") and ct.number:
        _promote_existing(db, ct, ct.customer, actor)
    await db.commit()
    return await get(db, actor, ct.id)


async def approve(db: AsyncSession, actor: User, contract_id: int) -> Contract:
    ct = await _own(db, actor, contract_id, lock=True)
    if ct.status != "signed":
        raise conflict("contract_not_signed", "Faqat imzolangan (tasdiq kutayotgan) shartnoma tasdiqlanadi")
    ct.status, ct.approved_at, ct.approved_by_id = "approved", utcnow(), actor.id
    _event(ct, actor, "approved")
    log(db, ct, ct.customer, actor, "act_contract_approved", f"Buxgalter tasdiqladi: {ct.display_number} «{ct.customer.name}»")
    await db.commit()
    return await get(db, actor, ct.id)


async def return_(db: AsyncSession, actor: User, contract_id: int, comment: str) -> Contract:
    ct = await _own(db, actor, contract_id, lock=True)
    if ct.status != "signed":
        raise conflict("contract_not_signed", "Faqat tasdiq kutayotgan shartnoma qaytariladi")
    ct.status, ct.return_comment = "returned", comment.strip()
    _event(ct, actor, "returned", comment.strip())
    log(db, ct, ct.customer, actor, "act_contract_returned", f"Buxgalter qaytardi: {ct.display_number} «{ct.customer.name}»", comment.strip())
    await db.commit()
    return await get(db, actor, ct.id)


async def scan(db: AsyncSession, storage: Storage, actor: User, contract_id: int) -> tuple[bytes, str, str]:
    ct = await _own(db, actor, contract_id)
    if not ct.scan_key:
        raise not_found("scan")
    return await run_in_threadpool(storage.get, ct.scan_key), ct.scan_type or "application/octet-stream", ct.scan_name or "scan"


# --- ro'yxat ---
async def used_m3(db: AsyncSession, contracts: list[Contract]) -> dict[int, float]:
    """Shartnoma muddati ichida yashil murojaatlarning kubi (varaqa yoki akt)."""
    if not contracts:
        return {}
    custs = list((await db.execute(select(Customer).where(Customer.id.in_({c.customer_id for c in contracts})))).scalars())
    led = await billing.load(db, custs)
    return {c.id: float(led.usage.get(c.id, 0)) for c in contracts}


async def search(db: AsyncSession, actor: User, status: str | None = None, q: str | None = None, district_id: int | None = None,
                 limit: int = 100, offset: int = 0) -> tuple[list[Contract], int]:
    qry = select(Contract).join(Customer, Customer.id == Contract.customer_id)
    s = access.scope(actor)
    if s is not None:
        qry = qry.where(Customer.district_id.in_(s or {-1}))
    if district_id:
        qry = qry.where(Customer.district_id == district_id)
    if status:
        qry = qry.where(Contract.status.in_([x for x in status.split(",") if x != "deleted"] or ["-"]))
    else:
        qry = qry.where(Contract.status != "deleted")
    if q and q.strip():
        t = f"%{q.strip().lower()}%"
        qry = qry.where(or_(func.lower(Customer.name).like(t), func.lower(Customer.code).like(t), Customer.stir.like(t),
                            func.lower(Contract.number).like(t), Contract.platform_id.like(t)))
    total = (await db.execute(select(func.count()).select_from(qry.subquery()))).scalar_one()
    rows = list((await db.execute(qry.options(selectinload(Contract.customer), selectinload(Contract.events))
                                  .order_by(Contract.id.desc()).limit(limit).offset(offset))).scalars())
    return rows, total


STATUS_LABEL = {"draft": "loyiha", "signed": "tasdiq kutilmoqda", "returned": "qaytarilgan", "approved": "tasdiqlangan"}


def out(ct: Contract, used: float | None = None, with_events: bool = False) -> dict:
    t = totals(ct.type, ct.price, ct.annual_volume, ct.annual_trips, ct.valid_from, ct.valid_to)
    c = ct.customer
    d = {"id": ct.id, "number": ct.number, "platform": ct.platform, "platform_id": ct.platform_id, "display_number": ct.display_number,
         "status": ct.status, "type": ct.type.value, "price": float(ct.price) if ct.price is not None else None,
         "annual_volume": float(ct.annual_volume) if ct.annual_volume is not None else None, "annual_trips": ct.annual_trips,
         "valid_from": ct.valid_from, "valid_to": ct.valid_to, "signed_on": ct.signed_on, "place": ct.place, "sign_method": ct.sign_method,
         "has_scan": bool(ct.scan_key), "return_comment": ct.return_comment, "signed_at": ct.signed_at, "approved_at": ct.approved_at,
         "created_at": ct.created_at, "total": float(t["total"]), "vat": float(t["vat"]), "is_active": ct.is_active,
         "customer": {"id": c.id, "name": c.name, "code": c.code, "stir": c.stir, "district_id": c.district_id, "director": c.director,
                      "phone": c.phone, "legal_address": c.legal_address, "address": c.address, "bank": c.bank, "mfo": c.mfo,
                      "account": c.account, "oked": c.oked, "cadastre": c.cadastre, "is_rented": c.is_rented,
                      "lat": c.lat, "lng": c.lng, "location_status": c.location_status.value} if c else None,
         "draft": json.loads(ct.draft_data) if ct.draft_data else None, "source": ct.source, "awaiting_scan": awaiting_scan(ct),
         "tariff_price": float(ct.tariff_price) if ct.tariff_price is not None else None, "price_reason": ct.price_reason,
         "submitted_by": next((e.actor.full_name for e in reversed(ct.events) if e.action in ("signed", "resubmitted", "imported") and e.actor),
                              None) if "events" in ct.__dict__ else None}
    if used is not None:
        d["used_m3"] = used
        if ct.annual_volume:
            pct = used / float(ct.annual_volume) * 100
            d["usage_pct"] = round(pct, 1)
            d["usage_level"] = "over" if pct >= 100 else "warn" if pct >= 90 else "ok"
    if with_events:
        d["events"] = [{"action": e.action, "comment": e.comment, "at": e.created_at, "actor": e.actor.full_name if e.actor else None}
                       for e in ct.events]
    return d


# --- hujjat ---
def _blank(v) -> str:
    return (str(v).strip() if v not in (None, "") else "") or "______"


def context(ct: Contract, cust: Customer, prov: Provider | None) -> dict:
    t = totals(ct.type, ct.price, ct.annual_volume, ct.annual_trips, ct.valid_from, ct.valid_to)
    qty_dec = 0 if t["qty"] == t["qty"].to_integral() else 3
    vf, vt = ct.valid_from, ct.valid_to
    p = prov
    return {
        "number": ct.platform_id or ct.number or "______", "place": _blank(ct.place), "date": (ct.signed_on or ct.valid_from).strftime("%d.%m.%Y"),
        "valid_from": vf.strftime("%d.%m.%Y"), "valid_to": vt.strftime("%d.%m.%Y"),
        "vf_d": f"{vf.day:02d}", "vf_m": f"{vf.month:02d}", "vf_y": str(vf.year), "vt_d": f"{vt.day:02d}", "vt_m": f"{vt.month:02d}", "vt_y": str(vt.year),
        "provider_name": _blank(p.full_name or p.name if p else None), "provider_director": _blank(p.director if p else None),
        "provider_address": _blank(p.address if p else None), "provider_phone": _blank(p.phone if p else None),
        "provider_inn": _blank(p.inn if p else None), "provider_oked": _blank(p.oked if p else None),
        "provider_account": _blank(p.account if p else None), "provider_bank": _blank(p.bank if p else None),
        "provider_mfo": _blank(p.mfo if p else None),
        "customer_name": _blank(cust.name), "customer_director": _blank(cust.director),
        "customer_address": _blank(cust.legal_address or cust.address), "customer_phone": _blank(cust.phone),
        "customer_stir": _blank(cust.stir), "customer_oked": _blank(cust.oked), "customer_account": _blank(cust.account),
        "customer_bank": _blank(cust.bank), "customer_mfo": _blank(cust.mfo),
        "object_address": _blank(cust.address or cust.legal_address), "cadastre": _blank(cust.cadastre),
        "ownership": "ijara" if cust.is_rented else "mulk",
        "ownership_text": "ijara huquqi asosida foydalanishga berilgan" if cust.is_rented else "mulk huquqi asosida tegishli",
        "qty": f"{t['qty']:,.{qty_dec}f}".replace(",", " "), "unit": t["unit"],
        "unit_net": _fmt(t["unit_net"]), "net": _fmt(t["net"]), "vat": _fmt(t["vat"]), "total": _fmt(t["total"]),
        "total_words": money_words(t["total"]), "price": _fmt(t["price"], 0), "price_words": money_words(t["price"]).split(" so‘m")[0],
    }


async def document(db: AsyncSession, actor: User, contract_id: int, fmt: str) -> tuple[bytes, str, str]:
    from app.services.contract_doc import render_docx, render_pdf
    ct = await _own(db, actor, contract_id)
    prov = await _provider(db, ct.customer.district_id)
    key, build = contract_templates.pick(prov.code if prov else None)
    blocks = build(context(ct, ct.customer, prov))
    title = f"Shartnoma {ct.display_number}"
    paper = ct.sign_method == "paper"
    fname = re.sub(r"[^\w\-]+", "_", f"shartnoma_{ct.display_number}")
    if fmt == "docx":
        data = await run_in_threadpool(render_docx, blocks, title, paper)
        return data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", f"{fname}.docx"
    mark = "LOYIHA — imzolanmagan" if ct.status == "draft" else None
    return await run_in_threadpool(render_pdf, blocks, title, paper, mark), "application/pdf", f"{fname}.pdf"


# --- GPS: «Yangi shartnoma» belgisi ---
def is_new(ct: Contract | None, today: date | None = None) -> bool:
    if not ct or ct.status not in LIVE or not ct.signed_at:
        return False
    today = today or local_day(utcnow())
    return (today - local_day(ct.signed_at)).days < NEW_BADGE_DAYS
