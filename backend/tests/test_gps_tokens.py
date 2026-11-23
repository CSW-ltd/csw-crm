"""GPS token chidamliligi (0028): zaxira token, har soatlik tekshiruv, avtomatik o'tish va qaytish, ogohlantirish (bir marta),
tarmoq xatosi tokenni o'ldirmaydi, dispatch xodimi tokenni ko'rmaydi. Faqat sun'iy ma'lumot (app/gps/mock_server.py)."""
import copy
from datetime import timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import func, select

from app.gps import client as gps_client, mock_server, tokens
from app.gps_worker import tick
from app.models import GpsSource, Notification, SituationEvent

SERVER = "http://mock.gps.test"
T = ASGITransport(app=mock_server.app)
BACKUP_TOKEN, BACKUP_USER = "d4" * 36, "zaxira_akkaunt"


@pytest.fixture(autouse=True)
def fresh_mock():
    saved = copy.deepcopy(mock_server.STATE)
    mock_server.STATE["tokens"][BACKUP_TOKEN] = {"user": BACKUP_USER, "at": 0x300}
    yield
    mock_server.STATE.clear()
    mock_server.STATE.update(saved)


async def _setup(admin, district_id) -> int:
    r = await admin.post("/api/v1/dispatch/sources", json={"system": "smartgps", "server": SERVER, "account": mock_server.MOCK_USER,
                                                           "district_id": district_id, "unit_group": "Test tumani mashinalari"})
    sid = r.json()["id"]
    assert (await admin.patch(f"/api/v1/dispatch/sources/{sid}", json={"backup_account": BACKUP_USER})).status_code == 200
    assert (await admin.put(f"/api/v1/dispatch/sources/{sid}/token", json={"token": mock_server.MOCK_TOKEN})).status_code == 200
    r = await admin.put(f"/api/v1/dispatch/sources/{sid}/token", params={"slot": "backup"}, json={"token": BACKUP_TOKEN})
    assert r.status_code == 200 and r.json()["token_status"] == "pending"
    return sid


async def _src(admin, sid) -> dict:
    return next(s for s in (await admin.get("/api/v1/dispatch/sources")).json()["sources"] if s["id"] == sid)


async def _age(sessionmaker, sid, hours=2):
    """Oxirgi tekshiruvni orqaga suradi — keyingi tick'da har soatlik tekshiruv ishlaydi."""
    async with sessionmaker() as db:
        src = await db.get(GpsSource, sid)
        src.token_checked_at = src.token_checked_at - timedelta(hours=hours)
        await db.commit()


async def _events(sessionmaker, kind) -> list[SituationEvent]:
    async with sessionmaker() as db:
        return list((await db.execute(select(SituationEvent).where(SituationEvent.kind == kind))).scalars())


async def _notifs(sessionmaker, user_id=None) -> list[Notification]:
    async with sessionmaker() as db:
        q = select(Notification).where(Notification.kind.like("gps_token_%"))
        if user_id is not None:
            q = q.where(Notification.user_id == user_id)
        return list((await db.execute(q)).scalars())


async def test_failover_alert_once_and_return(world, client_factory, sessionmaker):
    admin = await client_factory("admin")
    sid = await _setup(admin, world["districts"]["a"])
    assert await tick(sessionmaker, transport=T) == 1
    row = await _src(admin, sid)
    assert (row["token_status"], row["backup_token_status"], row["backup_token_user"]) == ("ok", "ok", BACKUP_USER)
    assert (row["active_slot"], row["alert_state"], row["zones"]) == ("main", "ok", 5) and row["token_checked_at"]

    # Bir soat ichida qayta tekshirilmaydi
    calls = len(mock_server.STATE["calls"])
    assert await tick(sessionmaker, transport=T) == 0
    assert len(mock_server.STATE["calls"]) == calls

    # Asosiy token SmartGPS'da o'chirildi → soatlik tekshiruv: zaxiraga o'tadi, ogohlantirish bitta
    del mock_server.STATE["tokens"][mock_server.MOCK_TOKEN]
    await _age(sessionmaker, sid)
    await tick(sessionmaker, transport=T)
    row = await _src(admin, sid)
    assert (row["token_status"], row["backup_token_status"], row["active_slot"], row["alert_state"]) == ("invalid", "ok", "backup", "d:main")
    ev = await _events(sessionmaker, "gps_token_dead")
    assert len(ev) == 1 and ev[0].level.value == "warning" and (ev[0].ref_type, ev[0].ref_id) == ("gps_source", sid)
    async with sessionmaker() as db:
        from app.models import User
        from app.models.enums import Role
        admin_ids = set((await db.execute(select(User.id).where(User.role == Role.admin, User.is_active.is_(True)))).scalars())
    ns = await _notifs(sessionmaker)
    assert {n.user_id for n in ns} == admin_ids and all(n.ref_type == "gps_source" and n.ref_id == sid for n in ns)
    gps_user = (await (await client_factory("gps")).get("/api/v1/auth/me")).json()["id"]
    assert not await _notifs(sessionmaker, gps_user)  # dispatch xodimiga bildirishnoma ketmaydi
    bell = (await admin.get("/api/v1/notifications")).json()
    assert bell["unread"] >= 1 and bell["items"][0]["kind"] == "gps_token_dead"

    # Sinxronlash zaxira token bilan ishlaydi
    await admin.post(f"/api/v1/dispatch/sources/{sid}/sync")
    assert await tick(sessionmaker, transport=T) == 1
    log = (await admin.get(f"/api/v1/dispatch/sources/{sid}/log")).json()
    assert log[0]["ok"] is True

    # Takror tekshiruv — yangi ogohlantirish yo'q
    await _age(sessionmaker, sid)
    await tick(sessionmaker, transport=T)
    assert len(await _events(sessionmaker, "gps_token_dead")) == 1 and len(await _notifs(sessionmaker)) == len(admin_ids)

    # Admin asosiy tokenni qayta uladi → asosiyga qaytadi, «tiklandi» faoliyat jurnalida
    new_main = "e5" * 36
    mock_server.STATE["tokens"][new_main] = {"user": mock_server.MOCK_USER, "at": 0x300}
    await admin.put(f"/api/v1/dispatch/sources/{sid}/token", json={"token": new_main})
    await tick(sessionmaker, transport=T)
    row = await _src(admin, sid)
    assert (row["token_status"], row["active_slot"], row["alert_state"]) == ("ok", "main", "ok")
    assert len(await _events(sessionmaker, "act_gps_token_ok")) == 1

    # Ikkalasi ham o'ldi → «GPS ma'lumoti to'xtadi» (error), sinxronlash tokensiz bajarilmaydi
    mock_server.STATE["tokens"].clear()
    await _age(sessionmaker, sid)
    await tick(sessionmaker, transport=T)
    row = await _src(admin, sid)
    assert (row["token_status"], row["backup_token_status"], row["alert_state"]) == ("invalid", "invalid", "down")
    ev = await _events(sessionmaker, "gps_token_down")
    assert len(ev) == 1 and ev[0].level.value == "error" and BACKUP_USER in ev[0].message
    await admin.post(f"/api/v1/dispatch/sources/{sid}/sync")
    await tick(sessionmaker, transport=T)
    assert "Ishlaydigan token yo'q" in (await _src(admin, sid))["last_error"]


async def test_failover_inside_sync(world, client_factory, sessionmaker):
    """Asosiy token soatlik tekshiruvlar orasida o'ldi — sinxronlash o'sha aylanishda zaxiraga o'tadi."""
    admin = await client_factory("admin")
    sid = await _setup(admin, world["districts"]["a"])
    await tick(sessionmaker, transport=T)
    del mock_server.STATE["tokens"][mock_server.MOCK_TOKEN]
    await admin.post(f"/api/v1/dispatch/sources/{sid}/sync")
    assert await tick(sessionmaker, transport=T) == 1
    row = await _src(admin, sid)
    assert (row["token_status"], row["active_slot"], row["alert_state"]) == ("invalid", "backup", "d:main")
    assert (await admin.get(f"/api/v1/dispatch/sources/{sid}/log")).json()[0]["ok"] is True
    assert len(await _events(sessionmaker, "gps_token_dead")) == 1


async def test_network_error_keeps_token(world, client_factory, sessionmaker, monkeypatch):
    admin = await client_factory("admin")
    sid = await _setup(admin, world["districts"]["a"])
    await tick(sessionmaker, transport=T)

    async def no_sleep(_):
        return None
    monkeypatch.setattr(gps_client.asyncio, "sleep", no_sleep)

    def down(request):
        raise httpx.ConnectError("server javob bermadi")
    await _age(sessionmaker, sid)
    await tick(sessionmaker, transport=httpx.MockTransport(down))
    row = await _src(admin, sid)
    assert (row["token_status"], row["backup_token_status"], row["alert_state"]) == ("ok", "ok", "ok")
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).where(SituationEvent.kind.like("gps_token_%")))).scalar_one() == 0


async def test_tokens_admin_only_and_hidden(world, client_factory, sessionmaker):
    admin, gps, manager = await client_factory("admin"), await client_factory("gps"), await client_factory("manager")
    sid = await _setup(admin, world["districts"]["a"])
    for c in (gps, manager):
        assert (await c.get("/api/v1/dispatch/sources")).status_code == 403
        assert (await c.put(f"/api/v1/dispatch/sources/{sid}/token", params={"slot": "backup"}, json={"token": BACKUP_TOKEN})).status_code == 403
        assert (await c.delete(f"/api/v1/dispatch/sources/{sid}/token", params={"slot": "backup"})).status_code == 403
        assert (await c.get(f"/api/v1/dispatch/sources/{sid}/connect-url",
                            params={"redirect": f"https://test/admin/gps-callback/{sid}/backup"})).status_code == 403
    raw = (await admin.get("/api/v1/dispatch/sources")).text
    assert mock_server.MOCK_TOKEN not in raw and BACKUP_TOKEN not in raw and "_enc" not in raw
    r = await admin.put(f"/api/v1/dispatch/sources/{sid}/token", params={"slot": "x"}, json={"token": BACKUP_TOKEN})
    assert r.status_code == 422 and r.json()["error"]["code"] == "gps_bad_slot"
    ok = await admin.get(f"/api/v1/dispatch/sources/{sid}/connect-url", params={"redirect": f"https://test/admin/gps-callback/{sid}/backup"})
    assert ok.status_code == 200
    # Zaxira tokenni o'chirish — ogohlantirish emas, asosiysi qoladi
    await tick(sessionmaker, transport=T)
    assert (await admin.delete(f"/api/v1/dispatch/sources/{sid}/token", params={"slot": "backup"})).status_code == 200
    row = await _src(admin, sid)
    assert (row["backup_token_status"], row["active_slot"], row["alert_state"]) == ("none", "main", "ok")
    # Asosiysini o'chirsa — zaxira yo'q, ulanmagan holat (ogohlantirish emas)
    await admin.delete(f"/api/v1/dispatch/sources/{sid}/token")
    assert (await _src(admin, sid))["alert_state"] == "ok"


def test_state_rules():
    src = GpsSource(system="smartgps", server="x", account="a", token_enc="m", token_status="ok", backup_token_enc="b",
                    backup_token_status="ok", active_slot="main")
    assert tokens.state(src) == "ok" and tokens.candidates(src) == ["main", "backup"]
    src.token_status = "invalid"
    tokens.pick_active(src)
    assert tokens.state(src) == "d:main" and src.active_slot == "backup" and tokens.candidates(src) == ["backup"]
    src.backup_token_status = "invalid"
    assert tokens.state(src) == "down" and tokens.candidates(src) == []
    src.backup_token_enc = None  # zaxira yo'q, asosiysi o'lik
    assert tokens.state(src) == "down"
    assert tokens.account(src, "backup") == "a"
