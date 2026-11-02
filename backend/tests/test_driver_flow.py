from tests.helpers import assign, FAR, NEAR, fill_act, schedule_driver, upload

ACT = {"containers": 3, "volume_m3": 6.5, "note": "Hammasi olib ketildi"}


async def _ready(world, client_factory):
    gps, driver = await client_factory("gps"), await client_factory("driver")
    await schedule_driver(gps, driver, world["users"]["driver"], world["vehicles"]["v1"])
    return gps, driver


async def test_assign_creates_naryad_per_provider_and_year(world, client_factory):
    gps, _ = await _ready(world, client_factory)
    ids = world["requests"]
    n1 = (await assign(gps, ids[0], world["vehicles"]["v1"])).json()["naryad_no"]
    n2 = (await assign(gps, ids[1], world["vehicles"]["v1"])).json()["naryad_no"]
    year = n1.split("-")[1]
    assert n1 == f"BTE-{year}-00001" and n2 == f"BTE-{year}-00002"


async def test_assign_requires_schedule_and_same_district(world, client_factory):
    gps = await client_factory("gps")
    rid = world["requests"][0]
    r = await assign(gps, rid, world["vehicles"]["v1"])
    assert r.json()["error"]["code"] == "vehicle_not_scheduled"
    r = await assign(gps, rid, world["vehicles"]["vb"])
    assert r.json()["error"]["code"] == "district_mismatch"


async def test_full_flow_done(world, client_factory):
    gps, driver = await _ready(world, client_factory)
    rid = world["requests"][0]
    await assign(gps, rid, world["vehicles"]["v1"])
    tasks = (await driver.get("/api/v1/driver/tasks")).json()
    assert [t["id"] for t in tasks][0] == rid and tasks[0]["customer"]["stir"] == "305123456"

    assert (await driver.post(f"/api/v1/driver/requests/{rid}/enroute")).json()["status"] == "enroute"
    assert (await driver.post("/api/v1/driver/location", json=NEAR)).status_code == 204
    await fill_act(driver, rid, NEAR)
    tasks = (await driver.get("/api/v1/driver/tasks")).json()
    assert tasks[0]["status"] == "onsite" and set(tasks[0]["files"]) == {"before", "after", "face", "sign"}

    r = await driver.post(f"/api/v1/driver/requests/{rid}/complete", json={**ACT, **NEAR})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["request"]["status"] == "done"
    assert body["act"]["in_radius"] and body["act"]["distance_m"] < 100 and body["act"]["vehicle_plate"] == "60 101 AB"


async def test_outside_radius_is_suspect(world, client_factory):
    gps, driver = await _ready(world, client_factory)
    rid = world["requests"][0]
    await assign(gps, rid, world["vehicles"]["v1"])
    await driver.post(f"/api/v1/driver/requests/{rid}/enroute")
    await fill_act(driver, rid, FAR)
    body = (await driver.post(f"/api/v1/driver/requests/{rid}/complete", json={**ACT, **FAR})).json()
    assert body["request"]["status"] == "suspect" and body["act"]["distance_m"] > 300


async def test_incomplete_act_rejected(world, client_factory):
    gps, driver = await _ready(world, client_factory)
    rid = world["requests"][0]
    await assign(gps, rid, world["vehicles"]["v1"])
    await driver.post(f"/api/v1/driver/requests/{rid}/enroute")
    assert (await upload(driver, rid, "before", NEAR)).status_code == 200
    r = await driver.post(f"/api/v1/driver/requests/{rid}/complete", json={**ACT, **NEAR})
    err = r.json()["error"]
    assert r.status_code == 422 and err["code"] == "act_incomplete"
    assert "file:after" in err["message"] and "file:face" in err["message"] and "file:sign" in err["message"]


async def test_photo_order_and_gps_rules(world, client_factory):
    gps, driver = await _ready(world, client_factory)
    rid = world["requests"][0]
    await assign(gps, rid, world["vehicles"]["v1"])
    await driver.post(f"/api/v1/driver/requests/{rid}/enroute")
    assert (await upload(driver, rid, "after", NEAR)).json()["error"]["code"] == "before_photo_first"
    assert (await upload(driver, rid, "before")).json()["error"]["code"] == "gps_required"


async def test_fail_keeps_request_open(world, client_factory):
    gps, driver = await _ready(world, client_factory)
    rid = world["requests"][0]
    await assign(gps, rid, world["vehicles"]["v1"])
    await driver.post(f"/api/v1/driver/requests/{rid}/enroute")
    r = await driver.post(f"/api/v1/driver/requests/{rid}/fail", json={"reason": "no_waste", "note": "Konteyner bo'sh"})
    assert r.json()["status"] == "failed" and r.json()["stage"] == "yellow"
    assert (await driver.get("/api/v1/driver/tasks")).json() == []  # Manager nazoratiga o'tdi


async def test_driver_cannot_touch_foreign_request(world, client_factory):
    gps, _ = await _ready(world, client_factory)
    rid = world["requests"][0]
    await assign(gps, rid, world["vehicles"]["v1"])
    other = await client_factory("driver2")
    await schedule_driver(gps, other, world["users"]["driver2"], world["vehicles"]["v2"])
    r = await other.post(f"/api/v1/driver/requests/{rid}/enroute")
    assert r.status_code == 404 and r.json()["error"]["code"] == "request_not_found"


async def test_after_photo_keeps_location_and_accuracy(world, client_factory, sessionmaker):
    from sqlalchemy import select

    from app.models import ActFile
    from app.models.enums import FileKind
    gps, driver = await _ready(world, client_factory)
    rid = world["requests"][0]
    await assign(gps, rid, world["vehicles"]["v1"])
    await driver.post(f"/api/v1/driver/requests/{rid}/enroute")
    assert (await upload(driver, rid, "before", NEAR)).status_code == 200
    r = await upload(driver, rid, "after", {**NEAR, "accuracy": 7.6})
    assert r.status_code == 200 and r.json()["accuracy_m"] == 8 and r.json()["lat"] == NEAR["lat"]
    async with sessionmaker() as s:
        row = (await s.execute(select(ActFile).where(ActFile.request_id == rid, ActFile.kind == FileKind.after))).scalar_one()
        assert (row.lat, row.lng, row.accuracy_m) == (NEAR["lat"], NEAR["lng"], 8)
