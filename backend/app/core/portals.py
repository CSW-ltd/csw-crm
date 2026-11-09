"""Portallar: har rol o'z subdomenida (ROLE_HOSTS). Bitta ilova, Host sarlavhasi bo'yicha ajratiladi.

ROLE_HOSTS — JSON: {"manager.csw.uz": ["manager"], "legal.csw.uz": ["legal"], ...}.
Bo'sh — cheklov yo'q (lokal ishlab chiqish va testlar). Ro'yxatda yo'q host — hech kim kira olmaydi.
"""
import json

from app.core.config import get_settings
from app.core.errors import AppError


class RoleHostsError(ValueError):
    pass


def normalize_host(host: str | None) -> str:
    """`Legal.CSW.uz:443` → `legal.csw.uz` (port, katta harf va oxirgi nuqta olib tashlanadi)."""
    h = (host or "").strip().lower()
    if h.startswith("["):  # IPv6 — portal bo'la olmaydi
        return h
    return h.split(":", 1)[0].rstrip(".")


def parse(raw: str) -> dict[str, frozenset[str]] | None:
    """None — cheklov yo'q. Xato format yoki noma'lum rol — RoleHostsError."""
    from app.models.enums import Role
    if not raw or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RoleHostsError(f"ROLE_HOSTS JSON emas: {e.msg}") from None
    if not isinstance(data, dict) or not data or not all(
            isinstance(h, str) and isinstance(rs, list) and rs and all(isinstance(r, str) for r in rs) for h, rs in data.items()):
        raise RoleHostsError('ROLE_HOSTS {"host": ["rol", ...], ...} ko\'rinishida bo\'lishi kerak')
    known = {r.value for r in Role}
    if unknown := sorted({r for rs in data.values() for r in rs} - known):
        raise RoleHostsError(f"ROLE_HOSTS'da noma'lum rol: {', '.join(unknown)}")
    return {normalize_host(h): frozenset(rs) for h, rs in data.items()}


def role_hosts() -> dict[str, frozenset[str]] | None:
    return parse(get_settings().role_hosts)


def portal_roles(host: str | None) -> frozenset[str] | None:
    """Shu hostda ruxsat etilgan rollar. None — cheklov yo'q; bo'sh to'plam — noma'lum host."""
    m = role_hosts()
    if m is None:
        return None
    return m.get(normalize_host(host), frozenset())


def home_host(role: str) -> str | None:
    """Rolning o'z portali (xato xabarida ko'rsatish uchun)."""
    m = role_hosts() or {}
    return next((h for h, rs in sorted(m.items()) if role in rs), None)


def host_allows(host: str | None, role: str) -> bool:
    roles = portal_roles(host)
    return roles is None or role in roles


def check_portal(host: str | None, role: str) -> None:
    roles = portal_roles(host)
    if roles is None or role in roles:
        return
    if not roles:
        raise AppError(403, "unknown_portal", "Bu manzil orqali tizimga kirib bo'lmaydi")
    home = home_host(role)
    raise AppError(403, "wrong_portal", "Bu portal sizning rolingiz uchun emas",
                   details={"home": home} if home else None)
