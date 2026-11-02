"""Ruxsatlar katalogi va rol andozalari.

Ruxsat kodi: "<bo'lim>.<amal>". Admin hammasiga ega (bazaga yozilmaydi). Boshqa xodimlarga ruxsat alohida yoziladi:
yangi xodim yaratilganda rolining andozasi qo'llanadi, keyin admin (yoki o'z xodimlari uchun manager) ochadi/yopadi.
Faqat admin: tumanlar, umumiy sozlamalar, Vaziyat paneli, xodimni tasdiqlash.
"""
from app.models.enums import Role

# bo'lim → amallar (frontend jadvali shu tartibda chiziladi)
MODULES: dict[str, list[str]] = {
    "customers": ["view", "create", "edit", "contract", "location_confirm", "import"],
    "staff": ["view", "create", "edit", "deactivate", "reset_password", "permissions"],
    "vehicles": ["view", "create", "edit", "deactivate"],
    "settings": ["view", "radius_edit", "tariff"],  # tariff — o'z tumanlari ta'rifini belgilash (manager; admin yopadi/ochadi)
    "requests": ["view", "create", "cancel"],
    "appeals": ["view", "create", "review"],
    "stats": ["view"],
    "orders": ["view", "print", "close", "unlock"],  # buyurtma varaqasi: ko'rish, chop etish (GPS), yopish (legal), blok/qayta chop (manager)
    "accounting": ["view", "payments"],  # debitor/kreditor ko'rish; to'lovlarni kiritish (buxgalter)
}
ALL_CODES: frozenset[str] = frozenset(f"{m}.{a}" for m, actions in MODULES.items() for a in actions)

# Hozirgi xatti-harakatni saqlaydigan andozalar (migratsiya mavjud xodimlarni shu bilan to'ldiradi)
ROLE_TEMPLATES: dict[Role, list[str]] = {
    Role.admin: [],
    Role.manager: ["customers.view", "customers.location_confirm", "staff.view", "vehicles.view", "settings.view", "settings.tariff",
                   "requests.view", "stats.view", "orders.view", "orders.unlock", "accounting.view"],
    Role.legal: ["customers.view", "customers.create", "customers.edit", "customers.contract", "appeals.view", "appeals.review",
                 "requests.view", "orders.view", "orders.close", "accounting.view"],
    Role.gps: ["customers.view", "requests.view", "orders.view", "orders.print"],
    Role.operator: ["customers.view", "requests.view", "requests.create", "appeals.view", "appeals.create",
                    "orders.view"],
    Role.driver: [],
    Role.accountant: ["customers.view", "accounting.view", "accounting.payments"],
}

# Manager o'z doirasida boshqara oladigan rollar ("o'z xodimlari")
STAFF_ROLES: frozenset[Role] = frozenset({Role.gps, Role.legal, Role.operator, Role.driver})
# Bitta tumanga bog'lanadigan rollar (users.district_id); qolganlari user_districts orqali bir nechta tumanga
SINGLE_DISTRICT_ROLES: frozenset[Role] = frozenset({Role.gps, Role.driver})
MULTI_DISTRICT_ROLES: frozenset[Role] = frozenset({Role.manager, Role.legal, Role.operator, Role.accountant})


def template(role: Role) -> list[str]:
    return list(ROLE_TEMPLATES.get(role, []))


def apply_template(user, district_ids: list[int] | None = None) -> None:
    """Seed va testlar uchun: rol andozasi va (manager/yurist/operator uchun) tumanlar."""
    from app.models import UserDistrict, UserPermission
    user.perm_rows = [UserPermission(code=c) for c in template(user.role)]
    if district_ids is not None and user.role in MULTI_DISTRICT_ROLES:
        user.district_rows = [UserDistrict(district_id=d) for d in district_ids]
