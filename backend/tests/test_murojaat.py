"""PR #13: operatorning yangi korxonasi (maxsus raqam + SMS), STIR xatosi, shartnomasiz murojaat GPS'ga ko'rinmaydi,
qora bosqich, 12/72/144 soatlik hisoblar, M- raqamlar, GPS socket xonasi."""
import asyncio
from datetime import date, timedelta

from sqlalchemy import select, update

from app.db.base import utcnow
from app.models import Customer, CustomerContact, Request
from app.services import sms


async def test_new_company_appeal_creates_no_customer(world, client_factory, sessionmaker):
    """Yangi korxona qo'ng'irog'i: korxona yaratilmaydi (korxona = shartnoma kontragenti) — murojaat legal'da shartnomani kutadi."""
    op = await client_factory("operator")
    a = world["districts"]["a"]
    sms.SENT.clear()
    body = {"phone": "94 512 11 16", "stir": "309876543", "contact_name": "Karimov Anvar"}
    r = await op.post("/api/v1/appeals/new-company", json=body)
    assert r.json()["error"]["code"] == "district_required"  # operatorda 2 ta tuman
    r = await op.post("/api/v1/appeals/new-company", json={**body, "district_id": a})
    assert r.status_code == 201, r.text
    ap = r.json()
    assert ap["number"].startswith("MR-") and ap["caller_name"] == "Karimov Anvar" and ap["status"] == "new"
    assert ap["customer_id"] is None and ap["contract_id"] is None and ap["stir"] == "309876543"
    await asyncio.sleep(0.05)
    assert not sms.SENT  # maxsus raqam korxona shartnomadan yaratilganda beriladi
    async with sessionmaker() as s:
        assert (await s.execute(select(Customer).where(Customer.stir == "309876543"))).scalars().all() == []


async def test_gps_hides_requests_without_contract(world, client_factory, sessionmaker):
    gps = await client_factory("gps")
    async with sessionmaker() as s:
        c = Customer(fixed_no="A-0900", name="Shartnomasiz", name_key="shartnomasiz", district_id=world["districts"]["a"])
        s.add(c); await s.flush()
        r = Request(customer_id=c.id, district_id=world["districts"]["a"]); s.add(r); await s.flush(); r.number = f"M-{r.id:06d}"
        await s.commit()
        hidden = r.id
    ids = [x["id"] for x in (await gps.get("/api/v1/gps/requests")).json()]
    assert hidden not in ids and set(world["requests"]) <= set(ids)


async def test_black_stage_and_summary(world, client_factory, sessionmaker):
    admin, gps = await client_factory("admin"), await client_factory("gps")
    r1, r2, r3 = world["requests"]
    async with sessionmaker() as s:
        await s.execute(update(Request).where(Request.id == r1).values(created_at=utcnow() - timedelta(hours=80)))
        await s.execute(update(Request).where(Request.id == r2).values(created_at=utcnow() - timedelta(hours=20)))
        await s.commit()
    items = {x["id"]: x["stage"] for x in (await admin.get("/api/v1/requests")).json()["items"]}
    assert items == {r1: "black", r2: "red", r3: "red"}
    assert [x["id"] for x in (await admin.get("/api/v1/requests", params={"stage": "black"})).json()["items"]] == [r1]
    s12 = (await admin.get("/api/v1/requests-summary", params={"hours": 12})).json()
    s72 = (await admin.get("/api/v1/requests-summary", params={"hours": 72})).json()
    s144 = (await admin.get("/api/v1/requests-summary", params={"hours": 144})).json()
    assert (s12["red"], s12["black"]) == (1, 0) and (s72["red"], s72["black"]) == (2, 0) and (s144["red"], s144["black"]) == (2, 1)
    assert s144["yellow"] == 0 and s144["green"] == 0
    # GPS kartasi ham qora ekanini biladi
    assert next(x for x in (await gps.get("/api/v1/gps/requests")).json() if x["id"] == r1)["stage"] == "black"


async def test_gps_socket_room_from_user(world, sessionmaker, monkeypatch):
    from app import realtime
    from app.core.security import ACCESS, create_token
    import app.db.session as session_mod
    monkeypatch.setattr(session_mod, "SessionLocal", sessionmaker)
    rooms: list[str] = []

    async def enter(sid, room):
        rooms.append(room)
    monkeypatch.setattr(realtime.sio, "enter_room", enter)
    token = create_token(world["users"]["gps"], "gps", ACCESS)
    assert await realtime.connect("sid1", {}, {"token": token}) is True
    assert f"gps:{world['districts']['a']}" in rooms
