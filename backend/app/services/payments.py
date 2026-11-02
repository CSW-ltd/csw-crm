"""To'lovlar (buxgalter): qo'lda kiritish, bekor qilish (o'chirilmaydi), bank ko'chirmasidan import (avval sinov)."""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import conflict, invalid, not_found
from app.db.base import utcnow
from app.models import Customer, Payment, User
from app.services import access, situation


def out(p: Payment) -> dict:
    return {"id": p.id, "customer_id": p.customer_id, "customer_name": p.customer.name if p.customer else None,
            "code": p.customer.code if p.customer else None, "paid_on": p.paid_on, "amount": float(p.amount), "doc_no": p.doc_no,
            "note": p.note, "source": p.source, "created_at": p.created_at, "cancelled": p.cancelled_at is not None,
            "cancel_reason": p.cancel_reason}


async def _customer(db: AsyncSession, actor: User, customer_id: int) -> Customer:
    c = await db.get(Customer, customer_id)
    if not c:
        raise not_found("customer")
    access.check_scope(actor, c.district_id)
    return c


async def create(db: AsyncSession, actor: User, customer_id: int, paid_on: date, amount: Decimal, doc_no: str | None,
                 note: str | None) -> Payment:
    await _customer(db, actor, customer_id)
    if amount <= 0:
        raise invalid("bad_amount", "Summa musbat bo'lsin")
    p = Payment(customer_id=customer_id, paid_on=paid_on, amount=amount, doc_no=(doc_no or "").strip() or None,
                note=(note or "").strip() or None, source="manual", created_by_id=actor.id)
    db.add(p)
    cust = await db.get(Customer, customer_id)
    situation.activity(db, "act_payment", f"To'lov kiritildi: «{cust.name}» {amount} so'm ({paid_on})",
                       params={"customer": cust.name, "amount": float(amount), "paid_on": str(paid_on), "doc": doc_no},
                       district_id=cust.district_id, actor_id=actor.id, ref=("customer", cust.id))
    await db.commit()
    return await by_id(db, p.id)


async def by_id(db: AsyncSession, pid: int) -> Payment:
    p = (await db.execute(select(Payment).where(Payment.id == pid).options(selectinload(Payment.customer)))).scalar_one_or_none()
    if not p:
        raise not_found("payment")
    return p


async def cancel(db: AsyncSession, actor: User, pid: int, reason: str) -> Payment:
    p = await by_id(db, pid)
    access.check_scope(actor, p.customer.district_id)
    if p.cancelled_at:
        raise conflict("payment_cancelled", "To'lov allaqachon bekor qilingan")
    p.cancelled_at, p.cancelled_by_id, p.cancel_reason = utcnow(), actor.id, reason.strip()
    situation.activity(db, "act_payment_cancelled", f"To'lov bekor qilindi: «{p.customer.name}» {p.amount} so'm — {p.cancel_reason}",
                       params={"customer": p.customer.name, "amount": float(p.amount), "reason": p.cancel_reason},
                       district_id=p.customer.district_id, actor_id=actor.id, ref=("customer", p.customer_id))
    await db.commit()
    return await by_id(db, pid)


async def search(db: AsyncSession, actor: User, q: str | None, date_from: date | None, date_to: date | None, customer_id: int | None,
                 limit: int, offset: int) -> tuple[list[Payment], int, float]:
    cond = []
    s = access.scope(actor)
    if s is not None:
        cond.append(Payment.customer_id.in_(select(Customer.id).where(Customer.district_id.in_(s or {-1}))))
    if customer_id:
        cond.append(Payment.customer_id == customer_id)
    if date_from:
        cond.append(Payment.paid_on >= date_from)
    if date_to:
        cond.append(Payment.paid_on <= date_to)
    if q and q.strip():
        t = q.strip()
        cond.append(or_(Payment.doc_no == t, Payment.customer_id.in_(select(Customer.id).where(
            (Customer.code == t.upper()) | Customer.name.ilike(f"%{t}%") | (Customer.stir == t)))))
    total = (await db.execute(select(func.count()).select_from(Payment).where(*cond))).scalar_one()
    active = (await db.execute(select(func.coalesce(func.sum(Payment.amount), 0)).where(*cond, Payment.cancelled_at.is_(None)))).scalar_one()
    rows = (await db.execute(select(Payment).where(*cond).options(selectinload(Payment.customer))
                             .order_by(Payment.paid_on.desc(), Payment.id.desc()).limit(limit).offset(offset))).scalars()
    return list(rows), total, float(active)


# --- bank ko'chirmasi importi ---
HEAD = {"code": ("maxsus", "code", "kod"), "stir": ("stir", "inn", "инн"), "date": ("sana", "дата", "date"),
        "amount": ("summa", "сумма", "amount"), "doc": ("hujjat", "документ", "doc", "№")}


def _num(v) -> Decimal | None:
    t = re.sub(r"[\s ']", "", str(v or "")).replace(",", ".")
    try:
        d = Decimal(t)
    except InvalidOperation:
        return None
    return d if d > 0 else None


def _date(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    t = str(v or "").strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(t[:10], fmt).date()
        except ValueError:
            pass
    return None


async def import_file(db: AsyncSession, actor: User, file_name: str, content: bytes, dry_run: bool) -> dict:
    from app.services.table_readers import read_tables
    _, tables = read_tables(file_name, content)
    s = access.scope(actor)
    customers = list((await db.execute(select(Customer))).scalars())
    by_code = {c.code: c for c in customers if c.code}
    by_stir = {c.stir: c for c in customers if c.stir}
    rows, errors = [], []
    for table in tables:
        header = None
        for i, row in enumerate(table.rows if hasattr(table, "rows") else table):
            cells = [str(x or "").strip().lower() for x in row]
            if header is None:
                found = {k: next((j for j, c in enumerate(cells) if any(n in c for n in needles)), None) for k, needles in HEAD.items()}
                if found["amount"] is not None and found["date"] is not None and (found["code"] is not None or found["stir"] is not None):
                    header = found
                continue
            get = lambda k: row[header[k]] if header[k] is not None and header[k] < len(row) else None  # noqa: E731
            if not any(str(x or "").strip() for x in row):
                continue
            code = str(get("code") or "").strip().upper()
            stir = re.sub(r"\D", "", str(get("stir") or ""))
            cust = by_code.get(code) or by_stir.get(stir)
            amount, day = _num(get("amount")), _date(get("date"))
            line = i + 1
            if not cust:
                errors.append({"line": line, "error": "customer_not_found", "value": code or stir})
            elif s is not None and cust.district_id not in s:
                errors.append({"line": line, "error": "out_of_scope", "value": cust.code})
            elif amount is None:
                errors.append({"line": line, "error": "bad_amount", "value": str(get("amount"))})
            elif day is None:
                errors.append({"line": line, "error": "bad_date", "value": str(get("date"))})
            else:
                rows.append({"line": line, "customer_id": cust.id, "name": cust.name, "code": cust.code, "paid_on": day,
                             "amount": float(amount), "doc_no": str(get("doc") or "").strip() or None})
        if header:
            break
    if not rows and not errors:
        raise invalid("bad_statement", "Ustunlar topilmadi: maxsus raqam yoki STIR, sana, summa")
    if not dry_run:
        for r in rows:
            db.add(Payment(customer_id=r["customer_id"], paid_on=r["paid_on"], amount=Decimal(str(r["amount"])), doc_no=r["doc_no"],
                           source="import", note=f"import: {file_name}"[:255], created_by_id=actor.id))
        situation.activity(db, "act_payment_import", f"Bank ko'chirmasidan to'lovlar: {len(rows)} ta, {sum(r['amount'] for r in rows)} so'm ({file_name})",
                           params={"count": len(rows), "total": sum(r["amount"] for r in rows), "file": file_name}, actor_id=actor.id)
        await db.commit()
    return {"dry_run": dry_run, "ok": len(rows), "errors": errors, "rows": rows[:200], "total": sum(r["amount"] for r in rows)}
