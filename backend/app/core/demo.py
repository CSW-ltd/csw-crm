"""Demo loginlari (*.test.csw.uz va lokal): DEMO_CREDENTIALS env'idan, JSON — {"csw.admin": "parol", ...}.

Parollar faqat serverdagi .env'da; kodda faqat login → rol bog'lanishi.
"""
import json

from app.models.enums import Role

# Har rolga bitta demo foydalanuvchi; GPS va haydovchi — Asaka tumani (seed.DEMO_DISTRICT)
DEMO_USERS: dict[str, tuple[Role, str]] = {
    "csw.admin": (Role.admin, "Demo administrator"),
    "csw.manager": (Role.manager, "Demo menejer"),
    "csw.yurist": (Role.legal, "Demo yurist"),
    "csw.buxgalter": (Role.accountant, "Demo buxgalter"),
    "csw.operator": (Role.operator, "Demo call-center operatori"),
    "csw.gps": (Role.gps, "Demo GPS xodimi — Asaka"),
    "csw.haydovchi": (Role.driver, "Demo haydovchi — Asaka"),
}


class DemoCredentialsError(ValueError):
    pass


def parse(raw: str) -> dict[str, str]:
    """login → parol. Barcha 7 login bo'lishi, noma'lumlari bo'lmasligi va parollar kuchli bo'lishi shart."""
    from app.services.auth_service import MIN_PASSWORD
    if not raw or not raw.strip():
        raise DemoCredentialsError("DEMO_CREDENTIALS bo'sh — test server .env'iga JSON yozing")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise DemoCredentialsError(f"DEMO_CREDENTIALS JSON emas: {e.msg}") from None
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        raise DemoCredentialsError('DEMO_CREDENTIALS {"login": "parol", ...} ko\'rinishida bo\'lishi kerak')
    data = {k.strip().lower(): v for k, v in data.items()}
    if unknown := sorted(set(data) - set(DEMO_USERS)):
        raise DemoCredentialsError(f"Noma'lum demo login: {', '.join(unknown)}")
    if missing := sorted(set(DEMO_USERS) - set(data)):
        raise DemoCredentialsError(f"Demo login yetishmaydi: {', '.join(missing)}")
    weak = sorted(u for u, p in data.items()
                  if len(p) < MIN_PASSWORD or not any(c.isalpha() for c in p) or not any(c.isdigit() for c in p))
    if weak:
        raise DemoCredentialsError(f"Kuchsiz parol (kamida {MIN_PASSWORD} belgi, harf va raqam): {', '.join(weak)}")
    return data


def accounts() -> list[dict]:
    """Login sahifasi chiplari uchun: faqat login va rol (parolsiz)."""
    return [{"username": u, "role": r.value} for u, (r, _) in DEMO_USERS.items()]
