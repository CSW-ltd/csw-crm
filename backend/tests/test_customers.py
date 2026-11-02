from datetime import date, timedelta

from sqlalchemy import func, select

from app.models import Customer, ImportBatch, Request
from app.models.enums import WasteType
from tests.helpers import assign, FAR, NEAR, fill_act, schedule_driver
from tests.xlsx_factory import build

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ACT = {"containers": 2, "volume_m3": 4, "note": "Olib ketildi"}


async def _import(client, dry_run: bool, content: bytes | None = None, name: str = "call-center.xlsx"):
    return await client.post(f"/api/v1/admin/import/customers?dry_run={str(dry_run).lower()}",
                             files={"file": (name, content or build(), XLSX)})


async def _count(sessionmaker, model) -> int:
    async with sessionmaker() as s:
        return (await s.execute(select(func.count()).select_from(model))).scalar_one()


async def test_dry_run_reports_and_writes_nothing(world, client_factory, sessionmaker):
    admin = await client_factory("admin")
    r = await _import(admin, dry_run=True)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["sheet"] == "Рес бўйича" and b["dry_run"] is True and b["batch_id"] is None
    assert (b["rows_total"], b["rows_ok"], b["rows_skipped"], b["septic_rows"]) == (6, 5, 1, 1)
    # «Янги Бозор» va "Янги бозор" — bitta korxona; "Асака Авто" bazada bor
    assert (b["customers_new"], b["customers_existing"], b["contacts_added"]) == (3, 1, 4)
    assert b["by_district"] == {"Asaka tumani": 3, "Termiz shahri": 1}
    messages = [e["message"] for e in b["errors"]]
    assert any("Tuman topilmadi" in m and "Ангор" in m for m in messages)
    assert any("Telefon" in m and "12345" in m for m in messages)
    assert await _count(sessionmaker, Customer) == 1 and await _count(sessionmaker, ImportBatch) == 0


async def test_import_then_reimport_is_idempotent(world, client_factory, sessionmaker):
    admin = await client_factory("admin")
    b = (await _import(admin, dry_run=False)).json()
    assert b["batch_id"] and b["customers_new"] == 3 and b["contacts_added"] == 4
    assert await _count(sessionmaker, Customer) == 4

    page = (await admin.get("/api/v1/customers", params={"q": "янги бозор"})).json()
    assert page["total"] == 1
    c = page["items"][0]
    assert c["source"] == "excel" and c["location_status"] == "none" and c["stir"] is None and c["lat"] is None
    assert c["fixed_no"].startswith("A-") and c["fixed_no"] != "A-0101" and c["contacts_count"] == 2
    assert c["missing_fields"] == ["contract"] and len(c["code"]) == 5  # STIR o'rniga maxsus raqam
    detail = (await admin.get(f"/api/v1/customers/{c['id']}")).json()
    assert {x["phone"] for x in detail["contacts"]} == {"+998 94 512-11-16", "+998 90 555-11-22"}

    again = (await _import(admin, dry_run=False)).json()
    assert (again["customers_new"], again["customers_existing"], again["contacts_added"]) == (0, 4, 0)
    assert await _count(sessionmaker, Customer) == 4
    batches = (await admin.get("/api/v1/admin/import/batches")).json()
    assert len(batches) == 2 and batches[0]["customers_merged"] == 4


async def test_import_validation_and_permissions(world, client_factory):
    admin, manager = await client_factory("admin"), await client_factory("manager")
    assert (await _import(manager, dry_run=True)).status_code == 403
    r = await _import(admin, dry_run=True, content=b"not an excel")
    assert r.json()["error"]["code"] == "bad_file"
    r = await _import(admin, dry_run=True, name="data.txt")
    assert r.json()["error"]["code"] == "unsupported_format"
    r = await _import(admin, dry_run=True, content=build(rows=[], header=["A", "B", "C"]))
    assert r.json()["error"]["code"] == "no_sheet"


async def test_search_filters_and_district_scope(world, client_factory):
    admin, gps = await client_factory("admin"), await client_factory("gps")
    await _import(admin, dry_run=False)
    assert (await admin.get("/api/v1/customers", params={"incomplete": "true"})).json()["total"] == 3
    assert (await admin.get("/api/v1/customers", params={"location": "none"})).json()["total"] == 3
    assert (await admin.get("/api/v1/customers", params={"q": "90 555 11 22"})).json()["total"] == 1
    assert (await admin.get("/api/v1/customers", params={"q": "305123456"})).json()["total"] == 1
    # GPS xodimi (Asaka) Termiz korxonalarini ko'rmaydi
    assert (await gps.get("/api/v1/customers", params={"district_id": world["districts"]["b"]})).json()["total"] == 0
    page = (await gps.get("/api/v1/customers")).json()
    assert page["total"] == 3 and all(i["district_id"] == world["districts"]["a"] for i in page["items"])
    termiz = (await admin.get("/api/v1/customers", params={"district_id": world["districts"]["b"]})).json()["items"][0]
    assert (await gps.get(f"/api/v1/customers/{termiz['id']}")).status_code == 403


async def test_card_editing_rules(world, client_factory):
    legal, manager = await client_factory("legal"), await client_factory("manager")
    da = world["districts"]["a"]
    r = await legal.post("/api/v1/customers", json={"name": "Yangi Mijoz", "district_id": da, "phone": "94 000 00 01"})
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["phone"] == "+998 94 000-00-01" and c["source"] == "manual"
    r = await legal.post("/api/v1/customers", json={"name": "ЯНГИ МИЖОЗ", "district_id": da})
    assert r.json()["error"]["code"] == "customer_exists"
    # STIR takrorlanmaydi: "STIRni xato kiritdingiz" + qaysi korxonaga tegishli
    r = await legal.patch(f"/api/v1/customers/{c['id']}", json={"stir": "305123456"})
    err = r.json()["error"]
    assert r.status_code == 409 and err["code"] == "stir_taken" and "xato kiritdingiz" in err["message"]
    assert err["details"]["customer_id"] == world["customer"].id
    r = await legal.patch(f"/api/v1/customers/{c['id']}", json={"stir": "12345"})
    assert r.status_code == 422
    assert (await manager.patch(f"/api/v1/customers/{c['id']}", json={"director": "X"})).status_code == 403
    assert (await legal.post(f"/api/v1/customers/{c['id']}/location/confirm", json={})).status_code == 403
    r = await manager.post(f"/api/v1/customers/{c['id']}/location/confirm", json={})
    assert r.json()["error"]["code"] == "no_location"
    r = await legal.post(f"/api/v1/customers/{c['id']}/contacts", json={"name": "Hisobchi", "phone": "123"})
    assert r.json()["error"]["code"] == "bad_phone"
    r = await legal.post(f"/api/v1/customers/{c['id']}/contacts", json={"name": "Hisobchi", "phone": "+998940000002"})
    assert r.status_code == 201 and len(r.json()["contacts"]) == 1
    ct = {"number": "SH-2026/0001", "type": "monthly", "valid_from": str(date.today()), "valid_to": str(date.today())}
    assert (await legal.post(f"/api/v1/customers/{c['id']}/contracts", json=ct)).json()["error"]["code"] == "contract_number_taken"
    bad = {**ct, "number": "SH-X", "valid_to": str(date.today() - timedelta(days=1))}
    assert (await legal.post(f"/api/v1/customers/{c['id']}/contracts", json=bad)).json()["error"]["code"] == "bad_dates"


async def _new_request(sessionmaker, customer_id: int, district_id: int, waste=WasteType.household) -> int:
    async with sessionmaker() as s:
        r = Request(customer_id=customer_id, district_id=district_id, waste_type=waste)
        s.add(r); await s.flush(); r.number = f"M-{r.id:06d}"
        await s.commit()
        return r.id


async def test_incomplete_customer_blocks_assignment_then_first_visit_flow(world, client_factory, sessionmaker):
    admin, legal, manager = await client_factory("admin"), await client_factory("legal"), await client_factory("manager")
    gps, driver = await client_factory("gps"), await client_factory("driver")
    await _import(admin, dry_run=False)
    cust = (await admin.get("/api/v1/customers", params={"q": "Боғ"})).json()["items"][0]
    rid = await _new_request(sessionmaker, cust["id"], world["districts"]["a"], WasteType.septic)
    await schedule_driver(gps, driver, world["users"]["driver"], world["vehicles"]["v1"])

    # Shartnomasiz — GPS ro'yxatida ko'rinmaydi
    assert rid not in [r["id"] for r in (await gps.get("/api/v1/gps/requests")).json()]
    r = await assign(gps, rid, world["vehicles"]["v1"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "customer_incomplete"

    # Yuridik bo'lim shartnomani kiritadi (STIR shart emas)
    expired = {"number": "SH-OLD", "type": "per_trip", "valid_from": "2025-01-01", "valid_to": "2025-12-31"}
    await legal.post(f"/api/v1/customers/{cust['id']}/contracts", json=expired)
    assert (await assign(gps, rid, world["vehicles"]["v1"])).status_code == 409
    ct = {"number": "SH-NEW", "type": "per_trip", "valid_from": str(date.today()), "valid_to": str(date.today() + timedelta(days=90))}
    card = (await legal.post(f"/api/v1/customers/{cust['id']}/contracts", json=ct)).json()
    assert card["missing_fields"] == [] and len(card["contracts"]) == 2
    listed = next(r for r in (await gps.get("/api/v1/gps/requests")).json() if r["id"] == rid)
    assert listed["waste_type"] == "septic"
    r = await assign(gps, rid, world["vehicles"]["v1"])
    assert r.status_code == 200, r.text
    assert r.json()["contract"]["number"] == "SH-NEW"

    # Birinchi tashrif: koordinata yo'q → radius tekshirilmaydi, nuqta Manager tasdiqiga
    await driver.post(f"/api/v1/driver/requests/{rid}/enroute")
    await fill_act(driver, rid, FAR)
    body = (await driver.post(f"/api/v1/driver/requests/{rid}/complete", json={**ACT, **FAR})).json()
    assert body["request"]["status"] == "done"
    assert body["act"]["in_radius"] is None and body["act"]["distance_m"] is None
    card = (await manager.get(f"/api/v1/customers/{cust['id']}")).json()
    assert card["location_status"] == "pending" and card["lat"] == FAR["lat"]
    assert (await manager.get("/api/v1/customers", params={"location": "pending"})).json()["total"] == 1

    card = (await manager.post(f"/api/v1/customers/{cust['id']}/location/confirm", json={})).json()
    assert card["location_status"] == "confirmed"

    # Keyingi tashrif tasdiqlangan nuqta bo'yicha tekshiriladi: NEAR undan ~750 m uzoqda
    rid2 = await _new_request(sessionmaker, cust["id"], world["districts"]["a"])
    await assign(gps, rid2, world["vehicles"]["v1"])
    await driver.post(f"/api/v1/driver/requests/{rid2}/enroute")
    await fill_act(driver, rid2, NEAR)
    body = (await driver.post(f"/api/v1/driver/requests/{rid2}/complete", json={**ACT, **NEAR})).json()
    assert body["request"]["status"] == "suspect" and body["act"]["in_radius"] is False


async def test_manager_can_set_location_manually(world, client_factory):
    legal, manager = await client_factory("legal"), await client_factory("manager")
    c = (await legal.post("/api/v1/customers", json={"name": "Qo'lda", "district_id": world["districts"]["a"]})).json()
    r = await manager.post(f"/api/v1/customers/{c['id']}/location/confirm", json={"lat": 40.65})
    assert r.json()["error"]["code"] == "bad_coords"
    card = (await manager.post(f"/api/v1/customers/{c['id']}/location/confirm", json={"lat": 40.65, "lng": 72.24})).json()
    assert card["location_status"] == "confirmed" and card["lat"] == 40.65
