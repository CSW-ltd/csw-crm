"""GPS dispatch PR-B: SmartGPS ulanishi (faqat o'qish tokeni, shifrlangan), gps-worker sinxronlashi soxta SmartGPS bilan,
o'zgartiruvchi buyruqlar rad etilishi, huquqlar. Faqat sun'iy ma'lumot (app/gps/mock_server.py)."""
import copy
import json

import pytest
from httpx import ASGITransport
from sqlalchemy import select

from app.gps import mock_server
from app.gps.client import GpsForbidden, WialonClient, is_read_only, login_url
from app.gps.sync import due
from app.gps_worker import tick
from app.models import Geozone, GeozoneGroup, GpsSource, VehicleLink
from app.services.gps.importer import _zone, zone_from_wialon

SERVER = "http://mock.gps.test"
T = ASGITransport(app=mock_server.app)


@pytest.fixture(autouse=True)
def fresh_mock():
    saved = copy.deepcopy(mock_server.STATE)
    yield
    mock_server.STATE.clear()
    mock_server.STATE.update(saved)


async def _source(admin, district_id, account=mock_server.MOCK_USER, unit_group="Test tumani mashinalari") -> int:
    r = await admin.post("/api/v1/dispatch/sources", json={"system": "smartgps", "server": SERVER, "account": account,
                                                           "district_id": district_id, "unit_group": unit_group})
    assert r.status_code == 200, r.text
    return r.json()["id"]


async def _connect(admin, sid, token=mock_server.MOCK_TOKEN):
    r = await admin.put(f"/api/v1/dispatch/sources/{sid}/token", json={"token": token})
    assert r.status_code == 200, r.text
    assert r.json()["token_status"] == "pending"


async def _src(admin, sid) -> dict:
    return next(s for s in (await admin.get("/api/v1/dispatch/sources")).json()["sources"] if s["id"] == sid)


async def test_connect_and_sync(world, client_factory, sessionmaker):
    did = world["districts"]["a"]
    admin, manager, gps = await client_factory("admin"), await client_factory("manager"), await client_factory("gps")
    for c in (manager, gps):
        assert (await c.get("/api/v1/dispatch/sources")).status_code == 403
        assert (await c.post("/api/v1/dispatch/sources", json={"system": "smartgps", "server": "x.uz", "account": "a"})).status_code == 403
    r = await admin.post("/api/v1/dispatch/sources", json={"system": "smartgps", "server": "not a host", "account": "a"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "gps_bad_server"
    sid = await _source(admin, did)
    r = await admin.post("/api/v1/dispatch/sources", json={"system": "smartgps", "server": SERVER, "account": mock_server.MOCK_USER})
    assert r.status_code == 409

    # «Ulash» havolasi: faqat o'qish (0x300), qaytish — shu saytning callback sahifasi
    ok = await admin.get(f"/api/v1/dispatch/sources/{sid}/connect-url", params={"redirect": f"https://test/admin/gps-callback/{sid}"})
    assert ok.status_code == 200 and "access_type=0x300" in ok.json()["url"] and ok.json()["url"].startswith(f"{SERVER}/login.html?")
    for bad in (f"https://evil.example/admin/gps-callback/{sid}", "https://test/admin/other", f"http://test/admin/gps-callback/{sid}"):
        r = await admin.get(f"/api/v1/dispatch/sources/{sid}/connect-url", params={"redirect": bad})
        assert r.status_code == 422, bad

    r = await admin.put(f"/api/v1/dispatch/sources/{sid}/token", json={"token": "parol123 emas-token"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "gps_bad_token"
    await _connect(admin, sid)
    async with sessionmaker() as db:  # token bazada ochiq ko'rinishda emas
        src = await db.get(GpsSource, sid)
        assert src.token_enc and mock_server.MOCK_TOKEN not in src.token_enc

    s = (await admin.get("/api/v1/dispatch/sources")).json()
    assert s["worker"]["alive"] is False and s["encryption_ready"] is True
    assert await tick(sessionmaker, transport=T) == 1
    s = (await admin.get("/api/v1/dispatch/sources")).json()
    assert s["worker"]["alive"] is True
    row = next(x for x in s["sources"] if x["id"] == sid)
    assert (row["token_status"], row["token_user"], row["last_error"]) == ("ok", mock_server.MOCK_USER, None)
    assert (row["zones"], row["groups"], row["vehicles_linked"]) == (5, 2, 1)  # guruhda 60 101 AB bor, 60 102 AB yo'q
    st = row["last_stats"]
    assert (st["zones_new"], st["groups_new"], st["units"]) == (5, 2, 2)
    async with sessionmaker() as db:
        link = (await db.execute(select(VehicleLink).where(VehicleLink.source_id == sid))).scalar_one()
        assert link.vehicle_id == world["vehicles"]["v1"] and link.ext_unit_id == 9002
        g = (await db.execute(select(GeozoneGroup).where(GeozoneGroup.name == "Test МСП guruhi"))).scalar_one()
        assert json.loads(g.zone_ids) == [4]

    # Bugun sinxronlangan — qayta kerak emas; «Hozir sinxronlash» → o'zgarish 0
    assert await tick(sessionmaker, transport=T) == 0
    assert (await admin.post(f"/api/v1/dispatch/sources/{sid}/sync")).status_code == 200
    assert await tick(sessionmaker, transport=T) == 1
    st = (await _src(admin, sid))["last_stats"]
    assert (st["zones_new"], st["zones_changed"], st["zones_deactivated"], st["groups_changed"], st["vehicles_linked"]) == (0, 0, 0, 0, 0)

    # SmartGPS'da geozona o'chdi va biri o'zgardi → CRM'da o'chirilmaydi, is_active=False; o'zgargani yangilanadi
    del mock_server.STATE["zones"][2]
    mock_server.STATE["zones"][1]["w"] = 40
    await admin.post(f"/api/v1/dispatch/sources/{sid}/sync")
    await tick(sessionmaker, transport=T)
    st = (await _src(admin, sid))["last_stats"]
    assert (st["zones_new"], st["zones_changed"], st["zones_deactivated"]) == (0, 1, 1)
    async with sessionmaker() as db:
        assert (await db.execute(select(Geozone).where(Geozone.source_id == sid, Geozone.ext_id == 2))).scalar_one().is_active is False

    # SmartGPS bo'sh javob qaytarsa — CRM'dagi geozonalar o'chirilmaydi
    mock_server.STATE["zones"].clear()
    await admin.post(f"/api/v1/dispatch/sources/{sid}/sync")
    await tick(sessionmaker, transport=T)
    row = await _src(admin, sid)
    assert "geozona kelmadi" in row["last_error"] and row["zones"] == 4 and row["token_status"] == "ok"
    log = (await admin.get(f"/api/v1/dispatch/sources/{sid}/log")).json()
    assert log[0]["ok"] is False and log[1]["ok"] is True

    # Token o'chirildi — worker tegmaydi
    assert (await admin.delete(f"/api/v1/dispatch/sources/{sid}/token")).status_code == 200
    assert (await _src(admin, sid))["token_status"] == "none"
    r = await admin.post(f"/api/v1/dispatch/sources/{sid}/sync")
    assert r.status_code == 422 and r.json()["error"]["code"] == "gps_not_connected"


async def test_token_owner_and_rights(world, client_factory, sessionmaker):
    admin = await client_factory("admin")
    # Boshqa akkaunt tokeni — rad etiladi
    sid = await _source(admin, world["districts"]["a"], account="boshqa_akkaunt")
    await _connect(admin, sid)
    await tick(sessionmaker, transport=T)
    row = await _src(admin, sid)
    assert row["token_status"] == "invalid" and "boshqa_akkaunt" in row["last_error"] and row["zones"] == 0
    # O'zgartirish huquqli token — rad etiladi
    full = "b2" * 36
    mock_server.STATE["tokens"][full] = {"user": "full_user", "at": -1}
    sid2 = await _source(admin, world["districts"]["b"], account="full_user", unit_group=None)
    await _connect(admin, sid2, full)
    await tick(sessionmaker, transport=T)
    row = await _src(admin, sid2)
    assert row["token_status"] == "invalid" and "faqat o'qish" in row["last_error"] and row["zones"] == 0
    # Yaroqsiz token (SmartGPS xato 4)
    sid3 = await _source(admin, None, account="x", unit_group=None)
    await _connect(admin, sid3, "c3" * 36)
    await tick(sessionmaker, transport=T)
    assert (await _src(admin, sid3))["token_status"] == "invalid"
    # Topilmagan mashina guruhi — geozonalar sinxronlanadi, mashinalar bog'lanmaydi, ogohlantirish
    await admin.patch(f"/api/v1/dispatch/sources/{sid}", json={"account": mock_server.MOCK_USER, "unit_group": "Yo'q guruh"})
    await tick(sessionmaker, transport=T)
    row = await _src(admin, sid)
    assert row["token_status"] == "ok" and row["zones"] == 5 and row["vehicles_linked"] == 0 and "Yo'q guruh" in row["last_error"]


async def test_client_is_read_only():
    async with WialonClient(SERVER, transport=T) as c:
        await c.login(mock_server.MOCK_TOKEN)
        for svc in ("resource/update_zone", "item/update_name", "core/create_unit", "user/update_password", "report/update_report"):
            with pytest.raises(GpsForbidden):
                await c.call(svc, {})
    assert not any(x.startswith(("resource/update", "item/", "core/create", "user/")) for x in mock_server.STATE["calls"])
    assert is_read_only(0x300) and is_read_only(None) and not is_read_only(-1) and not is_read_only(0x700)
    assert "access_type=0x300" in login_url("gps.example.uz", "https://admin.example/admin/gps-callback/1")


def test_zone_hash_matches_export():
    """Jonli sinxron va gps_eksport.py zip importi bitta geozonani «o'zgardi» deb ko'rmasligi kerak."""
    z = mock_server.STATE["zones"][3]
    live = zone_from_wialon(z, 501)
    ring = [[p["x"], p["y"]] for p in z["p"]] + [[z["p"][0]["x"], z["p"][0]["y"]]]
    exported = _zone({"geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {"resurs_id": 501, "id": 3, "nom": z["n"], "rang": "#3388ff"}})
    assert live.hash == exported.hash


def test_due_rules():
    from datetime import datetime
    src = GpsSource(system="smartgps", server="x", account="a", token_enc="x", token_status="ok", is_active=True)
    morning, after = datetime(2026, 11, 24, 0, 0), datetime(2026, 11, 24, 1, 0)  # UTC: 05:00 va 06:00 Toshkent
    assert not due(src, morning, "05:30") and due(src, after, "05:30")
    src.last_sync_at = datetime(2026, 11, 24, 0, 45)  # bugun 05:45 da
    assert not due(src, after, "05:30")
    src.sync_requested_at = after
    assert due(src, after, "05:30")
    src.is_active = False
    assert not due(src, after, "05:30")
