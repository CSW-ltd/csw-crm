"""Barcha modellar shu yerdan import qilinadi (Alembic autogenerate ham shuni ishlatadi)."""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, false as sa_false, true as sa_true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow
from app.models.enums import (AppealStatus, ContractType, FailReason, FileKind, LocationStatus, RequestSource, RequestStatus, Role,
                              ShiftStatus, SituationLevel, WasteType)


def enum_col(enum_cls):
    # VARCHAR sifatida saqlanadi: yangi qiymat qo'shish migratsiyasiz ishlaydi
    return SAEnum(enum_cls, native_enum=False, length=20, validate_strings=True)


class Region(Base):
    __tablename__ = "regions"
    # Admin yopib qo'ysa — managerlar bu viloyat tumanlarining ta'rifini o'zgartira olmaydi
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    tariff_locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())


class Provider(Base):
    """Xizmat ko'rsatuvchi kompaniya (viloyat bo'yicha). `code` avtonaryad raqamida ishlatiladi."""
    __tablename__ = "providers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    code: Mapped[str] = mapped_column(String(10), unique=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), unique=True)
    # Rekvizitlar (schyot-faktura uchun)
    full_name: Mapped[str | None] = mapped_column(String(200))
    inn: Mapped[str | None] = mapped_column(String(9))
    address: Mapped[str | None] = mapped_column(String(255))
    bank: Mapped[str | None] = mapped_column(String(150))
    mfo: Mapped[str | None] = mapped_column(String(5))
    account: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(30))
    oked: Mapped[str | None] = mapped_column(String(10))
    director: Mapped[str | None] = mapped_column(String(150))
    chief_accountant: Mapped[str | None] = mapped_column(String(150))
    region: Mapped[Region] = relationship()


class District(Base):
    __tablename__ = "districts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Tuman GPS radiusi (100–300 m); bo'sh bo'lsa umumiy sozlama ishlaydi
    gps_radius_m: Mapped[int | None] = mapped_column(Integer)
    # Printer agentisiz rejim: GPS «Varaqa chiqdi»ni o'zi tasdiqlaydi (agent o'rnatilguncha). Admin o'chiradi.
    print_manual_confirm: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sa_true())
    tariff_locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())  # manager o'zgartira olmaydi
    region: Mapped[Region] = relationship()


class UserDistrict(Base):
    """Manager, yurist va operator uchun tumanlar doirasi (bir nechta bo'lishi mumkin)."""
    __tablename__ = "user_districts"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), primary_key=True)


class UserPermission(TimestampMixin, Base):
    """Xodimga berilgan ruxsat (masalan, "customers.edit"). Admin uchun yozilmaydi — admin hammasiga ega."""
    __tablename__ = "user_permissions"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    granted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    role: Mapped[Role] = mapped_column(enum_col(Role), index=True)
    # Haydovchi va GPS xodimi uchun: qaysi tumanga biriktirilgan
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"), index=True)
    language: Mapped[str] = mapped_column(String(5), default="uz")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Admin bergan vaqtinchalik paroldan keyin birinchi kirishda almashtirish shart
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    # Manager yaratgan xodim admin tasdiqlamaguncha "pending" (kira olmaydi)
    approval_status: Mapped[str] = mapped_column(String(10), default="approved", server_default="approved")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    district: Mapped[District | None] = relationship()
    # Xodimlar soni kichik (~20) — ruxsat va doira har doim birga yuklanadi
    perm_rows: Mapped[list[UserPermission]] = relationship(lazy="selectin", cascade="all, delete-orphan",
                                                           foreign_keys=[UserPermission.user_id])
    district_rows: Mapped[list[UserDistrict]] = relationship(lazy="selectin", cascade="all, delete-orphan")

    @property
    def permissions(self) -> list[str]:
        from app.core.permissions import ALL_CODES
        return sorted(ALL_CODES) if self.role == Role.admin else sorted(p.code for p in self.perm_rows)

    @property
    def district_ids(self) -> list[int]:
        """Ishlash doirasi: GPS/haydovchi — bitta tuman; manager/yurist/operator — biriktirilgan tumanlar."""
        ids = {d.district_id for d in self.district_rows}
        if self.district_id:
            ids.add(self.district_id)
        return sorted(ids)

    def can(self, code: str) -> bool:
        return self.role == Role.admin or any(p.code == code for p in self.perm_rows)


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    plate: Mapped[str] = mapped_column(String(20), unique=True)
    model: Mapped[str | None] = mapped_column(String(80))
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Shift(TimestampMixin, Base):
    """Kunlik smena: GPS xodimi haydovchini mashina bilan juftlaydi."""
    __tablename__ = "shifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True)
    opened_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[ShiftStatus] = mapped_column(enum_col(ShiftStatus), default=ShiftStatus.opened, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    odometer_start: Mapped[int | None] = mapped_column(Integer)
    odometer_end: Mapped[int | None] = mapped_column(Integer)
    fuel_start: Mapped[float | None] = mapped_column(Numeric(6, 1))
    fuel_end: Mapped[float | None] = mapped_column(Numeric(6, 1))
    vehicle_photo_key: Mapped[str | None] = mapped_column(String(255))
    last_lat: Mapped[float | None] = mapped_column(Float)
    last_lng: Mapped[float | None] = mapped_column(Float)
    last_location_at: Mapped[datetime | None] = mapped_column(DateTime)
    driver: Mapped[User] = relationship(foreign_keys=[driver_id])
    vehicle: Mapped[Vehicle] = relationship()


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("district_id", "name_key", name="uq_customers_district_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    fixed_no: Mapped[str] = mapped_column(String(20), unique=True)  # eski doimiy raqam, masalan A-0101
    # Korxona maxsus raqami: 3 harf + 2 raqam (KTR47). STIR o'rniga — maktablar kabi tashkilotlarda STIR bir xil bo'lishi mumkin.
    # Yangi korxonaga avtomatik beriladi (app.services.customer_code), o'zgarmaydi.
    code: Mapped[str | None] = mapped_column(String(5), unique=True)
    # STIR Excel'da yo'q — keyin yuridik bo'lim to'ldiradi; takrorlanmaydi (keyin Soliq API orqali tekshiriladi)
    stir: Mapped[str | None] = mapped_column(String(9), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(200))  # birlashtirish uchun normallashtirilgan nom
    activity_type: Mapped[str | None] = mapped_column(String(100))
    director: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True)
    address: Mapped[str | None] = mapped_column(String(255))  # obyekt (xizmat ko'rsatiladigan joy) manzili
    # Rekvizitlar (shartnoma uchun)
    legal_address: Mapped[str | None] = mapped_column(String(255))
    bank: Mapped[str | None] = mapped_column(String(150))
    mfo: Mapped[str | None] = mapped_column(String(5))
    account: Mapped[str | None] = mapped_column(String(20))
    oked: Mapped[str | None] = mapped_column(String(10))
    cadastre: Mapped[str | None] = mapped_column(String(40))
    is_rented: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())  # obyekt ijarada
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    location_status: Mapped[LocationStatus] = mapped_column(enum_col(LocationStatus), default=LocationStatus.none, server_default="none")
    source: Mapped[str] = mapped_column(String(10), default="manual", server_default="manual")
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"))
    district: Mapped[District] = relationship()
    contacts: Mapped[list["CustomerContact"]] = relationship(order_by="CustomerContact.id", cascade="all, delete-orphan")
    contracts: Mapped[list["Contract"]] = relationship(order_by="Contract.id", viewonly=True)

    def active_contract(self, today: date | None = None) -> "Contract | None":
        """Bugun amal qiladigan shartnoma (contracts oldindan yuklangan bo'lishi kerak)."""
        today = today or date.today()
        return next((c for c in reversed(self.contracts) if c.is_active and c.valid_from <= today <= c.valid_to), None)

    @property
    def new_contract(self) -> bool:
        """GPS kartasida «Yangi shartnoma» belgisi: amaldagi shartnoma oxirgi 30 kunda imzolangan."""
        from app.services.contracts import is_new
        return is_new(self.active_contract())

    @property
    def missing_fields(self) -> list[str]:
        """Mashina biriktirish uchun yetishmayotgan ma'lumot: amaldagi shartnoma (STIR o'rniga maxsus raqam ishlatiladi)."""
        return [] if self.active_contract() is not None else ["contract"]


class CustomerContact(TimestampMixin, Base):
    __tablename__ = "customer_contacts"
    __table_args__ = (UniqueConstraint("customer_id", "phone", name="uq_customer_contacts_phone"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str] = mapped_column(String(30))


class ImportBatch(TimestampMixin, Base):
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255))
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    customers_created: Mapped[int] = mapped_column(Integer, default=0)
    customers_merged: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0)
    report: Mapped[str | None] = mapped_column(Text)  # JSON: xatolar ro'yxati


class Contract(TimestampMixin, Base):
    __tablename__ = "contracts"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    number: Mapped[str | None] = mapped_column(String(40), unique=True)  # tugallanmagan loyihada bo'sh
    signed_on: Mapped[date | None] = mapped_column(Date)
    type: Mapped[ContractType] = mapped_column(enum_col(ContractType))
    price: Mapped[float | None] = mapped_column(Numeric(14, 2))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # «Yangi shartnoma» jarayoni: draft → signed (faol, buxgalteriya tasdig'ini kutadi) → approved; signed → returned → signed.
    # Hisob-kitob (faktura, debitor) faqat approved. Eski/qo'lda kiritilgan shartnomalar — approved.
    status: Mapped[str] = mapped_column(String(10), default="approved", server_default="approved", index=True)
    annual_volume: Mapped[float | None] = mapped_column(Numeric(12, 2))  # yillik hajm, m³
    annual_trips: Mapped[int | None] = mapped_column(Integer)  # reys bo'yicha shartnomada yillik reyslar soni
    place: Mapped[str | None] = mapped_column(String(100))  # tuzilgan joyi
    sign_method: Mapped[str | None] = mapped_column(String(10))  # electronic | paper
    platform: Mapped[str | None] = mapped_column(String(15))  # didox | hujjat | soliq | other
    platform_id: Mapped[str | None] = mapped_column(String(40))
    scan_key: Mapped[str | None] = mapped_column(String(200))
    scan_name: Mapped[str | None] = mapped_column(String(150))
    scan_type: Mapped[str | None] = mapped_column(String(60))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    return_comment: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    draft_data: Mapped[str | None] = mapped_column(Text)  # tugallanmagan forma (JSON) — tekshiruvdan o'tmagan
    source: Mapped[str] = mapped_column(String(10), default="flow", server_default="flow")  # flow | manual | import (mavjud shartnoma)
    customer: Mapped["Customer"] = relationship(viewonly=True)
    events: Mapped[list["ContractEvent"]] = relationship(order_by="ContractEvent.id", cascade="all, delete-orphan")

    @property
    def display_number(self) -> str:
        """Platforma (Didox / hujjat.uz) raqami bo'lsa — o'sha, aks holda ichki raqam."""
        return self.platform_id or self.number or ""


class Tariff(Base):
    """Davlat ta'rifi: 1 m³ qattiq maishiy chiqindi narxi (QQS bilan). Viloyat bo'yicha (district_id bo'sh) yoki tuman/shahar uchun alohida.
    Sanadan kuchga kiradi; hisob-kitob varaqa yopilgan kundagi ta'rif bo'yicha (tuman ta'rifi bo'lsa — u, aks holda viloyatniki)."""
    __tablename__ = "tariffs"
    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"), index=True)
    price: Mapped[float] = mapped_column(Numeric(14, 2))
    valid_from: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_by: Mapped["User | None"] = relationship(lazy="selectin")


class ContractEvent(Base):
    """Shartnoma tarixi: kim, qachon, nima qildi (created, edited, signed, approved, returned, resubmitted)."""
    __tablename__ = "contract_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(15))
    comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    actor: Mapped["User | None"] = relationship(lazy="selectin")


class Request(TimestampMixin, Base):
    __tablename__ = "requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str | None] = mapped_column(String(20), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"))
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True)
    status: Mapped[RequestStatus] = mapped_column(enum_col(RequestStatus), default=RequestStatus.new, index=True)
    waste_type: Mapped[WasteType] = mapped_column(enum_col(WasteType), default=WasteType.household)
    volume_estimate: Mapped[float | None] = mapped_column(Numeric(8, 2))
    preferred_time: Mapped[str | None] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id"), index=True)
    naryad_no: Mapped[str | None] = mapped_column(String(30), unique=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    fail_reason: Mapped[FailReason | None] = mapped_column(enum_col(FailReason))
    fail_note: Mapped[str | None] = mapped_column(Text)
    # Call-center: kim qo'ng'iroq qildi, qayerdan keldi, 72 soatlik muddat, takroriy ariza
    source: Mapped[RequestSource] = mapped_column(enum_col(RequestSource), default=RequestSource.phone, server_default="phone")
    caller_name: Mapped[str | None] = mapped_column(String(150))
    caller_phone: Mapped[str | None] = mapped_column(String(30))
    due_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    is_repeat: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    repeat_of_id: Mapped[int | None] = mapped_column(ForeignKey("requests.id"))
    overdue_notified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    cancel_reason: Mapped[str | None] = mapped_column(String(500))
    # Uch bosqichli jarayon: GPS mashina biriktiradi (haydovchi — kunlik ish jadvalidan)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), index=True)

    @property
    def driver_name(self) -> str | None:
        return self.driver.full_name if self.driver else None

    @property
    def stage(self) -> str:
        """Kartaning rangi: red — mashina biriktirilmagan, yellow — chiqindi olinishi kutilmoqda, green — bajarilgan."""
        st = self.status.value
        if st in ("new", "printing"):  # printing — varaqa printerdan chiqqani tasdiqlanmaguncha qizil
            from app.db.base import utcnow
            return "black" if self.created_at and (utcnow() - self.created_at).total_seconds() >= 72 * 3600 else "red"
        if st in ("done", "suspect"):
            return "green"
        if st == "cancelled":
            return "cancelled"
        return "yellow"

    @property
    def overdue(self) -> bool:
        """Normativ muddat (72 soat) o'tgan va hali bajarilmagan."""
        from app.db.base import utcnow
        from app.models.enums import OPEN_STATUSES
        return bool(self.due_at) and self.status.value in OPEN_STATUSES and utcnow() > self.due_at

    customer: Mapped[Customer] = relationship()
    contract: Mapped[Contract | None] = relationship()
    shift: Mapped[Shift | None] = relationship()
    vehicle: Mapped[Vehicle | None] = relationship()
    driver: Mapped[User | None] = relationship(foreign_keys=[driver_id])
    order_form: Mapped["OrderForm | None"] = relationship(back_populates="request", uselist=False)


class Appeal(TimestampMixin, Base):
    """Birinchi murojaat: bazada yo'q korxona qo'ng'iroq qildi — yuridik bo'lim karta va shartnoma ochadi."""
    __tablename__ = "appeals"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str | None] = mapped_column(String(20), unique=True)
    status: Mapped[AppealStatus] = mapped_column(enum_col(AppealStatus), default=AppealStatus.new, index=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True)
    org_name: Mapped[str] = mapped_column(String(200))
    stir: Mapped[str | None] = mapped_column(String(9))
    address: Mapped[str | None] = mapped_column(String(255))
    activity_type: Mapped[str | None] = mapped_column(String(100))
    caller_name: Mapped[str | None] = mapped_column(String(150))
    caller_phone: Mapped[str | None] = mapped_column(String(30))
    source: Mapped[RequestSource] = mapped_column(enum_col(RequestSource), default=RequestSource.phone)
    waste_type: Mapped[WasteType] = mapped_column(enum_col(WasteType), default=WasteType.household)
    volume_estimate: Mapped[float | None] = mapped_column(Numeric(8, 2))
    preferred_time: Mapped[str | None] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reject_reason: Mapped[str | None] = mapped_column(String(500))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    request_id: Mapped[int | None] = mapped_column(ForeignKey("requests.id"))


class WorkSchedule(TimestampMixin, Base):
    """Kunlik ish jadvali: GPS xodimi har tuman uchun mashinani haydovchi va xizmat turi (yuridik/jismoniy) bilan biriktiradi.
    Kelajakdagi GPS-monitoring tizimi shu jadvalni API orqali o'qiydi va to'ldiradi."""
    __tablename__ = "work_schedule"
    __table_args__ = (UniqueConstraint("day", "vehicle_id", name="uq_work_schedule_day_vehicle"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id"), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    service: Mapped[str] = mapped_column(String(12), default="legal")  # "legal" | "individual"
    mahallas: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    vehicle: Mapped[Vehicle] = relationship()
    driver: Mapped[User | None] = relationship(foreign_keys=[driver_id])


class VehiclePosition(Base):
    """Mashinaning oxirgi joylashuvi: tashqi GPS-monitoring tizimi (API kalit bilan) yoki haydovchi plansheti yuboradi."""
    __tablename__ = "vehicle_positions"
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), primary_key=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    at: Mapped[datetime] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(20), default="monitoring")


class OrderForm(TimestampMixin, Base):
    """Buyurtma varaqasi (ko'rsatilgan xizmat bo'yicha buyurtma cheki): mashina biriktirilganda yaratiladi.
    Ochiq raqam hamma ko'radi; maxfiy tasdiq kodi faqat chop etilgan qog'ozda bo'ladi, bazada — HMAC xeshi."""
    __tablename__ = "order_forms"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str | None] = mapped_column(String(12), unique=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), unique=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    code_hash: Mapped[str | None] = mapped_column(String(64))
    print_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    printed_at: Mapped[datetime | None] = mapped_column(DateTime)
    printed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reprint_allowed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    scan_key: Mapped[str | None] = mapped_column(String(255))
    scan_content_type: Mapped[str | None] = mapped_column(String(50))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    volume_m3: Mapped[float | None] = mapped_column(Numeric(8, 2))
    waste_kind: Mapped[str | None] = mapped_column(String(10))  # "solid" | "liquid"
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    closed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    closed_via: Mapped[str | None] = mapped_column(String(10))  # "form" — legal varaqa bilan, "act" — planshetdagi dalolatnoma
    # Printerdan chiqqani tasdig'i: agent (printer navbati «chop etildi») yoki qo'lda (agentsiz rejim)
    print_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    print_confirmed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    print_confirm_via: Mapped[str | None] = mapped_column(String(10))  # "agent" | "manual"
    request: Mapped["Request"] = relationship(back_populates="order_form")


class Invoice(TimestampMixin, Base):
    """Oylik schyot-faktura: har korxonaga oyiga bitta. draft → sent (yuborilgach o'zgarmaydi)."""
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("customer_id", "period", name="uq_invoices_customer_period"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"))
    period: Mapped[date] = mapped_column(Date, index=True)  # oyning 1-kuni
    status: Mapped[str] = mapped_column(String(10), default="draft")  # draft | sent
    total: Mapped[float] = mapped_column(Numeric(14, 2))
    vat: Mapped[float] = mapped_column(Numeric(14, 2))
    token: Mapped[str] = mapped_column(String(64), unique=True)  # SMS havolasi uchun (login talab qilmaydi)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    sent_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    sms_phone: Mapped[str | None] = mapped_column(String(30))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    customer: Mapped["Customer"] = relationship()
    lines: Mapped[list["InvoiceLine"]] = relationship(order_by="InvoiceLine.id", cascade="all, delete-orphan", lazy="selectin")


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # form | monthly | one_off | annex (oylik shartnomada summasiz varaqa)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("requests.id"))
    day: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(255))
    qty: Mapped[float] = mapped_column(Numeric(10, 2))
    unit: Mapped[str] = mapped_column(String(10))
    price: Mapped[float] = mapped_column(Numeric(14, 2))
    amount: Mapped[float] = mapped_column(Numeric(14, 2))


class Payment(TimestampMixin, Base):
    """Korxona to'lovi (kreditor tomoni). Buxgalter qo'lda yoki bank ko'chirmasidan kiritadi; o'chirilmaydi — bekor qilinadi."""
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    paid_on: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    doc_no: Mapped[str | None] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(10), default="manual")  # "manual" | "import"
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    customer: Mapped["Customer"] = relationship()



class NaryadCounter(Base):
    """Avtonaryad tartib raqami: har bir xizmat ko'rsatuvchi uchun har yili 1 dan."""
    __tablename__ = "naryad_counters"
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, default=0)


class Act(Base):
    """Elektron dalolatnoma — haydovchi qo'lda kiritadigan va GPS natijasi."""
    __tablename__ = "acts"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), unique=True)
    containers: Mapped[int] = mapped_column(Integer)
    volume_m3: Mapped[float] = mapped_column(Numeric(8, 2))
    note: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    distance_m: Mapped[int | None] = mapped_column(Integer)
    radius_m: Mapped[int] = mapped_column(Integer)
    in_radius: Mapped[bool | None] = mapped_column(Boolean)  # None — koordinatasiz korxona, radius tekshirilmadi
    vehicle_plate: Mapped[str] = mapped_column(String(20))
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ActFile(TimestampMixin, Base):
    __tablename__ = "act_files"
    __table_args__ = (UniqueConstraint("request_id", "kind", name="uq_act_files_request_kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), index=True)
    kind: Mapped[FileKind] = mapped_column(enum_col(FileKind))
    storage_key: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    accuracy_m: Mapped[int | None] = mapped_column(Integer)  # rasm olingan paytdagi GPS aniqligi (planshet)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class RequestEvent(TimestampMixin, Base):
    __tablename__ = "request_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), index=True)
    status: Mapped[RequestStatus] = mapped_column(enum_col(RequestStatus))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(String(255))


class RequestSeen(TimestampMixin, Base):
    """Xodim arizani ko'rganmi ("Yangi" belgisi har xodim uchun alohida)."""
    __tablename__ = "request_seen"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"), primary_key=True)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))


class SituationEvent(TimestampMixin, Base):
    """Vaziyat paneli: admin va manager ko'rishi kerak bo'lgan hodisalar (90 kun saqlanadi)."""
    __tablename__ = "situation_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[SituationLevel] = mapped_column(enum_col(SituationLevel), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)  # frontend shu kalit bo'yicha tarjima qiladi
    message: Mapped[str] = mapped_column(String(500))          # o'zbekcha matn (log va zaxira uchun)
    params: Mapped[str | None] = mapped_column(Text)           # JSON: tarjima uchun qiymatlar
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    ref_type: Mapped[str | None] = mapped_column(String(20))   # request / customer / user / district / vehicle / import
    ref_id: Mapped[int | None] = mapped_column(Integer)


class SituationRead(Base):
    """Har bir xodim qaysi hodisagacha o'qigani."""
    __tablename__ = "situation_reads"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    last_read_id: Mapped[int] = mapped_column(Integer, default=0)


__all__ = [
    "Base", "Region", "Provider", "District", "User", "Vehicle", "Shift", "Customer", "CustomerContact", "ImportBatch", "Contract",
    "ContractEvent", "Tariff", "Request", "NaryadCounter", "Act", "ActFile", "RequestEvent", "AppSetting", "SituationEvent", "SituationRead",
    "UserDistrict", "UserPermission", "Appeal", "RequestSeen", "WorkSchedule", "VehiclePosition", "OrderForm", "Payment", "Invoice", "InvoiceLine",
]


# --- korxona maxsus raqami: yangi korxonaga flush paytida avtomatik ---
CODE_LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"  # O, I, Q yo'q — 0 va 1 bilan adashtirilmasin
CODE_DIGITS = "0123456789"


def random_customer_code() -> str:
    import secrets
    return "".join(secrets.choice(CODE_LETTERS) for _ in range(3)) + "".join(secrets.choice(CODE_DIGITS) for _ in range(2))


def _assign_customer_codes(session, flush_context, instances) -> None:
    from sqlalchemy import select as _select
    new = [o for o in session.new if isinstance(o, Customer) and not o.code]
    if not new:
        return
    taken: set[str] = {o.code for o in session.new if isinstance(o, Customer) and o.code}
    for cust in new:
        for _ in range(50):
            c = random_customer_code()
            if c in taken:
                continue
            with session.no_autoflush:
                if session.execute(_select(Customer.id).where(Customer.code == c)).first() is None:
                    break
        else:  # 1,2 mln variantdan 50 tasi band — amalda bo'lmaydi
            raise RuntimeError("Korxona maxsus raqamini yaratib bo'lmadi")
        cust.code = c
        taken.add(c)


from sqlalchemy import event as _event  # noqa: E402
from sqlalchemy.orm import Session as _Session  # noqa: E402

_event.listen(_Session, "before_flush", _assign_customer_codes)
