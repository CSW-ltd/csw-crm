"""Vaziyat paneli: admin va manager uchun hodisalar jurnali.

Ishlatish: `situation.add(db, ...)` hodisani sessiyaga qo'shadi, `await situation.commit(db)` saqlab,
Socket.IO orqali "managers" xonasiga jonli yuboradi. Hodisa biznes amali bilan bitta tranzaksiyada yoziladi.
"""
import json
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app import realtime
from app.db.base import utcnow
from app.models import SituationEvent
from app.models.enums import SituationLevel

RETENTION_DAYS = 90
_PENDING = "situation_pending"


def add(db: AsyncSession, level: SituationLevel, kind: str, message: str, *, params: dict | None = None,
        district_id: int | None = None, actor_id: int | None = None, ref: tuple[str, int] | None = None) -> SituationEvent:
    ev = SituationEvent(level=level, kind=kind, message=message[:500], params=json.dumps(params, ensure_ascii=False) if params else None,
                        district_id=district_id, actor_id=actor_id, ref_type=ref[0] if ref else None, ref_id=ref[1] if ref else None)
    db.add(ev)
    db.info.setdefault(_PENDING, []).append(ev)
    return ev


def activity(db: AsyncSession, kind: str, message: str, *, params: dict | None = None, district_id: int | None = None,
             actor_id: int | None = None, ref: tuple[str, int] | None = None) -> SituationEvent:
    """Faoliyat jurnali: tuman xodimlari bajargan har bir amal. Jonli yuborilmaydi, o'qilmaganlar soniga kirmaydi.
    Biznes amali bilan bitta tranzaksiyada (chaqiruvchi commit qiladi)."""
    ev = SituationEvent(level=SituationLevel.activity, kind=kind, message=message[:500],
                        params=json.dumps(params, ensure_ascii=False, default=str) if params else None,
                        district_id=district_id, actor_id=actor_id, ref_type=ref[0] if ref else None, ref_id=ref[1] if ref else None)
    db.add(ev)
    return ev


def payload(ev: SituationEvent) -> dict:
    return {"id": ev.id, "level": ev.level.value, "kind": ev.kind, "message": ev.message,
            "params": json.loads(ev.params) if ev.params else {}, "district_id": ev.district_id, "actor_id": ev.actor_id,
            "ref_type": ev.ref_type, "ref_id": ev.ref_id, "created_at": ev.created_at.isoformat()}


async def publish(db: AsyncSession) -> None:
    """Commit'dan keyin: navbatdagi hodisalarni jonli yuborish."""
    for ev in db.info.pop(_PENDING, []):
        await realtime.emit_situation(payload(ev))


async def commit(db: AsyncSession) -> None:
    await db.commit()
    await publish(db)


def discard(db: AsyncSession) -> None:
    db.info.pop(_PENDING, None)


async def purge_old(db: AsyncSession, days: int = RETENTION_DAYS) -> int:
    res = await db.execute(delete(SituationEvent).where(SituationEvent.created_at < utcnow() - timedelta(days=days)))
    await db.commit()
    return res.rowcount or 0
