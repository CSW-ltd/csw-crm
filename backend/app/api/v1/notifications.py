"""Xodimning shaxsiy bildirishnomalari (qo'ng'iroqcha)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, current_user
from app.models import User
from app.services import notifications as svc

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def mine(user: User = Depends(current_user), db: AsyncSession = DB) -> dict:
    return await svc.mine(db, user)


class ReadIn(BaseModel):
    ids: list[int] | None = Field(None, max_length=500)  # bo'sh — hammasi o'qildi


@router.post("/read", status_code=204)
async def read(body: ReadIn, user: User = Depends(current_user), db: AsyncSession = DB) -> None:
    await svc.mark_read(db, user, body.ids)
