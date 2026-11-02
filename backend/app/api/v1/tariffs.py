"""Ta'riflar (1 m³ narxi, QQS bilan): ko'rish — admin, manager, legal, buxgalter; o'zgartirish — admin va manager (o'z tumanlari)."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, require_roles
from app.db.base import utcnow
from app.models import User
from app.models.enums import Role
from app.services import tariffs as svc
from app.services.billing import local_day

router = APIRouter(prefix="/tariffs", tags=["tariffs"])
Viewer = Depends(require_roles(Role.admin, Role.manager, Role.legal, Role.accountant))
Editor = Depends(require_roles(Role.admin, Role.manager))
Admin = Depends(require_roles(Role.admin))


class TariffIn(BaseModel):
    region_id: int | None = None
    district_id: int | None = None
    price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    valid_from: date
    note: str | None = Field(None, max_length=255)


class LockIn(BaseModel):
    region_id: int | None = None
    district_id: int | None = None
    locked: bool


@router.get("")
async def overview(user: User = Viewer, db: AsyncSession = DB) -> dict:
    return await svc.overview(db, user, local_day(utcnow()))


@router.get("/price")
async def price(district_id: int, day: date | None = None, user: User = Viewer, db: AsyncSession = DB) -> dict:
    """Shartnoma formasi uchun: tumanning shu kundagi ta'rifi."""
    p = await svc.price_for(db, district_id, day or local_day(utcnow()))
    return {"district_id": district_id, "price": float(p) if p is not None else None}


@router.post("", status_code=201)
async def set_price(body: TariffIn, user: User = Editor, db: AsyncSession = DB) -> dict:
    t = await svc.set_price(db, user, body.region_id, body.district_id, body.price, body.valid_from, body.note)
    return {"id": t.id, "price": float(t.price), "valid_from": t.valid_from}


@router.delete("/{tariff_id}", status_code=204)
async def remove(tariff_id: int, user: User = Editor, db: AsyncSession = DB) -> Response:
    await svc.remove(db, user, tariff_id, local_day(utcnow()))
    return Response(status_code=204)


@router.put("/lock", status_code=204)
async def lock(body: LockIn, user: User = Admin, db: AsyncSession = DB) -> Response:
    """Admin: managerga ta'rifni o'zgartirishni viloyat yoki tuman bo'yicha yopish / ochish."""
    await svc.set_lock(db, user, body.region_id, body.district_id, body.locked)
    return Response(status_code=204)
