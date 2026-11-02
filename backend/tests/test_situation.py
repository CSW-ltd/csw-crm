from datetime import timedelta

from sqlalchemy import func, select

from app.db.base import utcnow
from app.models import SituationEvent
from app.models.enums import SituationLevel
from app.services.situation import purge_old
from tests.helpers import assign, FAR, fill_act, schedule_driver
from tests.test_customers import _import

ACT = {"containers": 2, "volume_m3": 4, "note": "Olib ketildi"}


async def _events(client, **params) -> dict:
    r = await client.get("/api/v1/situation", params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_lockout_creates_warning_for_admin(world, client_factory):
    anon, admin = await client_factory(), await client_factory("admin")
    for _ in range(5):
        await anon.post("/api/v1/auth/login", json={"username": "driver", "password": "wrong-pass1"})
    for c in (admin,):
        page = await _events(c)
        assert page["unread"] == 1 and page["total"] == 1
        ev = page["items"][0]
        assert ev["kind"] == "account_locked" and ev["level"] == "warning"
        assert ev["params"]["username"] == "driver" and ev["district_id"] == world["districts"]["a"]
        assert ev["ref_type"] == "user" and ev["ref_id"] == world["users"]["driver"]


async def test_only_admin_sees_situation(world, client_factory):
    for username in ("manager", "gps", "legal", "driver"):
        c = await client_factory(username)
        assert (await c.get("/api/v1/situation")).status_code == 403
        assert (await c.get("/api/v1/situation/unread")).status_code == 403


async def test_admin_actions_are_logged_with_actor(world, client_factory):
    admin = manager = await client_factory("admin")
    r = await admin.post("/api/v1/admin/users", json={"username": "yangi", "full_name": "Yangi Xodim", "role": "manager",
                                                      "password": "Vaqtincha1"})
    assert r.status_code == 201, r.text
    await admin.patch(f"/api/v1/admin/vehicles/{world['vehicles']['v2']}", json={"is_active": False})
    await admin.put("/api/v1/admin/settings", json={"gps_radius_m": 200})
    await admin.put("/api/v1/admin/settings", json={"gps_radius_m": 200})  # o'zgarmadi — hodisa yo'q
    await admin.patch(f"/api/v1/admin/users/{world['users']['driver2']}", json={"full_name": "Boshqa ism"})  # holat o'zgarmadi
    await admin.post(f"/api/v1/admin/users/{world['users']['driver2']}/reset-password", json={"password": "Yangi1234"})
    await admin.patch(f"/api/v1/admin/districts/{world['districts']['b']}", json={"is_active": False})
    page = await _events(manager)
    kinds = [e["kind"] for e in page["items"]]
    assert kinds == ["district_deactivated", "password_reset", "settings_changed", "vehicle_deactivated", "user_created"]
    assert all(e["actor_name"] == "Admin" for e in page["items"])
    radius = next(e for e in page["items"] if e["kind"] == "settings_changed")
    assert radius["params"] == {"old": 300, "new": 200}
    assert (await _events(manager, level="warning"))["total"] == 2
    assert (await _events(manager, kind="user_created"))["items"][0]["params"]["username"] == "yangi"


async def test_read_marker_is_per_user_and_never_goes_back(world, client_factory):
    admin = await client_factory("admin")
    r = await admin.post("/api/v1/admin/users", json={"username": "admin2", "full_name": "Ikkinchi Admin", "role": "admin",
                                                      "password": "Vaqtincha1"})
    assert r.status_code == 201
    manager = await client_factory()
    await manager.post("/api/v1/auth/login", json={"username": "admin2", "password": "Vaqtincha1"})
    await manager.post("/api/v1/auth/change-password", json={"current_password": "Vaqtincha1", "new_password": "Ikkinchi2026"})
    await admin.post("/api/v1/situation/read", json={})
    await admin.put("/api/v1/admin/settings", json={"gps_radius_m": 200})
    await admin.put("/api/v1/admin/settings", json={"gps_radius_m": 250})
    first = (await _events(admin))["items"][1]["id"]  # birinchi radius hodisasi
    r = (await admin.post("/api/v1/situation/read", json={"up_to_id": first})).json()
    assert r["unread"] == 1
    assert (await admin.post("/api/v1/situation/read", json={})).json()["unread"] == 0
    assert (await admin.post("/api/v1/situation/read", json={"up_to_id": first})).json()["unread"] == 0  # orqaga qaytmaydi
    assert (await manager.get("/api/v1/situation/unread")).json()["unread"] == 3  # ikkinchi admin hali o'qimagan (+ user_created)
    await admin.put("/api/v1/admin/settings", json={"gps_radius_m": 300})
    assert (await admin.get("/api/v1/situation/unread")).json()["unread"] == 1
    assert (await _events(admin, unread="true"))["total"] == 1


async def test_driver_events_suspect_failed_and_import(world, client_factory):
    admin, gps, driver = await client_factory("admin"), await client_factory("gps"), await client_factory("driver")
    await schedule_driver(gps, driver, world["users"]["driver"], world["vehicles"]["v1"])
    r1, r2 = world["requests"][:2]
    for rid in (r1, r2):
        await assign(gps, rid, world["vehicles"]["v1"])
        await driver.post(f"/api/v1/driver/requests/{rid}/enroute")
    await fill_act(driver, r1, FAR)
    assert (await driver.post(f"/api/v1/driver/requests/{r1}/complete", json={**ACT, **FAR})).json()["request"]["status"] == "suspect"
    await driver.post(f"/api/v1/driver/requests/{r2}/fail", json={"reason": "no_recipient", "note": "Qo'riqchi kiritmadi"})
    await _import(admin, dry_run=True)   # tahlil — hodisa yo'q
    await _import(admin, dry_run=False)
    items = [e for e in (await _events(admin))["items"] if e["level"] != "activity"]
    assert [e["kind"] for e in items] == ["import_done", "request_failed", "act_suspect"]
    assert items[0]["params"]["new"] == 3 and items[0]["ref_type"] == "import"
    assert items[1]["params"]["reason"] == "no_recipient" and items[1]["params"]["note"] == "Qo'riqchi kiritmadi"
    assert items[2]["params"]["distance"] > 300 and items[2]["district_id"] == world["districts"]["a"]


async def test_failed_action_leaves_no_event(world, client_factory):
    admin = await client_factory("admin")
    r = await admin.post("/api/v1/admin/users", json={"username": "admin", "full_name": "Ikkinchi Admin", "role": "manager", "password": "Vaqtincha1"})
    assert r.json()["error"]["code"] == "username_taken"
    assert (await _events(admin))["total"] == 0


async def test_purge_removes_events_older_than_90_days(sessionmaker):
    async with sessionmaker() as db:
        db.add_all([SituationEvent(level=SituationLevel.info, kind="old", message="eski", created_at=utcnow() - timedelta(days=91)),
                    SituationEvent(level=SituationLevel.info, kind="new", message="yangi", created_at=utcnow() - timedelta(days=89))])
        await db.commit()
        assert await purge_old(db) == 1
        assert (await db.execute(select(func.count()).select_from(SituationEvent))).scalar_one() == 1
