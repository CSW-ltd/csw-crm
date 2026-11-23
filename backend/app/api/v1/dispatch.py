"""GPS dispatch (docs/plans/gps-dispatch.md). PR-A: admin uchun GPS eksport importi (geozonalar, mahallalar, mashina bog'lanishi).
PR-B: SmartGPS/Wialon ulanishlari (token — faqat o'qish, shifrlangan), sinxronlash gps-worker'da."""
import json

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, require_perm
from app.core.errors import invalid
from app.gps import tokens
from app.models import User
from app.services.gps import connections, importer

router = APIRouter(prefix="/dispatch", tags=["dispatch"])
Import = Depends(require_perm("dispatch.import"))
Connect = Depends(require_perm("dispatch.connect"))


def _mapping(raw: str) -> dict[str, int]:
    """{"<bo'lim (tuman) nomi>": <CRM tuman id>} — JSON matn (multipart forma maydoni)."""
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        return {str(k): int(v) for k, v in data.items() if v not in (None, "", 0)}
    except (ValueError, TypeError, AttributeError):
        raise invalid("bad_mapping", "Tumanlar bog'lanishi noto'g'ri")


async def _bundle(file: UploadFile) -> importer.Bundle:
    return importer.read_zip(await file.read(importer.MAX_ZIP + 1))


@router.post("/import/preview")
async def import_preview(file: UploadFile = File(...), mapping: str = Form(""), user: User = Import, db: AsyncSession = DB) -> dict:
    """Tekshirish (bazaga yozmaydi): geozonalar soni va o'zgarishlar, har bo'lim bo'yicha mahalla/tayoqcha/mashina sonlari."""
    return await importer.analyze(db, await _bundle(file), _mapping(mapping))


@router.post("/import/apply")
async def import_apply(file: UploadFile = File(...), mapping: str = Form(...), user: User = Import, db: AsyncSession = DB) -> dict:
    """Import: tanlangan bo'limlar CRM tumanlariga bog'lanadi. Qayta import — faqat o'zgarganlari."""
    return await importer.apply(db, user, await _bundle(file), _mapping(mapping))


@router.get("/summary")
async def summary(user: User = Import, db: AsyncSession = DB) -> dict:
    """Tumanlar bo'yicha import holati: mahallalar, tayoqchalar, chegaralar, GPS'ga bog'langan mashinalar."""
    return await importer.summary(db)


# --- PR-B: GPS ulanishlari ---
class SourceIn(BaseModel):
    system: str = Field(pattern="^(smartgps|wialon)$")
    server: str = Field(min_length=3, max_length=120)
    account: str = Field(min_length=1, max_length=100)
    district_id: int | None = None
    unit_group: str | None = Field(default=None, max_length=150)


class SourcePatch(BaseModel):
    district_id: int | None = None
    unit_group: str | None = Field(default=None, max_length=150)
    account: str | None = Field(default=None, max_length=100)
    backup_account: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@router.get("/sources")
async def sources(user: User = Connect, db: AsyncSession = DB) -> dict:
    """Ulanishlar, token holati, oxirgi sinxronlash va worker holati (heartbeat)."""
    return await connections.overview(db)


@router.post("/sources")
async def create_source(body: SourceIn, user: User = Connect, db: AsyncSession = DB) -> dict:
    src = await connections.create(db, user, body.system, body.server, body.account, body.district_id, body.unit_group)
    return {"id": src.id}


@router.patch("/sources/{source_id}")
async def update_source(source_id: int, body: SourcePatch, user: User = Connect, db: AsyncSession = DB) -> dict:
    await connections.update(db, source_id, body.model_dump(exclude_unset=True))
    return {"ok": True}


@router.get("/sources/{source_id}/connect-url")
async def connect_url(source_id: int, redirect: str, request: Request, user: User = Connect, db: AsyncSession = DB) -> dict:
    """SmartGPS'ning o'z kirish sahifasi (foydalanuvchi o'zi kiradi, parol CRM'ga kelmaydi). Token redirect bilan qaytadi."""
    src = await connections._get(db, source_id)
    return {"url": connections.connect_url(src, redirect, request.headers.get("host"))}


@router.put("/sources/{source_id}/token")
async def set_token(source_id: int, body: TokenIn, slot: str = "main", user: User = Connect, db: AsyncSession = DB) -> dict:
    """Tokenni shifrlab saqlaydi (slot: main | backup); tekshiruv (egasi, faqat o'qish huquqi) va sinxronlash — gps-worker'da."""
    src = await connections.set_token(db, user, source_id, body.token, slot)
    return {"token_status": tokens.status(src, slot)}


@router.delete("/sources/{source_id}/token")
async def clear_token(source_id: int, slot: str = "main", user: User = Connect, db: AsyncSession = DB) -> dict:
    await connections.clear_token(db, user, source_id, slot)
    return {"ok": True}


@router.post("/sources/{source_id}/sync")
async def request_sync(source_id: int, user: User = Connect, db: AsyncSession = DB) -> dict:
    await connections.request_sync(db, source_id)
    return {"ok": True}


@router.get("/sources/{source_id}/log")
async def sync_log(source_id: int, user: User = Connect, db: AsyncSession = DB) -> list[dict]:
    return await connections.logs(db, source_id)
