"""gps-worker: SmartGPS/Wialon bilan ishlaydigan YAGONA jarayon (alohida konteyner, o'sha api rasmi).

    python -m app.gps_worker

Har 30 soniyada: heartbeat (admin panelida «Worker ishlayapti») → token tekshiruvi (har soatda, yangi token — darhol; o'lsa
zaxiraga o'tish va adminlarga ogohlantirish — app/gps/tokens.py) → sinxronlash kerak bo'lgan manbalar (yangi token, «Hozir
sinxronlash», kunlik GPS_SYNC_TIME). API jarayoni SmartGPS'ga chiqmaydi — faqat bazaga belgi qo'yadi, worker bajaradi.
Keyingi bosqichlarda jonli joylashuv va qamrov hisoblari ham shu yerga qo'shiladi."""
import asyncio
import logging
import signal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core import secretbox
from app.core.config import get_settings
from app.db.base import utcnow
from app.gps import tokens
from app.gps.sync import due, sync_source
from app.models import AppSetting, GpsSource

log = logging.getLogger("gps_worker")
HEARTBEAT = "gps_worker_seen"
TICK_S = 30


async def heartbeat(db) -> None:
    row = await db.get(AppSetting, HEARTBEAT)
    stamp = utcnow().isoformat(timespec="seconds")
    if row:
        row.value = stamp
    else:
        db.add(AppSetting(key=HEARTBEAT, value=stamp))
    await db.commit()


async def tick(sessionmaker: async_sessionmaker, *, transport=None) -> int:
    """Bir aylanish. Qaytaradi: nechta manba sinxronlandi."""
    s = get_settings()
    async with sessionmaker() as db:
        await heartbeat(db)
        now = utcnow()
        rows = list((await db.execute(select(GpsSource).order_by(GpsSource.id))).scalars())
        ids = [src.id for src in rows if due(src, now, s.gps_sync_time)]  # tekshiruvdan oldin: yangi (pending) token ham sinxronlanadi
        checks = [src.id for src in rows if tokens.need_check(src, now)]
    for sid in checks:  # har soatlik token tekshiruvi (yangi token — darhol); o'lsa zaxiraga o'tish va ogohlantirish
        async with sessionmaker() as db:
            try:
                await tokens.check_source(db, await db.get(GpsSource, sid), transport=transport)
            except Exception:
                log.exception("token tekshiruvi %s: kutilmagan xato", sid)
                await db.rollback()
    n = 0
    for sid in ids:
        async with sessionmaker() as db:
            src = await db.get(GpsSource, sid)
            try:
                lg = await sync_source(db, src, transport=transport)
                log.info("sinxron %s: %s", src.server, "ok" if lg.ok else lg.error)
            except Exception:  # kutilmagan xato — keyingi manbalar to'xtamasin
                log.exception("sinxron %s: kutilmagan xato", sid)
                await db.rollback()
                src = await db.get(GpsSource, sid)
                src.sync_requested_at, src.last_error = None, "Kutilmagan xato (worker jurnalini ko'ring)"
                await db.commit()
        n += 1
    return n


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = get_settings()
    if not s.gps_worker_enabled:
        log.warning("GPS_WORKER_ENABLED=false — worker hech narsa qilmaydi (konteyner to'xtamasligi uchun kutib turadi)")
        await asyncio.Event().wait()
    if s.app_env == "production":
        from app.core.secretbox import KeyError_, check_key
        try:
            check_key(s.gps_enc_key)
        except KeyError_ as e:  # qayta-qayta ishga tushib jurnalni to'ldirmasin — kutib turadi (api'ga ta'sir qilmaydi)
            log.error("%s — worker ishlamaydi. .env'ga kalit qo'shib: ../dc up -d gps-worker", e)
            await asyncio.Event().wait()
    if not secretbox.available():
        log.error("GPS_ENC_KEY noto'g'ri — worker ishlamaydi")
        await asyncio.Event().wait()
    from app.db.session import SessionLocal
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    log.info("gps-worker ishga tushdi (kunlik sinxron %s)", s.gps_sync_time)
    while not stop.is_set():
        try:
            await tick(SessionLocal)
        except Exception:
            log.exception("aylanish xatosi")
        try:
            await asyncio.wait_for(stop.wait(), TICK_S)
        except asyncio.TimeoutError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
