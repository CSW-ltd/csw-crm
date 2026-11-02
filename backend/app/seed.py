"""Boshlang'ich ma'lumotlar: viloyatlar, xizmat ko'rsatuvchilar, 12 tuman, mashinalar, foydalanuvchilar, namunaviy korxonalar.

Ishga tushirish:  python -m app.seed
Parol SEED_PASSWORD muhit o'zgaruvchisidan olinadi (bo'lmasa: ChangeMe123!). Qayta ishga tushirilsa hech narsa qo'shmaydi.
"""
import asyncio
import os
from datetime import date, timedelta

from sqlalchemy import select

from app.core.permissions import apply_template
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.services.schedule import today as schedule_today
from app.models import AppSetting, Contract, ContractEvent, Tariff, Customer, District, Provider, Region, OrderForm, Payment, Request, RequestEvent, User, VehiclePosition, WorkSchedule, UserDistrict, Vehicle
from app.db.base import utcnow
from app.models.enums import ContractType, LocationStatus, RequestStatus, Role, WasteType

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


async def seed() -> None:
    pwd = hash_password(os.getenv("SEED_PASSWORD", "ChangeMe123!"))
    async with SessionLocal() as db:
        if (await db.execute(select(Region))).first():
            print("Seed allaqachon bajarilgan — o'tkazib yuborildi")
            return
        db.add(AppSetting(key="gps_radius_m", value="300"))
        db.add(User(username="admin", password_hash=pwd, full_name="Administrator", role=Role.admin))
        # Manager va yurist — barcha 12 tuman (pastda biriktiriladi)
        manager = User(username="manager", password_hash=pwd, full_name="Manager", role=Role.manager)
        legal = User(username="legal", password_hash=pwd, full_name="Yuridik bo'lim xodimi", role=Role.legal)
        apply_template(manager)
        apply_template(legal)
        db.add_all([manager, legal])
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
                gps = User(username=f"gps{n}", password_hash=pwd, full_name=f"GPS xodimi — {d_name}", role=Role.gps, district_id=d.id)
                apply_template(gps)
                db.add(gps)
                for k in (1, 2):
                    veh = Vehicle(plate=f"{plate_code} {n:02d}{k} {code[:2]}", model="ISUZU NQR", district_id=d.id)
                    drv = User(username=f"driver{n}{k}", password_hash=pwd, full_name=f"Haydovchi {n}-{k}",
                               phone=f"+998 90 000-{n:02d}-{k:02d}", role=Role.driver, district_id=d.id)
                    apply_template(drv)  # yozishma ruxsatlari
                    db.add_all([veh, drv])
                    await db.flush()
                    # Bugungi ish jadvali: 1-mashina — yuridik bo'lim, 2-mashina — mahallalar (jismoniy abonentlar).
                    # Joylashuv (GPS-monitoring ulanmaguncha namunaviy): 1-mashina korxonaga yaqinroq.
                    db.add(WorkSchedule(day=schedule_today(), district_id=d.id, vehicle_id=veh.id, driver_id=drv.id,
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
        # Call-center operatori (demo: barcha tumanlar)
        accountant = User(username="buxgalter", password_hash=pwd, full_name="Buxgalter", role=Role.accountant)
        apply_template(accountant)
        db.add(accountant)
        operator = User(username="operator", password_hash=pwd, full_name="Call-center operatori", role=Role.operator)
        apply_template(operator)
        db.add(operator)
        await db.flush()
        db.add_all([UserDistrict(user_id=u.id, district_id=d) for u in (manager, legal, operator, accountant) for d in district_ids])
        await db.commit()
        print("Seed tayyor: admin, manager, legal, operator, buxgalter, gps1..gps12, driver11..driver122")


if __name__ == "__main__":
    asyncio.run(seed())
