from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ActFile, Customer, Request
from app.models.enums import ACTIVE_REQUEST_STATUSES, FileKind, RequestStatus


def _with_details(q):
    return q.options(
        selectinload(Request.customer).selectinload(Customer.district),
        selectinload(Request.customer).selectinload(Customer.contracts),
        selectinload(Request.contract),
        selectinload(Request.shift),
        selectinload(Request.vehicle),
        selectinload(Request.driver),
        selectinload(Request.order_form),
    )


async def by_id(db: AsyncSession, request_id: int, lock: bool = False) -> Request | None:
    q = _with_details(select(Request).where(Request.id == request_id))
    if lock:
        q = q.with_for_update()
    return (await db.execute(q)).scalar_one_or_none()


async def active_for_driver(db: AsyncSession, driver_id: int) -> list[Request]:
    q = _with_details(select(Request).where(Request.driver_id == driver_id, Request.status.in_(ACTIVE_REQUEST_STATUSES))
                      .order_by(Request.created_at))
    return list((await db.execute(q)).scalars())


async def new_in_district(db: AsyncSession, district_id: int | None) -> list[Request]:
    """Qizil kartalar: biriktirilmagan va varaqasi printerdan chiqishi kutilayotgan murojaatlar — eng yangisi tepada."""
    q = select(Request).where(Request.status.in_([RequestStatus.new, RequestStatus.printing]))
    if district_id:
        q = q.where(Request.district_id == district_id)
    return list((await db.execute(_with_details(q.order_by(Request.created_at.desc(), Request.id.desc())))).scalars())


async def seen_ids(db: AsyncSession, user_id: int, request_ids: list[int]) -> set[int]:
    from app.models import RequestSeen
    if not request_ids:
        return set()
    q = select(RequestSeen.request_id).where(RequestSeen.user_id == user_id, RequestSeen.request_id.in_(request_ids))
    return set((await db.execute(q)).scalars())


async def mark_seen(db: AsyncSession, user_id: int, request_ids: list[int]) -> None:
    from app.models import RequestSeen
    have = await seen_ids(db, user_id, request_ids)
    db.add_all([RequestSeen(user_id=user_id, request_id=r) for r in set(request_ids) - have])
    await db.commit()


async def count_active_on_shift(db: AsyncSession, shift_id: int) -> int:
    q = select(func.count()).select_from(Request).where(Request.shift_id == shift_id, Request.status.in_(ACTIVE_REQUEST_STATUSES))
    return (await db.execute(q)).scalar_one()


async def files_for(db: AsyncSession, request_id: int) -> dict[FileKind, ActFile]:
    rows = (await db.execute(select(ActFile).where(ActFile.request_id == request_id))).scalars()
    return {f.kind: f for f in rows}


async def done_for_driver(db: AsyncSession, driver_id: int, limit: int = 50) -> list[Request]:
    """Haydovchining bajarilgan (yashil) arizalari — eng oxirgisi tepada."""
    q = _with_details(select(Request).where(Request.driver_id == driver_id,
                                            Request.status.in_([RequestStatus.done, RequestStatus.suspect]))
                      .order_by(Request.finished_at.desc(), Request.id.desc()).limit(limit))
    return list((await db.execute(q)).scalars())
