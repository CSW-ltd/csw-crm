"""4-bosqich: demo loginlari — DEMO_CREDENTIALS (JSON), seed faqat 7 demo foydalanuvchi bilan, --reset, prod himoyasi."""
import json

import pytest
from sqlalchemy import func, select

from app import seed as seed_mod
from app.core.config import Settings, get_settings
from app.core.demo import DEMO_USERS, DemoCredentialsError, parse
from app.core.security import hash_password, verify_password
from app.models import District, Region, User, UserDistrict
from app.models.enums import Role

CREDS = {u: f"Demo{i}parol{i}" for i, u in enumerate(DEMO_USERS)}


def test_parse_ok_and_errors():
    assert parse(json.dumps(CREDS)) == CREDS
    with pytest.raises(DemoCredentialsError, match="bo'sh"):
        parse("")
    with pytest.raises(DemoCredentialsError, match="JSON emas"):
        parse("csw.admin:Parol123")
    with pytest.raises(DemoCredentialsError, match="Noma'lum demo login: boss"):
        parse(json.dumps(CREDS | {"boss": "Parol1234"}))
    with pytest.raises(DemoCredentialsError, match="yetishmaydi: csw.gps"):
        parse(json.dumps({k: v for k, v in CREDS.items() if k != "csw.gps"}))
    with pytest.raises(DemoCredentialsError, match="Kuchsiz parol.*csw.operator"):
        parse(json.dumps(CREDS | {"csw.operator": "qisqa1"}))


async def test_seed_creates_only_demo_users(sessionmaker):
    async with sessionmaker() as db:
        assert await seed_mod.seed(db, CREDS) is True
    async with sessionmaker() as db:
        users = {u.username: u for u in (await db.execute(select(User))).scalars()}
        assert set(users) == set(DEMO_USERS)
        for name, (role, _) in DEMO_USERS.items():
            assert users[name].role == role and verify_password(CREDS[name], users[name].password_hash)
        asaka = (await db.execute(select(District).where(District.name == seed_mod.DEMO_DISTRICT))).scalar_one()
        assert users["csw.gps"].district_id == asaka.id and users["csw.haydovchi"].district_id == asaka.id
        n_districts = (await db.execute(select(func.count(District.id)))).scalar_one()
        for name in ("csw.manager", "csw.yurist", "csw.buxgalter", "csw.operator"):
            cnt = (await db.execute(select(func.count()).select_from(UserDistrict).where(UserDistrict.user_id == users[name].id))).scalar_one()
            assert cnt == n_districts == 12
        assert await seed_mod.seed(db, CREDS) is False  # to'ldirilgan baza — hech narsa qo'shilmaydi


async def test_reset_removes_old_users(sessionmaker):
    async with sessionmaker() as db:
        db.add(Region(name="Eski viloyat"))
        db.add(User(username="gps1", password_hash=hash_password("Eski12345"), full_name="Eski GPS", role=Role.gps))
        await db.commit()
    async with sessionmaker() as db:
        assert await seed_mod.seed(db, CREDS) is False  # reset'siz — tegmaydi
        await seed_mod.reset(db)
        assert await seed_mod.seed(db, CREDS) is True
    async with sessionmaker() as db:
        names = set((await db.execute(select(User.username))).scalars())
        assert "gps1" not in names and names == set(DEMO_USERS)
        assert not (await db.execute(select(Region).where(Region.name == "Eski viloyat"))).first()


@pytest.mark.parametrize("argv, env, msg", [
    (["--reset", "--yes"], {"app_env": "production"}, "production"),
    (["--reset"], {"app_env": "development"}, "--yes"),
    ([], {"app_env": "development", "demo_credentials": ""}, "DEMO_CREDENTIALS bo'sh"),
])
async def test_seed_cli_guards(monkeypatch, capsys, argv, env, msg):
    for k, v in env.items():
        monkeypatch.setattr(get_settings(), k, v)
    assert await seed_mod._main(argv) == 1
    assert msg in capsys.readouterr().err


def test_demo_env_requires_credentials():
    with pytest.raises(RuntimeError, match="Demo sozlamalari"):
        Settings(app_env="demo", demo_credentials="").check_production()
    Settings(app_env="demo", demo_credentials=json.dumps(CREDS)).check_production()


async def test_auth_config_demo_accounts_without_passwords(app, client_factory, monkeypatch):
    c = await client_factory()
    assert (await c.get("/api/v1/auth/config")).json()["demo_accounts"] == []
    monkeypatch.setattr(get_settings(), "app_env", "demo")
    monkeypatch.setattr(get_settings(), "demo_credentials", json.dumps(CREDS))
    r = await c.get("/api/v1/auth/config")
    accounts = r.json()["demo_accounts"]
    assert [a["username"] for a in accounts] == list(DEMO_USERS)
    assert {"username": "csw.yurist", "role": "legal"} in accounts
    assert not any(p in r.text for p in CREDS.values())
