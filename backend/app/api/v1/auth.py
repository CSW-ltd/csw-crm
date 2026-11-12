from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, current_user
from app.core.config import get_settings
from app.core.demo import accounts as demo_accounts
from app.core.errors import AppError
from app.core.portals import check_portal, normalize_host, portal_roles
from app.core.security import ACCESS, REFRESH, create_token, decode_token
from app.models import User
from app.repositories import users as users_repo
from app.schemas import ChangePasswordIn, LoginIn, LoginOut, MeOut, RefreshIn
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_PATH = "/api/v1/auth"


def _set_cookies(resp: Response, user: User) -> None:
    s = get_settings()
    common = {"httponly": True, "secure": s.cookie_secure, "samesite": "lax"}
    resp.set_cookie("access_token", create_token(user.id, user.role.value, ACCESS),
                    max_age=s.access_token_minutes * 60, path="/", **common)
    resp.set_cookie("refresh_token", create_token(user.id, user.role.value, REFRESH),
                    max_age=s.refresh_token_days * 86400, path=REFRESH_PATH, **common)


def _tab_mode(request: Request) -> bool:
    """Demo/sinov rejimi: frontend `X-Session-Mode: tab` yuborsa, tokenlar tabning o'z xotirasida saqlanadi."""
    return get_settings().tab_sessions and request.headers.get("x-session-mode") == "tab"


def _issue(request: Request, response: Response, user: User) -> LoginOut:
    out = LoginOut.model_validate(user)
    if _tab_mode(request):
        out.access_token = create_token(user.id, user.role.value, ACCESS)
        out.refresh_token = create_token(user.id, user.role.value, REFRESH)
    else:
        _set_cookies(response, user)
    return out


@router.get("/config")
async def auth_config(request: Request) -> dict:
    """Frontend uchun: tab sessiyalari, demo rejimi, faol rollar (None — hammasi faol) va joriy portal.

    portal: None — cheklov yo'q (ROLE_HOSTS bo'sh); {"host", "roles"} — shu subdomen rollari (bo'sh — noma'lum host).
    """
    s = get_settings()
    demo = s.app_env == "demo"
    roles = portal_roles(request.headers.get("host"))
    accounts = demo_accounts() if demo else []
    if roles is not None:
        accounts = [a for a in accounts if a["role"] in roles]
    portal = None if roles is None else {"host": normalize_host(request.headers.get("host")), "roles": sorted(roles)}
    return {"tab_sessions": s.tab_sessions, "demo": demo, "active_roles": s.active_role_list,
            "demo_accounts": accounts, "portal": portal}


@router.post("/login", response_model=LoginOut)
async def login(body: LoginIn, request: Request, response: Response, db: AsyncSession = DB):
    user = await auth_service.login(db, body.username, body.password, request.headers.get("host"))
    return _issue(request, response, user)


@router.post("/refresh", response_model=LoginOut)
async def refresh(request: Request, response: Response, body: RefreshIn | None = None, db: AsyncSession = DB):
    token = body.refresh_token if body and body.refresh_token and _tab_mode(request) else request.cookies.get("refresh_token")
    data = decode_token(token, REFRESH) if token else None
    user = await users_repo.by_id(db, int(data["sub"])) if data else None
    if not user or not user.is_active or not get_settings().role_active(user.role.value):
        raise AppError(401, "not_authenticated", "Sessiya tugadi, qayta kiring")
    check_portal(request.headers.get("host"), user.role.value)
    return _issue(request, response, user)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path=REFRESH_PATH)


@router.post("/change-password", response_model=MeOut)
async def change_password(body: ChangePasswordIn, user: User = Depends(current_user), db: AsyncSession = DB):
    return await auth_service.change_password(db, user, body.current_password, body.new_password)


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(current_user)):
    return user
