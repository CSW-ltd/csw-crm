"""Prod/test uchun boshlang'ich ma'lumotlar: viloyatlar, xizmat ko'rsatuvchilar, tumanlar va xodimlar — YAML fayldan.

Ishga tushirish:  python -m app.bootstrap /path/to/bootstrap.yaml
Namuna: deploy/bootstrap.example.yaml (faqat sun'iy ma'lumot). Haqiqiy fayl serverda saqlanadi, repoga qo'shilmaydi.

- Mavjud yozuvlar (viloyat nomi, provider kodi, tuman nomi, login) o'zgartirilmaydi — qayta ishga tushirish xavfsiz.
- Har yangi xodimga tasodifiy vaqtinchalik parol beriladi va terminalga BIR MARTA chiqariladi;
  birinchi kirishda parolni almashtirish majburiy (must_change_password).
- Demo ma'lumot (mashinalar, korxonalar, ta'riflar) yaratilmaydi — buning uchun app.seed.
"""
import asyncio
import secrets
import string
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions import MULTI_DISTRICT_ROLES, SINGLE_DISTRICT_ROLES, apply_template
from app.core.security import hash_password
from app.models import AppSetting, District, Provider, Region, User
from app.models.enums import Role

_ALPHABET = "".join(c for c in string.ascii_letters + string.digits if c not in "0OoIl1")


def temp_password(length: int = 12) -> str:
    """Kamida bitta harf va bitta raqam (check_password_strength talabi)."""
    while True:
        p = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        if any(c.isalpha() for c in p) and any(c.isdigit() for c in p):
            return p


class BootstrapError(ValueError):
    pass


@dataclass
class Result:
    created: list[str] = field(default_factory=list)   # "viloyat: ..." kabi qatorlar
    passwords: list[tuple[str, str, str]] = field(default_factory=list)  # (login, rol, vaqtinchalik parol)
    skipped_users: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise BootstrapError("YAML ildizi lug'at (mapping) bo'lishi kerak")
    return data


async def run(db: AsyncSession, data: dict) -> Result:
    res = Result()
    settings = get_settings()

    if not (await db.execute(select(AppSetting).where(AppSetting.key == "gps_radius_m"))).scalar_one_or_none():
        db.add(AppSetting(key="gps_radius_m", value=str(settings.gps_radius_default_m)))

    districts: dict[str, District] = {d.name: d for d in (await db.execute(select(District))).scalars()}
    for r in data.get("regions") or []:
        name = str(r["name"]).strip()
        region = (await db.execute(select(Region).where(Region.name == name))).scalar_one_or_none()
        if not region:
            region = Region(name=name)
            db.add(region)
            await db.flush()
            res.created.append(f"viloyat: {name}")
        if p := r.get("provider"):
            code = str(p["code"]).strip().upper()
            if not (await db.execute(select(Provider).where(Provider.code == code))).scalar_one_or_none():
                if (await db.execute(select(Provider).where(Provider.region_id == region.id))).scalar_one_or_none():
                    raise BootstrapError(f"«{name}» viloyatida boshqa provider bor — {code} qo'shilmadi")
                db.add(Provider(name=str(p["name"]).strip(), code=code, region_id=region.id))
                res.created.append(f"provider: {code}")
        for d_name in r.get("districts") or []:
            d_name = str(d_name).strip()
            if d_name in districts:
                if districts[d_name].region_id != region.id:
                    raise BootstrapError(f"«{d_name}» tumani boshqa viloyatda allaqachon bor")
                continue
            d = District(name=d_name, region_id=region.id)
            db.add(d)
            await db.flush()
            districts[d_name] = d
            res.created.append(f"tuman: {d_name}")

    seen: set[str] = set()
    for u in data.get("users") or []:
        username = str(u["username"]).strip().lower()
        if username in seen:
            raise BootstrapError(f"«{username}» YAML'da ikki marta yozilgan")
        seen.add(username)
        try:
            role = Role(u["role"])
        except ValueError:
            raise BootstrapError(f"«{username}»: noma'lum rol «{u['role']}»") from None
        names = [str(x).strip() for x in (u.get("districts") or ([u["district"]] if u.get("district") else []))]
        missing = [n for n in names if n not in districts]
        if missing:
            raise BootstrapError(f"«{username}»: tuman topilmadi — {', '.join(missing)}")
        if role in SINGLE_DISTRICT_ROLES and len(names) != 1:
            raise BootstrapError(f"«{username}» ({role.value}) aynan bitta tumanga bog'lanadi")
        if (await db.execute(select(User).where(User.username == username))).scalar_one_or_none():
            res.skipped_users.append(username)
            continue
        if not settings.role_active(role.value):
            res.warnings.append(f"«{username}»: {role.value} roli ACTIVE_ROLES'da yo'q — kira olmaydi, rol faollashguncha")
        pwd = temp_password()
        user = User(username=username, full_name=str(u["full_name"]).strip(), role=role, phone=u.get("phone"),
                    password_hash=hash_password(pwd), must_change_password=True,
                    district_id=districts[names[0]].id if role in SINGLE_DISTRICT_ROLES else None)
        apply_template(user, [districts[n].id for n in names] if role in MULTI_DISTRICT_ROLES else None)
        db.add(user)
        res.passwords.append((username, role.value, pwd))
    await db.commit()
    return res


async def _main(path: str) -> int:
    from app.db.session import SessionLocal, engine
    try:
        data = load(path)
        async with SessionLocal() as db:
            res = await run(db, data)
    except (BootstrapError, KeyError) as e:
        print(f"XATO: {e}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()
    for line in res.created:
        print(f"+ {line}")
    for name in res.skipped_users:
        print(f"= {name} — allaqachon bor, o'zgartirilmadi")
    for w in res.warnings:
        print(f"! {w}")
    if res.passwords:
        print("\nVaqtinchalik parollar (faqat hozir ko'rinadi — xavfsiz kanal orqali tarqating; birinchi kirishda almashtiriladi):")
        for username, role, pwd in res.passwords:
            print(f"  {username:<24} {role:<11} {pwd}")
    else:
        print("Yangi xodim yo'q.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Foydalanish: python -m app.bootstrap <bootstrap.yaml>", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(_main(sys.argv[1])))
