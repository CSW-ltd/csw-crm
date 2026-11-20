"""Buxgalteriya (vaqtincha tizim ichida): korxonalar debitor/kreditori, davrlarni solishtirish, yashil murojaatlar, to'lovlar."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, require_perm
from app.models import User
from app.services import billing, invoices, payments

router = APIRouter(prefix="/accounting", tags=["accounting"])
public_router = APIRouter(prefix="/public", tags=["public"])
View = Depends(require_perm("accounting.view"))
Pay = Depends(require_perm("accounting.payments"))


@router.get("/companies")
async def companies(q: str | None = Query(None, max_length=100), district_id: int | None = None, user: User = View,
                    db: AsyncSession = DB) -> dict:
    """Shartnomasi bor korxonalar: debitor, kreditor, jami kub (legal «Korxonalar» jadvali)."""
    return await billing.companies(db, user, q, district_id)


@router.get("/new-contracts")
async def new_contracts(district_id: int | None = None, user: User = View, db: AsyncSession = DB) -> dict:
    """Yangi shartnomalar: 7 kun, 15 kun, 1 oy, 6 oy, 1 yil — jami va tumanlar kesimida."""
    return await billing.new_contracts(db, user, district_id)


@router.get("/companies/{customer_id}/compare")
async def compare(customer_id: int, a_from: date, a_to: date, b_from: date, b_to: date, user: User = View, db: AsyncSession = DB) -> dict:
    return await billing.compare(db, user, customer_id, [(a_from, a_to), (b_from, b_to)])


@router.get("/companies/{customer_id}/green")
async def green(customer_id: int, user: User = View, db: AsyncSession = DB) -> dict:
    """Korxonaga xizmat ko'rsatilgan barcha yashil murojaatlar — har birining kubi bilan."""
    return await billing.green_list(db, user, customer_id)


class PaymentIn(BaseModel):
    customer_id: int
    paid_on: date
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    doc_no: str | None = Field(None, max_length=50)
    note: str | None = Field(None, max_length=255)
    force: bool = False  # takror ogohlantirishidan keyin «Baribir saqlash»


class CancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=255)


@router.get("/payments")
async def list_payments(q: str | None = Query(None, max_length=100), date_from: date | None = None, date_to: date | None = None,
                        customer_id: int | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                        user: User = View, db: AsyncSession = DB) -> dict:
    rows, total, s = await payments.search(db, user, q, date_from, date_to, customer_id, limit, offset)
    return {"items": [payments.out(p) for p in rows], "total": total, "sum": s}


@router.post("/payments", status_code=201)
async def create_payment(body: PaymentIn, user: User = Pay, db: AsyncSession = DB) -> dict:
    return payments.out(await payments.create(db, user, body.customer_id, body.paid_on, body.amount, body.doc_no, body.note,
                                              force=body.force))


@router.post("/payments/{payment_id}/cancel")
async def cancel_payment(payment_id: int, body: CancelIn, user: User = Pay, db: AsyncSession = DB) -> dict:
    return payments.out(await payments.cancel(db, user, payment_id, body.reason))


@router.post("/payments/import")
async def import_payments(dry_run: bool = True, include: str = Query("", max_length=4000), file: UploadFile = File(...),
                          user: User = Pay, db: AsyncSession = DB) -> dict:
    """Bank ko'chirmasi (xlsx/xls/csv): maxsus raqam yoki STIR, sana, summa, hujjat raqami. Avval dry_run=true.
    Aniq takrorlar yozilmaydi; `include` — yozilishi kerak bo'lgan ehtimoliy takror qatorlari (vergul bilan: "5,9")."""
    lines = [int(x) for x in include.split(",") if x.strip().isdigit()]
    return await payments.import_file(db, user, file.filename or "statement.xlsx", await file.read(), dry_run, lines)


# --- buyurtma varaqalari va oylik schyot-fakturalar ---
@router.get("/order-forms")
async def order_forms(month: date, district_id: int | None = None, customer_id: int | None = None, user: User = View,
                      db: AsyncSession = DB) -> dict:
    """Oy ichida yashil bo'lgan barcha buyurtma varaqalari — amaldagi shartnoma bo'yicha summasi bilan; korxonalar bo'yicha jami."""
    return await billing.month_forms(db, user, month, district_id, customer_id)


@router.get("/invoices")
async def list_invoices(month: date, district_id: int | None = None, user: User = View, db: AsyncSession = DB) -> dict:
    items = [invoices.out(i) for i in await invoices.list_month(db, user, month, district_id)]
    return {"month": billing.month_bounds(month)[0], "items": items, "total": sum(x["total"] for x in items),
            "drafts": sum(1 for x in items if x["status"] == "draft"), "sent": sum(1 for x in items if x["status"] == "sent")}


@router.post("/invoices/generate")
async def generate_invoices(month: date, user: User = Pay, db: AsyncSession = DB) -> dict:
    """Oyni yopish: har korxonaga bitta faktura (yuborilmaganlar qayta hisoblanadi, yuborilganlariga tegilmaydi)."""
    return await invoices.generate(db, user, month)


@router.post("/invoices/send")
async def send_invoices(month: date, user: User = Pay, db: AsyncSession = DB) -> dict:
    """Hammasiga jo'natish: SMS (summa + PDF havola). Yuborilgan faktura qulflanadi."""
    return await invoices.send_all(db, user, month)


@router.post("/invoices/{invoice_id}/mark-sent")
async def mark_invoice_sent(invoice_id: int, user: User = Pay, db: AsyncSession = DB) -> dict:
    """Telefoni yo'q korxona: PDF qo'lda topshirildi — raqam beriladi, faktura qulflanadi (SMS ketmaydi)."""
    return invoices.out(await invoices.mark_sent(db, user, invoice_id))


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: int, user: User = View, db: AsyncSession = DB) -> dict:
    return invoices.out(await invoices.by_id(db, user, invoice_id), with_lines=True)


@router.get("/invoices/{invoice_id}/pdf")
async def invoice_pdf(invoice_id: int, user: User = View, db: AsyncSession = DB) -> Response:
    inv = await invoices.by_id(db, user, invoice_id)
    return Response(await invoices.pdf(db, inv), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{inv.number or f"qoralama-{inv.id}"}.pdf"'})


@public_router.get("/invoices/{token}")
async def public_invoice(token: str, db: AsyncSession = DB) -> Response:
    """SMS havolasi: login talab qilmaydi, faqat yuborilgan faktura, token taxmin qilib bo'lmaydi (32 bayt)."""
    inv = await invoices.by_id(db, None, token=token)
    return Response(await invoices.pdf(db, inv), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{inv.number}.pdf"', "Cache-Control": "private, no-store",
                             "X-Robots-Tag": "noindex"})
