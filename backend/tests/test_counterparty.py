"""Korxona = shartnoma kontragenti: STIR bo'yicha qidiruv, rekvizitlardan korxona, yangi korxona murojaatidan shartnoma."""
from datetime import timedelta

from sqlalchemy import select

from app.models import Appeal, Customer
from tests.test_contracts import REQ, T, body, tariffs  # noqa: F401 — tariffs: autouse fixture (84 000 so'm/m³)

STIR = "309555777"


async def test_lookup_unknown_stir(world, client_factory):
    legal = await client_factory("legal")
    r = await legal.get("/api/v1/contracts/lookup", params={"stir": STIR})
    assert r.status_code == 200 and r.json() == {"customer": None, "active_contract": None}
    assert (await legal.get("/api/v1/contracts/lookup", params={"stir": "12345"})).status_code == 422


async def test_counterparty_creates_once(world, client_factory, sessionmaker):
    legal = await client_factory("legal")
    a = world["districts"]["a"]
    r = await legal.post("/api/v1/contracts/counterparty", json={"stir": STIR, "name": "Kontragent MChJ", "district_id": a})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    again = await legal.post("/api/v1/contracts/counterparty", json={"stir": STIR, "name": "Boshqa nom", "district_id": a})
    assert again.json()["id"] == cid  # STIR bazada — o'sha korxona, takror yaratilmaydi
    async with sessionmaker() as s:
        c = await s.get(Customer, cid)
        assert c.stir == STIR and c.lat is None and c.location_status.value == "none"
    lk = (await legal.get("/api/v1/contracts/lookup", params={"stir": STIR})).json()
    assert lk["customer"]["id"] == cid and lk["active_contract"] is None


async def test_lookup_reports_active_contract(world, client_factory):
    legal = await client_factory("legal")
    cid = world["customer"].id  # world: amaldagi shartnomasi bor (bugun ichida)
    stir = "305123456"  # world mijozining STIR'i
    lk = (await legal.get("/api/v1/contracts/lookup", params={"stir": stir})).json()
    assert lk["customer"]["id"] == cid
    assert lk["active_contract"] is not None and lk["active_contract"]["valid_to"] >= str(T)


async def test_appeal_to_contract_closes_on_number(world, client_factory, sessionmaker):
    op, legal = await client_factory("operator"), await client_factory("legal")
    a = world["districts"]["a"]
    ap = (await op.post("/api/v1/appeals/new-company", json={"phone": "94 512 11 16", "stir": STIR, "contact_name": "Karimov Anvar",
                                                            "district_id": a})).json()
    cust = (await legal.post("/api/v1/contracts/counterparty", json={"stir": STIR, "name": "Murojaat MChJ", "district_id": a,
                                                                     "phone": "94 512 11 16"})).json()
    ct = await legal.post("/api/v1/contracts/start", json={"customer_id": cust["id"], "appeal_id": ap["id"]})
    assert ct.status_code == 201, ct.text
    ct = ct.json()
    async with sessionmaker() as s:
        row = await s.get(Appeal, ap["id"])
        assert row.contract_id == ct["id"] and row.status.value == "new"  # hali raqamsiz loyiha
    req = {**REQ, "stir": STIR, "name": "Murojaat MChJ"}
    r = await legal.put(f"/api/v1/contracts/{ct['id']}", json=body(cust["id"], requisites=req))
    assert r.status_code == 200, r.text
    assert r.json()["number"]
    async with sessionmaker() as s:
        row = await s.get(Appeal, ap["id"])
        assert row.status.value == "accepted" and row.customer_id == cust["id"]
    # Yopilgan murojaatdan yana shartnoma boshlab bo'lmaydi
    again = await legal.post("/api/v1/contracts/start", json={"customer_id": cust["id"], "appeal_id": ap["id"]})
    assert again.status_code == 409 and again.json()["error"]["code"] == "appeal_not_new"


async def test_contract_without_coords_ok(world, client_factory):
    legal = await client_factory("legal")
    a = world["districts"]["a"]
    cust = (await legal.post("/api/v1/contracts/counterparty", json={"stir": STIR, "name": "Nuqtasiz MChJ", "district_id": a})).json()
    req = {k: v for k, v in REQ.items() if k not in ("lat", "lng")} | {"stir": STIR, "name": "Nuqtasiz MChJ"}
    r = await legal.post("/api/v1/contracts", json=body(cust["id"], requisites=req))
    assert r.status_code == 201, r.text
    assert r.json()["customer"]["location_status"] == "none"
