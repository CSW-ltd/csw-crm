"""Oxirgi chora: admin 2FA'sini serverda qayta o'rnatish (telefon va zaxira kodlar yo'qolgan, boshqa admin yo'q).

Ishga tushirish (csw-app):  ../dc exec api python -m app.reset_2fa <login> "<sabab>"
Keyingi kirishda admin QR kodni qaytadan skanerlaydi. Hodisa Vaziyat paneliga «server (CLI)» nomidan yoziladi.
"""
import asyncio
import sys

from app.core.errors import AppError
from app.repositories import users as users_repo
from app.services import mfa_service


async def _main(username: str, reason: str) -> int:
    from app.db.session import SessionLocal, engine
    try:
        async with SessionLocal() as db:
            user = await users_repo.by_username(db, username.strip().lower())
            if not user:
                print(f"XATO: «{username}» topilmadi", file=sys.stderr)
                return 1
            await mfa_service.reset(db, None, user.id, reason)
    except AppError as e:
        print(f"XATO: {e.message}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()
    print(f"✓ «{username}» 2FA qayta o'rnatildi — keyingi kirishda QR kod qaytadan skanerlanadi")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print('Foydalanish: python -m app.reset_2fa <login> "<sabab>"', file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(_main(sys.argv[1], sys.argv[2])))
