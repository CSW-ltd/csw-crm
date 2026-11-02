"""Boshqaruv paneli: xodimlar, tumanlar, mashinalar, sozlamalar, import.

Har amal ruxsat kodi bilan tekshiriladi (app.core.permissions); manager faqat o'z tumanlari doirasida ishlaydi.
Tumanlar, umumiy sozlama va xodimni tasdiqlash — faqat admin.
"""
from dataclasses import asdict

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, require_perm, require_roles
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.errors import invalid, not_found
from app.models import Provider, User
from app.models.enums import Role
from app.repositories import catalog
from app.repositories import customers as customers_repo
from app.repositories import settings as settings_repo
from app.schemas import (
    AdminUserOut,
    AccessIn,
    AccessOut,
    AdminVehicleOut,
    DistrictRadiusIn,
    DistrictRadiusOut,
    DistrictIn,
    DistrictOut,
    DistrictUpdateIn,
    ImportBatchOut,
    ImportResultOut,
    PasswordResetIn,
    RegionOut,
    SettingsIn,
    SettingsOut,
    UserCreateIn,
    UserUpdateIn,
    VehicleIn,
    VehicleUpdateIn,
)
from app.services import admin_service, customer_import
from app.services.table_readers import file_kind

router = APIRouter(prefix="/admin", tags=["admin"])
AdminOnly = Depends(require_roles(Role.admin))
# Ma'lumotnomalar (viloyat/tuman) — doirasi bor barcha boshqaruv xodimlari o'qiydi
RefReader = Depends(require_roles(Role.admin, Role.manager, Role.legal, Role.operator, Role.gps, Role.accountant))


def perm(*codes: str):
    return Depends(require_perm(*codes))


# --- xodimlar ---
@router.get("/users", response_model=list[AdminUserOut])
async def users(role: Role | None = None, district_id: int | None = None, active: bool | None = Query(None),
                user: User = perm("staff.view"), db: AsyncSession = DB):
    return await admin_service.list_users(db, user, role, district_id, active)


@router.post("/users", response_model=AdminUserOut, status_code=201)
async def create_user(body: UserCreateIn, user: User = perm("staff.create"), db: AsyncSession = DB):
    return await admin_service.create_user(db, user, body)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def update_user(user_id: int, body: UserUpdateIn, user: User = perm("staff.edit", "staff.deactivate"), db: AsyncSession = DB):
    return await admin_service.update_user(db, user, user_id, body)


@router.post("/users/{user_id}/reset-password", response_model=AdminUserOut)
async def reset_password(user_id: int, body: PasswordResetIn, user: User = perm("staff.reset_password"), db: AsyncSession = DB):
    return await admin_service.reset_password(db, user, user_id, body.password)


@router.post("/users/{user_id}/approve", response_model=AdminUserOut)
async def approve_user(user_id: int, admin: User = AdminOnly, db: AsyncSession = DB):
    return await admin_service.decide_user(db, admin, user_id, approve=True)


@router.post("/users/{user_id}/reject", response_model=AdminUserOut)
async def reject_user(user_id: int, admin: User = AdminOnly, db: AsyncSession = DB):
    return await admin_service.decide_user(db, admin, user_id, approve=False)


# --- huquqlar ---
@router.get("/permissions/catalog")
async def permission_catalog(_: User = perm("staff.view")) -> dict:
    from app.core.permissions import MODULES
    return {"modules": MODULES}


@router.get("/users/{user_id}/access", response_model=AccessOut)
async def get_access(user_id: int, user: User = perm("staff.view"), db: AsyncSession = DB):
    return await admin_service.get_access(db, user, user_id)


@router.put("/users/{user_id}/access", response_model=AccessOut)
async def put_access(user_id: int, body: AccessIn, user: User = perm("staff.permissions"), db: AsyncSession = DB):
    return await admin_service.set_access(db, user, user_id, body)


# --- tumanlar ---
@router.get("/regions", response_model=list[RegionOut])
async def regions(_: User = RefReader, db: AsyncSession = DB):
    return await catalog.regions(db)


@router.get("/districts", response_model=list[DistrictOut])
async def districts(user: User = RefReader, db: AsyncSession = DB):
    return await admin_service.list_districts(db, user)


@router.post("/districts", response_model=DistrictOut, status_code=201)
async def create_district(body: DistrictIn, _: User = AdminOnly, db: AsyncSession = DB):
    return await admin_service.create_district(db, body)


@router.patch("/districts/{district_id}", response_model=DistrictOut)
async def update_district(district_id: int, body: DistrictUpdateIn, admin: User = AdminOnly, db: AsyncSession = DB):
    return await admin_service.update_district(db, admin, district_id, body)


# --- mashinalar ---
@router.get("/vehicles", response_model=list[AdminVehicleOut])
async def vehicles(district_id: int | None = None, user: User = perm("vehicles.view"), db: AsyncSession = DB):
    return await admin_service.list_vehicles(db, user, district_id)


@router.post("/vehicles", response_model=AdminVehicleOut, status_code=201)
async def create_vehicle(body: VehicleIn, user: User = perm("vehicles.create"), db: AsyncSession = DB):
    return await admin_service.create_vehicle(db, user, body)


@router.patch("/vehicles/{vehicle_id}", response_model=AdminVehicleOut)
async def update_vehicle(vehicle_id: int, body: VehicleUpdateIn, user: User = perm("vehicles.edit", "vehicles.deactivate"),
                         db: AsyncSession = DB):
    return await admin_service.update_vehicle(db, user, vehicle_id, body)


# --- sozlamalar: umumiy GPS radiusi (admin) va tumanlar radiusi ---
async def _settings(db: AsyncSession, user: User) -> SettingsOut:
    default = await settings_repo.gps_radius(db)
    rows = [DistrictRadiusOut(id=d.id, name=d.name, gps_radius_m=d.gps_radius_m, effective_m=d.gps_radius_m or default,
                              print_manual_confirm=d.print_manual_confirm)
            for d in await admin_service.list_districts(db, user)]
    return SettingsOut(gps_radius_m=default, districts=rows)


@router.get("/settings", response_model=SettingsOut)
async def get_settings(user: User = perm("settings.view", "settings.radius_edit"), db: AsyncSession = DB):
    return await _settings(db, user)


@router.put("/settings", response_model=SettingsOut)
async def put_settings(body: SettingsIn, admin: User = AdminOnly, db: AsyncSession = DB):
    await admin_service.set_gps_radius(db, admin, body.gps_radius_m)
    return await _settings(db, admin)


@router.put("/districts/{district_id}/radius", response_model=SettingsOut)
async def put_district_radius(district_id: int, body: DistrictRadiusIn, user: User = perm("settings.radius_edit"),
                              db: AsyncSession = DB):
    await admin_service.set_district_radius(db, user, district_id, body.gps_radius_m)
    return await _settings(db, user)


# --- xizmat ko'rsatuvchi rekvizitlari (schyot-faktura uchun) ---
PROVIDER_FIELDS = ("full_name", "inn", "address", "phone", "bank", "mfo", "account", "oked", "director", "chief_accountant")


class ProviderIn(BaseModel):
    full_name: str | None = Field(None, max_length=200)
    inn: str | None = Field(None, pattern=r"^\d{9}$")
    address: str | None = Field(None, max_length=255)
    bank: str | None = Field(None, max_length=150)
    mfo: str | None = Field(None, pattern=r"^\d{5}$")
    account: str | None = Field(None, pattern=r"^\d{20}$")
    director: str | None = Field(None, max_length=150)
    chief_accountant: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=30)
    oked: str | None = Field(None, pattern=r"^\d{4,5}$")


def _prov(p: Provider) -> dict:
    return {"id": p.id, "name": p.name, "code": p.code, "region_id": p.region_id, **{k: getattr(p, k) for k in PROVIDER_FIELDS}}


@router.get("/providers")
async def list_providers(user: User = perm("settings.view"), db: AsyncSession = DB) -> list[dict]:
    return [_prov(p) for p in (await db.execute(select(Provider).order_by(Provider.id))).scalars()]


@router.put("/providers/{provider_id}")
async def put_provider(provider_id: int, body: ProviderIn, admin: User = AdminOnly, db: AsyncSession = DB) -> dict:
    p = await db.get(Provider, provider_id)
    if not p:
        raise not_found("provider")
    for k in PROVIDER_FIELDS:
        v = getattr(body, k)
        setattr(p, k, v.strip() if isinstance(v, str) and v.strip() else None)
    await db.commit()
    return _prov(p)


class PrintModeIn(BaseModel):
    manual: bool


@router.put("/districts/{district_id}/print-mode", response_model=SettingsOut)
async def put_print_mode(district_id: int, body: PrintModeIn, admin: User = AdminOnly, db: AsyncSession = DB):
    """Agentsiz rejim: yoqilgan bo'lsa GPS «Varaqa chiqdi»ni o'zi tasdiqlaydi; o'chirilsa — faqat printer agenti."""
    from app.models import District
    d = await db.get(District, district_id)
    if not d:
        raise not_found("district")
    d.print_manual_confirm = body.manual
    await db.commit()
    return await _settings(db, admin)


# --- Excel import ---
MAX_IMPORT_BYTES = 10 * 1024 * 1024


@router.post("/import/customers", response_model=ImportResultOut)
async def import_customers(file: UploadFile = File(...), dry_run: bool = True, user: User = perm("customers.import"),
                           db: AsyncSession = DB):
    """Call-center jadvali: .xlsx, .xls, .csv, .docx yoki matnli .pdf. Avval dry_run=true (tahlil, bazaga yozilmaydi),
    keyin dry_run=false. Manager uchun — faqat o'z tumanlari qatorlari; boshqalari ogohlantirish bilan o'tkazib yuboriladi."""
    file_kind(file.filename or "")  # qo'llab-quvvatlanmaydigan format — darhol 422
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise invalid("file_too_large", "Fayl hajmi 10 MB dan oshmasin")
    result = await customer_import.run(db, user, file.filename or "import.xlsx", content, dry_run)
    return ImportResultOut(**asdict(result), dry_run=dry_run)


@router.get("/import/batches", response_model=list[ImportBatchOut])
async def import_batches(_: User = perm("customers.import"), db: AsyncSession = DB):
    return await customers_repo.import_batches(db)
