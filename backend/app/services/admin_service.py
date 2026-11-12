"""Xodimlar, tumanlar, mashinalar va sozlamalar qoidalari. O'chirish yo'q — faqat faolsizlantirish, tarix saqlanadi.

Admin — cheklovsiz. Manager — faqat berilgan ruxsatlar va o'z tumanlari doirasida; uning har bir o'zgarishi
admin Vaziyat paneliga "eski → yangi" ko'rinishida yoziladi. Manager yaratgan xodim admin tasdiqlamaguncha kira olmaydi.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import conflict, forbidden, invalid, not_found
from app.core.permissions import ALL_CODES, MULTI_DISTRICT_ROLES, SINGLE_DISTRICT_ROLES, STAFF_ROLES, template
from app.core.security import hash_password
from app.models import AppSetting, District, Region, User, UserDistrict, UserPermission, Vehicle
from app.models.enums import Role, SituationLevel
from app.repositories import catalog
from app.repositories import settings as settings_repo
from app.repositories import shifts as shift_repo
from app.repositories import users as users_repo
from app.schemas import AccessIn, DistrictIn, DistrictUpdateIn, UserCreateIn, UserUpdateIn, VehicleIn, VehicleUpdateIn
from app.services import access, situation
from app.services.auth_service import check_password_strength

I, W = SituationLevel.info, SituationLevel.warning


def _diff(obj, data: dict, fields: tuple[str, ...]) -> list[dict]:
    """O'zgargan maydonlar: [{"field", "old", "new"}] — Vaziyat paneli uchun."""
    out = []
    for f in fields:
        if f in data:
            old, new = getattr(obj, f), data[f]
            old = old.value if hasattr(old, "value") else old
            new = new.value if hasattr(new, "value") else new
            if old != new:
                out.append({"field": f, "old": old, "new": new})
    return out


# Vaziyat panelida maydon nomlari o'zbekcha
FIELD_LABELS = {"full_name": "F.I.Sh.", "phone": "telefon", "role": "rol", "language": "til", "districts": "tumanlar",
                "plate": "davlat raqami", "model": "model", "district_id": "tuman", "is_active": "holat"}


def _diff_text(changes: list[dict]) -> str:
    def v(x):
        return "—" if x in (None, "", []) else ", ".join(map(str, x)) if isinstance(x, list) else str(x)
    return "; ".join(f"{FIELD_LABELS.get(c['field'], c['field'])}: {v(c['old'])} → {v(c['new'])}" for c in changes)


async def _district_names(db: AsyncSession) -> dict[int, str]:
    return {d.id: d.name for d in (await db.execute(select(District))).scalars()}


async def _check_district(db: AsyncSession, district_id: int | None) -> None:
    if district_id:
        d = await db.get(District, district_id)
        if not d:
            raise not_found("district")
        if not d.is_active:
            raise invalid("district_inactive", "Bu tuman faolsizlantirilgan")


async def _resolve_districts(db: AsyncSession, actor: User, role: Role, district_id: int | None,
                             district_ids: list[int]) -> tuple[int | None, list[int]]:
    """Rolga qarab: GPS/haydovchi — bitta tuman (majburiy); manager/yurist/operator — bir nechta; admin — yo'q."""
    if role in SINGLE_DISTRICT_ROLES:
        if not district_id:
            raise invalid("district_required", "Haydovchi va GPS xodimi tumanga biriktirilishi shart")
        await _check_district(db, district_id)
        access.check_scope(actor, district_id)
        return district_id, []
    if role in MULTI_DISTRICT_ROLES:
        ids = sorted(set(district_ids))
        for d in ids:
            await _check_district(db, d)
            access.check_scope(actor, d)
        if not access.is_admin(actor) and not ids:
            raise invalid("district_required", "Kamida bitta tuman tanlang")
        return None, ids
    return None, []


def _set_districts(user: User, ids: list[int]) -> None:
    user.district_rows = [UserDistrict(district_id=d) for d in ids]


def _set_permissions(user: User, codes: list[str], actor: User) -> None:
    keep = {p.code: p for p in user.perm_rows if p.code in codes}
    user.perm_rows = [keep.get(c) or UserPermission(code=c, granted_by_id=actor.id) for c in sorted(set(codes))]


async def list_users(db: AsyncSession, actor: User, role: Role | None, district_id: int | None, active: bool | None) -> list[User]:
    users = await catalog.list_users(db, role, None, active)
    if district_id:
        users = [u for u in users if district_id in u.district_ids]
    if not access.is_admin(actor):
        users = [u for u in users if access.is_own_staff(actor, u)]
    return users


async def create_user(db: AsyncSession, actor: User, body: UserCreateIn) -> User:
    if not access.is_admin(actor) and body.role not in STAFF_ROLES:
        raise forbidden("Manager faqat GPS xodimi, yurist, operator yoki haydovchi qo'sha oladi")
    if not get_settings().role_active(body.role.value):
        raise invalid("role_inactive", "Bu rol hozircha faol emas")
    if await users_repo.by_username(db, body.username):
        raise conflict("username_taken", "Bu login band")
    district_id, district_ids = await _resolve_districts(db, actor, body.role, body.district_id, body.district_ids)
    check_password_strength(body.password)
    pending = not access.is_admin(actor)
    user = User(username=body.username, full_name=body.full_name.strip(), phone=body.phone, role=body.role,
                district_id=district_id, language=body.language, password_hash=hash_password(body.password),
                must_change_password=True, created_by_id=actor.id,
                approval_status="pending" if pending else "approved", is_active=not pending)
    _set_districts(user, district_ids)
    _set_permissions(user, template(body.role), actor)
    db.add(user)
    await db.flush()
    params = {"name": user.full_name, "username": user.username, "role": user.role.value}
    first_district = district_id or (district_ids[0] if district_ids else None)
    if pending:
        situation.add(db, W, "staff_pending", f"Manager yangi xodim qo'shdi — tasdiqlang: {user.full_name} ({user.username}, {user.role.value})",
                      params=params, district_id=first_district, actor_id=actor.id, ref=("user", user.id))
    else:
        situation.add(db, I, "user_created", f"Yangi xodim: {user.full_name} ({user.username}, {user.role.value})",
                      params=params, district_id=first_district, actor_id=actor.id, ref=("user", user.id))
    await situation.commit(db)
    return await users_repo.by_id(db, user.id)


async def _target(db: AsyncSession, actor: User, user_id: int) -> User:
    user = await users_repo.by_id(db, user_id)
    if not user:
        raise not_found("user")
    access.check_own_staff(actor, user)
    return user


async def update_user(db: AsyncSession, actor: User, user_id: int, body: UserUpdateIn) -> User:
    user = await _target(db, actor, user_id)
    data = body.model_dump(exclude_unset=True)
    if user.id == actor.id and (data.get("is_active") is False or data.get("role", user.role) != user.role):
        raise conflict("cannot_change_self", "O'zingizni faolsizlantira yoki rolingizni o'zgartira olmaysiz")
    if "is_active" in data and data["is_active"] != user.is_active and not actor.can("staff.deactivate"):
        raise forbidden("Faolsizlantirish uchun ruxsat yo'q")
    if set(data) - {"is_active"} and not actor.can("staff.edit"):
        raise forbidden("Tahrirlash uchun ruxsat yo'q")
    if data.get("is_active") and user.approval_status != "approved":
        raise conflict("user_not_approved", "Xodim hali admin tomonidan tasdiqlanmagan")
    role = data.get("role") or user.role
    if not access.is_admin(actor) and role not in STAFF_ROLES:
        raise forbidden("Manager faqat GPS xodimi, yurist, operator yoki haydovchi rolini bera oladi")
    district_changed = "role" in data or "district_id" in data or "district_ids" in data
    if district_changed:
        district_id, district_ids = await _resolve_districts(
            db, actor, role, data.get("district_id", user.district_id),
            data["district_ids"] if data.get("district_ids") is not None else [d for d in user.district_ids if d != user.district_id])
    if user.role == Role.driver and (data.get("is_active") is False or district_changed):
        if await shift_repo.open_for_driver(db, user.id):
            raise conflict("driver_has_open_shift", "Haydovchida ochiq smena bor — avval smenani yoping")

    old_districts = user.district_ids
    changes = _diff(user, data, ("full_name", "phone", "role", "language", "is_active"))
    was_active, old_role = user.is_active, user.role
    for key in ("full_name", "phone", "role", "language", "is_active"):
        if key in data and data[key] is not None or key == "phone" and "phone" in data:
            setattr(user, key, data[key].strip() if key == "full_name" else data[key])
    if district_changed:
        user.district_id = district_id
        _set_districts(user, district_ids)
        if sorted(old_districts) != user.district_ids:
            names = await _district_names(db)
            changes.append({"field": "districts", "old": [names.get(d, d) for d in old_districts],
                            "new": [names.get(d, d) for d in user.district_ids]})
    if user.role != old_role:
        _set_permissions(user, template(user.role), actor)  # yangi rol — yangi andoza

    params = {"name": user.full_name, "username": user.username}
    if user.is_active != was_active:
        kind = "user_activated" if user.is_active else "user_deactivated"
        situation.add(db, I if user.is_active else W, kind,
                      f"Xodim {'faollashtirildi' if user.is_active else 'faolsizlantirildi'}: {user.full_name} ({user.username})",
                      params=params, district_id=(user.district_ids or [None])[0], actor_id=actor.id, ref=("user", user.id))
    other = [c for c in changes if c["field"] != "is_active"]
    if other and not access.is_admin(actor):
        situation.add(db, I, "staff_updated", f"Manager xodim ma'lumotini o'zgartirdi: {user.full_name} — {_diff_text(other)}",
                      params={**params, "changes": _diff_text(other)}, district_id=(user.district_ids or [None])[0],
                      actor_id=actor.id, ref=("user", user.id))
    await situation.commit(db)
    return await users_repo.by_id(db, user.id)


async def reset_password(db: AsyncSession, actor: User, user_id: int, password: str) -> User:
    user = await _target(db, actor, user_id)
    check_password_strength(password)
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.failed_logins = 0
    user.locked_until = None  # blokdan chiqarish ham shu yerda
    situation.add(db, I, "password_reset", f"Parol tiklandi: {user.full_name} ({user.username})",
                  params={"name": user.full_name, "username": user.username},
                  district_id=(user.district_ids or [None])[0], actor_id=actor.id, ref=("user", user.id))
    await situation.commit(db)
    return user


async def decide_user(db: AsyncSession, admin: User, user_id: int, approve: bool) -> User:
    """Manager qo'shgan xodimni admin tasdiqlaydi yoki rad etadi."""
    user = await users_repo.by_id(db, user_id)
    if not user:
        raise not_found("user")
    if user.approval_status != "pending":
        raise conflict("user_not_pending", "Bu xodim bo'yicha qaror allaqachon qabul qilingan")
    user.approval_status = "approved" if approve else "rejected"
    user.is_active = approve
    situation.add(db, I if approve else W, "staff_approved" if approve else "staff_rejected",
                  f"Xodim {'tasdiqlandi' if approve else 'rad etildi'}: {user.full_name} ({user.username})",
                  params={"name": user.full_name, "username": user.username},
                  district_id=(user.district_ids or [None])[0], actor_id=admin.id, ref=("user", user.id))
    await situation.commit(db)
    return user


# --- huquqlar ---
def grantable(actor: User) -> list[str]:
    """Joriy xodim boshqalarga bera/ola oladigan ruxsatlar: admin — hammasi; manager — faqat o'zida borlari."""
    if access.is_admin(actor):
        return sorted(ALL_CODES)
    return sorted(c for c in actor.permissions if c in ALL_CODES) if actor.can("staff.permissions") else []


async def get_access(db: AsyncSession, actor: User, user_id: int) -> dict:
    user = await _target(db, actor, user_id)
    return {"user_id": user.id, "role": user.role, "permissions": user.permissions, "district_ids": user.district_ids,
            "multi_district": user.role in MULTI_DISTRICT_ROLES, "grantable": grantable(actor),
            "assignable_district_ids": None if access.is_admin(actor) else actor.district_ids}


async def set_access(db: AsyncSession, actor: User, user_id: int, body: AccessIn) -> dict:
    user = await _target(db, actor, user_id)
    if user.role == Role.admin:
        raise conflict("admin_has_all", "Admin barcha ruxsatlarga ega")
    if user.id == actor.id:
        raise conflict("cannot_change_self", "O'z ruxsatlaringizni o'zgartira olmaysiz")
    unknown = set(body.permissions) - ALL_CODES
    if unknown:
        raise invalid("unknown_permission", "Noma'lum ruxsat: " + ", ".join(sorted(unknown)))
    allowed = set(grantable(actor))
    if not allowed:
        raise forbidden("Ruxsat berish uchun ruxsat yo'q")
    current = set(user.permissions)
    wanted = set(body.permissions)
    # Manager faqat o'zida bor ruxsatlarni o'zgartiradi; boshqalari avvalgidek qoladi
    forbidden_changes = (wanted ^ current) - allowed
    if forbidden_changes:
        raise forbidden("Sizda yo'q ruxsatni bera yoki ola olmaysiz: " + ", ".join(sorted(forbidden_changes)))
    added, removed = sorted(wanted - current), sorted(current - wanted)
    _set_permissions(user, sorted(wanted), actor)

    d_added: list[int] = []
    d_removed: list[int] = []
    if body.district_ids is not None:
        if user.role not in MULTI_DISTRICT_ROLES:
            raise invalid("single_district_role", "GPS xodimi va haydovchi tumani xodim kartasida o'zgartiriladi")
        ids = sorted(set(body.district_ids))
        old = set(user.district_ids)
        for d in set(ids) ^ old:
            if d in ids:
                await _check_district(db, d)
            access.check_scope(actor, d)
        if not access.is_admin(actor) and not ids:
            raise invalid("district_required", "Kamida bitta tuman qoldiring")
        d_added, d_removed = sorted(set(ids) - old), sorted(old - set(ids))
        _set_districts(user, ids)

    if added or removed or d_added or d_removed:
        names = {d.id: d.name for d in (await db.execute(select(District))).scalars()}
        parts = ([f"+{', '.join(added)}"] if added else []) + ([f"−{', '.join(removed)}"] if removed else []) + \
                ([f"tuman +{', '.join(names[d] for d in d_added)}"] if d_added else []) + \
                ([f"tuman −{', '.join(names[d] for d in d_removed)}"] if d_removed else [])
        situation.add(db, I, "access_changed", f"Ruxsatlar o'zgardi: {user.full_name} ({user.username}) — {'; '.join(parts)}",
                      params={"name": user.full_name, "username": user.username, "added": ", ".join(added) or "—",
                              "removed": ", ".join(removed) or "—",
                              "districts_added": ", ".join(names[d] for d in d_added) or "—",
                              "districts_removed": ", ".join(names[d] for d in d_removed) or "—"},
                      district_id=(user.district_ids or [None])[0], actor_id=actor.id, ref=("user", user.id))
    await situation.commit(db)
    return await get_access(db, actor, user.id)


# --- tumanlar ---
async def list_districts(db: AsyncSession, actor: User) -> list[District]:
    rows = await catalog.districts(db)
    s = access.scope(actor)
    return rows if s is None else [d for d in rows if d.id in s]


async def create_district(db: AsyncSession, body: DistrictIn) -> District:
    if not await db.get(Region, body.region_id):
        raise not_found("region")
    d = District(name=body.name.strip(), region_id=body.region_id)
    db.add(d)
    await db.commit()
    return d


async def update_district(db: AsyncSession, actor: User, district_id: int, body: DistrictUpdateIn) -> District:
    d = await db.get(District, district_id)
    if not d:
        raise not_found("district")
    data = body.model_dump(exclude_unset=True)
    if data.get("is_active") is False and await shift_repo.open_in_district(db, d.id):
        raise conflict("district_has_open_shifts", "Tumanda ochiq smenalar bor")
    if "name" in data:
        d.name = data["name"].strip()
    if "is_active" in data and d.is_active != data["is_active"]:
        d.is_active = data["is_active"]
        situation.add(db, I if d.is_active else W, "district_activated" if d.is_active else "district_deactivated",
                      f"Tuman {'faollashtirildi' if d.is_active else 'faolsizlantirildi'}: {d.name}",
                      params={"name": d.name}, district_id=d.id, actor_id=actor.id, ref=("district", d.id))
    await situation.commit(db)
    return d


# --- mashinalar ---
def normalize_plate(plate: str) -> str:
    """'60 a123bc' → '60 A123BC': katta harf, ortiqcha bo'shliqlarsiz."""
    return " ".join(plate.upper().split())


async def list_vehicles(db: AsyncSession, actor: User, district_id: int | None) -> list[Vehicle]:
    rows = await catalog.vehicles(db, district_id)
    s = access.scope(actor)
    return rows if s is None else [v for v in rows if v.district_id in s]


async def create_vehicle(db: AsyncSession, actor: User, body: VehicleIn) -> Vehicle:
    plate = normalize_plate(body.plate)
    if await catalog.vehicle_by_plate(db, plate):
        raise conflict("plate_taken", "Bu davlat raqami allaqachon bor")
    await _check_district(db, body.district_id)
    access.check_scope(actor, body.district_id)
    v = Vehicle(plate=plate, model=body.model, district_id=body.district_id)
    db.add(v)
    await db.flush()
    if not access.is_admin(actor):
        situation.add(db, I, "vehicle_created", f"Manager mashina qo'shdi: {v.plate}", params={"plate": v.plate},
                      district_id=v.district_id, actor_id=actor.id, ref=("vehicle", v.id))
    await situation.commit(db)
    return v


async def update_vehicle(db: AsyncSession, actor: User, vehicle_id: int, body: VehicleUpdateIn) -> Vehicle:
    v = await db.get(Vehicle, vehicle_id)
    if not v:
        raise not_found("vehicle")
    access.check_scope(actor, v.district_id)
    data = body.model_dump(exclude_unset=True)
    if "is_active" in data and data["is_active"] != v.is_active and not actor.can("vehicles.deactivate"):
        raise forbidden("Faolsizlantirish uchun ruxsat yo'q")
    if set(data) - {"is_active"} and not actor.can("vehicles.edit"):
        raise forbidden("Tahrirlash uchun ruxsat yo'q")
    if "plate" in data:
        plate = normalize_plate(data["plate"])
        other = await catalog.vehicle_by_plate(db, plate)
        if other and other.id != v.id:
            raise conflict("plate_taken", "Bu davlat raqami allaqachon bor")
        data["plate"] = plate
    if (data.get("is_active") is False or "district_id" in data) and await shift_repo.open_for_vehicle(db, v.id):
        raise conflict("vehicle_busy", "Mashina ochiq smenada — avval smenani yoping")
    if "district_id" in data:
        await _check_district(db, data["district_id"])
        access.check_scope(actor, data["district_id"])
    changes = _diff(v, data, ("plate", "model", "district_id"))
    if any(c["field"] == "district_id" for c in changes):
        names = await _district_names(db)
        for c in changes:
            if c["field"] == "district_id":
                c["old"], c["new"] = names.get(c["old"], c["old"]), names.get(c["new"], c["new"])
    was_active = v.is_active
    for key, value in data.items():
        setattr(v, key, value)
    if v.is_active != was_active:
        situation.add(db, I if v.is_active else W, "vehicle_activated" if v.is_active else "vehicle_deactivated",
                      f"Mashina {'faollashtirildi' if v.is_active else 'faolsizlantirildi'}: {v.plate}",
                      params={"plate": v.plate}, district_id=v.district_id, actor_id=actor.id, ref=("vehicle", v.id))
    if changes and not access.is_admin(actor):
        situation.add(db, I, "vehicle_updated", f"Manager mashinani o'zgartirdi: {v.plate} — {_diff_text(changes)}",
                      params={"plate": v.plate, "changes": _diff_text(changes)}, district_id=v.district_id,
                      actor_id=actor.id, ref=("vehicle", v.id))
    await situation.commit(db)
    return v


# --- GPS radiusi ---
async def set_gps_radius(db: AsyncSession, actor: User, value: int) -> int:
    old = await settings_repo.gps_radius(db)
    row = await db.get(AppSetting, settings_repo.GPS_RADIUS)
    if row:
        row.value = str(value)
    else:
        db.add(AppSetting(key=settings_repo.GPS_RADIUS, value=str(value)))
    if old != value:
        situation.add(db, I, "settings_changed", f"GPS radiusi o'zgardi: {old} m → {value} m",
                      params={"old": old, "new": value}, actor_id=actor.id)
    await situation.commit(db)
    return await settings_repo.gps_radius(db)


async def set_district_radius(db: AsyncSession, actor: User, district_id: int, value: int | None) -> District:
    d = await db.get(District, district_id)
    if not d:
        raise not_found("district")
    access.check_scope(actor, d.id)
    default = await settings_repo.gps_radius(db)
    old = d.gps_radius_m
    d.gps_radius_m = value
    if old != value:
        situation.add(db, I, "district_radius_changed",
                      f"{d.name}: GPS radiusi {old or default} m → {value or default} m" + ("" if value else " (umumiy)"),
                      params={"name": d.name, "old": old or default, "new": value or default}, district_id=d.id,
                      actor_id=actor.id, ref=("district", d.id))
    await situation.commit(db)
    return d
