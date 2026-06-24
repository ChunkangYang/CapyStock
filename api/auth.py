"""Google OAuth 登入 + email 白名單 + 存取閘門（外網部署用）。

設計重點（可在 public GitHub repo 安全使用）：
  - **Client Secret 絕不進 repo**：只從環境變數讀取，secret 放在 PaaS 的加密環境變數。
  - **email 白名單**：只有 `CAPYSTOCK_ALLOWED_EMAILS` 列出的 Google 帳號能登入，
    其他人即使用 Google 登入也回 403。
  - **預設關閉**：未設定 `GOOGLE_CLIENT_ID` / 白名單時 auth 完全停用，
    本地開發與既有 Docker 行為不變（零回歸）。

環境變數：
  GOOGLE_CLIENT_ID          Google OAuth 2.0 Client ID（公開不敏感）
  GOOGLE_CLIENT_SECRET      Google OAuth 2.0 Client Secret（敏感，只放主機 env）
  CAPYSTOCK_ALLOWED_EMAILS  允許登入的 email，逗號分隔（小寫比對）
  CAPYSTOCK_SESSION_SECRET  session cookie 簽章用 secret（未設則隨機，重啟需重新登入）
  CAPYSTOCK_PUBLIC_BASE_URL 對外網址（如 https://capystock.onrender.com），
                            用於組 OAuth redirect_uri；未設則用 request.base_url 推導
"""
from __future__ import annotations

import os
import secrets

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

# Authlib 為選用相依：未安裝（或未啟用 auth）時不應讓整個 app 起不來。
try:
    from authlib.integrations.starlette_client import OAuth  # type: ignore

    _AUTHLIB_AVAILABLE = True
except Exception:  # noqa: BLE001
    OAuth = None  # type: ignore
    _AUTHLIB_AVAILABLE = False


GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# 永遠放行（不需登入）的路徑前綴 / 完整路徑：
#  - /auth/*        登入流程本身
#  - /api/v1/health PaaS healthcheck 必須匿名可打
_PUBLIC_PREFIXES = ("/auth/",)
_PUBLIC_EXACT = {"/api/v1/health"}


def allowed_emails() -> set[str]:
    raw = os.environ.get("CAPYSTOCK_ALLOWED_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def auth_enabled() -> bool:
    """有 client id/secret + 白名單 + authlib 才算啟用。任一缺則停用（本地零回歸）。"""
    return bool(
        _AUTHLIB_AVAILABLE
        and os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        and os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
        and allowed_emails()
    )


def is_email_allowed(email: str | None) -> bool:
    if not email:
        return False
    return email.strip().lower() in allowed_emails()


def is_public_path(path: str) -> bool:
    if path in _PUBLIC_EXACT:
        return True
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)


def current_user(request: Request) -> dict | None:
    """從 session 取目前登入者（且 email 仍在白名單內）。"""
    try:
        user = request.session.get("user")
    except Exception:  # noqa: BLE001 — SessionMiddleware 未掛時
        return None
    if user and is_email_allowed(user.get("email")):
        return user
    return None


def session_secret() -> str:
    return os.environ.get("CAPYSTOCK_SESSION_SECRET", "").strip() or secrets.token_hex(32)


# --- OAuth client（lazy 建立，避免未啟用時碰 authlib）---
_oauth = None


def _get_oauth():
    global _oauth
    if _oauth is not None:
        return _oauth
    oauth = OAuth()
    oauth.register(
        name="google",
        server_metadata_url=GOOGLE_DISCOVERY_URL,
        client_id=os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", "").strip(),
        client_kwargs={"scope": "openid email profile"},
    )
    _oauth = oauth
    return _oauth


def _redirect_uri(request: Request) -> str:
    base = os.environ.get("CAPYSTOCK_PUBLIC_BASE_URL", "").strip()
    if base:
        return base.rstrip("/") + "/auth/callback"
    # 推導；proxy-headers 讓 base_url 帶正確 scheme（https）
    return str(request.url_for("auth_callback"))


# --- ASGI 閘門：放在 SessionMiddleware 內層，純 ASGI 不干擾 SSE/streaming ---
class AuthGateMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not auth_enabled():
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        if is_public_path(path):
            return await self.app(scope, receive, send)

        session = scope.get("session") or {}
        user = session.get("user")
        if user and is_email_allowed(user.get("email")):
            return await self.app(scope, receive, send)

        if path.startswith("/api/"):
            response = JSONResponse({"detail": "未登入或無權限"}, status_code=401)
        else:
            response = RedirectResponse(url="/auth/login", status_code=302)
        return await response(scope, receive, send)


def register_auth(app) -> bool:
    """把登入相關路由掛上 app。回傳是否啟用 auth（供 main.py 決定要不要掛閘門）。

    路由永遠掛（即使未啟用），這樣 /auth/me 在停用時也能誠實回 {enabled:false}。
    """

    @app.get("/auth/me", include_in_schema=False)
    async def auth_me(request: Request):
        if not auth_enabled():
            return {"enabled": False, "user": None}
        return {"enabled": True, "user": current_user(request)}

    @app.get("/auth/login", include_in_schema=False)
    async def auth_login(request: Request):
        if not auth_enabled():
            return RedirectResponse(url="/", status_code=302)
        oauth = _get_oauth()
        return await oauth.google.authorize_redirect(request, _redirect_uri(request))

    @app.get("/auth/callback", name="auth_callback", include_in_schema=False)
    async def auth_callback(request: Request):
        if not auth_enabled():
            return RedirectResponse(url="/", status_code=302)
        oauth = _get_oauth()
        try:
            token = await oauth.google.authorize_access_token(request)
        except Exception as e:  # noqa: BLE001
            return HTMLResponse(_deny_html(f"登入失敗：{e}"), status_code=400)

        userinfo = token.get("userinfo")
        if not userinfo:
            try:
                userinfo = await oauth.google.userinfo(token=token)
            except Exception:  # noqa: BLE001
                userinfo = None
        email = (userinfo or {}).get("email")

        if not is_email_allowed(email):
            request.session.pop("user", None)
            return HTMLResponse(
                _deny_html(f"此 Google 帳號（{email or '未知'}）無權限存取此系統。"),
                status_code=403,
            )

        request.session["user"] = {
            "email": email,
            "name": (userinfo or {}).get("name"),
            "picture": (userinfo or {}).get("picture"),
        }
        return RedirectResponse(url="/", status_code=302)

    @app.get("/auth/logout", include_in_schema=False)
    async def auth_logout(request: Request):
        try:
            request.session.pop("user", None)
        except Exception:  # noqa: BLE001
            pass
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
            "<h2>已登出</h2><p><a href='/auth/login'>重新登入</a></p></body></html>"
        )

    return auth_enabled()


def _deny_html(msg: str) -> str:
    return (
        "<html><body style='font-family:sans-serif;text-align:center;margin-top:80px'>"
        f"<h2>⛔ 無法存取</h2><p>{msg}</p>"
        "<p><a href='/auth/logout'>用其他帳號登入</a></p></body></html>"
    )
