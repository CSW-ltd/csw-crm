"""Oylik schyot-faktura: har korxonaga oyiga bitta (draft → sent). Narx QQS bilan, fakturada "shu jumladan QQS 12%".
Jo'natish: SMS (summa + PDF havola, maxfiy token). Didox / Soliq e-faktura integratsiyasi keyin (ERI kaliti kerak) — `send_efaktura`."""
import secrets
from datetime import date
from decimal import Decimal

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings, public_url
from app.core.errors import conflict, not_found
from app.db.base import utcnow
from app.models import Customer, District, Invoice, InvoiceLine, Provider, User
from app.services import access, billing, situation, sms
from app.services.billing import ZERO, money, month_bounds


def vat_of(total: Decimal) -> Decimal:
    rate = Decimal(str(get_settings().vat_rate))
    return money(total * rate / (100 + rate))


def out(i: Invoice, with_lines: bool = False) -> dict:
    d = {"id": i.id, "number": i.number, "customer_id": i.customer_id, "customer_name": i.customer.name if i.customer else None,
         "code": i.customer.code if i.customer else None, "district_id": i.customer.district_id if i.customer else None,
         "period": i.period, "status": i.status, "total": float(i.total), "vat": float(i.vat), "sent_at": i.sent_at,
         "sms_phone": i.sms_phone, "lines_count": sum(1 for x in i.lines if x.kind != "annex"),
         "forms_count": sum(1 for x in i.lines if x.kind in ("form", "annex"))}
    if with_lines:
        d["lines"] = [{"kind": x.kind, "day": x.day, "description": x.description, "qty": float(x.qty), "unit": x.unit,
                       "price": float(x.price), "amount": float(x.amount)} for x in i.lines]
    return d


async def _provider_for(db: AsyncSession, district_id: int) -> Provider | None:
    d = await db.get(District, district_id)
    return (await db.execute(select(Provider).where(Provider.region_id == d.region_id))).scalar_one_or_none() if d else None


async def list_month(db: AsyncSession, actor: User, month: date, district_id: int | None = None) -> list[Invoice]:
    start, _ = month_bounds(month)
    q = select(Invoice).where(Invoice.period == start).options(selectinload(Invoice.customer)).order_by(Invoice.number)
    s = access.scope(actor)
    cond = []
    if s is not None:
        cond.append(Customer.district_id.in_(s or {-1}))
    if district_id:
        cond.append(Customer.district_id == district_id)
    if cond:
        q = q.where(Invoice.customer_id.in_(select(Customer.id).where(*cond)))
    return list((await db.execute(q)).scalars())


async def generate(db: AsyncSession, actor: User, month: date) -> dict:
    """Tanlangan oy uchun har korxonaga bitta faktura. Yuborilmaganlari qayta yaratiladi, yuborilganlariga tegilmaydi."""
    start, end = month_bounds(month)
    custs = await billing.scoped_customers(db, actor, only_contracted=True)
    led = await billing.load(db, custs)
    existing = {i.customer_id: i for i in (await db.execute(select(Invoice).where(Invoice.period == start))).scalars()}
    created = updated = skipped_sent = 0
    seq = (await db.execute(select(Invoice.number).where(Invoice.period == start))).scalars().all()
    next_no = max([int(n.rsplit("-", 1)[1]) for n in seq] or [0]) + 1
    for c in custs:
        lines = billing.month_lines(led, c.id, start)
        total = sum((x["amount"] for x in lines), ZERO)
        inv = existing.get(c.id)
        if inv and inv.status == "sent":
            skipped_sent += 1
            continue
        if not lines or total <= 0:
            if inv:
                await db.delete(inv)
            continue
        if inv is None:
            inv = Invoice(number=f"SF-{start.year}-{start.month:02d}-{next_no:05d}", customer_id=c.id, period=start,
                          token=secrets.token_urlsafe(32), created_by_id=actor.id, total=0, vat=0, lines=[])
            next_no += 1
            db.add(inv)
            created += 1
        else:
            inv.lines.clear()
            updated += 1
        prov = await _provider_for(db, c.district_id)
        inv.provider_id = prov.id if prov else None
        inv.total, inv.vat = total, vat_of(total)
        for x in lines:
            inv.lines.append(InvoiceLine(kind=x["kind"], request_id=x["request_id"], day=x["day"], description=x["description"][:255],
                                         qty=x["qty"], unit=x["unit"], price=x["price"], amount=x["amount"]))
        await db.flush()
    situation.activity(db, "act_invoices_generated", f"Oy yopildi: {start.strftime('%m.%Y')} — yaratildi {created}, yangilandi {updated}",
                       params={"month": str(start), "created": created, "updated": updated}, actor_id=actor.id)
    await db.commit()
    # Imzolangan, lekin buxgalter tasdiqlamagan shartnomalar bo'yicha varaqalar fakturaga kirmadi — ogohlantirish
    pending = sum(1 for c in custs for g in led.greens[c.id] if g.pending and start <= g.day <= end)
    return {"month": start, "created": created, "updated": updated, "skipped_sent": skipped_sent, "pending_forms": pending}


def start_of(month: date) -> str:
    return month_bounds(month)[0].strftime("%m.%Y")


def link(inv: Invoice) -> str:
    return f"{public_url()}/api/v1/public/invoices/{inv.token}"


async def send_all(db: AsyncSession, actor: User, month: date) -> dict:
    """Hamma yuborilmagan fakturalar: SMS (summa + PDF havola), status "sent" — keyin o'zgarmaydi."""
    invs = [i for i in await list_month(db, actor, month) if i.status == "draft"]
    sent = no_phone = 0
    for inv in invs:
        phone = inv.customer.phone
        inv.status, inv.sent_at, inv.sent_by_id, inv.sms_phone = "sent", utcnow(), actor.id, phone
        if phone:
            total = f"{int(inv.total):,}".replace(",", " ")
            sms.send_later(phone, f"Schyot-faktura {inv.number} ({inv.period.strftime('%m.%Y')}): {total} so'm, shu jumladan QQS. "
                                  f"Yuklab olish: {link(inv)}")
            sent += 1
        else:
            no_phone += 1
    situation.activity(db, "act_invoices_sent", f"Schyot-fakturalar jo'natildi: {len(invs)} ta ({start_of(month)})",
                       params={"count": len(invs), "sms": sent, "month": start_of(month)}, actor_id=actor.id)
    await db.commit()
    return {"sent": sent, "no_phone": no_phone, "total": len(invs)}


async def by_id(db: AsyncSession, actor: User | None, invoice_id: int | None = None, token: str | None = None) -> Invoice:
    q = select(Invoice).options(selectinload(Invoice.customer))
    q = q.where(Invoice.id == invoice_id) if invoice_id is not None else q.where(Invoice.token == token)
    inv = (await db.execute(q)).scalar_one_or_none()
    if not inv or (token is not None and inv.status != "sent"):
        raise not_found("invoice")
    if actor is not None:
        access.check_scope(actor, inv.customer.district_id)
    return inv


async def pdf(db: AsyncSession, inv: Invoice) -> bytes:
    from app.services.invoice_pdf import render
    prov = await db.get(Provider, inv.provider_id) if inv.provider_id else None
    return await run_in_threadpool(render, inv, inv.customer, prov)


async def ensure_draft(inv: Invoice) -> None:
    if inv.status == "sent":
        raise conflict("invoice_sent", "Faktura yuborilgan — o'zgartirib bo'lmaydi")
