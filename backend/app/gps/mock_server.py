"""Soxta SmartGPS (Wialon Local) — test server (dispatch.test.csw.uz) va pytest uchun. FAQAT SUN'IY MA'LUMOT.

    python -m app.gps.mock_server            # 0.0.0.0:8765

Qo'llab-quvvatlaydi: login.html (token bilan redirect_uri'ga qaytaradi), token/login, token/list, core/search_items
(avl_resource zl/zg bilan, avl_unit, avl_unit_group), resource/get_zone_data, core/logout. Har qanday boshqa svc — xato 5.
Production'da ishga tushmaydi."""
import json
import os
from urllib.parse import urlencode

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

MOCK_TOKEN = "a1" * 36  # 72 belgi — soxta, faqat test uchun
MOCK_USER = "test_akkaunt"
RID = 501

STATE = {  # testlar o'zgartirishi mumkin (masalan geozonani o'chirish)
    "tokens": {MOCK_TOKEN: {"user": MOCK_USER, "at": 0x300}},
    "zones": {
        1: {"id": 1, "n": "1", "t": 1, "w": 30, "c": 0x00FF00, "p": [{"x": 70.501, "y": 40.501}, {"x": 70.502, "y": 40.502}]},
        2: {"id": 2, "n": "2", "t": 1, "w": 30, "c": 0x00FF00, "p": [{"x": 70.505, "y": 40.505}, {"x": 70.506, "y": 40.506}]},
        3: {"id": 3, "n": "Test MFY-1 chegara", "t": 2, "c": 0x3388FF,
            "p": [{"x": 70.5, "y": 40.5}, {"x": 70.52, "y": 40.5}, {"x": 70.52, "y": 40.52}, {"x": 70.5, "y": 40.52}]},
        4: {"id": 4, "n": "Test МСП-1", "t": 3, "c": 0xFF0000, "p": [{"x": 70.51, "y": 40.51, "r": 25}]},
        5: {"id": 5, "n": "Test konteyner-1", "t": 3, "c": 0xFF8800, "p": [{"x": 70.512, "y": 40.512, "r": 15}]},
    },
    "zgroups": {1: {"id": 1, "n": "Test МСП guruhi", "zns": [4]}, 2: {"id": 2, "n": "Test konteynerlar", "zns": [5]}},
    "units": {9001: "01 001 AAA (test)", 9002: "60 101 AB", 9003: "99 999 ZZZ"},
    "unit_groups": {7001: {"id": 7001, "nm": "Test tumani mashinalari", "u": [9001, 9002]}},
    "calls": [],
}


def _resource() -> dict:
    return {"id": RID, "nm": "Test resurs",
            "zl": {str(i): {"id": i, "n": z["n"], "t": z["t"]} for i, z in STATE["zones"].items()},
            "zg": {str(i): g for i, g in STATE["zgroups"].items()}}


async def ajax(request: Request):
    form = await request.form()
    svc = form.get("svc", "")
    params = json.loads(form.get("params") or "{}")
    STATE["calls"].append(svc)
    if svc == "token/login":
        t = STATE["tokens"].get(params.get("token"))
        if not t:
            return JSONResponse({"error": 4})
        return JSONResponse({"eid": "mock-sid", "au": t["user"], "user": {"nm": t["user"]}})
    if svc == "token/list":
        return JSONResponse([{"h": h, "at": t["at"]} for h, t in STATE["tokens"].items()])
    if svc == "core/logout":
        return JSONResponse({"error": 0})
    if svc == "core/search_items":
        typ = (params.get("spec") or {}).get("itemsType")
        if typ == "avl_resource":
            items = [_resource()]
        elif typ == "avl_unit":
            items = [{"id": i, "nm": n} for i, n in STATE["units"].items()]
        elif typ == "avl_unit_group":
            items = list(STATE["unit_groups"].values())
        else:
            items = []
        return JSONResponse({"items": items, "totalItemsCount": len(items)})
    if svc == "resource/get_zone_data":
        return JSONResponse([STATE["zones"][i] for i in params.get("col") or [] if i in STATE["zones"]])
    return JSONResponse({"error": 5, "reason": f"mock: {svc} qo'llab-quvvatlanmaydi"})


async def login_page(request: Request):
    """Haqiqiy login.html o'rniga: darhol redirect_uri'ga soxta token bilan qaytaradi."""
    uri = request.query_params.get("redirect_uri") or "/"
    sep = "&" if "?" in uri else "?"
    return RedirectResponse(f"{uri}{sep}{urlencode({'access_token': MOCK_TOKEN, 'user_name': MOCK_USER, 'svc_error': 0})}")


app = Starlette(routes=[Route("/wialon/ajax.html", ajax, methods=["POST"]), Route("/login.html", login_page)])


if __name__ == "__main__":
    if os.environ.get("APP_ENV") == "production" and not os.environ.get("GPS_MOCK_ALLOW"):
        raise SystemExit("Soxta SmartGPS production'da ishga tushmaydi")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("GPS_MOCK_PORT", "8765")))
