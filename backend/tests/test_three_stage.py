"""PR #12: uch bosqich (qizil → sariq → yashil), korxona maxsus raqami, ish jadvali, buyurtma varaqasi va uning himoyasi."""
import re
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.models import Customer, SituationEvent
from app.services import order_forms, schedule
from tests.conftest import PNG
from tests.helpers import assign, NEAR, fill_act, schedule_driver

CODE = "KD7HX2M"


@pytest.fixture
def fixed_code(monkeypatch):
    codes = iter([CODE, "PRT2345", "ZZZ9999", "YYY8888", "XXX7777"])
    monkeypatch.setattr(order_forms, "new_code", lambda: next(codes))


async def _assigned(world, client_factory):
    gps, driver = await client_factory("gps"), await client_factory("driver")
    await schedule_driver(gps, driver, world["users"]["driver"], world["vehicles"]["v1"])
    rid = world["requests"][0]
    r = await assign(gps, rid, world["vehicles"]["v1"], confirm=False)
    assert r.status_code == 200, r.text
    return gps, driver, rid, r.json()


async def test_customer_code_format_unique_and_searchable(world, client_factory, sessionmaker):
    legal = await client_factory("legal")
    async with sessionmaker() as s:
        codes = [c for (c,) in (await s.execute(select(Customer.code))).all()]
    assert all(re.fullmatch(r"[A-HJ-NPR-Z]{3}\d{2}", c) for c in codes)
    ids = []
    for i in range(30):
        r = await legal.post("/api/v1/customers", json={"name": f"Maktab {i}", "district_id": world["districts"]["a"], "stir": f"2010001{i:02d}"})
        assert r.status_code == 201, r.text
        ids.append(r.json()["code"])
    assert len(set(ids)) == 30
    found = (await legal.get("/api/v1/customers", params={"q": ids[7].lower()})).json()["items"]
    assert [c["name"] for c in found] == ["Maktab 7"]


async def test_schedule_validation_copy_and_vehicle_options(world, client_factory, sessionmaker):
    gps = await client_factory("gps")
    a, v1, v2, vb = world["districts"]["a"], world["vehicles"]["v1"], world["vehicles"]["v2"], world["vehicles"]["vb"]
    d1, d2 = world["users"]["driver"], world["users"]["driver2"]
    put = lambda rows, **p: gps.put("/api/v1/gps/schedule", json={"rows": rows}, params=p)  # noqa: E731
    assert (await put([{"vehicle_id": vb, "driver_id": d1}])).json()["error"]["code"] == "bad_vehicle"
    assert (await put([{"vehicle_id": v1, "driver_id": world["users"]["driver_b"]}])).json()["error"]["code"] == "bad_driver"
    assert (await put([{"vehicle_id": v1, "driver_id": d1}, {"vehicle_id": v2, "driver_id": d1}])).json()["error"]["code"] == "driver_twice"
    yesterday = schedule.today() - timedelta(days=1)
    r = await put([{"vehicle_id": v1, "driver_id": d1, "service": "individual", "mahallas": "Bog'bon"},
                   {"vehicle_id": v2, "driver_id": d2, "service": "legal"}], day=str(yesterday))
    assert r.status_code == 200 and len(r.json()) == 2
    assert (await gps.get("/api/v1/gps/schedule")).json()["rows"] == []
    rows = (await gps.post("/api/v1/gps/schedule/copy", params={"from_day": str(yesterday)})).json()
    assert {(x["plate"], x["service"]) for x in rows} == {("60 101 AB", "individual"), ("60 102 AB", "legal")}
    # Joylashuv: v1 korxonaga yaqin, lekin jismoniy abonentlar uchun → yuridik (v2) baribir yuqorida
    from app.services.schedule import set_position
    async with sessionmaker() as s:
        await set_position(s, v1, 40.6420, 72.2395, None, "monitoring")
        await s.commit()
    opts = (await gps.get(f"/api/v1/gps/requests/{world['requests'][0]}/vehicles")).json()
    assert [(o["plate"], o["service"]) for o in opts["items"]] == [("60 102 AB", "legal"), ("60 101 AB", "individual")]
    assert opts["items"][0]["distance_m"] is None and 0 < opts["items"][1]["distance_m"] < 200
    assert opts["items"][0]["driver_name"] == "Haydovchi A2" and opts["items"][0]["available"]


async def test_integration_api_key(world, client_factory, monkeypatch):
    from app.core.config import get_settings
    c = await client_factory()
    body = {"positions": [{"plate": "60101AB", "lat": 40.64, "lng": 72.24}, {"plate": "XX 000", "lat": 40.6, "lng": 72.2}]}
    assert (await c.post("/api/v1/integrations/vehicle-positions", json=body, headers={"X-Api-Key": "k"})).status_code == 503
    monkeypatch.setattr(get_settings(), "integration_api_key", "secret-key")
    assert (await c.post("/api/v1/integrations/vehicle-positions", json=body, headers={"X-Api-Key": "nope"})).status_code == 401
    r = await c.post("/api/v1/integrations/vehicle-positions", json=body, headers={"X-Api-Key": "secret-key", "X-Requested-With": ""})
    assert r.status_code == 200 and r.json() == {"saved": 1, "unknown": ["XX 000"]}
    r = await c.get("/api/v1/integrations/schedule", params={"district_id": world["districts"]["a"]}, headers={"X-Api-Key": "secret-key"})
    assert r.status_code == 200 and r.json() == []


async def test_assign_creates_order_form_without_exposing_code(world, client_factory, fixed_code):
    gps, driver, rid, req = await _assigned(world, client_factory)
    # Varaqa printerdan chiqmaguncha — qizil (printing), haydovchiga vazifa ko'rinmaydi
    assert req["status"] == "printing" and req["stage"] == "red" and req["vehicle"]["plate"] == "60 101 AB" and req["driver_name"] == "Haydovchi A"
    assert rid in [x["id"] for x in (await gps.get("/api/v1/gps/requests")).json()]
    assert (await driver.get("/api/v1/driver/tasks")).json() == [] or rid not in [x["id"] for x in (await driver.get("/api/v1/driver/tasks")).json()]
    form = req["order_form"]
    assert re.fullmatch(r"\d{7}", form["number"]) and not form["printed"]
    assert (await gps.post(f"/api/v1/order-forms/{form['id']}/confirm-print")).json()["error"]["code"] == "not_printed"
    paper = await gps.get(f"/api/v1/order-forms/{form['id']}")
    assert paper.status_code == 200 and paper.json()["customer"]["code"] == world["customer"].code
    pdf = await gps.post(f"/api/v1/order-forms/{form['id']}/print")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["cache-control"] == "no-store"
    # Printer xato bersa — tasdiqgacha o'sha raqam bilan qayta chop etiladi (manager ruxsatisiz)
    assert (await gps.post(f"/api/v1/order-forms/{form['id']}/print")).status_code == 200
    r = (await gps.post(f"/api/v1/order-forms/{form['id']}/confirm-print")).json()
    assert r["status"] == "assigned" and r["form"]["number"] == form["number"] and r["form"]["print_confirm_via"] == "manual"
    assert rid not in [x["id"] for x in (await gps.get("/api/v1/gps/requests")).json()]
    assert rid in [x["id"] for x in (await driver.get("/api/v1/driver/tasks")).json()]
    assert (await gps.post(f"/api/v1/order-forms/{form['id']}/confirm-print")).json()["error"]["code"] == "not_printing"
    # Kod yoki uning xeshi hech bir JSON javobida yo'q
    legal, admin = await client_factory("legal"), await client_factory("admin")
    for c, url in ((gps, f"/api/v1/order-forms/{form['id']}"), (legal, f"/api/v1/requests/{rid}"), (admin, "/api/v1/requests"),
                   (driver, "/api/v1/driver/tasks"), (gps, "/api/v1/gps/requests")):
        text = (await c.get(url)).text
        assert CODE not in text and order_forms.hash_code(CODE) not in text and "code_hash" not in text
    # Faqat GPS (orders.print) chop etadi; qayta — manager ruxsati bilan
    assert (await legal.post(f"/api/v1/order-forms/{form['id']}/print")).status_code == 403
    assert (await gps.post(f"/api/v1/order-forms/{form['id']}/print")).json()["error"]["code"] == "already_printed"
    manager = await client_factory("manager")
    assert (await manager.post(f"/api/v1/order-forms/{form['id']}/allow-reprint")).json()["reprint_allowed"]
    assert (await gps.post(f"/api/v1/order-forms/{form['id']}/print")).status_code == 200  # yangi kod
    assert (await gps.post(f"/api/v1/order-forms/{form['id']}/print")).json()["error"]["code"] == "already_printed"


async def test_legal_closes_with_scan_code_volume_and_type(world, client_factory, sessionmaker, fixed_code):
    gps, driver, rid, req = await _assigned(world, client_factory)
    fid = req["order_form"]["id"]
    legal, manager = await client_factory("legal"), await client_factory("manager")
    assert (await legal.post(f"/api/v1/order-forms/{fid}/verify", json={"code": CODE})).json()["error"]["code"] == "not_printed"
    await gps.post(f"/api/v1/order-forms/{fid}/print")
    await gps.post(f"/api/v1/order-forms/{fid}/confirm-print")
    # Sariq ro'yxatda: maxsus raqam va varaqa raqami bo'yicha topiladi
    for q in (world["customer"].code, req["order_form"]["number"]):
        items = (await legal.get("/api/v1/requests", params={"stage": "yellow", "q": q})).json()["items"]
        assert [i["id"] for i in items] == [rid]
    assert (await legal.post(f"/api/v1/order-forms/{fid}/verify", json={"code": CODE})).json()["error"]["code"] == "scan_required"
    r = await legal.post(f"/api/v1/order-forms/{fid}/scan", files={"file": ("scan.png", PNG, "image/png")})
    assert r.status_code == 200 and r.json()["has_scan"]
    assert (await legal.post(f"/api/v1/order-forms/{fid}/scan", files={"file": ("x.txt", b"hi", "text/plain")})).status_code == 422
    assert (await legal.post(f"/api/v1/order-forms/{fid}/close", json={"volume_m3": 5, "waste_kind": "solid"})).json()["error"]["code"] == "code_required"
    # Noto'g'ri kod: 3 urinish, keyin blok + Vaziyat
    r = await legal.post(f"/api/v1/order-forms/{fid}/verify", json={"code": "AAAAAAA"})
    assert r.status_code == 422 and r.json()["error"]["details"]["attempts_left"] == 2
    await legal.post(f"/api/v1/order-forms/{fid}/verify", json={"code": "BBBBBBB"})
    r = await legal.post(f"/api/v1/order-forms/{fid}/verify", json={"code": "CCCCCCC"})
    assert r.status_code == 423 and r.json()["error"]["code"] == "order_locked"
    assert (await legal.post(f"/api/v1/order-forms/{fid}/verify", json={"code": CODE})).status_code == 423  # to'g'ri kod ham
    async with sessionmaker() as s:
        assert (await s.execute(select(SituationEvent).where(SituationEvent.kind == "order_locked"))).scalar_one()
    assert (await legal.post(f"/api/v1/order-forms/{fid}/unlock")).status_code == 403
    assert not (await manager.post(f"/api/v1/order-forms/{fid}/unlock")).json()["locked"]
    # To'g'ri kod (kichik harf va bo'sh joy bilan ham) — forma avtomatik to'ladi
    r = await legal.post(f"/api/v1/order-forms/{fid}/verify", json={"code": "kd7 hx2m"})
    assert r.status_code == 200, r.text
    auto = r.json()
    assert auto["vehicle"]["plate"] == "60 101 AB" and auto["driver_name"] == "Haydovchi A" and auto["customer"]["code"]
    # Kub va tur majburiy
    assert (await legal.post(f"/api/v1/order-forms/{fid}/close", json={"volume_m3": 5})).status_code == 422
    assert (await legal.post(f"/api/v1/order-forms/{fid}/close", json={"volume_m3": 0, "waste_kind": "solid"})).status_code == 422
    assert (await gps.post(f"/api/v1/order-forms/{fid}/close", json={"volume_m3": 5, "waste_kind": "solid"})).status_code == 403
    r = await legal.post(f"/api/v1/order-forms/{fid}/close", json={"volume_m3": 7.5, "waste_kind": "liquid"})
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["stage"] == "green" and done["status"] == "done" and done["order_form"]["closed_via"] == "form"
    assert done["order_form"]["volume_m3"] == 7.5 and done["order_form"]["waste_kind"] == "liquid"
    assert [x["id"] for x in (await driver.get("/api/v1/driver/done")).json()] == [rid]
    assert (await driver.get("/api/v1/driver/tasks")).json() == []
    assert [x["id"] for x in (await legal.get("/api/v1/requests", params={"stage": "green"})).json()["items"]] == [rid]
    assert (await legal.post(f"/api/v1/order-forms/{fid}/close", json={"volume_m3": 1, "waste_kind": "solid"})).json()["error"]["code"] == "order_closed"
    scan = await legal.get(f"/api/v1/order-forms/{fid}/scan")
    assert scan.status_code == 200 and scan.content == PNG


async def test_tablet_act_turns_green_and_closes_form(world, client_factory):
    gps, driver, rid, req = await _assigned(world, client_factory)
    await gps.post(f"/api/v1/order-forms/{req['order_form']['id']}/print")
    await gps.post(f"/api/v1/order-forms/{req['order_form']['id']}/confirm-print")
    await driver.post(f"/api/v1/driver/requests/{rid}/enroute")
    await fill_act(driver, rid, NEAR)
    r = await driver.post(f"/api/v1/driver/requests/{rid}/complete",
                          json={"containers": 2, "volume_m3": 4, "note": "ok", **NEAR})
    assert r.status_code == 200, r.text
    assert r.json()["request"]["stage"] == "green" and r.json()["act"]["vehicle_plate"] == "60 101 AB"
    legal = await client_factory("legal")
    item = (await legal.get(f"/api/v1/requests/{rid}")).json()
    assert item["order_form"]["closed_via"] == "act" and item["stage"] == "green"
    # Haydovchi plansheti joylashuvi jadvaldagi mashinaga yoziladi
    assert (await driver.post("/api/v1/driver/location", json=NEAR)).status_code == 204
    today = (await driver.get("/api/v1/driver/today")).json()
    assert today["vehicle"]["plate"] == "60 101 AB" and today["service"] == "legal"


async def test_print_confirm_requires_agent_when_manual_mode_off(world, client_factory, sessionmaker):
    from sqlalchemy import update
    from app.models import District
    async with sessionmaker() as s:
        await s.execute(update(District).where(District.id == world["districts"]["a"]).values(print_manual_confirm=False))
        await s.commit()
    gps, driver, rid, req = await _assigned(world, client_factory)
    fid = req["order_form"]["id"]
    await gps.post(f"/api/v1/order-forms/{fid}/print")
    r = await gps.post(f"/api/v1/order-forms/{fid}/confirm-print")
    assert r.status_code == 403
    # Qayta biriktirish urinishi — o'sha murojaat (printing) yangi varaqa yaratmaydi
    assert (await gps.post(f"/api/v1/gps/requests/{rid}/assign", json={"vehicle_id": world["vehicles"]["v1"]})).status_code == 409
