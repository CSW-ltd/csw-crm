from tests.conftest import PNG

# Korxona koordinatasidan ~50 m va ~800 m
NEAR = {"lat": 40.6419, "lng": 72.2392}
FAR = {"lat": 40.6487, "lng": 72.2390}


async def schedule_driver(gps, driver, driver_id: int, vehicle_id: int, service: str = "legal") -> list[dict]:
    """Bugungi ish jadvaliga mashina + haydovchi qo'shadi (smena o'rniga). `driver` — moslik uchun, ishlatilmaydi."""
    rows = [{k: r[k] for k in ("vehicle_id", "driver_id", "service", "mahallas")} for r in (await gps.get("/api/v1/gps/schedule")).json()["rows"]]
    rows = [r for r in rows if r["vehicle_id"] != vehicle_id and r["driver_id"] != driver_id]
    rows.append({"vehicle_id": vehicle_id, "driver_id": driver_id, "service": service})
    r = await gps.put("/api/v1/gps/schedule", json={"rows": rows})
    assert r.status_code == 200, r.text
    return r.json()


async def upload(driver, request_id: int, kind: str, coords: dict | None = None):
    return await driver.post(f"/api/v1/driver/requests/{request_id}/files",
                             data={"kind": kind, **{k: str(v) for k, v in (coords or {}).items()}},
                             files={"file": (f"{kind}.png", PNG, "image/png")})


async def fill_act(driver, request_id: int, coords: dict) -> None:
    assert (await upload(driver, request_id, "before", coords)).status_code == 200
    for kind in ("face", "sign"):
        assert (await upload(driver, request_id, kind)).status_code == 200
    assert (await upload(driver, request_id, "after", coords)).status_code == 200


async def assign(gps, request_id: int, vehicle_id: int, confirm: bool = True):
    """Mashina biriktirish + varaqani chop etish va «printerdan chiqdi» tasdig'i (agentsiz rejim) — murojaat sariqqa o'tadi.
    Biriktirish javobini qaytaradi (xato bo'lsa — chop etilmaydi)."""
    r = await gps.post(f"/api/v1/gps/requests/{request_id}/assign", json={"vehicle_id": vehicle_id})
    if r.status_code == 200 and confirm:
        fid = r.json()["order_form"]["id"]
        assert (await gps.post(f"/api/v1/order-forms/{fid}/print")).status_code == 200
        c = await gps.post(f"/api/v1/order-forms/{fid}/confirm-print")
        assert c.status_code == 200, c.text
    return r
