"""Shartnomada obyekt koordinatasi (majburiy): tekshiruv, «kutilmoqda» (legal), haydovchi tashrifida avtomatik tasdiq yoki ogohlantirish."""
from sqlalchemy import select, update

from app.models import Customer, SituationEvent
from app.models.enums import LocationStatus
from tests.helpers import FAR, NEAR, assign, fill_act
from tests.test_contracts import REQ, body
from tests.test_driver_flow import ACT, _ready


async def _new_cust(legal, world) -> int:
    r = await legal.post("/api/v1/customers", json={"name": "Koordinata MChJ", "district_id": world["districts"]["a"]})
    return r.json()["id"]


def _codes(r) -> set:
    return {(e["field"], e["code"]) for e in r.json()["errors"]}


async def test_coords_required_and_validated(world, client_factory):
    legal = await client_factory("legal")
    cid = await _new_cust(legal, world)
    no = {k: v for k, v in REQ.items() if k not in ("lat", "lng")}
    assert ("coords", "required") in _codes(await legal.post("/api/v1/contracts/check", json=body(cid, requisites=no)))
    swapped = {**REQ, "lat": 72.2390, "lng": 40.6415}
    assert ("coords", "swapped") in _codes(await legal.post("/api/v1/contracts/check", json=body(cid, requisites=swapped)))
    far = {**REQ, "lat": 25.20, "lng": 55.27}  # Dubay
    assert ("coords", "out_of_uz") in _codes(await legal.post("/api/v1/contracts/check", json=body(cid, requisites=far)))
    ok = await legal.post("/api/v1/contracts/check", json=body(cid))
    assert not any(e["field"] == "coords" for e in ok.json()["errors"])


async def test_existing_contract_sets_pending_legal(world, client_factory, sessionmaker):
    legal = await client_factory("legal")
    cid = await _new_cust(legal, world)
    meta = {"number": "KOORD-1", "signed_on": "2026-01-10"}
    b = body(cid, price=84000, price_reason="Eski shartnoma narxi", valid_from="2026-01-10", valid_to="2026-12-31", sign_method="paper", existing=meta,
             requisites={**REQ, "stir": "309111333", "lat": 40.65, "lng": 72.25})
    r = await legal.post("/api/v1/contracts/existing", json=b)
    assert r.status_code in (200, 201), r.text
    assert r.json()["customer"]["location_status"] == "pending"
    async with sessionmaker() as s:
        c = await s.get(Customer, cid)
        assert (c.lat, c.lng, c.location_status, c.location_source) == (40.65, 72.25, LocationStatus.pending, "legal")


async def _set_legal_point(sessionmaker, world, lat, lng):
    async with sessionmaker() as s:
        await s.execute(update(Customer).where(Customer.id == world["customer"].id)
                        .values(lat=lat, lng=lng, location_status=LocationStatus.pending, location_source="legal"))
        await s.commit()


async def _visit(world, client_factory, coords):
    gps, driver = await _ready(world, client_factory)
    rid = world["requests"][0]
    await assign(gps, rid, world["vehicles"]["v1"])
    await driver.post(f"/api/v1/driver/requests/{rid}/enroute")
    await fill_act(driver, rid, coords)
    return (await driver.post(f"/api/v1/driver/requests/{rid}/complete", json={**ACT, **coords})).json()


async def test_driver_visit_inside_radius_confirms_legal_point(world, client_factory, sessionmaker):
    await _set_legal_point(sessionmaker, world, 40.6415, 72.2390)
    body_ = await _visit(world, client_factory, NEAR)
    assert body_["request"]["status"] == "done"
    async with sessionmaker() as s:
        c = await s.get(Customer, world["customer"].id)
        assert c.location_status == LocationStatus.confirmed and (c.lat, c.lng) == (40.6415, 72.2390)
        kinds = set((await s.execute(select(SituationEvent.kind))).scalars())
        assert "act_location_confirmed" in kinds and "location_mismatch" not in kinds


async def test_driver_visit_outside_radius_warns_not_suspect(world, client_factory, sessionmaker):
    await _set_legal_point(sessionmaker, world, 40.6415, 72.2390)
    body_ = await _visit(world, client_factory, FAR)
    assert body_["request"]["status"] == "done"  # tasdiqlanmagan nuqta — «Shubhali» emas
    assert body_["act"]["in_radius"] is None and body_["act"]["distance_m"] > 300
    async with sessionmaker() as s:
        c = await s.get(Customer, world["customer"].id)
        assert c.location_status == LocationStatus.pending  # manager hal qiladi
        ev = (await s.execute(select(SituationEvent).where(SituationEvent.kind == "location_mismatch"))).scalar_one()
        assert ev.level.value == "warning" and "mos kelmadi" in ev.message


async def test_unchanged_confirmed_point_stays_confirmed(world, client_factory, sessionmaker):
    """World korxonasi tasdiqlangan (40.6415, 72.2390) — REQ'dagi bir xil nuqta bilan shartnoma maqomni o'zgartirmaydi."""
    from app.services.contracts import _apply_location
    async with sessionmaker() as s:
        c = await s.get(Customer, world["customer"].id)
        _apply_location(c, 40.6415, 72.2390)
        assert c.location_status == LocationStatus.confirmed
        _apply_location(c, 40.7, 72.3)
        assert (c.location_status, c.location_source) == (LocationStatus.pending, "legal")


async def test_manager_confirm_sets_source(world, client_factory, sessionmaker):
    await _set_legal_point(sessionmaker, world, 40.6415, 72.2390)
    from tests.test_permissions import _manager_a
    admin = await client_factory("admin")
    _, mgr = await _manager_a(world, client_factory, admin, ["customers.location_confirm"])
    r = await mgr.post(f"/api/v1/customers/{world['customer'].id}/location/confirm", json={})
    assert r.status_code == 200, r.text
    assert r.json()["location_status"] == "confirmed" and r.json()["location_source"] == "manager"
