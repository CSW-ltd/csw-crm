from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (AppealStatus, ContractType, FailReason, FileKind, LocationStatus, RequestSource, RequestStatus, Role,
                              ShiftStatus, WasteType)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth ---
class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UserOut(ORM):
    id: int
    username: str
    full_name: str
    phone: str | None
    role: Role
    district_id: int | None
    language: str
    must_change_password: bool = False


class MeOut(UserOut):
    """Joriy xodim: ruxsatlar va tumanlar doirasi (frontend yorliq va tugmalarni shunga qarab ko'rsatadi)."""
    permissions: list[str] = []
    district_ids: list[int] = []


class LoginOut(MeOut):
    """Tab sessiya rejimida tokenlar javob tanasida qaytadi (cookie yozilmaydi)."""
    access_token: str | None = None
    refresh_token: str | None = None


class RefreshIn(BaseModel):
    refresh_token: str | None = None


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


# --- admin ---
USERNAME_PATTERN = r"^[a-z0-9_.]{3,50}$"


class AdminUserOut(UserOut):
    is_active: bool
    locked_until: datetime | None
    created_at: datetime
    district_ids: list[int] = []
    permissions: list[str] = []
    approval_status: str = "approved"
    created_by_id: int | None = None


class UserCreateIn(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    full_name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    role: Role
    district_id: int | None = None
    district_ids: list[int] = []  # manager/yurist/operator: bir nechta tuman
    language: str = Field(default="uz", pattern=r"^(uz|cy|ru|en)$")
    password: str = Field(min_length=1, max_length=128)  # vaqtinchalik — birinchi kirishda almashtiriladi


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    role: Role | None = None
    district_id: int | None = None
    district_ids: list[int] | None = None
    language: str | None = Field(default=None, pattern=r"^(uz|cy|ru|en)$")
    is_active: bool | None = None


class PasswordResetIn(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class RegionOut(ORM):
    id: int
    name: str


class DistrictOut(ORM):
    id: int
    name: str
    region_id: int
    is_active: bool
    gps_radius_m: int | None = None
    print_manual_confirm: bool = True  # agentsiz rejim: GPS «Varaqa chiqdi»ni o'zi tasdiqlaydi


class DistrictIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    region_id: int


class DistrictUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    is_active: bool | None = None


class AdminVehicleOut(ORM):
    id: int
    plate: str
    model: str | None
    district_id: int
    is_active: bool


class VehicleIn(BaseModel):
    plate: str = Field(min_length=4, max_length=20)
    model: str | None = Field(default=None, max_length=80)
    district_id: int


class VehicleUpdateIn(BaseModel):
    plate: str | None = Field(default=None, min_length=4, max_length=20)
    model: str | None = Field(default=None, max_length=80)
    district_id: int | None = None
    is_active: bool | None = None


class DistrictRadiusOut(BaseModel):
    id: int
    name: str
    gps_radius_m: int | None  # o'z qiymati; None — umumiy
    effective_m: int
    print_manual_confirm: bool = True


class SettingsOut(BaseModel):
    gps_radius_m: int
    districts: list[DistrictRadiusOut] = []


class DistrictRadiusIn(BaseModel):
    gps_radius_m: int | None = Field(default=None, ge=100, le=300)  # None — umumiy qiymatga qaytish


class AccessOut(BaseModel):
    user_id: int
    role: Role
    permissions: list[str]
    district_ids: list[int]
    multi_district: bool            # tumanlar shu oynada boshqariladi (manager/yurist/operator)
    grantable: list[str]            # joriy xodim bera/ola oladigan ruxsatlar
    assignable_district_ids: list[int] | None  # None — hammasi (admin)


class AccessIn(BaseModel):
    permissions: list[str]
    district_ids: list[int] | None = None


class SettingsIn(BaseModel):
    gps_radius_m: int = Field(ge=100, le=300)


# --- shifts ---
class VehicleOut(ORM):
    id: int
    plate: str
    model: str | None
    district_id: int


class ShiftOpenIn(BaseModel):
    driver_id: int
    vehicle_id: int


class ShiftEndIn(BaseModel):
    odometer: int = Field(ge=0)
    fuel: Decimal = Field(ge=0, max_digits=6, decimal_places=1)


class ShiftOut(ORM):
    id: int
    status: ShiftStatus
    driver_id: int
    district_id: int
    vehicle: VehicleOut
    started_at: datetime | None
    ended_at: datetime | None
    odometer_start: int | None
    odometer_end: int | None
    fuel_start: Decimal | None
    fuel_end: Decimal | None
    distance_km: int | None = None
    fuel_used: Decimal | None = None

    @classmethod
    def build(cls, s) -> "ShiftOut":
        out = cls.model_validate(s)
        if s.odometer_end is not None and s.odometer_start is not None:
            out.distance_km = s.odometer_end - s.odometer_start
        if s.fuel_end is not None and s.fuel_start is not None:
            out.fuel_used = Decimal(s.fuel_start) - Decimal(s.fuel_end)
        return out


# --- requests / driver ---
class CustomerOut(ORM):
    id: int
    fixed_no: str
    code: str | None = None  # korxona maxsus raqami (KTR47)
    stir: str | None
    name: str
    director: str | None
    phone: str | None
    address: str | None
    district_id: int
    lat: float | None
    lng: float | None
    location_status: LocationStatus
    location_source: str | None = None
    missing_fields: list[str] = []  # 'stir', 'contract' — bo'lsa haydovchi biriktirilmaydi
    new_contract: bool = False  # oxirgi 30 kunda imzolangan shartnoma (GPS belgisi)


class ContractOut(ORM):
    id: int
    number: str | None
    signed_on: date | None
    type: ContractType


class RequestOut(ORM):
    id: int
    number: str | None
    status: RequestStatus
    waste_type: WasteType
    volume_estimate: Decimal | None
    preferred_time: str | None
    note: str | None
    naryad_no: str | None
    district_id: int
    driver_id: int | None
    created_at: datetime
    assigned_at: datetime | None
    customer: CustomerOut
    contract: ContractOut | None
    # call-center
    source: RequestSource = RequestSource.phone
    due_at: datetime | None = None
    overdue: bool = False
    is_repeat: bool = False
    seen: bool | None = None  # joriy xodim ko'rganmi ("Yangi" belgisi); None — hisoblanmagan
    # uch bosqich: red / yellow / green (+ cancelled)
    stage: str = "red"
    vehicle: VehicleOut | None = None
    driver_name: str | None = None
    finished_at: datetime | None = None
    order_form: dict | None = None  # buyurtma varaqasi (maxfiy kodsiz)

    @field_validator("order_form", mode="before")
    @classmethod
    def _brief_form(cls, v):
        if v is None or isinstance(v, dict):
            return v
        from app.services.order_forms import brief
        return brief(v)


class DriverTaskOut(RequestOut):
    files: list[FileKind] = []


class LocationIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float | None = None


class CompleteIn(BaseModel):
    containers: int = Field(ge=1, le=100)
    volume_m3: Decimal = Field(gt=0, le=1000, max_digits=8, decimal_places=2)
    note: str = Field(min_length=1, max_length=2000)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ActOut(ORM):
    containers: int
    volume_m3: Decimal
    distance_m: int | None  # korxona koordinatasi tasdiqlanmagan bo'lsa — None
    radius_m: int
    in_radius: bool | None
    vehicle_plate: str
    completed_at: datetime


class CompleteOut(BaseModel):
    request: RequestOut
    act: ActOut


class FailIn(BaseModel):
    reason: FailReason
    note: str | None = Field(default=None, max_length=2000)


class FileOut(ORM):
    id: int
    kind: FileKind
    size_bytes: int
    lat: float | None = None
    lng: float | None = None
    accuracy_m: int | None = None


class AssignIn(BaseModel):
    vehicle_id: int


# --- korxonalar ---
class ContactOut(ORM):
    id: int
    name: str | None
    phone: str


class ContactIn(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    phone: str = Field(min_length=1, max_length=30)


class ContractFullOut(ContractOut):
    price: Decimal | None
    valid_from: date
    valid_to: date
    is_active: bool
    status: str = "approved"
    platform_id: str | None = None
    display_number: str | None = None
    annual_volume: Decimal | None = None


class CustomerListOut(CustomerOut):
    activity_type: str | None
    source: str
    contacts_count: int = 0


class CustomerDetailOut(CustomerListOut):
    legal_address: str | None = None
    bank: str | None = None
    mfo: str | None = None
    account: str | None = None
    oked: str | None = None
    cadastre: str | None = None
    is_rented: bool = False
    contacts: list[ContactOut]
    contracts: list[ContractFullOut]
    created_at: datetime


class CustomerPage(BaseModel):
    items: list[CustomerListOut]
    total: int


class CustomerIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    district_id: int
    stir: str | None = Field(default=None, pattern=r"^\d{9}$")
    director: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=255)
    activity_type: str | None = Field(default=None, max_length=100)


class CustomerUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    stir: str | None = Field(default=None, pattern=r"^\d{9}$")
    director: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=255)
    activity_type: str | None = Field(default=None, max_length=100)


class ContractIn(BaseModel):
    number: str = Field(min_length=1, max_length=40)
    type: ContractType
    signed_on: date | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    valid_from: date
    valid_to: date


class LocationConfirmIn(BaseModel):
    """Bo'sh bo'lsa — haydovchi olgan nuqta tasdiqlanadi; berilsa — shu nuqta (qo'lda tuzatish)."""
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class ImportErrorOut(BaseModel):
    row: int
    message: str


class ImportResultOut(BaseModel):
    sheet: str
    file_kind: str = "xlsx"
    rows_total: int
    rows_ok: int
    rows_skipped: int
    septic_rows: int
    customers_new: int
    customers_existing: int
    contacts_added: int
    by_district: dict[str, int]
    errors: list[ImportErrorOut]
    batch_id: int | None = None
    dry_run: bool = True


class ImportBatchOut(ORM):
    id: int
    file_name: str
    uploaded_by_id: int
    rows_total: int
    customers_created: int
    customers_merged: int
    rows_skipped: int
    created_at: datetime


# --- vaziyat paneli ---
class SituationOut(BaseModel):
    id: int
    level: str
    kind: str
    message: str
    params: dict = {}
    district_id: int | None
    actor_id: int | None
    actor_name: str | None = None
    ref_type: str | None
    ref_id: int | None
    created_at: datetime
    resolved: bool = False  # staff_pending: admin qaror qabul qilganmi


class SituationPage(BaseModel):
    items: list[SituationOut]
    total: int
    unread: int
    last_read_id: int


class SituationReadIn(BaseModel):
    up_to_id: int | None = None  # bo'sh — hammasi o'qildi


# --- call-center: arizalar va murojaatlar ---
class RequestCreateIn(BaseModel):
    customer_id: int
    waste_type: WasteType = WasteType.household
    volume_estimate: Decimal | None = Field(default=None, gt=0, le=1000, max_digits=8, decimal_places=2)
    preferred_time: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=2000)
    caller_name: str | None = Field(default=None, max_length=150)
    caller_phone: str | None = Field(default=None, max_length=30)
    source: RequestSource = RequestSource.phone
    confirm_repeat: bool = False  # korxonada ochiq ariza bor — operator "qayta ariza" deb tasdiqladi


class RequestListOut(RequestOut):
    caller_name: str | None = None
    caller_phone: str | None = None
    repeat_of_id: int | None = None
    created_by_id: int | None = None
    finished_at: datetime | None = None
    cancel_reason: str | None = None


class RequestEventOut(BaseModel):
    status: RequestStatus
    note: str | None
    actor_name: str | None
    created_at: datetime


class RequestDetailOut(RequestListOut):
    driver_name: str | None = None
    created_by_name: str | None = None
    events: list[RequestEventOut] = []


class SeenIn(BaseModel):
    request_ids: list[int] = Field(max_length=500)


class RequestPage(BaseModel):
    items: list[RequestListOut]
    total: int


class ReasonIn(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


class AppealIn(BaseModel):
    district_id: int
    org_name: str = Field(min_length=2, max_length=200)
    stir: str | None = Field(default=None, pattern=r"^\d{9}$")
    address: str | None = Field(default=None, max_length=255)
    activity_type: str | None = Field(default=None, max_length=100)
    caller_name: str | None = Field(default=None, max_length=150)
    caller_phone: str | None = Field(default=None, max_length=30)
    source: RequestSource = RequestSource.phone
    waste_type: WasteType = WasteType.household
    volume_estimate: Decimal | None = Field(default=None, gt=0, le=1000, max_digits=8, decimal_places=2)
    preferred_time: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=2000)


class NewCompanyIn(BaseModel):
    """Operator: yangi korxona — faqat telefon, STIR va mashinani kutib oluvchi shaxs (tuman — operatorda bir nechta bo'lsa)."""
    phone: str = Field(min_length=7, max_length=30)
    stir: str = Field(pattern=r"^\d{9}$")
    contact_name: str = Field(min_length=2, max_length=150)
    district_id: int | None = None
    waste_type: WasteType = WasteType.household


class AppealOut(ORM):
    id: int
    number: str | None
    status: AppealStatus
    district_id: int
    org_name: str
    stir: str | None
    address: str | None
    activity_type: str | None
    caller_name: str | None
    caller_phone: str | None
    source: RequestSource
    waste_type: WasteType
    volume_estimate: Decimal | None
    preferred_time: str | None
    note: str | None
    created_by_id: int | None
    reviewed_by_id: int | None
    reviewed_at: datetime | None
    reject_reason: str | None
    customer_id: int | None
    request_id: int | None
    created_at: datetime


class AppealAcceptIn(BaseModel):
    """Yurist murojaat asosida korxona kartasini (va ixtiyoriy shartnomani) yaratadi — ariza avtomatik ochiladi."""
    customer: CustomerIn
    contract: ContractIn | None = None


# --- statistika ---
class StatMetrics(BaseModel):
    received: int = 0
    repeat: int = 0
    pending: int = 0
    overdue: int = 0
    done: int = 0
    not_done: int = 0
    done_share: float = 0.0
    not_done_share: float = 0.0


class DistrictStats(StatMetrics):
    district_id: int
    name: str


class StatsOut(BaseModel):
    period: str
    since: datetime
    total: StatMetrics
    districts: list[DistrictStats]
