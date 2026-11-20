"""GPS dispatch (docs/plans/gps-dispatch.md). PR-A: admin uchun GPS eksport importi (geozonalar, mahallalar, mashina bog'lanishi)."""
import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, require_perm
from app.core.errors import invalid
from app.models import User
from app.services.gps import importer

router = APIRouter(prefix="/dispatch", tags=["dispatch"])
Import = Depends(require_perm("dispatch.import"))


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
