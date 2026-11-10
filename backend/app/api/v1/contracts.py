"""«Yangi shartnoma» jarayoni: forma → tekshirish → hujjat (PDF/DOCX) → imzolandi → buxgalter tasdig'i yoki qaytarish."""
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, get_storage, require_perm
from app.models import User
from app.services import contracts as svc
from app.services import contracts_import as imp
from app.services.storage import Storage

router = APIRouter(prefix="/contracts", tags=["contracts"])
Legal = Depends(require_perm("customers.contract"))
Viewer = Depends(require_perm("customers.contract", "accounting.view"))
Accountant = Depends(require_perm("accounting.payments"))


def _file(data: bytes, ctype: str, name: str, inline: bool = True) -> Response:
    disp = "inline" if inline else "attachment"
    return Response(data, media_type=ctype, headers={"Content-Disposition": f"{disp}; filename*=UTF-8''{quote(name)}",
                                                     "Cache-Control": "private, no-store"})


@router.post("/check")
async def check(body: svc.ContractDraftIn, user: User = Legal, db: AsyncSession = DB) -> dict:
    """«Tekshirish»: majburiy maydonlar, formatlar, STIR, muddatlar va ustma-ust faol shartnoma; jami summa va QQS."""
    return await svc.check(db, user, body)


@router.post("/{contract_id}/check")
async def check_existing(contract_id: int, body: svc.ContractDraftIn, user: User = Legal, db: AsyncSession = DB) -> dict:
    ct = await svc.get(db, user, contract_id)
    body.customer_id = ct.customer_id
    return await svc.check(db, user, body, own_id=ct.id)


@router.post("", status_code=201)
async def create(body: svc.ContractDraftIn, user: User = Legal, db: AsyncSession = DB) -> dict:
    return svc.out(await svc.create(db, user, body), with_events=True)


# --- mavjud (qo'lda tuzilgan) shartnomalarni kiritish ---
@router.post("/existing", status_code=201)
async def create_existing(body: svc.ContractDraftIn, user: User = Legal, db: AsyncSession = DB, storage: Storage = Depends(get_storage)) -> dict:
    """Mavjud shartnoma: to'liq ma'lumot (rekvizitlar, shartlar + raqam, imzolangan sana, platforma ID) → buxgalter tasdig'iga."""
    return svc.out(await svc.create_existing(db, storage, user, body), with_events=True)


@router.get("/existing/template")
async def existing_template(user: User = Legal) -> Response:
    return _file(imp.template_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "mavjud_shartnomalar_shablon.xlsx",
                 inline=False)


@router.post("/existing/import")
async def existing_import(dry_run: bool = True, file: UploadFile = File(...), user: User = Legal, db: AsyncSession = DB) -> dict:
    """Excel: avval dry_run=true (xatolar ro'yxati), keyin dry_run=false."""
    return await imp.import_file(db, user, file.filename or "shartnomalar.xlsx", await file.read(), dry_run)


@router.post("/{contract_id}/scan-upload")
async def scan_upload(contract_id: int, file: UploadFile = File(...), user: User = Legal, db: AsyncSession = DB,
                      storage: Storage = Depends(get_storage)) -> dict:
    """Mavjud shartnoma skanini biriktirish."""
    return svc.out(await svc.attach_scan(db, storage, user, contract_id, (await file.read(), file.content_type or "", file.filename or "")),
                   with_events=True)


class StartIn(BaseModel):
    customer_id: int
    appeal_id: int | None = None  # yangi korxona murojaatidan


@router.post("/start", status_code=201)
async def start(body: StartIn, user: User = Legal, db: AsyncSession = DB) -> dict:
    """Usta: korxona tanlandi — tugallanmagan loyiha (raqamsiz) yaratiladi."""
    return svc.out(await svc.start(db, user, body.customer_id, body.appeal_id), with_events=True)


@router.get("/lookup")
async def lookup(stir: str = Query(pattern=r"^\d{9}$"), user: User = Legal, db: AsyncSession = DB) -> dict:
    """STIR bo'yicha korxona va amaldagi shartnoma (bo'lsa — qo'shimcha shartnoma taklif qilinadi)."""
    return await svc.lookup(db, user, stir)


@router.post("/requests", status_code=201)
async def create_request(body: svc.RequestIn, user: User = Legal, db: AsyncSession = DB) -> dict:
    """Mavjud kontragent: qo'shimcha shartnoma (buxgalterga), yangi filial yoki manzil o'zgartirish (GPS'ga) so'rovi."""
    r = await svc.create_request(db, user, body)
    return {"id": r.id, "kind": r.kind, "status": r.status, "contract_id": r.contract_id, "customer_id": r.customer_id}


@router.get("/requests")
async def list_requests(kind: str | None = Query(None, pattern="^(amendment|branch|address)$"),
                        status: str | None = Query(None, pattern="^(new|done|cancelled)$"),
                        user: User = Depends(require_perm("customers.contract", "accounting.view", "requests.view")),
                        db: AsyncSession = DB) -> list[dict]:
    """So'rovlar navbati (buxgalter — qo'shimcha shartnoma, GPS — filial/manzil; 2–3-qismlarda bajariladi)."""
    return await svc.list_requests(db, user, kind, status)


@router.post("/counterparty", status_code=201)
async def counterparty(body: svc.CounterpartyIn, user: User = Legal, db: AsyncSession = DB) -> dict:
    """Kontragent → korxona: STIR bazada bo'lsa o'sha, aks holda rekvizitlardan yangi korxona."""
    c = await svc.counterparty(db, user, body)
    return {"id": c.id, "name": c.name, "district_id": c.district_id, "code": c.code}


@router.put("/{contract_id}/draft")
async def save_draft(contract_id: int, body: svc.ContractDraftIn, user: User = Legal, db: AsyncSession = DB) -> dict:
    """Formani tekshiruvsiz saqlash (usta yopilganda / «Orqaga»)."""
    return svc.out(await svc.save_draft(db, user, contract_id, body), with_events=True)


@router.get("")
async def search(status: str | None = Query(None, max_length=40), q: str | None = Query(None, max_length=100), district_id: int | None = None,
                 limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), user: User = Viewer, db: AsyncSession = DB) -> dict:
    rows, total = await svc.search(db, user, status, q, district_id, limit, offset)
    used = await svc.used_m3(db, rows)
    return {"items": [svc.out(c, used.get(c.id)) for c in rows], "total": total}


@router.get("/{contract_id}")
async def get(contract_id: int, user: User = Viewer, db: AsyncSession = DB) -> dict:
    ct = await svc.get(db, user, contract_id)
    return svc.out(ct, (await svc.used_m3(db, [ct])).get(ct.id), with_events=True)


@router.put("/{contract_id}")
async def update(contract_id: int, body: svc.ContractDraftIn, user: User = Legal, db: AsyncSession = DB) -> dict:
    return svc.out(await svc.update(db, user, contract_id, body), with_events=True)


class DeleteIn(BaseModel):
    reason: str = Field("", max_length=500)


@router.post("/{contract_id}/delete", status_code=204)
async def delete(contract_id: int, body: DeleteIn, user: User = Legal, db: AsyncSession = DB) -> Response:
    """Tugallanmagan shartnomani izoh bilan o'chirish (arxivga)."""
    await svc.delete_draft(db, user, contract_id, body.reason)
    return Response(status_code=204)


@router.get("/{contract_id}/document")
async def document(contract_id: int, format: str = Query("pdf", pattern="^(pdf|docx)$"), user: User = Viewer,
                   db: AsyncSession = DB) -> Response:
    data, ctype, name = await svc.document(db, user, contract_id, format)
    return _file(data, ctype, name, inline=format == "pdf")


@router.post("/{contract_id}/sign")
async def sign(contract_id: int, signed_on: date = Form(...), sign_method: str = Form(...), platform: str | None = Form(None),
               platform_id: str | None = Form(None, max_length=40), file: UploadFile | None = File(None), user: User = Legal,
               db: AsyncSession = DB, storage: Storage = Depends(get_storage)) -> dict:
    """«Imzolandi — buxgalteriyaga yuborish». Shu paytdan shartnoma faol (murojaat ochiladi), hisob-kitob — buxgalter tasdig'idan keyin."""
    f = (await file.read(), file.content_type or "", file.filename or "") if file and file.filename else None
    return svc.out(await svc.sign(db, storage, user, contract_id, signed_on, sign_method, platform, platform_id, f), with_events=True)


@router.get("/{contract_id}/scan")
async def scan(contract_id: int, user: User = Viewer, db: AsyncSession = DB, storage: Storage = Depends(get_storage)) -> Response:
    data, ctype, name = await svc.scan(db, storage, user, contract_id)
    return _file(data, ctype, name)


class ReturnIn(BaseModel):
    comment: str = Field(min_length=3, max_length=500)


@router.post("/{contract_id}/approve")
async def approve(contract_id: int, user: User = Accountant, db: AsyncSession = DB) -> dict:
    return svc.out(await svc.approve(db, user, contract_id), with_events=True)


@router.post("/{contract_id}/return")
async def return_(contract_id: int, body: ReturnIn, user: User = Accountant, db: AsyncSession = DB) -> dict:
    return svc.out(await svc.return_(db, user, contract_id, body.comment), with_events=True)
