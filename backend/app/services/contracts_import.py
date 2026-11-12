"""Mavjud (qo'lda tuzilgan) shartnomalarni Excel orqali kiritish (avval sinov). Bittalab forma — contracts.create_existing.

Yangi shartnoma bilan bir xil to'liq ma'lumot (rekvizitlar majburiy). Har bir shartnoma «Tugallanmagan»da asl PDF'ini kutadi;
PDF yuklangach buxgalter navbatiga tushadi va bittalab tasdiqlanadi. source = import, tarixda «imported».
Korxona: tuman + STIR (yoki tuman + nom) bo'yicha topiladi, topilmasa yaratiladi. Kub turidagi shartnomada hisob — ta'rif bo'yicha.
"""
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import conflict, invalid, not_found
from app.db.base import utcnow
from app.models import Contract, ContractEvent, Customer, District, User
from app.models.enums import ContractType, LocationStatus
from app.services import access, situation
from app.services.geo import coords_error
from app.services.tariffs import price_for
from app.services.customer_service import _check_stir
from app.services.normalize import format_phone, key as name_key
from app.services.customer_import import next_fixed_no_start

TYPES = {"kub": ContractType.by_volume, "hajm": ContractType.by_volume, "by_volume": ContractType.by_volume,
         "reys": ContractType.per_trip, "per_trip": ContractType.per_trip, "oylik": ContractType.monthly, "abonent": ContractType.monthly,
         "monthly": ContractType.monthly, "bir martalik": ContractType.one_off, "one_off": ContractType.one_off}


async def _check(db: AsyncSession, cust: Customer, number: str, platform_id: str | None, ctype: ContractType, price, vf: date, vt: date,
                 seen_numbers: set[str] | None = None) -> str | None:
    """Xato kodi yoki None."""
    from app.services.contracts import _overlap
    if vt < vf:
        return "bad_dates"
    if ctype != ContractType.by_volume and not price:
        return "price_required"
    if (seen_numbers is not None and number in seen_numbers) or (await db.execute(select(Contract.id).where(Contract.number == number))).first():
        return "contract_number_taken"
    if platform_id and (await db.execute(select(Contract.id).where(Contract.platform_id == platform_id))).first():
        return "platform_id_taken"
    if cust.id and await _overlap(db, cust.id, vf, vt, None):
        return "overlap"
    return None


def _make(cust_id: int, actor: User, number: str, platform: str | None, platform_id: str | None, ctype: ContractType, price, volume,
          signed_on: date, vf: date, vt: date, method: str, source: str) -> Contract:
    return Contract(customer_id=cust_id, number=number, platform=platform if platform_id else None, platform_id=platform_id or None,
                    type=ctype, price=price, annual_volume=volume, signed_on=signed_on, valid_from=vf, valid_to=vt, sign_method=method,
                    status="draft", is_active=False, created_by_id=actor.id,  # PDF yuklangach — buxgalter tasdig'iga
                    source=source, events=[ContractEvent(actor_id=actor.id, action="imported")])


# --- Excel ---
COLUMNS = [("district", "Tuman / shahar", 22), ("name", "Korxona nomi", 32), ("stir", "STIR (9 raqam)", 14), ("director", "Direktor F.I.Sh.", 24),
           ("phone", "Telefon", 16), ("legal_address", "Yuridik manzil", 30), ("address", "Obyekt manzili", 30), ("bank", "Bank", 22),
           ("mfo", "MFO (5)", 9), ("account", "Hisob raqam (20)", 24), ("oked", "OKED", 9), ("number", "Shartnoma raqami", 18),
           ("platform_id", "Platforma ID (Didox / hujjat.uz)", 22), ("type", "Turi (kub / reys / oylik)", 14),
           ("price", "Narx, QQS bilan (shartnomadagi)", 16), ("price_reason", "Narx sababi (ta'rifdan farq qilsa)", 30),
           ("annual_volume", "Yillik hajm, m³", 12),
           ("signed_on", "Imzolangan sana", 14), ("valid_from", "Boshlanish", 13), ("valid_to", "Tugash", 13),
           ("lat", "Kenglik (ixtiyoriy)", 13), ("lng", "Uzunlik (ixtiyoriy)", 13)]


def template_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Shartnomalar"
    for i, (_, title, width) in enumerate(COLUMNS, start=1):
        c = ws.cell(row=1, column=i, value=title)
        c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="00A651")
        ws.column_dimensions[c.column_letter].width = width
    sample = ["Asaka tumani", "\"Namuna\" MChJ", "300000000", "Namuna Direktor", "90 123 45 67", "Asaka, Namuna ko'chasi 1",
              "Asaka, Namuna ko'chasi 1", "DEMO bank", "00000", "20208000000000000000", "56290", "1234", "", "kub", "75000", "2025 yilgi shartnoma, eski ta'rif", "120",
              "01.03.2026", "01.03.2026", "31.12.2026", "40.6415", "72.2390"]
    for i, v in enumerate(sample, start=1):
        ws.cell(row=2, column=i, value=v).font = Font(italic=True, color="888888")
    ws.freeze_panes = "A2"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _date(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v or "").strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _dec(v) -> Decimal | None:
    s = re.sub(r"[\s ]", "", str(v or "")).replace(",", ".")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _digits(v) -> str:
    s = str(v or "").strip()
    if re.fullmatch(r"\d+\.0", s):  # Excel son sifatida saqlagan
        s = s[:-2]
    return re.sub(r"\D", "", s)


async def import_file(db: AsyncSession, actor: User, file_name: str, content: bytes, dry_run: bool) -> dict:
    from app.services.table_readers import read_tables
    _, tables = read_tables(file_name, content)
    titles = {t.lower(): k for k, t, _ in COLUMNS} | {"narx (reys/oylik uchun, qqs bilan)": "price"}  # PR #20 shabloni ham o'qiladi
    manual = actor.can("customers.existing_price")
    districts = list((await db.execute(select(District).where(District.is_active.is_(True)))).scalars())
    by_dname = {name_key(d.name): d for d in districts}
    scope = access.scope(actor)
    customers = list((await db.execute(select(Customer))).scalars())
    rows, errors, seen_numbers = [], [], set()
    header = None
    table = tables[0] if tables else []
    for i, row in enumerate(table.rows if hasattr(table, "rows") else table):
        cells = [str(x or "").strip() for x in row]
        if header is None:
            m = {titles[c.lower()]: j for j, c in enumerate(cells) if c.lower() in titles}
            if {"district", "name", "number", "valid_from", "valid_to"} <= set(m):
                header = m
            continue
        if not any(cells):
            continue
        g = lambda k: row[header[k]] if k in header and header[k] < len(row) else None  # noqa: E731
        line = i + 1
        dname, name, number = str(g("district") or "").strip(), str(g("name") or "").strip(), str(g("number") or "").strip()
        if name.startswith('"Namuna"') and number == "1234":
            continue  # shablondagi namuna qatori
        d = by_dname.get(name_key(dname))
        stir = _digits(g("stir"))
        account, mfo = _digits(g("account")), _digits(g("mfo"))
        ctype = TYPES.get(str(g("type") or "kub").strip().lower())
        vf, vt, signed = _date(g("valid_from")), _date(g("valid_to")), _date(g("signed_on"))
        price, volume = _dec(g("price")), _dec(g("annual_volume"))
        lat, lng = _dec(g("lat")), _dec(g("lng"))
        err = None
        if not d:
            err = "district_not_found"
        elif scope is not None and d.id not in scope:
            err = "out_of_scope"
        elif len(name) < 2:
            err = "name_required"
        elif len(stir) != 9:
            err = "stir"
        elif not str(g("director") or "").strip():
            err = "director_required"
        elif len(_digits(g("phone"))[-9:]) != 9:
            err = "phone"
        elif not str(g("legal_address") or "").strip():
            err = "legal_address_required"
        elif not str(g("bank") or "").strip():
            err = "bank_required"
        elif len(account) != 20:
            err = "account"
        elif len(mfo) != 5:
            err = "mfo"
        elif not number:
            err = "number_required"
        elif not ctype:
            err = "bad_type"
        elif not vf or not vt or not signed:
            err = "bad_date"
        elif ctype == ContractType.by_volume and not volume:
            err = "volume_required"
        elif (lat is None) != (lng is None):
            err = "coords_pair"  # koordinata ixtiyoriy, lekin ikkalasi birga
        elif lat is not None and coords_error(float(lat), float(lng)):
            err = f"coords_{coords_error(float(lat), float(lng))}"
        tariff, reason = None, str(g("price_reason") or "").strip() or None
        if not err and ctype == ContractType.by_volume:
            # Kub: ruxsat bo'lsa — shartnomadagi (eski) narx majburiy, ta'rifdan farq qilsa sababi bilan; aks holda — ta'rif
            tariff = await price_for(db, d.id, vf)
            if manual:
                if not price:
                    err = "price_required"
                elif price != tariff and (not reason or len(reason) < 3):
                    err = "price_reason_required"
            else:
                price, reason = tariff, None
                if not price:
                    err = "no_tariff"
        if not err:
            cust = next((c for c in customers if c.district_id == d.id and ((stir and c.stir == stir) or c.name_key == name_key(name))), None)
            if stir and not cust:
                other = next((c for c in customers if c.stir == stir), None)
                if other:
                    err = "stir_taken"
            if not err:
                err = await _check(db, cust or Customer(id=None), number, str(g("platform_id") or "").strip() or None,
                                   ctype, price, vf, vt, seen_numbers)
        if err:
            errors.append({"line": line, "error": err, "value": number or name})
            continue
        seen_numbers.add(number)
        rows.append({"line": line, "district_id": d.id, "district": d.name, "name": name, "stir": stir or None, "number": number,
                     "type": ctype.value, "valid_from": vf, "valid_to": vt, "existing_customer": cust.id if cust else None,
                     "_cust": cust, "_data": {"director": str(g("director") or "").strip() or None, "phone": format_phone(str(g("phone") or "")),
                                             "legal_address": str(g("legal_address") or "").strip() or None,
                                             "address": str(g("address") or "").strip() or None, "bank": str(g("bank") or "").strip() or None,
                                             "mfo": mfo or None, "account": account or None, "oked": _digits(g("oked")) or None},
                     "_coords": (float(lat), float(lng)) if lat is not None else None,
                     "_contract": (str(g("platform_id") or "").strip() or None, price, volume, signed or vf,
                                   tariff, reason if tariff is None or price != tariff else None)})
    if header is None:
        raise invalid("bad_template", "Ustunlar topilmadi — shablondan foydalaning")
    created = 0
    if not dry_run and rows:
        fixed = await next_fixed_no_start(db)
        for r in rows:
            cust = r["_cust"]
            if cust is None:
                cust = Customer(fixed_no=f"A-{fixed:04d}", name=r["name"], name_key=name_key(r["name"]), district_id=r["district_id"],
                                stir=r["stir"], source="import", location_status=LocationStatus.none)
                fixed += 1
                db.add(cust)
                await db.flush()
                customers.append(cust)
            for k, v in r["_data"].items():
                if v and not getattr(cust, k):
                    setattr(cust, k, v)
            if r["stir"] and not cust.stir:
                cust.stir = r["stir"]
            if r["_coords"] and cust.location_status != LocationStatus.confirmed:
                # Exceldagi nuqta — shartnomadagi kabi «kutilmoqda» (manba legal); tasdiqlangan nuqtaga tegilmaydi
                cust.lat, cust.lng = r["_coords"]
                cust.location_status, cust.location_source = LocationStatus.pending, "legal"
            pid, price, volume, signed, tariff, reason = r["_contract"]
            c = _make(cust.id, actor, r["number"], "didox" if pid else None, pid, ContractType(r["type"]), price, volume, signed,
                      r["valid_from"], r["valid_to"], "electronic" if pid else "paper", "import")
            if c.type == ContractType.by_volume:
                c.tariff_price, c.price_reason = tariff, reason
            db.add(c)
            created += 1
        situation.activity(db, "act_contract_import", f"Excel'dan mavjud shartnomalar kiritildi (tasdiqqa): {created} ta ({file_name})",
                           params={"count": created, "file": file_name}, actor_id=actor.id)
        await db.commit()
    return {"dry_run": dry_run, "ok": len(rows), "total": len(rows) + len(errors), "created": created, "errors": errors,
            "rows": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows[:500]]}
