"""Korxona kartasi: yaratish, tahrirlash, aloqalar, shartnomalar, koordinatani tasdiqlash."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, conflict, forbidden, invalid, not_found
from app.models import Contract, Customer, CustomerContact, District, User
from app.models.enums import LocationStatus, Role, SituationLevel
from app.repositories import customers as repo
from app.schemas import (
    ContactIn,
    ContractIn,
    CustomerIn,
    CustomerUpdateIn,
    LocationConfirmIn,
)
from app.services import access, situation
from app.services.customer_import import next_fixed_no_start
from app.services.geo import valid_coords
from app.services.normalize import format_phone, key, phone_digits


def _notify(actor: User | None) -> bool:
    """Manager o'zgarishlari admin Vaziyat paneliga yoziladi."""
    return actor is not None and actor.role == Role.manager


def _event(db: AsyncSession, actor: User | None, kind: str, cust: Customer, message: str, extra: dict | None = None) -> None:
    if _notify(actor):
        situation.add(db, SituationLevel.info, kind, message, params={"customer": cust.name, "fixed_no": cust.fixed_no, **(extra or {})},
                      district_id=cust.district_id, actor_id=actor.id, ref=("customer", cust.id))


def check_district_access(user: User, district_id: int) -> None:
    """Tumanga bog'langan xodim (GPS) faqat o'z tumanini ko'radi."""
    if not access.in_scope(user, district_id):
        raise forbidden("Bu korxona sizning tumaningizga tegishli emas")


async def _load(db: AsyncSession, customer_id: int, lock: bool = False, actor: User | None = None) -> Customer:
    cust = await repo.get(db, customer_id, lock=lock)
    if not cust:
        raise not_found("customer")
    if actor is not None:
        check_district_access(actor, cust.district_id)
    return cust


async def _check_stir(db: AsyncSession, stir: str | None, own_id: int | None = None) -> None:
    """STIR takrorlanmaydi: boshqa korxonaga tegishli bo'lsa — "STIRni xato kiritdingiz" va o'sha korxona."""
    if stir:
        other = await repo.by_stir(db, stir)
        if other and other.id != own_id:
            raise stir_taken(other)


def stir_taken(other: Customer) -> AppError:
    return AppError(409, "stir_taken", f"Siz STIRni xato kiritdingiz — bu STIR «{other.name}» korxonasiga tegishli",
                    {"customer_id": other.id, "name": other.name, "district_id": other.district_id})


async def _check_name(db: AsyncSession, district_id: int, name: str, own_id: int | None = None) -> str:
    k = key(name)
    if not k:
        raise invalid("bad_name", "Korxona nomi noto'g'ri")
    other = await repo.by_name_key(db, district_id, k)
    if other and other.id != own_id:
        raise conflict("customer_exists", f"Bu tumanda shu nomli korxona bor: {other.fixed_no}")
    return k


async def create(db: AsyncSession, body: CustomerIn, actor: User | None = None) -> Customer:
    district = await db.get(District, body.district_id)
    if not district or not district.is_active:
        raise not_found("district")
    if actor is not None:
        check_district_access(actor, district.id)
    name_key = await _check_name(db, body.district_id, body.name)
    await _check_stir(db, body.stir)
    cust = Customer(fixed_no=f"A-{await next_fixed_no_start(db):04d}", name=body.name.strip(), name_key=name_key,
                    district_id=body.district_id, stir=body.stir, director=body.director, address=body.address,
                    activity_type=body.activity_type, phone=format_phone(body.phone), source="manual",
                    location_status=LocationStatus.none)
    db.add(cust)
    await db.flush()
    _event(db, actor, "customer_created", cust, f"Manager korxona qo'shdi: {cust.fixed_no} «{cust.name}»")
    await situation.commit(db)
    return await _load(db, cust.id)


async def update(db: AsyncSession, customer_id: int, body: CustomerUpdateIn, actor: User | None = None) -> Customer:
    cust = await _load(db, customer_id, lock=True, actor=actor)
    data = body.model_dump(exclude_unset=True)
    fields = ("name", "stir", "director", "phone", "address", "activity_type")
    before = {f: getattr(cust, f) for f in fields}
    if data.get("name"):
        cust.name_key = await _check_name(db, cust.district_id, data["name"], cust.id)
        cust.name = data["name"].strip()
    if "stir" in data:
        await _check_stir(db, data["stir"], cust.id)
        cust.stir = data["stir"]
    if "phone" in data:
        cust.phone = format_phone(data["phone"])
    for f in ("director", "address", "activity_type"):
        if f in data:
            setattr(cust, f, (data[f] or "").strip() or None)
    labels = {"name": "nomi", "stir": "STIR", "director": "rahbar", "phone": "telefon", "address": "manzil", "activity_type": "faoliyat turi"}
    changes = "; ".join(f"{labels[f]}: {before[f] or '—'} → {getattr(cust, f) or '—'}" for f in fields if before[f] != getattr(cust, f))
    if changes:
        _event(db, actor, "customer_updated", cust, f"Manager korxonani o'zgartirdi: {cust.fixed_no} «{cust.name}» — {changes}",
               {"changes": changes})
    await situation.commit(db)
    return await _load(db, cust.id)


async def add_contact(db: AsyncSession, customer_id: int, body: ContactIn, actor: User | None = None) -> Customer:
    cust = await _load(db, customer_id, lock=True, actor=actor)
    if len(phone_digits(body.phone)) != 9:
        raise invalid("bad_phone", "Telefon raqami 9 xonali bo'lishi kerak (masalan, 94 512 11 16)")
    phone = format_phone(body.phone)
    if any(c.phone == phone for c in cust.contacts):
        raise conflict("contact_exists", "Bu raqam allaqachon bor")
    cust.contacts.append(CustomerContact(name=(body.name or "").strip() or None, phone=phone))
    cust.phone = cust.phone or phone
    _event(db, actor, "customer_updated", cust, f"Manager korxonaga raqam qo'shdi: {cust.fixed_no} «{cust.name}» — {phone}",
           {"changes": f"+{phone}"})
    await situation.commit(db)
    return await _load(db, cust.id)


async def add_contract(db: AsyncSession, customer_id: int, body: ContractIn, actor: User | None = None) -> Customer:
    cust = await _load(db, customer_id, lock=True, actor=actor)
    if body.valid_to < body.valid_from:
        raise invalid("bad_dates", "Tugash sanasi boshlanish sanasidan oldin bo'lmasin")
    number = body.number.strip()
    if await repo.contract_by_number(db, number):
        raise conflict("contract_number_taken", "Bu raqamli shartnoma bor")
    db.add(Contract(customer_id=cust.id, number=number, type=body.type, signed_on=body.signed_on, price=body.price,
                    valid_from=body.valid_from, valid_to=body.valid_to, is_active=True))
    _event(db, actor, "customer_updated", cust, f"Manager shartnoma qo'shdi: {cust.fixed_no} «{cust.name}» — {number}",
           {"changes": f"+{number}"})
    await situation.commit(db)
    return await _load(db, cust.id)


async def confirm_location(db: AsyncSession, customer_id: int, body: LocationConfirmIn, actor: User | None = None) -> Customer:
    cust = await _load(db, customer_id, lock=True, actor=actor)
    if (body.lat is None) != (body.lng is None):
        raise invalid("bad_coords", "lat va lng birga beriladi")
    if body.lat is not None:
        if not valid_coords(body.lat, body.lng):
            raise invalid("bad_coords", "Koordinatalar noto'g'ri")
        cust.lat, cust.lng = body.lat, body.lng
    elif cust.lat is None or cust.lng is None:
        raise conflict("no_location", "Tasdiqlash uchun koordinata yo'q — birinchi tashrifni kuting yoki qo'lda kiriting")
    cust.location_status, cust.location_source = LocationStatus.confirmed, "manager"
    _event(db, actor, "customer_updated", cust, f"Manager koordinatani tasdiqladi: {cust.fixed_no} «{cust.name}» — {cust.lat:.6f}, {cust.lng:.6f}",
           {"changes": f"{cust.lat:.6f}, {cust.lng:.6f}"})
    await situation.commit(db)
    return await _load(db, cust.id)
