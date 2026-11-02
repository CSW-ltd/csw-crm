"""Buyurtma varaqasi: qog'oz ko'rinishi, chop etish (GPS), skan + maxfiy kod + yopish (legal), blok/qayta chop (manager)."""
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, get_storage, require_perm
from app.models import User
from app.schemas import RequestOut
from app.services import order_forms as svc
from app.services.storage import Storage

router = APIRouter(prefix="/order-forms", tags=["order-forms"])


class CodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=20)


class CloseIn(BaseModel):
    volume_m3: Decimal = Field(gt=0, le=1000, max_digits=8, decimal_places=2)
    waste_kind: str = Field(pattern="^(solid|liquid)$")


@router.get("/{form_id}")
async def paper(form_id: int, user: User = Depends(require_perm("orders.view")), db: AsyncSession = DB) -> dict:
    """Qog'oz ko'rinishi uchun (maxfiy kod yo'q)."""
    return await svc.paper(db, user, form_id)


@router.post("/{form_id}/print")
async def print_pdf(form_id: int, user: User = Depends(require_perm("orders.print")), db: AsyncSession = DB) -> Response:
    pdf, number = await svc.print_pdf(db, user, form_id)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="buyurtma-varaqasi-{number}.pdf"', "Cache-Control": "no-store"})


@router.post("/{form_id}/confirm-print")
async def confirm_print(form_id: int, user: User = Depends(require_perm("orders.print")), db: AsyncSession = DB) -> dict:
    """«Varaqa printerdan chiqdi» (agentsiz rejim). Printer agenti o'z endpointi orqali tasdiqlaydi (PR #20)."""
    req = await svc.confirm_printed(db, user, form_id, "manual")
    return {"request_id": req.id, "status": req.status.value, "form": svc.brief(req.order_form)}


@router.post("/{form_id}/allow-reprint")
async def allow_reprint(form_id: int, user: User = Depends(require_perm("orders.unlock")), db: AsyncSession = DB) -> dict:
    return svc.brief(await svc.allow_reprint(db, user, form_id))


@router.post("/{form_id}/unlock")
async def unlock(form_id: int, user: User = Depends(require_perm("orders.unlock")), db: AsyncSession = DB) -> dict:
    return svc.brief(await svc.unlock(db, user, form_id))


@router.post("/{form_id}/scan")
async def scan(form_id: int, file: UploadFile = File(...), user: User = Depends(require_perm("orders.close")), db: AsyncSession = DB,
               storage: Storage = Depends(get_storage)) -> dict:
    data = await file.read()
    return svc.brief(await svc.upload_scan(db, storage, user, form_id, data, file.content_type or ""))


@router.get("/{form_id}/scan")
async def scan_file(form_id: int, user: User = Depends(require_perm("orders.view")), db: AsyncSession = DB,
                    storage: Storage = Depends(get_storage)) -> Response:
    data, ctype = await svc.scan_file(db, storage, user, form_id)
    return Response(data, media_type=ctype, headers={"Cache-Control": "private, max-age=600"})


@router.post("/{form_id}/verify")
async def verify(form_id: int, body: CodeIn, user: User = Depends(require_perm("orders.close")), db: AsyncSession = DB) -> dict:
    return await svc.verify(db, user, form_id, body.code)


@router.post("/{form_id}/close", response_model=RequestOut)
async def close(form_id: int, body: CloseIn, user: User = Depends(require_perm("orders.close")), db: AsyncSession = DB):
    return await svc.close(db, user, form_id, body.volume_m3, body.waste_kind)
