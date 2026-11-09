"""Portallar (ROLE_HOSTS): har rol faqat o'z subdomenida; cookie host-only."""
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, get_settings
from app.core.portals import RoleHostsError, normalize_host, parse
from tests.conftest import HEADERS, PASSWORD

HOSTS = {
    "admin.csw.uz": ["admin"],
    "manager.csw.uz": ["manager"],
    "legal.csw.uz": ["legal"],
    "gps.csw.uz": ["gps"],
}


@pytest.fixture
def portals(monkeypatch):
    monkeypatch.setattr(get_settings(), "role_hosts", json.dumps(HOSTS))


@pytest.fixture
def host_client(app):
    clients = []

    async def make(host: str, username: str | None = None, expect: int = 200) -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app), base_url=f"https://{host}", headers=HEADERS)
        clients.append(c)
        if username:
            r = await c.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
            assert r.status_code == expect, r.text
        return c

    yield make


def test_normalize_host():
    assert normalize_host("Legal.CSW.uz:443") == "legal.csw.uz"
    assert normalize_host("legal.csw.uz.") == "legal.csw.uz"
    assert normalize_host(None) == ""


@pytest.mark.parametrize("raw", ["not json", "[]", "{}", '{"a.csw.uz": []}', '{"a.csw.uz": "legal"}', '{"a.csw.uz": ["boss"]}'])
def test_parse_rejects_bad(raw):
    with pytest.raises(RoleHostsError):
        parse(raw)


def test_parse_empty_means_unrestricted():
    assert parse("") is None and parse("  ") is None


async def test_login_on_own_portal(world, host_client, portals):
    c = await host_client("legal.csw.uz", "legal")
    assert (await c.get("/api/v1/auth/me")).json()["role"] == "legal"


async def test_login_on_other_portal_rejected(world, host_client, portals):
    c = await host_client("manager.csw.uz")
    r = await c.post("/api/v1/auth/login", json={"username": "legal", "password": PASSWORD})
    assert r.status_code == 403
    err = r.json()["error"]
    assert err["code"] == "wrong_portal" and err["details"] == {"home": "legal.csw.uz"}
    assert "set-cookie" not in r.headers


async def test_wrong_password_on_other_portal_does_not_reveal_portal(world, host_client, portals):
    c = await host_client("manager.csw.uz")
    r = await c.post("/api/v1/auth/login", json={"username": "legal", "password": "wrong-pass-1"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials"


async def test_admin_only_on_admin_portal(world, host_client, portals):
    await host_client("admin.csw.uz", "admin")
    c = await host_client("manager.csw.uz")
    r = await c.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert r.status_code == 403 and r.json()["error"]["code"] == "wrong_portal"


async def test_unknown_host_rejected(world, host_client, portals):
    c = await host_client("mine.csw.uz")
    r = await c.post("/api/v1/auth/login", json={"username": "legal", "password": PASSWORD})
    assert r.status_code == 403 and r.json()["error"]["code"] == "unknown_portal"


async def test_token_from_other_portal_rejected(world, host_client, portals):
    """Token boshqa hostga olib o'tilsa (Bearer) — /auth/me, API va refresh rad etadi."""
    legal = await host_client("legal.csw.uz", "legal")
    access, refresh = legal.cookies.get("access_token"), legal.cookies.get("refresh_token")
    other = await host_client("manager.csw.uz")
    r = await other.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "wrong_portal"
    r = await other.get("/api/v1/customers", headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 403
    other.cookies.set("refresh_token", refresh, domain="manager.csw.uz", path="/api/v1/auth")
    r = await other.post("/api/v1/auth/refresh")
    assert r.status_code == 403 and r.json()["error"]["code"] == "wrong_portal"


async def test_cookies_are_host_only(world, host_client, portals):
    c = await host_client("legal.csw.uz")
    r = await c.post("/api/v1/auth/login", json={"username": "legal", "password": PASSWORD})
    cookies = r.headers.get_list("set-cookie")
    assert len(cookies) == 2 and all("domain=" not in h.lower() for h in cookies)


async def test_config_reports_portal_and_filters_demo(world, host_client, portals, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "demo")
    c = await host_client("legal.csw.uz")
    cfg = (await c.get("/api/v1/auth/config")).json()
    assert cfg["portal"] == {"host": "legal.csw.uz", "roles": ["legal"]}
    assert [a["role"] for a in cfg["demo_accounts"]] == ["legal"]
    unknown = (await (await host_client("x.csw.uz")).get("/api/v1/auth/config")).json()
    assert unknown["portal"]["roles"] == [] and unknown["demo_accounts"] == []


async def test_no_role_hosts_means_no_restriction(world, client_factory):
    c = await client_factory("legal")
    assert (await c.get("/api/v1/auth/config")).json()["portal"] is None
    assert (await c.get("/api/v1/auth/me")).status_code == 200


async def test_socket_rejects_other_portal(world, portals, monkeypatch):
    from app import realtime
    from app.core.security import ACCESS, create_token

    async def enter(sid, room):
        pass
    monkeypatch.setattr(realtime.sio, "enter_room", enter)
    token = create_token(world["users"]["legal"], "legal", ACCESS)
    assert await realtime.connect("s1", {"HTTP_HOST": "manager.csw.uz"}, {"token": token}) is False
    assert await realtime.connect("s2", {"HTTP_HOST": "legal.csw.uz"}, {"token": token}) is True


def test_production_requires_role_hosts():
    base = dict(app_env="production", jwt_secret="x" * 40, cookie_secure=True,
                database_url="mysql+aiomysql://u:p@h/db")
    with pytest.raises(RuntimeError, match="ROLE_HOSTS"):
        Settings(**base, role_hosts="").check_production()
    Settings(**base, role_hosts=json.dumps(HOSTS)).check_production()
    with pytest.raises(RuntimeError, match="ROLE_HOSTS"):
        Settings(**base, role_hosts='{"a.csw.uz": ["boss"]}').check_production()
