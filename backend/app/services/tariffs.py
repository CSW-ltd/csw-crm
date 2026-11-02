"""Davlat ta'riflari (1 m³ narxi, QQS bilan): viloyat bo'yicha va tuman/shahar uchun alohida, sanadan kuchga kiradi.

Kim o'zgartiradi: admin — istalgan viloyat yoki tuman; manager — faqat o'z tumanlari (tuman darajasida), agar admin
viloyat yoki tumanni yopib qo'ymagan bo'lsa. Har o'zgarish yangi yozuv (tarix saqlanadi), eskisi o'chirilmaydi.
"""
from bisect import bisect_right
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import forbidden, invalid, not_found
from app.models import District, Region, Tariff, User
from app.models.enums import Role
from app.services import access, situation


class TariffBook:
    """Barcha ta'riflar xotirada: price(district_id, day) — tuman ta'rifi, bo'lmasa viloyatniki."""

    def __init__(self, tariffs: list[Tariff], district_region: dict[int, int]):
        self.district_region = district_region
        self.by_district: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)
        self.by_region: dict[int, list[tuple[date, Decimal]]] = defaultdict(list)
        for t in sorted(tariffs, key=lambda t: (t.valid_from, t.id)):
            target = self.by_district[t.district_id] if t.district_id else self.by_region[t.region_id]
            target.append((t.valid_from, Decimal(str(t.price))))

    @staticmethod
    def _at(rows: list[tuple[date, Decimal]], day: date) -> Decimal | None:
        i = bisect_right([d for d, _ in rows], day)
        return rows[i - 1][1] if i else None

    def price(self, district_id: int, day: date) -> Decimal | None:
        p = self._at(self.by_district.get(district_id, []), day)
        if p is None and district_id in self.district_region:
            p = self._at(self.by_region.get(self.district_region[district_id], []), day)
        return p


async def book(db: AsyncSession) -> TariffBook:
    tariffs = list((await db.execute(select(Tariff))).scalars())
    dr = dict((await db.execute(select(District.id, District.region_id))).all())
    return TariffBook(tariffs, dr)


async def price_for(db: AsyncSession, district_id: int, day: date) -> Decimal | None:
    return (await book(db)).price(district_id, day)


def _can_edit(user: User, region: Region, district: District | None) -> None:
    if user.role == Role.admin:
        return
    if user.role != Role.manager or district is None:
        raise forbidden("Viloyat ta'rifini faqat admin o'zgartiradi")
    if not user.can("settings.tariff"):
        raise forbidden("Ta'rifni belgilash huquqi yo'q (admin huquqlar bo'limida yoqadi)")
    access.check_scope(user, district.id)
    if region.tariff_locked or district.tariff_locked:
        raise forbidden("Admin bu hudud ta'rifini o'zgartirishni yopib qo'ygan")


async def overview(db: AsyncSession, user: User, today: date) -> dict:
    """Viloyatlar → tumanlar: amaldagi ta'rif (o'zi yoki viloyatdan), keyingi rejalashtirilgan, qulf, tahrir huquqi, tarix."""
    tb = await book(db)
    scope = access.scope(user)
    regions = list((await db.execute(select(Region).order_by(Region.id))).scalars())
    districts = list((await db.execute(select(District).where(District.is_active.is_(True)).order_by(District.region_id, District.name))).scalars())
    tariffs = list((await db.execute(select(Tariff).order_by(Tariff.valid_from.desc(), Tariff.id.desc()))).scalars())

    def hist(region_id, district_id):
        return [{"id": t.id, "price": float(t.price), "valid_from": t.valid_from, "note": t.note, "created_at": t.created_at,
                 "by": t.created_by.full_name if t.created_by else None}
                for t in tariffs if t.region_id == region_id and t.district_id == district_id][:20]

    def upcoming(rows):
        nxt = [(d, p) for d, p in rows if d > today]
        return {"price": float(nxt[0][1]), "valid_from": nxt[0][0]} if nxt else None

    out = []
    for r in regions:
        ds = [d for d in districts if d.region_id == r.id and (scope is None or d.id in scope)]
        if scope is not None and not ds:
            continue
        rp = tb._at(tb.by_region.get(r.id, []), today)
        out.append({
            "region_id": r.id, "name": r.name, "locked": r.tariff_locked, "price": float(rp) if rp is not None else None,
            "upcoming": upcoming(tb.by_region.get(r.id, [])), "can_edit": user.role == Role.admin,
            "history": hist(r.id, None) if user.role == Role.admin or scope is None else hist(r.id, None)[:5],
            "districts": [{
                "district_id": d.id, "name": d.name, "locked": d.tariff_locked,
                "own_price": float(op) if (op := tb._at(tb.by_district.get(d.id, []), today)) is not None else None,
                "price": float(p) if (p := tb.price(d.id, today)) is not None else None,
                "upcoming": upcoming(tb.by_district.get(d.id, [])),
                "can_edit": user.role == Role.admin or (user.role == Role.manager and user.can("settings.tariff")
                                                        and not r.tariff_locked and not d.tariff_locked),
                "history": hist(r.id, d.id),
            } for d in ds],
        })
    return {"today": today, "regions": out}


async def set_price(db: AsyncSession, user: User, region_id: int | None, district_id: int | None, price: Decimal, valid_from: date,
                    note: str | None) -> Tariff:
    if price <= 0:
        raise invalid("bad_price", "Narx musbat bo'lsin")
    district = await db.get(District, district_id) if district_id else None
    if district_id and not district:
        raise not_found("district")
    region = await db.get(Region, district.region_id if district else region_id)
    if not region:
        raise not_found("region")
    _can_edit(user, region, district)
    t = Tariff(region_id=region.id, district_id=district.id if district else None, price=price, valid_from=valid_from,
               note=(note or "").strip() or None, created_by_id=user.id)
    db.add(t)
    situation.activity(db, "act_tariff_set", f"Ta'rif: {(district or region).name} — {price} so'm/m³, {valid_from} dan"
                       + (f" ({t.note})" if t.note else ""), params={"place": (district or region).name, "price": float(price),
                       "from": str(valid_from), "note": t.note}, district_id=district.id if district else None, actor_id=user.id)
    await db.commit()
    return t


async def set_lock(db: AsyncSession, user: User, region_id: int | None, district_id: int | None, locked: bool) -> None:
    if user.role != Role.admin:
        raise forbidden("Faqat admin")
    obj = await db.get(District, district_id) if district_id else await db.get(Region, region_id)
    if not obj:
        raise not_found("district" if district_id else "region")
    obj.tariff_locked = locked
    situation.activity(db, "act_tariff_lock", f"Ta'rif managerga {'yopildi' if locked else 'ochildi'}: {obj.name}",
                       params={"place": obj.name, "locked": locked}, district_id=district_id, actor_id=user.id)
    await db.commit()


async def remove(db: AsyncSession, user: User, tariff_id: int, today: date) -> None:
    """Faqat hali kuchga kirmagan (kelajakdagi) ta'rifni o'chirish mumkin — o'tmish hisob-kitobi o'zgarmasin."""
    t = await db.get(Tariff, tariff_id)
    if not t:
        raise not_found("tariff")
    if t.valid_from <= today:
        raise invalid("tariff_in_force", "Kuchga kirgan ta'rif o'chirilmaydi — yangi sana bilan yangi ta'rif kiriting")
    region = await db.get(Region, t.region_id)
    _can_edit(user, region, await db.get(District, t.district_id) if t.district_id else None)
    await db.delete(t)
    await db.commit()
