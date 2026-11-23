"""Wialon Remote API klienti (SmartGPS va Wialon — ikkalasi Wialon Local). FAQAT O'QISH.

Qat'iy qoida: SmartGPS/Wialon'da hech narsa o'zgartirilmaydi. Shu sabab klient faqat READ_ONLY ro'yxatidagi buyruqlarni
yuboradi — boshqa har qanday `svc` kod darajasida rad etiladi (`GpsForbidden`), so'rov tarmoqqa chiqmaydi. Token ham faqat
o'qish huquqli (access_type 0x300) bo'lishi tekshiriladi.

Bu modulni faqat gps-worker ishlatadi; API jarayoni SmartGPS'ga chiqmaydi."""
import asyncio
import json
import re

import httpx

# Faqat o'qish buyruqlari. Yangi buyruq qo'shishdan oldin u ma'lumotni O'ZGARTIRMASLIGI tekshiriladi.
READ_ONLY: frozenset[str] = frozenset({
    "token/login", "token/list", "core/logout",
    "core/search_items", "core/search_item", "core/get_hw_types",
    "resource/get_zone_data",
    "report/exec_report", "report/get_result_rows", "report/select_result_rows", "report/get_report_data",
    "report/cleanup_result", "render/set_locale",  # natijani sessiyadan tozalash / sessiya tili — GPS ma'lumoti o'zgarmaydi
    "messages/load_interval", "messages/unload",
})
# access_type bitlari: 0x100 — onlayn kuzatish, 0x200 — ma'lumotlarni ko'rish. 0x400 va yuqorisi — o'zgartirish huquqlari.
READ_ACCESS = 0x300
WRITE_BITS = ~0x3FF

ERR = {1: "sessiya yaroqsiz", 4: "noto'g'ri parametr", 5: "bajarishda xato", 6: "noma'lum xato", 7: "ruxsat yo'q",
       8: "login/parol yoki token noto'g'ri", 1003: "boshqa so'rov bajarilmoqda"}
TOKEN_RE = re.compile(r"^[0-9a-fA-F]{64,96}$")
HEADERS = {  # ba'zi serverlar brauzerdan kelmagan so'rovni (python UA) 403 bilan to'sadi
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ru-RU,ru;q=0.9,uz;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}


class GpsError(Exception):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code

    @property
    def auth(self) -> bool:
        """Token yaroqsiz/muddati tugagan (qayta «Ulash» kerak)."""
        return self.code in (1, 4, 7, 8)


class GpsForbidden(GpsError):
    """Ro'yxatda yo'q (o'zgartiruvchi bo'lishi mumkin) buyruq — yuborilmaydi."""


def base_url(server: str) -> str:
    s = server.strip().rstrip("/")
    return s if s.startswith(("http://", "https://")) else f"https://{s}"


def valid_token(token: str) -> bool:
    return bool(TOKEN_RE.match(token or ""))


def login_url(server: str, redirect_uri: str, client_id: str = "CSW CRM") -> str:
    """SmartGPS'ning o'z kirish sahifasi: foydalanuvchi o'zi kiradi, token faqat o'qish (0x300), muddatsiz."""
    from urllib.parse import urlencode
    q = {"client_id": client_id, "access_type": hex(READ_ACCESS), "activation_time": 0, "duration": 0, "flags": 1,
         "response_type": "token", "redirect_uri": redirect_uri}
    return f"{base_url(server)}/login.html?{urlencode(q)}"


class WialonClient:
    def __init__(self, server: str, *, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 300,
                 retry_delay: float = 5):
        self.base = base_url(server)
        self.url = self.base + "/wialon/ajax.html"
        self.sid: str | None = None
        self.user: str | None = None
        self.retry_delay = retry_delay
        self._http = httpx.AsyncClient(transport=transport, timeout=timeout,
                                       headers={**HEADERS, "Origin": self.base, "Referer": self.base + "/"})

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def close(self) -> None:
        if self.sid:
            try:
                await self.call("core/logout", {}, retries=1)
            except GpsError:
                pass
            self.sid = None
        await self._http.aclose()

    async def call(self, svc: str, params: dict, retries: int = 3):
        if svc not in READ_ONLY:
            raise GpsForbidden(f"{svc}: faqat o'qish buyruqlariga ruxsat bor — yuborilmadi")
        data = {"svc": svc, "params": json.dumps(params, ensure_ascii=False)}
        if self.sid:
            data["sid"] = self.sid
        last: str = ""
        for attempt in range(retries):
            try:
                r = await self._http.post(self.url, data=data)
            except httpx.HTTPError as e:
                last = f"tarmoq xatosi: {e.__class__.__name__}"
                await asyncio.sleep(self.retry_delay * (attempt + 1))
                continue
            if r.status_code != 200:
                last = f"HTTP {r.status_code}"
                if r.status_code in (401, 403, 404):
                    break
                await asyncio.sleep(self.retry_delay * (attempt + 1))
                continue
            try:
                res = r.json()
            except ValueError:
                last = "javob JSON emas"
                break
            if isinstance(res, dict) and res.get("error", 0) != 0:
                code = res["error"]
                if code == 1003 and attempt < retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                raise GpsError(f"{svc}: xato {code} ({ERR.get(code, '')}) {res.get('reason', '')}".strip(), code)
            return res
        raise GpsError(f"{svc}: server so'rovni qabul qilmadi ({last})")

    async def login(self, token: str) -> str:
        res = await self.call("token/login", {"token": token, "fl": 1})
        self.sid = res.get("eid")
        self.user = res.get("au") or (res.get("user") or {}).get("nm") or ""
        return self.user

    async def token_access(self, token: str) -> int | None:
        """Shu tokenning huquqlari (access_type). Server token/list'ni bermasa — None."""
        try:
            res = await self.call("token/list", {}, retries=1)
        except GpsError:
            return None
        for t in res if isinstance(res, list) else []:
            if str(t.get("h", "")).lower() == token.lower():
                try:
                    return int(t.get("at"))
                except (TypeError, ValueError):
                    return None
        return None

    async def search(self, items_type: str, flags: int, prop: str = "sys_name", mask: str = "*") -> list[dict]:
        spec = {"itemsType": items_type, "propName": prop, "propValueMask": mask, "sortType": "sys_name"}
        res = await self.call("core/search_items", {"spec": spec, "force": 1, "flags": flags, "from": 0, "to": 0})
        return res.get("items", []) or []

    async def zone_data(self, resource_id: int, ids: list[int]) -> list[dict]:
        out: list[dict] = []
        for i in range(0, len(ids), 500):
            out += await self.call("resource/get_zone_data", {"itemId": resource_id, "col": ids[i:i + 500], "flags": 0x1F}) or []
        return out


def is_read_only(access: int | None) -> bool:
    """None — tekshirib bo'lmadi (server token/list bermadi): klientdagi buyruqlar ro'yxati baribir faqat o'qishga ruxsat beradi."""
    if access is None:
        return True
    return access != -1 and not (access & WRITE_BITS)
