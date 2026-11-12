"""Prod'ga tayyorlik: /api/v1/health, ACTIVE_ROLES, prod sozlamalari tekshiruvi, app.bootstrap."""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.bootstrap import BootstrapError, run, temp_password
from app.core.config import Settings, get_settings
from app.core.security import verify_password
from app.db.session import get_session
from app.models import District, Provider, Region, User
from app.services.auth_service import check_password_strength
from tests.conftest import PASSWORD


@pytest.fixture
def phase1(monkeypatch):
    monkeypatch.setattr(get_settings(), "active_roles", "manager,legal,accountant")


# --- health ---

async def test_health_ok(world, client_factory):
    c = await client_factory()
    r = await c.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["db"] == "ok"


async def test_health_db_down(app, client_factory, tmp_path):
    broken = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/no/such/dir/x.db")

    async def override():
        async with async_sessionmaker(broken)() as s:
            yield s

    app.dependency_overrides[get_session] = override
    c = await client_factory()
    r = await c.get("/api/v1/health")
    assert r.status_code == 503 and r.json()["db"] == "down"
    await broken.dispose()


# --- ACTIVE_ROLES ---

async def test_inactive_role_cannot_login(world, client_factory, phase1):
    c = await client_factory()
    r = await c.post("/api/v1/auth/login", json={"username": "operator", "password": PASSWORD})
    assert r.status_code == 403 and r.json()["error"]["code"] == "role_inactive"
    assert (await client_factory("manager"))  # faol rol kiradi
    assert (await client_factory("admin"))    # admin har doim faol


async def test_inactive_role_existing_session_rejected(world, client_factory, monkeypatch):
    c = await client_factory("gps")
    monkeypatch.setattr(get_settings(), "active_roles", "manager")
    assert (await c.get("/api/v1/auth/me")).status_code == 401
    assert (await c.post("/api/v1/auth/refresh")).status_code == 401


async def test_cannot_create_inactive_role(world, client_factory, phase1):
    admin = await client_factory("admin")
    body = {"username": "op2", "full_name": "Operator 2", "role": "operator", "password": "Parol1234",
            "district_ids": [world["districts"]["a"]]}
    r = await admin.post("/api/v1/admin/users", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "role_inactive"


async def test_auth_config_active_roles(world, client_factory, phase1):
    c = await client_factory()
    assert (await c.get("/api/v1/auth/config")).json()["active_roles"] == ["accountant", "admin", "legal", "manager"]


async def test_auth_config_all_roles_by_default(world, client_factory):
    c = await client_factory()
    assert (await c.get("/api/v1/auth/config")).json()["active_roles"] is None


# --- prod sozlamalari ---

def test_production_rejects_defaults():
    with pytest.raises(RuntimeError) as e:
        Settings(app_env="production", jwt_secret="dev-only-secret-change-me", cookie_secure=False,
                 database_url="sqlite+aiosqlite:///x.db", active_roles="admin,boss").check_production()
    msg = str(e.value)
    assert "JWT_SECRET" in msg and "COOKIE_SECURE" in msg and "SQLite" in msg and "boss" in msg


def test_production_accepts_good_settings():
    Settings(app_env="production", jwt_secret="x" * 40, cookie_secure=True, tab_sessions=False,
             database_url="mysql+aiomysql://u:p@db/csw", active_roles="admin,manager,legal,accountant",
             role_hosts='{"admin.csw.uz": ["admin"], "legal.csw.uz": ["legal"]}').check_production()


def test_development_not_checked():
    Settings(app_env="development").check_production()


# --- bootstrap ---

DATA = {
    "regions": [
        {"name": "Namuna viloyati", "provider": {"name": "Namuna Eko", "code": "nme"}, "districts": ["Birinchi tumani", "Ikkinchi tumani"]},
    ],
    "users": [
        {"username": "Bosh.Admin", "full_name": "Bosh admin", "role": "admin"},
        {"username": "menejer", "full_name": "Menejer", "role": "manager", "districts": ["Birinchi tumani", "Ikkinchi tumani"]},
        {"username": "gps.bir", "full_name": "GPS xodimi", "role": "gps", "district": "Birinchi tumani"},
    ],
}


def test_temp_password_is_strong():
    for _ in range(50):
        check_password_strength(temp_password())


async def test_bootstrap_creates_and_is_idempotent(sessionmaker):
    async with sessionmaker() as db:
        res = await run(db, DATA)
    assert {p[0] for p in res.passwords} == {"bosh.admin", "menejer", "gps.bir"}
    async with sessionmaker() as db:
        assert (await db.execute(select(Provider))).scalar_one().code == "NME"
        users = {u.username: u for u in (await db.execute(select(User))).scalars()}
        assert all(u.must_change_password for u in users.values())
        pwd = dict((p[0], p[2]) for p in res.passwords)
        assert verify_password(pwd["menejer"], users["menejer"].password_hash)
        d1 = (await db.execute(select(District).where(District.name == "Birinchi tumani"))).scalar_one()
        assert users["gps.bir"].district_id == d1.id
    async with sessionmaker() as db:
        again = await run(db, DATA)
    assert again.passwords == [] and again.created == [] and set(again.skipped_users) == {"bosh.admin", "menejer", "gps.bir"}
    async with sessionmaker() as db:
        assert len((await db.execute(select(Region))).scalars().all()) == 1


async def test_bootstrap_login_requires_password_change(sessionmaker, app, client_factory):
    async with sessionmaker() as db:
        res = await run(db, DATA)
    pwd = dict((p[0], p[2]) for p in res.passwords)["menejer"]
    c = await client_factory()
    r = await c.post("/api/v1/auth/login", json={"username": "menejer", "password": pwd})
    assert r.status_code == 200 and r.json()["must_change_password"] is True
    assert (await c.get("/api/v1/admin/users")).json()["error"]["code"] == "password_change_required"


@pytest.mark.parametrize("bad, code", [
    ({"users": [{"username": "x", "full_name": "X", "role": "boss"}]}, "noma'lum rol"),
    ({"users": [{"username": "x", "full_name": "X", "role": "gps"}]}, "bitta tumanga"),
    ({"users": [{"username": "x", "full_name": "X", "role": "manager", "districts": ["Yo'q tuman"]}]}, "tuman topilmadi"),
])
async def test_bootstrap_validation(sessionmaker, bad, code):
    async with sessionmaker() as db:
        with pytest.raises(BootstrapError, match=code):
            await run(db, bad)
