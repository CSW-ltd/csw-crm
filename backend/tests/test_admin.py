from tests.conftest import PASSWORD
from tests.helpers import assign, schedule_driver  # noqa: F401

TEMP = "Vaqtincha123"


async def test_only_admin_writes_manager_reads(world, client_factory):
    admin, manager, gps = await client_factory("admin"), await client_factory("manager"), await client_factory("gps")
    assert (await manager.get("/api/v1/admin/users")).status_code == 200
    body = {"username": "new.driver", "full_name": "Yangi Haydovchi", "role": "driver", "district_id": world["districts"]["a"], "password": TEMP}
    assert (await manager.post("/api/v1/admin/users", json=body)).status_code == 403
    assert (await gps.get("/api/v1/admin/users")).status_code == 403
    r = await admin.post("/api/v1/admin/users", json=body)
    assert r.status_code == 201 and r.json()["must_change_password"] is True


async def test_new_user_must_change_password_first(world, client_factory):
    admin = await client_factory("admin")
    await admin.post("/api/v1/admin/users", json={"username": "drv9", "full_name": "Haydovchi 9", "role": "driver",
                                                 "district_id": world["districts"]["a"], "password": TEMP})
    c = await client_factory()
    me = (await c.post("/api/v1/auth/login", json={"username": "drv9", "password": TEMP})).json()
    assert me["must_change_password"] is True
    r = await c.get("/api/v1/driver/today")
    assert r.status_code == 403 and r.json()["error"]["code"] == "password_change_required"
    r = await c.post("/api/v1/auth/change-password", json={"current_password": TEMP, "new_password": "12345678"})
    assert r.json()["error"]["code"] == "weak_password"
    r = await c.post("/api/v1/auth/change-password", json={"current_password": TEMP, "new_password": "Yangi2026parol"})
    assert r.status_code == 200 and r.json()["must_change_password"] is False
    assert (await c.get("/api/v1/driver/today")).status_code == 200


async def test_role_requires_district_and_unique_username(world, client_factory):
    admin = await client_factory("admin")
    r = await admin.post("/api/v1/admin/users", json={"username": "gpsx", "full_name": "GPS X", "role": "gps", "password": TEMP})
    assert r.json()["error"]["code"] == "district_required"
    r = await admin.post("/api/v1/admin/users", json={"username": "driver", "full_name": "Dup", "role": "operator", "password": TEMP})
    assert r.json()["error"]["code"] == "username_taken"
    r = await admin.post("/api/v1/admin/users", json={"username": "Bad Name", "full_name": "X", "role": "operator", "password": TEMP})
    assert r.status_code == 422


async def test_deactivated_user_cannot_login_or_use_session(world, client_factory):
    admin, driver = await client_factory("admin"), await client_factory("driver")
    r = await admin.patch(f"/api/v1/admin/users/{world['users']['driver']}", json={"is_active": False})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await driver.get("/api/v1/auth/me")).status_code == 401  # mavjud sessiya ham to'xtaydi
    c = await client_factory()
    assert (await c.post("/api/v1/auth/login", json={"username": "driver", "password": PASSWORD})).status_code == 401


async def test_admin_cannot_lock_themselves_out(world, client_factory):
    admin = await client_factory("admin")
    r = await admin.patch(f"/api/v1/admin/users/{world['users']['admin']}", json={"is_active": False})
    assert r.json()["error"]["code"] == "cannot_change_self"
    r = await admin.patch(f"/api/v1/admin/users/{world['users']['admin']}", json={"role": "manager"})
    assert r.json()["error"]["code"] == "cannot_change_self"


async def test_reset_password_unlocks_and_forces_change(world, client_factory):
    admin, c = await client_factory("admin"), await client_factory()
    for _ in range(5):
        await c.post("/api/v1/auth/login", json={"username": "driver2", "password": "wrong"})
    assert (await c.post("/api/v1/auth/login", json={"username": "driver2", "password": PASSWORD})).status_code == 423
    r = await admin.post(f"/api/v1/admin/users/{world['users']['driver2']}/reset-password", json={"password": TEMP})
    assert r.status_code == 200 and r.json()["locked_until"] is None
    me = (await c.post("/api/v1/auth/login", json={"username": "driver2", "password": TEMP})).json()
    assert me["must_change_password"] is True


async def test_districts_and_vehicles(world, client_factory):
    admin = await client_factory("admin")
    regions = (await admin.get("/api/v1/admin/regions")).json()
    d = (await admin.post("/api/v1/admin/districts", json={"name": "Baliqchi tumani", "region_id": regions[0]["id"]})).json()
    v = await admin.post("/api/v1/admin/vehicles", json={"plate": "60  a777bc", "model": "ISUZU", "district_id": d["id"]})
    assert v.status_code == 201 and v.json()["plate"] == "60 A777BC"
    dup = await admin.post("/api/v1/admin/vehicles", json={"plate": "60 a777BC", "district_id": d["id"]})
    assert dup.json()["error"]["code"] == "plate_taken"
    r = await admin.patch(f"/api/v1/admin/districts/{d['id']}", json={"is_active": False})
    assert r.json()["is_active"] is False
    r = await admin.post("/api/v1/admin/users", json={"username": "drvx", "full_name": "X Y", "role": "driver", "district_id": d["id"], "password": TEMP})
    assert r.json()["error"]["code"] == "district_inactive"


async def test_gps_radius_bounds(world, client_factory):
    admin = await client_factory("admin")
    assert (await admin.put("/api/v1/admin/settings", json={"gps_radius_m": 50})).status_code == 422
    assert (await admin.put("/api/v1/admin/settings", json={"gps_radius_m": 350})).status_code == 422
    r = await admin.put("/api/v1/admin/settings", json={"gps_radius_m": 150})
    assert r.json()["gps_radius_m"] == 150
    assert (await admin.get("/api/v1/admin/settings")).json()["gps_radius_m"] == 150


async def test_radius_setting_changes_act_result(world, client_factory):
    from tests.helpers import fill_act
    admin, gps, driver = await client_factory("admin"), await client_factory("gps"), await client_factory("driver")
    await admin.put("/api/v1/admin/settings", json={"gps_radius_m": 150})
    await schedule_driver(gps, driver, world["users"]["driver"], world["vehicles"]["v1"])
    rid = world["requests"][0]
    await assign(gps, rid, world["vehicles"]["v1"])
    await driver.post(f"/api/v1/driver/requests/{rid}/enroute")
    at_200m = {"lat": 40.6433, "lng": 72.2390}  # korxonadan ~200 m
    await fill_act(driver, rid, at_200m)
    body = (await driver.post(f"/api/v1/driver/requests/{rid}/complete",
                              json={"containers": 1, "volume_m3": 2, "note": "ok", **at_200m})).json()
    assert 150 < body["act"]["distance_m"] < 300 and body["act"]["radius_m"] == 150
    assert body["request"]["status"] == "suspect"
