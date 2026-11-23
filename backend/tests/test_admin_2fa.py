"""Admin 2FA (TOTP): ulash, har login'da kod, zaxira kodlar, qayta ishlatish, blok, refresh, qayta o'rnatish, oxirgi admin."""
import time

import pyotp
import pytest
from httpx import ASGITransport, AsyncClient

from app.core import totp
from app.core.config import get_settings
from app.core.security import hash_password
from app.models import SituationEvent, User
from app.models.enums import Role
from sqlalchemy import select

from tests.conftest import HEADERS, PASSWORD

AUTH = "/api/v1/auth"


@pytest.fixture
def mfa_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_2fa", True)


def _client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS)


async def _challenge(c: AsyncClient, username: str = "admin") -> dict:
    r = await c.post(f"{AUTH}/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 401 and r.json()["error"]["code"] == "mfa_required", r.text
    assert "access_token" not in r.cookies
    return r.json()["error"]["details"]


def _code(secret: str, offset_steps: int = 0) -> str:
    return pyotp.TOTP(secret).at(time.time() + offset_steps * totp.STEP)


async def _enroll(c: AsyncClient, username: str = "admin") -> tuple[str, list[str]]:
    d = await _challenge(c, username)
    assert d["mode"] == "setup"
    s = (await c.post(f"{AUTH}/2fa/setup", json={"mfa_token": d["mfa_token"]})).json()
    assert s["uri"].startswith("otpauth://totp/") and s["qr_svg"].startswith("<svg")
    r = await c.post(f"{AUTH}/2fa/enable", json={"mfa_token": d["mfa_token"], "code": _code(s["secret"])})
    assert r.status_code == 200, r.text
    codes = r.json()["backup_codes"]
    assert len(codes) == 10 and len(set(codes)) == 10
    assert (await c.get(f"{AUTH}/me")).status_code == 200  # sessiya ochildi
    return s["secret"], codes


async def test_disabled_by_default_outside_production(world, client_factory):
    assert get_settings().admin_2fa_on is False
    await client_factory("admin")  # oddiy login (demo/lokal/testlar)


async def test_other_roles_not_affected(world, client_factory, mfa_on):
    await client_factory("manager")


async def test_setup_enable_then_verify_each_login(world, app, sessionmaker, mfa_on):
    c = _client(app)
    secret, _ = await _enroll(c)
    async with sessionmaker() as db:
        u = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
        assert u.totp_enabled and secret not in (u.totp_secret_enc or "")  # bazada shifrlangan
        kinds = {e.kind for e in (await db.execute(select(SituationEvent))).scalars()}
        assert "mfa_enabled" in kinds

    c2 = _client(app)
    d = await _challenge(c2)
    assert d["mode"] == "verify"
    r = await c2.post(f"{AUTH}/2fa/verify", json={"mfa_token": d["mfa_token"], "code": _code(secret, 1)})
    assert r.status_code == 200, r.text
    # aynan shu kod (va undan oldingisi) qayta ishlamaydi
    d = await _challenge(_client(app))
    r = await _client(app).post(f"{AUTH}/2fa/verify", json={"mfa_token": d["mfa_token"], "code": _code(secret, 1)})
    assert r.json()["error"]["code"] == "mfa_invalid_code"


async def test_enable_wrong_code_and_setup_after_enable(world, app, mfa_on):
    c = _client(app)
    d = await _challenge(c)
    s = (await c.post(f"{AUTH}/2fa/setup", json={"mfa_token": d["mfa_token"]})).json()
    bad = "000000" if _code(s["secret"]) != "000000" else "111111"
    r = await c.post(f"{AUTH}/2fa/enable", json={"mfa_token": d["mfa_token"], "code": bad})
    assert r.status_code == 422 and r.json()["error"]["code"] == "mfa_invalid_code"
    r = await c.post(f"{AUTH}/2fa/enable", json={"mfa_token": d["mfa_token"], "code": _code(s["secret"])})
    assert r.status_code == 200
    r = await c.post(f"{AUTH}/2fa/setup", json={"mfa_token": d["mfa_token"]})
    assert r.json()["error"]["code"] == "mfa_already_enabled"  # ulangan kalitni login'siz almashtirib bo'lmaydi


async def test_backup_code_single_use(world, app, sessionmaker, mfa_on):
    _, codes = await _enroll(_client(app))
    d = await _challenge(_client(app))
    r = await _client(app).post(f"{AUTH}/2fa/verify", json={"mfa_token": d["mfa_token"], "code": codes[0].upper()})
    assert r.status_code == 200, r.text
    d = await _challenge(_client(app))
    r = await _client(app).post(f"{AUTH}/2fa/verify", json={"mfa_token": d["mfa_token"], "code": codes[0]})
    assert r.json()["error"]["code"] == "mfa_invalid_code"
    async with sessionmaker() as db:
        ev = [e for e in (await db.execute(select(SituationEvent))).scalars() if e.kind == "mfa_backup_used"]
        assert len(ev) == 1 and '"left": 9' in ev[0].params


async def test_wrong_codes_lock_even_with_correct_password(world, app, mfa_on):
    secret, _ = await _enroll(_client(app))
    bad = "000000" if _code(secret) != "000000" else "111111"
    for _ in range(get_settings().login_max_attempts):
        d = await _challenge(_client(app))  # to'g'ri parol hisoblagichni tozalamaydi
        await _client(app).post(f"{AUTH}/2fa/verify", json={"mfa_token": d["mfa_token"], "code": bad})
    r = await _client(app).post(f"{AUTH}/login", json={"username": "admin", "password": PASSWORD})
    assert r.status_code == 423 and r.json()["error"]["code"] == "account_locked"


async def test_bad_token(world, app, mfa_on):
    r = await _client(app).post(f"{AUTH}/2fa/verify", json={"mfa_token": "x.y.z", "code": "123456"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "mfa_expired"


async def test_refresh_requires_enrolled_admin(world, app, client_factory, sessionmaker, monkeypatch):
    c = await client_factory("admin")  # 2FA yoqilmasdan oldin ochilgan sessiya
    monkeypatch.setattr(get_settings(), "admin_2fa", True)
    r = await c.post(f"{AUTH}/refresh")
    assert r.status_code == 401
    m = await client_factory("manager")
    assert (await m.post(f"{AUTH}/refresh")).status_code == 200


async def _second_admin(sessionmaker) -> int:
    async with sessionmaker() as db:
        u = User(username="admin2", password_hash=hash_password(PASSWORD), full_name="Zaxira admin", role=Role.admin)
        db.add(u)
        await db.commit()
        return u.id


async def test_reset_by_other_admin(world, app, sessionmaker, mfa_on):
    a2 = await _second_admin(sessionmaker)
    c1 = _client(app)
    await _enroll(c1)
    c2 = _client(app)
    await _enroll(c2, "admin2")
    admin_id = world["users"]["admin"]

    r = await c1.post(f"/api/v1/admin/users/{admin_id}/reset-2fa", json={"reason": "telefon yo'qoldi"})
    assert r.json()["error"]["code"] == "cannot_reset_own_2fa"
    r = await c2.post(f"/api/v1/admin/users/{admin_id}/reset-2fa", json={"reason": "  "})
    assert r.json()["error"]["code"] == "mfa_reason_required"
    r = await c2.post(f"/api/v1/admin/users/{admin_id}/reset-2fa", json={"reason": "telefon yo'qoldi"})
    assert r.status_code == 200 and r.json()["totp_enabled"] is False
    assert (await c1.post(f"{AUTH}/refresh")).status_code == 401  # eski sessiya uzaytirilmaydi
    assert (await _challenge(_client(app)))["mode"] == "setup"
    async with sessionmaker() as db:
        ev = [e for e in (await db.execute(select(SituationEvent))).scalars() if e.kind == "mfa_reset"]
        assert len(ev) == 1 and "telefon" in ev[0].params and ev[0].actor_id == a2
    users = (await c2.get("/api/v1/admin/users")).json()
    assert {u["username"]: u["totp_enabled"] for u in users if u["role"] == "admin"} == {"admin": False, "admin2": True}


async def test_cli_reset(world, app, sessionmaker, mfa_on, monkeypatch):
    from app import reset_2fa
    from app.db import session as db_session
    await _enroll(_client(app))

    class _Eng:
        async def dispose(self):
            pass
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker)
    monkeypatch.setattr(db_session, "engine", _Eng())
    assert await reset_2fa._main("admin", "server orqali") == 0
    assert await reset_2fa._main("yoq", "x") == 1
    assert (await _challenge(_client(app)))["mode"] == "setup"


async def test_last_admin_protected(world, client_factory, sessionmaker):
    from app.core.errors import AppError
    from app.schemas import UserUpdateIn
    from app.services import admin_service
    a2 = await _second_admin(sessionmaker)
    admin = await client_factory("admin")
    # boshqa faol admin bor — o'chirish va rolini o'zgartirish mumkin
    assert (await admin.patch(f"/api/v1/admin/users/{a2}", json={"role": "manager"})).status_code == 200
    assert (await admin.patch(f"/api/v1/admin/users/{a2}", json={"role": "admin"})).status_code == 200
    assert (await admin.patch(f"/api/v1/admin/users/{a2}", json={"is_active": False})).status_code == 200
    # endi "admin" yagona faol admin: uni hech kim (masalan faolsiz admin2 nomidan) o'chira olmaydi
    async with sessionmaker() as db:
        actor = await db.get(User, a2)
        for body in (UserUpdateIn(is_active=False), UserUpdateIn(role=Role.manager)):
            with pytest.raises(AppError) as e:
                await admin_service.update_user(db, actor, world["users"]["admin"], body)
            assert e.value.code == "last_admin"


def test_totp_helpers():
    secret = totp.new_secret()
    enc = totp.encrypt(secret)
    assert enc != secret and totp.decrypt(enc) == secret and totp.decrypt("buzilgan") is None
    now = time.time()
    step = totp.match_step(secret, pyotp.TOTP(secret).at(now), None, now)
    assert step == int(now // totp.STEP)
    assert totp.match_step(secret, pyotp.TOTP(secret).at(now), step, now) is None
    assert totp.match_step(secret, "12345", None, now) is None
    assert totp.hash_backup("ABCD-efgh") == totp.hash_backup("abcdefgh")


def test_production_requires_key(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "app_env", "production")
    monkeypatch.setattr(s, "jwt_secret", "x" * 40)
    monkeypatch.setattr(s, "cookie_secure", True)
    monkeypatch.setattr(s, "database_url", "mysql+aiomysql://u:p@h/db")
    monkeypatch.setattr(s, "role_hosts", '{"admin.example.test": ["admin"]}')
    monkeypatch.setattr(s, "totp_enc_key", "")
    with pytest.raises(RuntimeError, match="TOTP_ENC_KEY"):
        s.check_production()
    from cryptography.fernet import Fernet
    monkeypatch.setattr(s, "totp_enc_key", Fernet.generate_key().decode())
    s.check_production()
