import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import socketio
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import accounting, admin, auth, callcenter, contracts, customers, driver, gps, integrations, orders, situation, tariffs
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler
from app.db.session import get_session
from app.middleware import CsrfHeaderMiddleware, RequestContextMiddleware
from app.realtime import sio
from app.services.storage import MemoryStorage, MinioStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("csw")


async def _purge_situation_daily(storage) -> None:
    """Sutkada bir marta: Vaziyat jurnalidan 90 kundan eski hodisalarni o'chiradi."""
    from app.db.session import SessionLocal
    from app.services.situation import purge_old
    while True:
        try:
            async with SessionLocal() as db:
                n = await purge_old(db)
            if n:
                log.info("situation: %s ta eski hodisa o'chirildi", n)
        except Exception:  # noqa: BLE001 — tozalash xatosi ilovani to'xtatmasin
            log.exception("situation purge failed")
        await asyncio.sleep(24 * 3600)


async def _overdue_watch() -> None:
    """Har 10 daqiqada: 72 soatlik muddati o'tgan arizalar — admin Vaziyat paneliga."""
    from app.db.session import SessionLocal
    from app.services.callcenter import check_overdue
    while True:
        try:
            async with SessionLocal() as db:
                n = await check_overdue(db)
            if n:
                log.info("overdue: %s ta ariza muddati o'tdi", n)
        except Exception:  # noqa: BLE001
            log.exception("overdue watch failed")
        await asyncio.sleep(600)


def create_app(storage=None) -> FastAPI:
    s = get_settings()
    s.check_production()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.storage = storage or (MemoryStorage() if s.storage_backend == "memory" else MinioStorage(s))
        purge = asyncio.create_task(_purge_situation_daily(app.state.storage))
        overdue = asyncio.create_task(_overdue_watch())
        yield
        purge.cancel()
        overdue.cancel()

    app = FastAPI(title="CSW Chiqindi CRM API", version="0.1.0", lifespan=lifespan)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_middleware(CsrfHeaderMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_list, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"])
    for r in (auth.router, driver.router, gps.router, admin.router, customers.router, situation.router, callcenter.router,
              orders.router, integrations.router, accounting.router, accounting.public_router, contracts.router, tariffs.router):
        app.include_router(r, prefix="/api/v1")

    @app.get("/api/health", tags=["system"])
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/health", tags=["system"])
    async def health_v1(db: AsyncSession = Depends(get_session)):
        """Deploy va monitoring uchun: ilova + baza. Baza javob bermasa 503."""
        try:
            await db.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001
            log.exception("health: database unavailable")
            return JSONResponse({"status": "error", "db": "down", "version": s.app_version}, status_code=503)
        return {"status": "ok", "db": "ok", "version": s.app_version}

    if s.static_dir:
        _mount_spa(app, Path(s.static_dir))
    return app


def _mount_spa(app: FastAPI, root: Path) -> None:
    """Demo/preview: React build'ini shu server beradi; noma'lum yo'llar index.html ga (client-side routing)."""
    index = root / "index.html"
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith("api/"):
            raise AppError(404, "not_found", "Topilmadi")
        f = (root / path).resolve()
        if path and f.is_file() and root.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = create_app()
# uvicorn app.main:asgi_app — Socket.IO /socket.io yo'lida, qolgani FastAPI
asgi_app = socketio.ASGIApp(sio, other_asgi_app=app)
