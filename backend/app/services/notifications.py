"""Xodimga shaxsiy bildirishnomalar (qo'ng'iroqcha): masalan, GPS joylashuvni o'zgartirdi — shartnomani kiritgan legal'ga.
add() — biznes amali bilan bitta tranzaksiyada; publish() — commit'dan keyin jonli yuborish (Socket.IO, user:{id} xonasi)."""
import json

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models import Notification, User

_PENDING = "notifications_pending"


def add(db: AsyncSession, user_id: int, kind: str, message: str, *, params: dict | None = None, actor_id: int | None = None,
        ref: tuple[str, int] | None = None) -> Notification:
    n = Notification(user_id=user_id, kind=kind, message=message[:500], actor_id=actor_id,
                     params=json.dumps(params, ensure_ascii=False, default=str) if params else None,
                     ref_type=ref[0] if ref else None, ref_id=ref[1] if ref else None)
    db.add(n)
    db.info.setdefault(_PENDING, []).append(n)
    return n


def payload(n: Notification, actor_name: str | None = None) -> dict:
    return {"id": n.id, "kind": n.kind, "message": n.message, "params": json.loads(n.params) if n.params else None,
            "actor": actor_name, "ref_type": n.ref_type, "ref_id": n.ref_id, "read": n.read_at is not None, "created_at": n.created_at}


async def publish(db: AsyncSession) -> None:
    from app import realtime
    rows = db.info.pop(_PENDING, [])
    for n in rows:
        actor = await db.get(User, n.actor_id) if n.actor_id else None
        try:
            await realtime.emit_notification(n.user_id, payload(n, actor.full_name if actor else None))
        except Exception:  # noqa: BLE001 — jonli yuborish ixtiyoriy, bildirishnoma bazada bor
            pass


async def mine(db: AsyncSession, user: User, limit: int = 50) -> dict:
    rows = (await db.execute(select(Notification, User.full_name).outerjoin(User, User.id == Notification.actor_id)
                             .where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(limit))).all()
    unread = (await db.execute(select(func.count()).select_from(Notification)
                               .where(Notification.user_id == user.id, Notification.read_at.is_(None)))).scalar_one()
    return {"unread": unread, "items": [payload(n, name) for n, name in rows]}


async def mark_read(db: AsyncSession, user: User, ids: list[int] | None) -> None:
    q = update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if ids:
        q = q.where(Notification.id.in_(ids))
    await db.execute(q.values(read_at=utcnow()))
    await db.commit()
