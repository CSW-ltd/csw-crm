"""PR #14: debitor/kreditor hisobi (shartnoma turiga qarab), davrlarni solishtirish, yashil murojaatlar, to'lovlar, import, huquqlar."""
import io
from datetime import date, timedelta
from decimal import Decimal

from openpyxl import Workbook
from sqlalchemy import update

from app.core.permissions import apply_template
from app.core.security import hash_password
from app.db.base import utcnow
from app.models import Contract, OrderForm, Request, User, UserDistrict
from app.models.enums import ContractType, RequestStatus, Role
from tests.conftest import PASSWORD

T = date.today()


async def _setup(world, sessionmaker, ctype=ContractType.by_volume, price=50_000):
    """A korxonaga: shartnoma turi/narxi, 2 ta yashil murojaat (5 va 3 m³), buxgalter foydalanuvchi."""
    cid = world["customer"].id
    async with sessionmaker() as s:
        await s.execute(update(Contract).where(Contract.customer_id == cid).values(type=ctype, price=price, valid_from=T - timedelta(days=90)))
        r1, r2 = world["requests"][:2]
        for rid, days, vol in ((r1, 40, 5), (r2, 10, 3)):
            await s.execute(update(Request).where(Request.id == rid).values(status=RequestStatus.done,
                                                                            finished_at=utcnow() - timedelta(days=days)))
            s.add(OrderForm(request_id=rid, number=f"{rid:07d}", print_count=1, volume_m3=vol, waste_kind="solid",
                            closed_at=utcnow() - timedelta(days=days), closed_via="form"))
        acc = User(username="buxgalter", password_hash=hash_password(PASSWORD), full_name="Buxgalter", role=Role.accountant)
        apply_template(acc)
        s.add(acc)
        await s.flush()
        s.add_all([UserDistrict(user_id=acc.id, district_id=d) for d in world["districts"].values()])
        await s.commit()
    return cid


async def test_by_volume_balance_and_payments(world, client_factory, sessionmaker):
    cid = await _setup(world, sessionmaker)
    acc, legal, gps = await client_factory("buxgalter"), await client_factory("legal"), await client_factory("gps")
    rows = (await legal.get("/api/v1/accounting/companies")).json()
    row = next(r for r in rows["items"] if r["customer_id"] == cid)
    assert rows["total_contracted"] == 1 and row["volume_m3"] == 8 and row["debit"] == 400_000 and row["credit"] == 0
    # To'lov: legal kirita olmaydi, buxgalter kiritadi
    body = {"customer_id": cid, "paid_on": str(T - timedelta(days=5)), "amount": 500000, "doc_no": "PP-1"}
    assert (await legal.post("/api/v1/accounting/payments", json=body)).status_code == 403
    assert (await gps.get("/api/v1/accounting/companies")).status_code == 403
    p = (await acc.post("/api/v1/accounting/payments", json=body)).json()
    row = next(r for r in (await legal.get("/api/v1/accounting/companies")).json()["items"] if r["customer_id"] == cid)
    assert row["debit"] == 0 and row["credit"] == 100_000  # oldindan to'lagan → kreditor
    # Bekor qilish: o'chirilmaydi, hisobga kirmaydi
    r = await acc.post(f"/api/v1/accounting/payments/{p['id']}/cancel", json={"reason": "Xato kiritildi"})
    assert r.json()["cancelled"]
    lst = (await acc.get("/api/v1/accounting/payments", params={"q": world["customer"].code})).json()
    assert lst["total"] == 1 and lst["sum"] == 0
    row = next(r for r in (await legal.get("/api/v1/accounting/companies")).json()["items"] if r["customer_id"] == cid)
    assert row["debit"] == 400_000


async def test_compare_periods_and_green_list(world, client_factory, sessionmaker):
    cid = await _setup(world, sessionmaker, ContractType.per_trip, 180_000)
    acc = await client_factory("buxgalter")
    await acc.post("/api/v1/accounting/payments", json={"customer_id": cid, "paid_on": str(T - timedelta(days=20)), "amount": 100000})
    a = (T - timedelta(days=60), T - timedelta(days=30))   # 1-davr: 1 reys (40 kun oldin)
    b = (T - timedelta(days=29), T)                        # 2-davr: 1 reys + 100 000 to'lov
    r = await acc.get(f"/api/v1/accounting/companies/{cid}/compare", params={"a_from": str(a[0]), "a_to": str(a[1]),
                                                                             "b_from": str(b[0]), "b_to": str(b[1])})
    assert r.status_code == 200, r.text
    p1, p2 = r.json()["periods"]
    assert (p1["opening"], p1["charged"], p1["paid"], p1["closing"], p1["debit"]) == (0, 180000, 0, 180000, 180000)
    assert (p2["opening"], p2["charged"], p2["paid"], p2["closing"], p2["debit"]) == (180000, 180000, 100000, 260000, 260000)
    assert sum(m["charged"] for m in r.json()["months"]) == 360000
    bad = await acc.get(f"/api/v1/accounting/companies/{cid}/compare", params={"a_from": str(T), "a_to": str(T - timedelta(days=1)),
                                                                               "b_from": str(T), "b_to": str(T)})
    assert bad.json()["error"]["code"] == "bad_dates"
    g = (await acc.get(f"/api/v1/accounting/companies/{cid}/green")).json()
    assert [x["volume_m3"] for x in g["items"]] == [3, 5] and g["total_m3"] == 8 and g["items"][0]["amount"] == 180000


async def test_monthly_and_one_off(world, client_factory, sessionmaker):
    cid = await _setup(world, sessionmaker, ContractType.monthly, 1_000_000)
    legal = await client_factory("legal")
    row = next(r for r in (await legal.get("/api/v1/accounting/companies")).json()["items"] if r["customer_id"] == cid)
    start = T - timedelta(days=90)
    months = (T.year - start.year) * 12 + T.month - start.month + 1
    assert row["debit"] == months * 1_000_000  # har oy uchun, murojaatlar soniga bog'liq emas
    async with sessionmaker() as s:
        await s.execute(update(Contract).where(Contract.customer_id == cid).values(type=ContractType.one_off, price=750_000))
        await s.commit()
    row = next(r for r in (await legal.get("/api/v1/accounting/companies")).json()["items"] if r["customer_id"] == cid)
    assert row["debit"] == 750_000


async def test_payment_import_dry_run_then_save(world, client_factory, sessionmaker):
    cid = await _setup(world, sessionmaker)
    acc = await client_factory("buxgalter")
    wb = Workbook()
    ws = wb.active
    ws.append(["Bank ko'chirmasi"])
    ws.append(["Sana", "Maxsus raqam", "STIR", "Summa", "Hujjat №"])
    ws.append([(T - timedelta(days=3)).strftime("%d.%m.%Y"), world["customer"].code, "", "250 000,00", "PP-77"])
    ws.append([T.strftime("%d.%m.%Y"), "", "305123456", 150000, "PP-78"])
    ws.append([T.strftime("%d.%m.%Y"), "ZZZ99", "", 1000, "PP-79"])
    ws.append(["xato sana", world["customer"].code, "", 1000, "PP-80"])
    buf = io.BytesIO(); wb.save(buf)
    files = {"file": ("kochirma.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = (await acc.post("/api/v1/accounting/payments/import", params={"dry_run": "true"}, files=files)).json()
    assert r["ok"] == 2 and r["total"] == 400000 and {e["error"] for e in r["errors"]} == {"customer_not_found", "bad_date"}
    assert (await acc.get("/api/v1/accounting/payments")).json()["total"] == 0  # sinovda saqlanmaydi
    r = (await acc.post("/api/v1/accounting/payments/import", params={"dry_run": "false"}, files=files)).json()
    lst = (await acc.get("/api/v1/accounting/payments")).json()
    assert lst["total"] == 2 and lst["sum"] == 400000 and {i["source"] for i in lst["items"]} == {"import"}
    row = next(x for x in (await acc.get("/api/v1/accounting/companies")).json()["items"] if x["customer_id"] == cid)
    assert row["debit"] == 0 and row["credit"] == 0  # 400 000 hisoblangan, 400 000 to'langan


async def test_board_hours_and_district_filters(world, client_factory, sessionmaker):
    admin = await client_factory("admin")
    r1, r2, r3 = world["requests"]
    async with sessionmaker() as s:
        await s.execute(update(Request).where(Request.id == r1).values(created_at=utcnow() - timedelta(hours=30)))
        await s.commit()
    a, b = world["districts"]["a"], world["districts"]["b"]
    assert (await admin.get("/api/v1/requests", params={"hours": 12})).json()["total"] == 2
    assert (await admin.get("/api/v1/requests", params={"hours": 72})).json()["total"] == 3
    assert (await admin.get("/api/v1/requests", params={"hours": 72, "district_id": b})).json()["total"] == 0
    s = (await admin.get("/api/v1/requests-summary", params={"hours": 12, "district_id": a})).json()
    assert s["red"] == 2
    s = (await admin.get("/api/v1/requests-summary", params={"hours": 72, "district_id": b})).json()
    assert s["red"] == 0


async def test_new_contracts_by_period_and_district(world, client_factory, sessionmaker):
    from app.models import Customer
    from tests.test_permissions import _manager_a
    a, b = world["districts"]["a"], world["districts"]["b"]
    async with sessionmaker() as s:
        await s.execute(update(Contract).where(Contract.customer_id == world["customer"].id).values(signed_on=T - timedelta(days=40)))
        for i, (did, back) in enumerate(((a, 2), (a, 10), (b, 20), (b, 100), (a, 300), (b, 500))):
            c = Customer(fixed_no=f"A-09{i}", name=f"K{i}", name_key=f"k{i}", district_id=did)
            s.add(c); await s.flush()
            s.add(Contract(customer_id=c.id, number=f"SH-T{i}", type=ContractType.monthly, price=1,
                           signed_on=T - timedelta(days=back), valid_from=T - timedelta(days=back), valid_to=T + timedelta(days=30)))
        await s.commit()
    admin = await client_factory("admin")
    r = (await admin.get("/api/v1/accounting/new-contracts")).json()
    assert {p["key"]: p["count"] for p in r["periods"]} == {"d7": 1, "d15": 2, "m1": 3, "m6": 5, "y1": 6}
    da = next(d for d in r["districts"] if d["district_id"] == a)
    assert (da["d7"], da["d15"], da["m1"], da["m6"], da["y1"]) == (1, 2, 2, 3, 4)
    r = (await admin.get("/api/v1/accounting/new-contracts", params={"district_id": b})).json()
    assert {p["key"]: p["count"] for p in r["periods"]} == {"d7": 0, "d15": 0, "m1": 1, "m6": 2, "y1": 2}
    assert [d["district_id"] for d in r["districts"]] == [b]
    # Manager (faqat A tumani) — faqat o'z tumani
    _, mgr = await _manager_a(world, client_factory, admin, [])
    r = (await mgr.get("/api/v1/accounting/new-contracts")).json()
    assert [d["district_id"] for d in r["districts"]] == [a] and r["periods"][-1]["count"] == 4
    # Korxonalar jadvali ham tuman bo'yicha
    rows = (await admin.get("/api/v1/accounting/companies", params={"district_id": b})).json()["items"]
    assert rows and {x["district_id"] for x in rows} == {b}


def _statement(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["Sana", "Maxsus raqam", "STIR", "Summa", "Hujjat №"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO(); wb.save(buf)
    return {"file": ("kochirma.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


async def test_payment_import_twice_does_not_double(world, client_factory, sessionmaker):
    """Ko'chirmani qayta yuklash: hujjat № mos keladigan qatorlar yozilmaydi; fayl ichidagi takror ham."""
    await _setup(world, sessionmaker)
    acc = await client_factory("buxgalter")
    code, day = world["customer"].code, (T - timedelta(days=2)).strftime("%d.%m.%Y")
    files = _statement([[day, code, "", 100000, "PP-1"], [day, code, "", 50000, "PP-2"], [day, code, "", 50000, "pp - 2"]])
    r = (await acc.post("/api/v1/accounting/payments/import", params={"dry_run": "true"}, files=files)).json()
    assert r["ok"] == 2 and r["duplicates"] == 1 and r["total"] == 150000  # 3-qator — fayl ichidagi takror (PP-2)
    await acc.post("/api/v1/accounting/payments/import", params={"dry_run": "false"}, files=files)
    r = (await acc.post("/api/v1/accounting/payments/import", params={"dry_run": "false"}, files=files)).json()
    assert r["ok"] == 0 and r["duplicates"] == 3
    lst = (await acc.get("/api/v1/accounting/payments")).json()
    assert lst["total"] == 2 and lst["sum"] == 150000


async def test_payment_import_possible_duplicate_needs_mark(world, client_factory, sessionmaker):
    """Hujjat №siz qator bazadagi to'lov bilan (korxona, sana, summa) mos kelsa — ehtimoliy takror: belgilanmasa yozilmaydi."""
    await _setup(world, sessionmaker)
    acc = await client_factory("buxgalter")
    paid = T - timedelta(days=1)
    await acc.post("/api/v1/accounting/payments", json={"customer_id": world["customer"].id, "paid_on": str(paid), "amount": 70000})
    files = _statement([[paid.strftime("%d.%m.%Y"), world["customer"].code, "", 70000, ""],
                        [paid.strftime("%d.%m.%Y"), world["customer"].code, "", 80000, ""]])
    r = (await acc.post("/api/v1/accounting/payments/import", params={"dry_run": "true"}, files=files)).json()
    assert r["ok"] == 1 and [p["line"] for p in r["possible"]] == [2]
    r = (await acc.post("/api/v1/accounting/payments/import", params={"dry_run": "false"}, files=files)).json()
    assert r["ok"] == 1
    assert (await acc.get("/api/v1/accounting/payments")).json()["total"] == 2
    # Buxgalter belgilagan ehtimoliy takror (2-qator) yoziladi; belgilanmagani (3-qator, endi bazada bor) — yo'q
    r = (await acc.post("/api/v1/accounting/payments/import", params={"dry_run": "false", "include": "2"}, files=files)).json()
    assert r["ok"] == 1 and r["total"] == 70000
    assert (await acc.get("/api/v1/accounting/payments")).json()["total"] == 3


async def test_manual_payment_duplicate_warns_then_force(world, client_factory, sessionmaker):
    await _setup(world, sessionmaker)
    acc = await client_factory("buxgalter")
    body = {"customer_id": world["customer"].id, "paid_on": str(T), "amount": 90000, "doc_no": "PP-9"}
    first = (await acc.post("/api/v1/accounting/payments", json=body)).json()
    r = await acc.post("/api/v1/accounting/payments", json={**body, "doc_no": " pp-9 "})
    assert r.status_code == 409 and r.json()["error"]["code"] == "payment_duplicate"
    assert r.json()["error"]["details"]["payment_id"] == first["id"]
    assert (await acc.post("/api/v1/accounting/payments", json={**body, "doc_no": "PP-10"})).status_code == 201  # boshqa hujjat
    assert (await acc.post("/api/v1/accounting/payments", json={**body, "doc_no": "PP-9", "force": True})).status_code == 201
    # Bekor qilingan to'lov takror emas
    await acc.post(f"/api/v1/accounting/payments/{first['id']}/cancel", json={"reason": "Xato kiritildi"})
    body2 = {"customer_id": world["customer"].id, "paid_on": str(T - timedelta(days=3)), "amount": 1000}
    p2 = (await acc.post("/api/v1/accounting/payments", json=body2)).json()
    await acc.post(f"/api/v1/accounting/payments/{p2['id']}/cancel", json={"reason": "Xato kiritildi"})
    assert (await acc.post("/api/v1/accounting/payments", json=body2)).status_code == 201
