"""PR #18: ta'riflar (viloyat → tuman, sana, qulf), tugallanmagan loyihalar, mavjud shartnomalarni kiritish (forma + Excel)."""
import io
from datetime import date, timedelta

from docx import Document
from openpyxl import load_workbook

from sqlalchemy import select

from app.models import District
from tests.test_accounting import _setup
from tests.test_contracts import REQ, body

T = date.today()


async def _region_ids(sessionmaker, world):
    async with sessionmaker() as s:
        da = await s.get(District, world["districts"]["a"])
        db_ = await s.get(District, world["districts"]["b"])
        return da.region_id, db_.region_id


async def test_tariff_hierarchy_permissions_and_lock(world, client_factory, sessionmaker):
    admin, legal, gps = await client_factory("admin"), await client_factory("legal"), await client_factory("gps")
    _, mgr = await _manager(world, client_factory, admin)
    ra, rb = await _region_ids(sessionmaker, world)
    a, b = world["districts"]["a"], world["districts"]["b"]
    y0 = date(T.year - 1, 1, 1)
    # Viloyat ta'rifi — faqat admin
    assert (await mgr.post("/api/v1/tariffs", json={"region_id": ra, "price": 80000, "valid_from": str(y0)})).status_code == 403
    assert (await admin.post("/api/v1/tariffs", json={"region_id": ra, "price": 80000, "valid_from": str(y0)})).status_code == 201
    assert (await legal.get("/api/v1/tariffs/price", params={"district_id": a})).json()["price"] == 80000
    # Manager — o'z tumani (tuman ta'rifi viloyatnikidan ustun), boshqa tuman — 403
    r = await mgr.post("/api/v1/tariffs", json={"district_id": a, "price": 85000, "valid_from": str(T - timedelta(days=10))})
    assert r.status_code == 201, r.text
    assert (await mgr.post("/api/v1/tariffs", json={"district_id": b, "price": 1, "valid_from": str(T)})).status_code == 403
    assert (await legal.get("/api/v1/tariffs/price", params={"district_id": a})).json()["price"] == 85000
    assert (await legal.get("/api/v1/tariffs/price", params={"district_id": a, "day": str(T - timedelta(days=20))})).json()["price"] == 80000
    ov = (await mgr.get("/api/v1/tariffs")).json()
    reg = next(x for x in ov["regions"] if x["region_id"] == ra)
    da = reg["districts"][0]
    assert reg["price"] == 80000 and da["price"] == 85000 and da["own_price"] == 85000 and da["can_edit"] and not reg["can_edit"]
    assert (await gps.get("/api/v1/tariffs")).status_code == 403
    # Admin managerga yopadi: tuman, keyin viloyat
    assert (await mgr.put("/api/v1/tariffs/lock", json={"district_id": a, "locked": True})).status_code == 403
    assert (await admin.put("/api/v1/tariffs/lock", json={"district_id": a, "locked": True})).status_code == 204
    r = await mgr.post("/api/v1/tariffs", json={"district_id": a, "price": 86000, "valid_from": str(T)})
    assert r.status_code == 403
    await admin.put("/api/v1/tariffs/lock", json={"district_id": a, "locked": False})
    await admin.put("/api/v1/tariffs/lock", json={"region_id": ra, "locked": True})
    assert (await mgr.post("/api/v1/tariffs", json={"district_id": a, "price": 86000, "valid_from": str(T)})).status_code == 403
    await admin.put("/api/v1/tariffs/lock", json={"region_id": ra, "locked": False})
    # Kelajakdagi ta'rifni o'chirish mumkin, kuchga kirganini — yo'q
    fut = (await mgr.post("/api/v1/tariffs", json={"district_id": a, "price": 90000, "valid_from": str(T + timedelta(days=30))})).json()
    assert (await mgr.delete(f"/api/v1/tariffs/{fut['id']}")).status_code == 204
    hist = next(x for x in (await admin.get("/api/v1/tariffs")).json()["regions"] if x["region_id"] == ra)["districts"][0]["history"]
    assert [h["price"] for h in hist] == [85000]
    assert (await mgr.delete(f"/api/v1/tariffs/{hist[0]['id']}")).json()["error"]["code"] == "tariff_in_force"


async def _manager(world, client_factory, admin):
    from tests.test_permissions import _manager_a
    return await _manager_a(world, client_factory, admin, [])


async def test_billing_uses_tariff_on_closing_day(world, client_factory, sessionmaker):
    cid = await _setup(world, sessionmaker, price=50_000)  # kub; 2 varaqa: 40 kun oldin 5 m³, 10 kun oldin 3 m³
    admin, acc = await client_factory("admin"), await client_factory("buxgalter")
    ra, _ = await _region_ids(sessionmaker, world)
    await admin.post("/api/v1/tariffs", json={"region_id": ra, "price": 60000, "valid_from": str(T - timedelta(days=100))})
    await admin.post("/api/v1/tariffs", json={"district_id": world["districts"]["a"], "price": 70000, "valid_from": str(T - timedelta(days=20))})
    row = next(r for r in (await acc.get("/api/v1/accounting/companies")).json()["items"] if r["customer_id"] == cid)
    assert row["debit"] == 5 * 60000 + 3 * 70000  # shartnomadagi 50 000 emas — o'sha kundagi ta'rif


async def test_draft_lifecycle_and_rented(world, client_factory, sessionmaker):
    from app.models import Tariff
    async with sessionmaker() as s:
        for rid in await _region_ids(sessionmaker, world):
            s.add(Tariff(region_id=rid, price=84000, valid_from=date(T.year - 1, 1, 1)))
        await s.commit()
    legal = await client_factory("legal")
    cid = (await legal.post("/api/v1/customers", json={"name": "Draft MChJ", "district_id": world["districts"]["a"]})).json()["id"]
    ct = (await legal.post("/api/v1/contracts/start", json={"customer_id": cid})).json()
    assert ct["number"] is None and ct["status"] == "draft"
    # Tekshiruvsiz saqlash (yarim to'ldirilgan, STIR xato) — korxona kartasiga yozilmaydi
    half = body(cid, requisites={**REQ, "stir": "12"})
    r = (await legal.put(f"/api/v1/contracts/{ct['id']}/draft", json=half)).json()
    assert r["draft"]["requisites"]["stir"] == "12" and r["customer"]["stir"] is None
    drafts = (await legal.get("/api/v1/contracts", params={"status": "draft"})).json()["items"]
    assert any(x["id"] == ct["id"] for x in drafts)
    assert (await legal.post(f"/api/v1/contracts/{ct['id']}/sign", data={"signed_on": str(T), "sign_method": "paper"})).json()["error"]["code"] == "contract_incomplete"
    # Narx — ta'rifdan (formadagi narx e'tiborga olinmaydi); faqat kub turi
    chk = (await legal.post(f"/api/v1/contracts/{ct['id']}/check", json=body(cid, price=1, type="monthly"))).json()
    assert {"field": "type", "code": "type_volume_only"} in chk["errors"]
    full = body(cid, price=1, requisites={**REQ, "cadastre": None, "is_rented": True})
    chk = (await legal.post(f"/api/v1/contracts/{ct['id']}/check", json=full)).json()
    assert chk["ok"] and chk["totals"]["price"] == 84000
    r = (await legal.put(f"/api/v1/contracts/{ct['id']}", json=full)).json()
    assert r["number"].startswith("BTE-") and r["draft"] is None and r["customer"]["is_rented"] and r["price"] == 84000
    dx = await legal.get(f"/api/v1/contracts/{ct['id']}/document", params={"format": "docx"})
    text = "\n".join(p.text for p in Document(io.BytesIO(dx.content)).paragraphs)
    assert "ijara huquqi asosida foydalanishga berilgan" in text and "kadastr raqami" not in text


async def test_existing_contract_full_data_and_accountant_approval(world, client_factory, sessionmaker):
    from app.models import Tariff
    async with sessionmaker() as s_:
        for rid in await _region_ids(sessionmaker, world):
            s_.add(Tariff(region_id=rid, price=84000, valid_from=date(T.year - 1, 1, 1)))
        await s_.commit()
    await _setup(world, sessionmaker)  # buxgalter
    legal, acc = await client_factory("legal"), await client_factory("buxgalter")
    cid = (await legal.post("/api/v1/customers", json={"name": "Eski MChJ", "district_id": world["districts"]["a"]})).json()["id"]
    meta = {"number": "721", "signed_on": "2026-03-02", "platform": "didox", "platform_id": "e0f94e10"}
    full = body(cid, type="monthly", price=500000, valid_from="2026-03-01", valid_to="2026-12-31", existing=meta)
    # Rekvizitlar yangi shartnoma bilan bir xil majburiy
    r = await legal.post("/api/v1/contracts/existing", json={**full, "requisites": {"name": "Eski MChJ", "stir": "12"}})
    assert r.json()["error"]["code"] == "contract_invalid"
    r = await legal.post("/api/v1/contracts/existing", json=full)
    assert r.status_code == 201, r.text
    c = r.json()
    # Asl PDF yuklanmaguncha — «Tugallanmagan» (PDF kutilmoqda), buxgalterga bormaydi
    assert c["status"] == "draft" and c["awaiting_scan"] and not c["is_active"] and c["source"] == "manual" and c["display_number"] == "e0f94e10"
    assert c["customer"]["account"] == REQ["account"] and [e["action"] for e in c["events"]] == ["imported"]
    assert not any(x["id"] == c["id"] for x in (await acc.get("/api/v1/contracts", params={"status": "signed"})).json()["items"])
    c = (await legal.post(f"/api/v1/contracts/{c['id']}/scan-upload", files={"file": ("asl.pdf", b"%PDF-1", "application/pdf")})).json()
    assert c["status"] == "signed" and c["is_active"] and c["has_scan"] and c["submitted_by"] == "Yurist"
    dup = (await legal.post("/api/v1/contracts/existing", json={**full, "existing": {**meta, "platform_id": "x2"}})).json()
    assert {"field": "number", "code": "number_taken"} in dup["error"]["details"]["errors"]
    # Buxgalter navbatida — tasdiqlagach «Tasdiqlangan»
    assert any(x["id"] == c["id"] for x in (await acc.get("/api/v1/contracts", params={"status": "signed"})).json()["items"])
    assert (await acc.post(f"/api/v1/contracts/{c['id']}/approve")).json()["status"] == "approved"
    # Excel: rekvizitlar majburiy, har bir qator — buxgalter navbatiga
    tpl = await legal.get("/api/v1/contracts/existing/template")
    wb = load_workbook(io.BytesIO(tpl.content))
    ws = wb.active
    R = lambda name, stir, dr, num, price, reason, vol, acc="20208000900123456001": ["Asaka tumani", name, stir, dr, "90 111 22 33", "A", "A", "B",  # noqa: E731
                                                                               "00873", acc, "", num, "", "kub", price, reason, vol,
                                                                               "01.02.2026", "01.02.2026", "31.12.2026"]
    rows = [R("Yangi Import MChJ", "301112223", "Dir", "IMP-1", "84000", "", "50"),
            R("Ikkinchi MChJ", "301112224", "", "IMP-2", "84000", "", "10", "20208000900123456002"),
            ["Yo'q tuman", "X MChJ", "", "", "", "", "", "", "", "", "", "IMP-3", "", "kub", "", "", "", "", "01.02.2026", "31.12.2026"],
            R("Uchinchi MChJ", "301112225", "D", "IMP-4", "84000", "", "", "20208000900123456003"),
            R("Narxsiz MChJ", "301112226", "D", "IMP-5", "", "", "20", "20208000900123456004"),
            R("Sababsiz MChJ", "301112227", "D", "IMP-6", "75000", "", "20", "20208000900123456005"),
            R("Eski narx MChJ", "301112228", "D", "IMP-7", "75000", "2025 yilgi shartnoma", "20", "20208000900123456006")]
    for r_ in rows:
        ws.append(r_)
    buf = io.BytesIO(); wb.save(buf)
    up = lambda dry: legal.post("/api/v1/contracts/existing/import", params={"dry_run": dry},  # noqa: E731
                                files={"file": ("s.xlsx", buf.getvalue(), "application/octet-stream")})
    dry = (await up(True)).json()
    errs = {e["value"]: e["error"] for e in dry["errors"]}
    assert dry["ok"] == 2 and errs == {"IMP-2": "director_required", "IMP-3": "district_not_found", "IMP-4": "volume_required",
                                       "IMP-5": "price_required", "IMP-6": "price_reason_required"}, dry
    assert (await up(False)).json()["created"] == 2
    old = (await acc.get("/api/v1/contracts", params={"q": "IMP-7"})).json()["items"][0]
    assert old["price"] == 75000 and old["tariff_price"] == 84000 and old["price_reason"] == "2025 yilgi shartnoma"
    found = (await acc.get("/api/v1/contracts", params={"q": "IMP-1"})).json()["items"]
    assert found[0]["status"] == "draft" and found[0]["awaiting_scan"] and found[0]["source"] == "import" and found[0]["price"] == 84000
    up2 = (await legal.post(f"/api/v1/contracts/{found[0]['id']}/scan-upload", files={"file": ("a.pdf", b"%PDF-1", "application/pdf")})).json()
    assert up2["status"] == "signed"


async def test_reassign_while_printing_and_activity_log(world, client_factory, sessionmaker):
    from tests.helpers import schedule_driver
    gps, driver, driver2 = await client_factory("gps"), await client_factory("driver"), await client_factory("driver2")
    await schedule_driver(gps, driver, world["users"]["driver"], world["vehicles"]["v1"])
    await schedule_driver(gps, driver2, world["users"]["driver2"], world["vehicles"]["v2"])
    rid = world["requests"][0]
    r = (await gps.post(f"/api/v1/gps/requests/{rid}/assign", json={"vehicle_id": world["vehicles"]["v1"]})).json()
    fid, num, naryad = r["order_form"]["id"], r["order_form"]["number"], r["naryad_no"]
    await gps.post(f"/api/v1/order-forms/{fid}/print")
    # Printerdan chiqqani tasdiqlanmaguncha — boshqa mashinaga qayta biriktirish; raqam o'zgarmaydi
    r2 = (await gps.post(f"/api/v1/gps/requests/{rid}/assign", json={"vehicle_id": world["vehicles"]["v2"]})).json()
    assert r2["status"] == "printing" and r2["vehicle"]["plate"] == "60 102 AB" and r2["order_form"]["number"] == num and r2["naryad_no"] == naryad
    paper = (await gps.get(f"/api/v1/order-forms/{fid}")).json()
    assert paper["needs_reprint"] and paper["vehicle"]["plate"] == "60 102 AB"
    assert (await gps.post(f"/api/v1/order-forms/{fid}/confirm-print")).json()["error"]["code"] == "not_printed"
    await gps.post(f"/api/v1/order-forms/{fid}/print")
    assert (await gps.post(f"/api/v1/order-forms/{fid}/confirm-print")).json()["status"] == "assigned"
    assert rid in [x["id"] for x in (await driver2.get("/api/v1/driver/tasks")).json()]
    assert rid not in [x["id"] for x in (await driver.get("/api/v1/driver/tasks")).json()]
    # Tasdiqlangandan keyin qayta biriktirib bo'lmaydi
    assert (await gps.post(f"/api/v1/gps/requests/{rid}/assign", json={"vehicle_id": world["vehicles"]["v1"]})).status_code == 409
    # Faoliyat jurnali (qo'ng'iroqchaga kirmaydi) + qayta biriktirish — managerga ogohlantirish (o'z tumani)
    admin = await client_factory("admin")
    page = (await admin.get("/api/v1/situation", params={"level": "activity"})).json()
    kinds = [e["kind"] for e in page["items"]]
    assert {"act_assigned", "act_form_printed", "act_print_confirmed"} <= set(kinds)
    warn = (await admin.get("/api/v1/situation", params={"kind": "request_reassigned"})).json()["items"]
    assert len(warn) == 1 and warn[0]["level"] == "warning" and warn[0]["actor_name"] == "GPS" and "60 101 AB" in warn[0]["message"]
    assert (await admin.get("/api/v1/situation/unread")).json()["unread"] == 1
    _, mgr = await _manager(world, client_factory, admin)
    mitems = (await mgr.get("/api/v1/situation")).json()["items"]
    assert any(e["kind"] == "request_reassigned" for e in mitems) and all(e["district_id"] == world["districts"]["a"] for e in mitems)
    assert (await mgr.get("/api/v1/situation/unread")).json()["unread"] >= 1
    acc_gps = await client_factory("gps")
    assert (await acc_gps.get("/api/v1/situation")).status_code == 403
    pdf = await admin.get("/api/v1/situation/export", params={"kind": "request_reassigned"})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    z = await admin.get("/api/v1/situation/export", params={"level": "activity"})
    import zipfile
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert "act_assigned.pdf" in names and "act_print_confirmed.pdf" in names


async def test_manager_tariff_permission_toggle(world, client_factory, sessionmaker):
    admin = await client_factory("admin")
    uid, mgr = await _manager(world, client_factory, admin)
    a = world["districts"]["a"]
    assert (await mgr.post("/api/v1/tariffs", json={"district_id": a, "price": 85000, "valid_from": str(T)})).status_code == 201
    perms = (await admin.get(f"/api/v1/admin/users/{uid}/access")).json()["permissions"]
    assert "settings.tariff" in perms
    await admin.put(f"/api/v1/admin/users/{uid}/access", json={"permissions": [p for p in perms if p != "settings.tariff"]})
    assert (await mgr.post("/api/v1/tariffs", json={"district_id": a, "price": 86000, "valid_from": str(T)})).status_code == 403
    d = next(x for r in (await mgr.get("/api/v1/tariffs")).json()["regions"] for x in r["districts"] if x["district_id"] == a)
    assert not d["can_edit"]


async def test_existing_manual_price_reason_and_permission(world, client_factory, sessionmaker):
    """PR #21: mavjud shartnomada kub narxini legal kiritadi; ta'rifdan farq qilsa — sabab majburiy; ruxsat o'chirilsa — ta'rif."""
    from app.models import Tariff, User, UserPermission
    async with sessionmaker() as s_:
        for rid in await _region_ids(sessionmaker, world):
            s_.add(Tariff(region_id=rid, price=84000, valid_from=date(T.year - 1, 1, 1)))
        await s_.commit()
    await _setup(world, sessionmaker)
    legal, acc, admin = await client_factory("legal"), await client_factory("buxgalter"), await client_factory("admin")
    cid = (await legal.post("/api/v1/customers", json={"name": "Eski Narx MChJ", "district_id": world["districts"]["a"]})).json()["id"]
    meta = {"number": "OLD-75", "signed_on": "2026-01-10"}
    base = body(cid, price=None, valid_from="2026-01-10", valid_to="2026-12-31", sign_method="paper", existing=meta)
    errs = lambda r: {(e["field"], e["code"]) for e in r["errors"]}  # noqa: E731
    r = (await legal.post("/api/v1/contracts/check", json=base)).json()
    assert ("price", "required") in errs(r) and r["totals"]["tariff"] == 84000
    r = (await legal.post("/api/v1/contracts/check", json={**base, "price": 75000})).json()
    assert ("price_reason", "required") in errs(r)
    r = (await legal.post("/api/v1/contracts/check", json={**base, "price": 84000})).json()
    assert r["ok"], r
    ok = {**base, "price": 75000, "price_reason": "2025 yilgi shartnoma, eski ta'rif"}
    r = (await legal.post("/api/v1/contracts/check", json=ok)).json()
    assert r["ok"] and r["totals"]["total"] == 75000 * 100
    c = (await legal.post("/api/v1/contracts/existing", json=ok)).json()
    assert c["price"] == 75000 and c["tariff_price"] == 84000 and c["price_reason"].startswith("2025")
    c = (await legal.post(f"/api/v1/contracts/{c['id']}/scan-upload", files={"file": ("a.pdf", b"%PDF-1", "application/pdf")})).json()
    # Buxgalter qaytaradi → legal tuzatadi: qo'lda narx saqlanadi (ta'rifga almashtirilmaydi)
    await acc.post(f"/api/v1/contracts/{c['id']}/return", json={"comment": "Hajmni tekshiring"})
    fix = {k: v for k, v in ok.items() if k != "existing"} | {"annual_volume": 90}
    r = await legal.put(f"/api/v1/contracts/{c['id']}", json=fix)
    assert r.status_code == 200 and r.json()["price"] == 75000 and r.json()["price_reason"], r.text
    bad = await legal.put(f"/api/v1/contracts/{c['id']}", json={**fix, "price_reason": None})
    assert {"field": "price_reason", "code": "required"} in bad.json()["error"]["details"]["errors"]
    # Faoliyat jurnalida narx izohi
    ev = (await admin.get("/api/v1/situation", params={"kind": "act_contract_imported"})).json()
    items = ev["items"] if isinstance(ev, dict) else ev
    assert any("narx qo'lda: 75 000 (ta'rif 84 000)" in (x.get("text") or x.get("message") or str(x)) for x in items)
    # Admin ruxsatni o'chirsa — narx yana ta'rifdan
    async with sessionmaker() as s_:
        from sqlalchemy import delete
        uid = (await s_.execute(select(User.id).where(User.username == "legal"))).scalar_one()
        await s_.execute(delete(UserPermission).where(UserPermission.user_id == uid, UserPermission.code == "customers.existing_price"))
        await s_.commit()
    r = (await legal.post("/api/v1/contracts/check", json={**base, "existing": {**meta, "number": "OLD-76"}, "price": 1})).json()
    assert r["totals"]["price"] == 84000 and not any(e["field"].startswith("price") for e in r["errors"]), r
