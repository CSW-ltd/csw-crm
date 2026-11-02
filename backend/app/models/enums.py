from enum import Enum


class Role(str, Enum):
    admin = "admin"
    manager = "manager"
    operator = "operator"      # call-center operatori
    gps = "gps"                # yuridik bo'lim GPS xodimi
    legal = "legal"            # yuridik bo'lim xodimi (shartnomachi)
    driver = "driver"
    accountant = "accountant"  # buxgalter: to'lovlar, shartnoma tasdig'i


class ShiftStatus(str, Enum):
    opened = "opened"    # GPS xodimi ochdi, haydovchi hali boshlamadi
    active = "active"    # haydovchi boshladi: rasm, spidometr, yoqilg'i kiritildi
    closed = "closed"


class RequestStatus(str, Enum):
    new = "new"
    printing = "printing"    # mashina biriktirildi, buyurtma varaqasi printerdan chiqishi kutilmoqda (karta hali qizil)
    assigned = "assigned"
    enroute = "enroute"
    onsite = "onsite"
    done = "done"
    suspect = "suspect"      # yopildi, lekin GPS radiusdan tashqarida
    failed = "failed"        # bajarib bo'lmadi — ochiq qoladi, Manager nazoratiga
    cancelled = "cancelled"


ACTIVE_REQUEST_STATUSES = (RequestStatus.assigned, RequestStatus.enroute, RequestStatus.onsite)


class FileKind(str, Enum):
    before = "before"
    after = "after"
    face = "face"
    sign = "sign"


class FailReason(str, Enum):
    no_waste = "no_waste"
    no_recipient = "no_recipient"
    no_access = "no_access"


class ContractType(str, Enum):
    per_trip = "per_trip"
    by_volume = "by_volume"
    monthly = "monthly"
    one_off = "one_off"


class WasteType(str, Enum):
    household = "household"
    construction = "construction"
    bulky = "bulky"
    green = "green"
    septic = "septic"  # ассенизатор — suyuq chiqindi


class LocationStatus(str, Enum):
    none = "none"            # koordinata yo'q (masalan, Excel'dan import)
    pending = "pending"      # birinchi tashrifda haydovchi GPS'idan olindi, Manager tasdiqlashi kerak
    confirmed = "confirmed"  # tasdiqlangan — radius tekshiruvi shu nuqta bo'yicha


class RequestSource(str, Enum):
    phone = "phone"        # call-center qo'ng'irog'i
    telegram = "telegram"
    excel = "excel"
    walk_in = "walk_in"    # shaxsan kelgan


class AppealStatus(str, Enum):
    new = "new"            # yuridik bo'lim ko'rib chiqishini kutmoqda
    accepted = "accepted"  # korxona kartasi va ariza yaratildi
    rejected = "rejected"


# Bajarilgan hisoblanadigan holatlar (statistika va 72 soat): "suspect" ham yakunlangan dalolatnoma
DONE_STATUSES = ("done", "suspect")
# Hali bajarilmagan (kutilmoqda yoki muddati o'tgan)
OPEN_STATUSES = ("new", "printing", "assigned", "enroute", "onsite", "failed")


class SituationLevel(str, Enum):
    activity = "activity"  # xodimlar faoliyati jurnali — qo'ng'iroqcha va popupga tushmaydi
    info = "info"
    warning = "warning"
    error = "error"
