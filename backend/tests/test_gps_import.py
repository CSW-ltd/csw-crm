"""GPS dispatch PR-A: gps_eksport zip importi — tekshirish, import, qayta import (o'zgarish 0), o'chgan geozona/mahalla,
umumiy tayoqcha ikki mahallada, mashina ↔ GPS obyekti, huquqlar. Faqat sun'iy ma'lumot."""
import io
import json
import zipfile

from app.models import Vehicle
from app.services.gps.names import match_unit, mfy_key, plate_key

SERVER, ACC = "gps.example.test", "test_akkaunt"


def _line(rid, zid, name, x0, y0):
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[x0, y0], [x0 + 0.001, y0 + 0.001]]},
            "properties": {"tizim": SERVER, "resurs_id": rid, "id": zid, "nom": name, "tur": "chiziq", "kenglik_m": 30, "rang": "#00ff00"}}


def _poly(rid, zid, name, x0, y0, d=0.02):
    ring = [[x0, y0], [x0 + d, y0], [x0 + d, y0 + d], [x0, y0 + d], [x0, y0]]
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"tizim": SERVER, "resurs_id": rid, "id": zid, "nom": name, "tur": "poligon"}}


def _circle(rid, zid):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [70.5, 40.5]},
            "properties": {"tizim": SERVER, "resurs_id": rid, "id": zid, "nom": "Test nuqta", "tur": "doira", "radius_m": 25}}


def _zip(feats, mahallalar, mashinalar, tuman="Test tumani", extra_dir="test_eksport/"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{extra_dir}geojson/test_1.geojson", json.dumps({"type": "FeatureCollection", "features": feats}))
        z.writestr(f"{extra_dir}mfy_xarita/test.json", json.dumps({
            "versiya": 1, "tuman": tuman, "tizim": SERVER, "akkaunt": ACC, "mahallalar": mahallalar, "mashinalar": mashinalar}))
    return {"file": ("eksport.zip", buf.getvalue(), "application/zip")}


FEATS = [_line(1, 11, "1", 70.501, 40.501), _line(1, 12, "2", 70.505, 40.505), _line(1, 13, "3", 70.511, 40.511),
         _poly(1, 21, "Test MFY-1 chegara", 70.5, 40.5), _circle(1, 31)]
MAH = [{"nomi": "Test MFY-1", "kalit": mfy_key("Test MFY-1"), "tayoqchalar": [[1, 11], [1, 12]], "chegara": [1, 21]},
       {"nomi": "Test MFY-2", "kalit": mfy_key("Test MFY-2"), "tayoqchalar": [[1, 12], [1, 13]], "chegara": None}]
UNITS = [{"id": 9001, "nomi": "01 001 AAA (test)"}, {"id": 9002, "nomi": "99 999 ZZZ"}]


def test_names_match_agent_rules():
    assert mfy_key("(1)Тест-1 МФЙ✅") == mfy_key("ТЕСТ-1") != mfy_key("Тест-2 МФЙ")
    assert mfy_key("Тест МФЙ (134) 473") == mfy_key("Тест")
    assert plate_key("01 001 ААА") == plate_key("01 001 AAA") and plate_key("01 001 AAA (izoh)") == "01001AAA"
    units = {1: "TEST 01 001 AAA", 2: "02 002 BBB"}
    assert match_unit(units, "01 001 ААА") == 1 and match_unit(units, "99 002 BBB") == 2  # hudud kodisiz ham
    assert match_unit(units, "77 777 XXX") is None


async def _add_vehicle(sessionmaker, district_id):
    async with sessionmaker() as s:
        v = Vehicle(plate="01 001 AAA", district_id=district_id)
        s.add(v)
        await s.commit()
        return v.id


async def test_import_preview_apply_reimport(world, client_factory, sessionmaker):
    did = world["districts"]["a"]
    vid = await _add_vehicle(sessionmaker, did)
    admin, manager = await client_factory("admin"), await client_factory("manager")
    files = _zip(FEATS, MAH, UNITS)
    assert (await manager.post("/api/v1/dispatch/import/preview", files=files)).status_code == 403
    p = (await admin.post("/api/v1/dispatch/import/preview", files=files)).json()
    assert p["zones"] == {"total": 5, "line": 3, "polygon": 1, "circle": 1, "new": 5, "changed": 0, "deactivated": 0}
    sec = p["sections"][0]
    assert (sec["tuman"], sec["mahallas"], sec["sticks"], sec["boundaries"], sec["missing_zones"]) == ("Test tumani", 2, 3, 1, 0)
    assert sec["no_boundary"] == ["Test MFY-2"] and sec["suggested_district_id"] is None
    # Tuman tanlangach: mashinalar shu tumandagi CRM mashinalari bilan solishtiriladi
    p = (await admin.post("/api/v1/dispatch/import/preview", files=files, data={"mapping": json.dumps({"Test tumani": did})})).json()
    sec = p["sections"][0]
    assert sec["vehicles_matched"] == 1 and "01 001 AAA" not in sec["vehicles_missing"] and sec["units_unmatched"] == ["99 999 ZZZ"]
    # Tumansiz import — rad etiladi
    r = await admin.post("/api/v1/dispatch/import/apply", files=files, data={"mapping": "{}"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "district_required"
    a = (await admin.post("/api/v1/dispatch/import/apply", files=files, data={"mapping": json.dumps({"Test tumani": did})})).json()
    assert a["applied"] and a["stats"] == {"mahallas_created": 2, "mahallas_updated": 0, "mahallas_deactivated": 0,
                                            "links_changed": 2, "vehicles_linked": 1}
    s = (await admin.get("/api/v1/dispatch/summary")).json()
    row = next(x for x in s["districts"] if x["district_id"] == did)
    assert (row["mahallas"], row["sticks"], row["boundaries"], row["vehicles_linked"]) == (2, 3, 1, 1)  # umumiy tayoqcha bir marta
    assert s["sources"][0]["server"] == SERVER and s["sources"][0]["zones"] == 5
    # Qayta import — o'zgarish 0; tuman avvalgi importdan taklif qilinadi
    p = (await admin.post("/api/v1/dispatch/import/preview", files=files)).json()
    assert p["zones"]["new"] == p["zones"]["changed"] == p["zones"]["deactivated"] == 0 and p["sections"][0]["suggested_district_id"] == did
    a = (await admin.post("/api/v1/dispatch/import/apply", files=files, data={"mapping": json.dumps({"Test tumani": did})})).json()
    assert a["stats"] == {"mahallas_created": 0, "mahallas_updated": 0, "mahallas_deactivated": 0, "links_changed": 0, "vehicles_linked": 0}
    # Eksportda 3-tayoqcha va «Test MFY-2» yo'q, 1-tayoqcha o'zgargan → o'chiriladi (is_active), o'zgargani yangilanadi
    feats2 = [_line(1, 11, "1", 70.502, 40.502), FEATS[1], FEATS[3], FEATS[4]]
    files2 = _zip(feats2, MAH[:1], UNITS)
    p = (await admin.post("/api/v1/dispatch/import/preview", files=files2)).json()
    assert (p["zones"]["new"], p["zones"]["changed"], p["zones"]["deactivated"]) == (0, 1, 1)
    a = (await admin.post("/api/v1/dispatch/import/apply", files=files2, data={"mapping": json.dumps({"Test tumani": did})})).json()
    assert a["stats"]["mahallas_deactivated"] == 1
    row = next(x for x in (await admin.get("/api/v1/dispatch/summary")).json()["districts"] if x["district_id"] == did)
    assert (row["mahallas"], row["sticks"], row["boundaries"]) == (1, 2, 1)
    assert vid


async def test_import_bad_files(world, client_factory):
    admin = await client_factory("admin")
    r = await admin.post("/api/v1/dispatch/import/preview", files={"file": ("x.zip", b"not a zip", "application/zip")})
    assert r.status_code == 422 and r.json()["error"]["code"] == "import_bad_zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("geojson/a.geojson", json.dumps({"features": []}))
    r = await admin.post("/api/v1/dispatch/import/preview", files={"file": ("x.zip", buf.getvalue(), "application/zip")})
    assert r.json()["error"]["code"] == "import_no_mfy_map"
    r = await admin.post("/api/v1/dispatch/import/preview", files={"file": ("x.zip", b"0" * (10 * 1024 * 1024 + 5), "application/zip")})
    assert r.status_code == 413 and r.json()["error"]["code"] == "import_too_large"
    r = await admin.post("/api/v1/dispatch/import/apply", files=_zip(FEATS, MAH, UNITS), data={"mapping": "[1"})
    assert r.json()["error"]["code"] == "bad_mapping"
