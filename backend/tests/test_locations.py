"""Joylashuvni GPS tasdiqlaydi: geofence (circle/polygon), navbat, «Tasdiqlash»/«O'zgartirish» (izoh), legal bildirishnomasi."""
import pytest
from sqlalchemy import select, update

from app.models import Customer, Notification, SituationEvent
from app.models.enums import LocationStatus
from app.services.geo import check_visit, geofence_error, in_polygon
from tests.test_contracts import REQ, body, tariffs  # noqa: F401

SQUARE = [[40.640, 72.238], [40.640, 72.241], [40.643, 72.241], [40.643, 72.238]]
CIRCLE = {"type": "circle", "radius": 150}


def test_geofence_validation():
    assert geofence_error(None) is None and geofence_error(CIRCLE) is None
    assert geofence_error({"type": "polygon", "points": SQUARE}) is None
    assert geofence_error({"type": "circle", "radius": 5}) == "bad_radius"
    assert geofence_error({"type": "polygon", "points": SQUARE[:2]}) == "bad_polygon"
    assert geofence_error({"type": "polygon", "points": [[25.2, 55.2]] * 3}) == "bad_polygon"  # O'zbekistondan tashqarida
    assert geofence_error({"type": "star"}) == "bad_geofence"


def test_polygon_and_visit_check():
    assert in_polygon(40.6415, 72.2395, SQUARE) and not in_polygon(40.65, 72.2395, SQUARE)
    poly = {"type": "polygon", "points": SQUARE}
    assert check_visit(40.6415, 72.2395, poly, 40.6420, 72.2400, 300)[1] is True
    assert check_visit(40.6415, 72.2395, poly, 40.6450, 72.2395, 300)[1] is False  # ~390 m, poligondan tashqarida
    dist, inside, radius = check_visit(40.6415, 72.2390, CIRCLE, 40.6425, 72.2390, 300)
    assert radius == 150 and inside and dist < 150


async def _legal_contract(world, legal, stir="309777111", lat=40.6415, lng=72.2390, gf=None):
    a = world["districts"]["a"]
    cust = (await legal.post("/api/v1/contracts/counterparty", json={"stir": stir, "name": "Joy MChJ", "district_id": a})).json()
    req = {**REQ, "stir": stir, "name": "Joy MChJ", "lat": lat, "lng": lng, "geofence": gf}
    r = await legal.post("/api/v1/contracts", json=body(cust["id"], requisites=req))
    assert r.status_code == 201, r.text
    return cust["id"], r.json()


async def test_contract_geofence_validated(world, client_factory):
    legal = await client_factory("legal")
    a = world["districts"]["a"]
    cust = (await legal.post("/api/v1/contracts/counterparty", json={"stir": "309777112", "name": "Gf MChJ", "district_id": a})).json()
    bad = {**REQ, "stir": "309777112", "name": "Gf MChJ", "geofence": {"type": "circle", "radius": 1}}
    errs = (await legal.post("/api/v1/contracts/check", json=body(cust["id"], requisites=bad))).json()["errors"]
    assert {"field": "geofence", "code": "bad_radius"} in errs


async def test_gps_queue_and_confirm_unchanged(world, client_factory, sessionmaker):
    legal, gps = await client_factory("legal"), await client_factory("gps")
    cid, ct = await _legal_contract(world, legal, gf=CIRCLE)
    q = (await gps.get("/api/v1/gps/locations")).json()
    row = next(x for x in q if x["customer"]["id"] == cid)
    assert row["state"] == "pending" and row["contract"]["number"] == ct["display_number"] and row["entered_by"] == "Yurist"
    assert row["customer"]["geofence"] == CIRCLE
    # Tasdiqlash — o'zgarishsiz, izoh shart emas
    r = await gps.post(f"/api/v1/gps/locations/{cid}/confirm", json={"lat": 40.6415, "lng": 72.2390, "geofence": CIRCLE})
    assert r.status_code == 200, r.text
    assert r.json()["location_status"] == "confirmed" and r.json()["location_source"] == "gps"
    assert all(x["customer"]["id"] != cid for x in (await gps.get("/api/v1/gps/locations")).json())
    assert (await legal.get("/api/v1/notifications")).json()["unread"] == 0


async def test_gps_change_requires_comment_and_notifies_legal(world, client_factory, sessionmaker):
    legal, gps = await client_factory("legal"), await client_factory("gps")
    cid, ct = await _legal_contract(world, legal, stir="309777113", gf=CIRCLE)
    poly = {"type": "polygon", "points": SQUARE}
    r = await gps.post(f"/api/v1/gps/locations/{cid}/confirm", json={"lat": 40.6416, "lng": 72.2396, "geofence": poly})
    assert r.status_code == 422 and r.json()["error"]["code"] == "comment_required"
    r = await gps.post(f"/api/v1/gps/locations/{cid}/confirm",
                       json={"lat": 40.6416, "lng": 72.2396, "geofence": poly, "comment": "Kirish darvozasi boshqa ko'chada"})
    assert r.status_code == 200, r.text
    async with sessionmaker() as s:
        c = await s.get(Customer, cid)
        assert c.location_status == LocationStatus.confirmed and c.location_confirmed_by_id == world["users"]["gps"]
        ev = (await s.execute(select(SituationEvent).where(SituationEvent.kind == "location_changed"))).scalar_one()
        assert "GPS" in ev.message and "darvozasi" in ev.message
    n = (await legal.get("/api/v1/notifications")).json()
    assert n["unread"] == 1 and n["items"][0]["kind"] == "location_changed" and n["items"][0]["actor"] == "GPS"
    assert n["items"][0]["params"]["comment"] == "Kirish darvozasi boshqa ko'chada"
    assert (await legal.post("/api/v1/notifications/read", json={})).status_code == 204
    assert (await legal.get("/api/v1/notifications")).json()["unread"] == 0
    # Boshqa xodim bu bildirishnomani ko'rmaydi
    assert (await gps.get("/api/v1/notifications")).json()["items"] == []


async def test_missing_location_filled_by_gps(world, client_factory, sessionmaker):
    legal, gps = await client_factory("legal"), await client_factory("gps")
    a = world["districts"]["a"]
    cust = (await legal.post("/api/v1/contracts/counterparty", json={"stir": "309777114", "name": "Nuqtasiz MChJ", "district_id": a})).json()
    req = {k: v for k, v in REQ.items() if k not in ("lat", "lng")} | {"stir": "309777114", "name": "Nuqtasiz MChJ"}
    assert (await legal.post("/api/v1/contracts", json=body(cust["id"], requisites=req))).status_code == 201
    row = next(x for x in (await gps.get("/api/v1/gps/locations")).json() if x["customer"]["id"] == cust["id"])
    assert row["state"] == "missing"
    r = await gps.post(f"/api/v1/gps/locations/{cust['id']}/confirm", json={"lat": 40.64, "lng": 72.24, "geofence": CIRCLE})
    assert r.status_code == 200, r.text  # legal kiritmagan — izohsiz
    bad = await gps.post(f"/api/v1/gps/locations/{cust['id']}/confirm", json={"lat": 40.64, "lng": 72.24, "geofence": {"type": "x"}})
    assert bad.status_code == 422


async def test_location_queue_forbidden_for_operator(world, client_factory):
    op = await client_factory("operator")
    assert (await op.get("/api/v1/gps/locations")).status_code == 403
