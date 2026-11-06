"""Demo ma'lumotlar (lokal va test.csw.uz): viloyatlar, xizmat ko'rsatuvchilar, 12 tuman, mashinalar, 7 demo foydalanuvchi, namunaviy korxonalar.

Ishga tushirish:  python -m app.seed               — bo'sh bazaga (to'ldirilgan bo'lsa hech narsa qilmaydi)
                  python -m app.seed --reset --yes — barcha ma'lumotni o'chirib, qayta yaratadi
Loginlar va parollar faqat DEMO_CREDENTIALS env'idan (JSON, app/core/demo.py). APP_ENV=production'da ishlamaydi —
prod uchun python -m app.bootstrap.
"""
import asyncio
import sys
from datetime import date, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.demo import DEMO_USERS, DemoCredentialsError, parse
from app.core.permissions import apply_template
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.services.schedule import today as schedule_today
from app.models import AppSetting, Contract, ContractEvent, Tariff, Customer, District, Provider, Region, OrderForm, Payment, Request, RequestEvent, User, VehiclePosition, WorkSchedule, UserDistrict, Vehicle
from app.db.base import utcnow
from app.models.enums import ContractType, LocationStatus, RequestStatus, WasteType

REGIONS = {
    "Andijon viloyati": ("Bio Tex Eko", "BTE", "60", [
        ("Andijon shahri", 40.7821, 72.3442), ("Andijon tumani", 40.7480, 72.4310),
        ("Oltinko'l tumani", 40.8030, 72.1700), ("Asaka tumani", 40.6415, 72.2390)]),
    "Surxondaryo viloyati": ("Bio Texno Klaster", "BTK", "75", [
        ("Termiz shahri", 37.2242, 67.2783), ("Termiz tumani", 37.3010, 67.3420), ("Angor tumani", 37.4620, 67.1510),
        ("Uzun tumani", 38.3680, 68.0020), ("Sariosiyo tumani", 38.4130, 67.9580)]),
    "Qashqadaryo viloyati": ("Bisay", "BSY", "70", [
        ("Shahrisabz shahri", 39.0570, 66.8340), ("Shahrisabz tumani", 39.0010, 66.9020), ("Kitob tumani", 39.1180, 66.8820)]),
}


REQUESTS_PER_DISTRICT = 5  # demo: GPS xodimi bir necha marta biriktirib sinashi uchun
DEMO_DISTRICT = "Asaka tumani"  # csw.gps va csw.haydovchi shu tumanda


class SeedError(RuntimeError):
    pass


async def reset(db: AsyncSession) -> None:
    """Barcha jadvallarni tozalaydi (alembic_version qoladi). Faqat demo/lokal baza uchun."""
    from app.models import Base
    mysql = db.bind.dialect.name == "mysql"
    if mysql:
        await db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    for table in reversed(Base.metadata.sorted_tables):
        await db.execute(table.delete())
    if mysql:
        await db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    await db.commit()


async def seed(db: AsyncSession, creds: dict[str, str]) -> bool:
    """creds — demo.parse() natijasi. Baza to'ldirilgan bo'lsa False qaytaradi (hech narsa qo'shmaydi)."""
    if (await db.execute(select(Region))).first():
        return False

    def demo_user(username: str, **kw) -> User:
        role, full_name = DEMO_USERS[username]
        u = User(username=username, password_hash=hash_password(creds[username]), full_name=full_name, role=role, **kw)
        apply_template(u)
        db.add(u)
        return u

    db.add(AppSetting(key="gps_radius_m", value="300"))
    demo_user("csw.admin")
    # Manager, yurist, buxgalter, operator — barcha 12 tuman (pastda biriktiriladi)
    manager = demo_user("csw.manager")
    legal = demo_user("csw.yurist")
    accountant = demo_user("csw.buxgalter")
    operator = demo_user("csw.operator")
    district_ids: list[int] = []
    n = 0
    for region_name, (prov_name, code, plate_code, districts) in REGIONS.items():
        region = Region(name=region_name)
        db.add(region)
        await db.flush()
        # DEMO ta'riflar (1 m³, QQS bilan): viloyat bo'yicha, yil boshidan
        db.add(Tariff(region_id=region.id, price={"BTE": 84000, "BTK": 179312}.get(code, 150000),
                      valid_from=date(date.today().year, 1, 1), note="Demo ta'rif"))
        # DEMO rekvizitlar (haqiqiy emas) — admin «Sozlamalar»da almashtiriladi
        k = len(district_ids) + 1
        db.add(Provider(name=prov_name, code=code, region_id=region.id, full_name=f'"{prov_name}" MChJ (demo)',
                        inn=f"30{k:07d}", address=f"{region_name}, demo ko'chasi, {k}-uy", bank="DEMO bank AT",
                        mfo="00000", account=f"2020800000000000{k:04d}", director="Demo Direktor", chief_accountant="Demo Bosh buxgalter",
                        phone="+998 00 000-00-00", oked="38210"))
        for d_name, lat, lng in districts:
            n += 1
            d = District(name=d_name, region_id=region.id)
            db.add(d)
            await db.flush()
            if d_name == "Andijon shahri":  # demo: shahar uchun alohida ta'rif
                db.add(Tariff(region_id=region.id, district_id=d.id, price=90000, valid_from=date(date.today().year, 1, 1),
                              note="Demo: shahar ta'rifi"))
            district_ids.append(d.id)
            demo_here = d_name == DEMO_DISTRICT
            if demo_here:
                demo_user("csw.gps", district_id=d.id)
            for k in (1, 2):
                veh = Vehicle(plate=f"{plate_code} {n:02d}{k} {code[:2]}", model="ISUZU NQR", district_id=d.id)
                db.add(veh)
                # Haydovchi faqat Asaka 1-mashinasida (csw.haydovchi); boshqa mashinalar jadvalda haydovchisiz
                drv = demo_user("csw.haydovchi", district_id=d.id, phone="+998 90 000-00-01") if demo_here and k == 1 else None
                await db.flush()
                # Bugungi ish jadvali: 1-mashina — yuridik bo'lim, 2-mashina — mahallalar (jismoniy abonentlar).
                # Joylashuv (GPS-monitoring ulanmaguncha namunaviy): 1-mashina korxonaga yaqinroq.
                db.add(WorkSchedule(day=schedule_today(), district_id=d.id, vehicle_id=veh.id, driver_id=drv.id if drv else None,
                                    service="legal" if k == 1 else "individual",
                                    mahallas=None if k == 1 else "Bog'bon, Navbahor mahallalari"))
                db.add(VehiclePosition(vehicle_id=veh.id, lat=lat + 0.01 * k, lng=lng - 0.008 * k, at=utcnow(), source="demo"))
            c = Customer(fixed_no=f"A-{100 + n:04d}", stir=f"{300000000 + n * 1111:09d}", name=f"\"Namuna {n}\" MChJ",
                         name_key=f"namuna {n} mchj", location_status=LocationStatus.confirmed, activity_type="Savdo",
                         director="Namuna rahbar", phone="+998 91 111-11-11", district_id=d.id,
                         address="Mustaqillik ko'chasi, 1-uy", lat=lat + 0.002, lng=lng + 0.002,
                         # DEMO rekvizitlar (haqiqiy emas)
                         legal_address=f"{d_name}, Mustaqillik ko'chasi, {n}-uy", bank="DEMO bank AT", mfo="00000",
                         account=f"2020800000{n:010d}", oked="56290")
            db.add(c)
            await db.flush()
            # Debitor/kreditor namunasi uchun turli shartnoma turlari va narxlari
            ctype, price = ((ContractType.monthly, 1_200_000), (ContractType.per_trip, 180_000),
                            (ContractType.by_volume, 45_000), (ContractType.monthly, 900_000))[n % 4]
            # Yangi shartnomalar statistikasi uchun imzolangan sanalar har xil (7/15/30/182/365 kun)
            signed_back = (3, 12, 25, 60, 150, 300)[n % 6]
            ct = Contract(customer_id=c.id, number=f"SH-2026/{n:04d}", signed_on=date.today() - timedelta(days=signed_back),
                          type=ctype, price=price, valid_from=date.today() - timedelta(days=120), valid_to=date.today() + timedelta(days=365),
                          annual_volume=40, place=d_name, sign_method="electronic")
            if signed_back == 3:
                # «Yangi shartnoma» jarayonidan o'tgan, buxgalter tasdig'ini kutayotgan shartnoma (GPS'da «Yangi shartnoma» belgisi)
                ct.status, ct.platform, ct.platform_id = "signed", "didox", f"DEMO{n:08d}"
                ct.signed_at, ct.created_by_id = utcnow() - timedelta(days=3), legal.id
                ct.events = [ContractEvent(actor_id=legal.id, action="created", created_at=utcnow() - timedelta(days=4)),
                             ContractEvent(actor_id=legal.id, action="signed", created_at=utcnow() - timedelta(days=3))]
            db.add(ct)
            await db.flush()
            now = utcnow()
            for k in range(REQUESTS_PER_DISTRICT):
                r = Request(customer_id=c.id, contract_id=ct.id, district_id=d.id, waste_type=WasteType.household,
                            volume_estimate=6, preferred_time="08:00–12:00", note=f"Namunaviy ariza {k + 1}",
                            due_at=now + timedelta(hours=72), is_repeat=k == REQUESTS_PER_DISTRICT - 1,
                            caller_name="Namuna qo'ng'iroq qiluvchi", caller_phone="+998 91 111-11-11")
                db.add(r)
                await db.flush()
                r.number = f"M-{r.id:06d}"
                db.add(RequestEvent(request_id=r.id, status=RequestStatus.new, created_at=now, note="namunaviy ariza"))
            # Statistika uchun tarix: 6 kun oldin bajarilgan va 4 kun oldin ochilib muddati o'tgan ariza
            for days, status in ((75, RequestStatus.done), (40, RequestStatus.done), (6, RequestStatus.done), (4, RequestStatus.new)):
                created = now - timedelta(days=days)
                r = Request(customer_id=c.id, contract_id=ct.id, district_id=d.id, waste_type=WasteType.household,
                            volume_estimate=6, note="Namunaviy (tarix)", status=status, created_at=created,
                            due_at=created + timedelta(hours=72), finished_at=created + timedelta(hours=20) if status == RequestStatus.done else None,
                            # Asakada muddati o'tgan ariza Vaziyat paneliga demo ishga tushgach 10 daqiqa ichida tushadi
                            overdue_notified=d_name != "Asaka tumani")
                db.add(r)
                await db.flush()
                r.number = f"M-{r.id:06d}"
                db.add(RequestEvent(request_id=r.id, status=RequestStatus.new, created_at=created))
                if r.finished_at:
                    db.add(RequestEvent(request_id=r.id, status=RequestStatus.done, created_at=r.finished_at))
                    # Yopilgan buyurtma varaqasi (kub bilan) — "Korxonalar" jadvali va hisob uchun
                    f = OrderForm(request_id=r.id, print_count=1, printed_at=created, print_confirmed_at=created, print_confirm_via="manual",
                                  volume_m3=3 + ((days + n * 3) % 9),
                                  waste_kind="solid", closed_at=r.finished_at, closed_via="form")
                    db.add(f)
                    await db.flush()
                    f.number = f"{f.id:07d}"
            if n % 3 != 0:  # to'lovlar: ba'zilari to'liq to'lamagan (debitor), ba'zilari oldindan (kreditor)
                for back, amount in ((100, price * (2 if n % 3 == 1 else 4)), (35, price)):
                    db.add(Payment(customer_id=c.id, paid_on=date.today() - timedelta(days=back), amount=amount,
                                   doc_no=f"PP-{n:02d}{back}", source="manual"))
            # Kartasi to'liq bo'lmagan korxona (STIR, shartnoma, koordinata yo'q) — assenizator arizasi biriktirilmaydi,
            # yurist STIR va shartnoma kiritgach biriktiriladi; birinchi tashrifdan keyin Manager koordinatani tasdiqlaydi
            c2 = Customer(fixed_no=f"A-{200 + n:04d}", name=f"\"Yangi mijoz {n}\" MChJ", name_key=f"yangi mijoz {n} mchj",
                          location_status=LocationStatus.none, activity_type="Umumiy ovqatlanish", phone="+998 93 222-22-22",
                          district_id=d.id, address="Navoiy ko'chasi, 5-uy", source="excel")
            db.add(c2)
            await db.flush()
            r = Request(customer_id=c2.id, district_id=d.id, waste_type=WasteType.septic, volume_estimate=4,
                        note="Assenizator: hojatxona chuquri to'lgan", due_at=utcnow() + timedelta(hours=72))
            db.add(r)
            await db.flush()
            r.number = f"M-{r.id:06d}"
            db.add(RequestEvent(request_id=r.id, status=RequestStatus.new, created_at=utcnow()))
    await db.flush()
    db.add_all([UserDistrict(user_id=u.id, district_id=d) for u in (manager, legal, operator, accountant) for d in district_ids])
    await db.commit()
    return True


async def _main(argv: list[str]) -> int:
    do_reset = "--reset" in argv
    if unknown := [a for a in argv if a not in ("--reset", "--yes")]:
        print(f"Noma'lum argument: {' '.join(unknown)}. Foydalanish: python -m app.seed [--reset --yes]", file=sys.stderr)
        return 2
    s = get_settings()
    try:
        if s.app_env == "production":
            raise SeedError("APP_ENV=production — demo seed prod bazada ishlamaydi (boshlang'ich ma'lumot: python -m app.bootstrap)")
        if do_reset and "--yes" not in argv:
            raise SeedError("--reset barcha ma'lumotni o'chiradi — tasdiq uchun --yes qo'shing")
        creds = parse(s.demo_credentials)
    except (SeedError, DemoCredentialsError) as e:
        print(f"XATO: {e}", file=sys.stderr)
        return 1
    try:
        async with SessionLocal() as db:
            if do_reset:
                await reset(db)
                print("Baza tozalandi")
            done = await seed(db, creds)
    finally:
        await engine.dispose()  # ulanishlar loop yopilishidan oldin yopiladi
    if not done:
        print("Baza allaqachon to'ldirilgan — o'tkazib yuborildi (qayta yaratish: --reset --yes)")
    else:
        print(f"Seed tayyor: {', '.join(DEMO_USERS)} (parollar — DEMO_CREDENTIALS)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
