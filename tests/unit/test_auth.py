"""api.auth：Google 登入閘門 + email 白名單測試。

不需要真的打 Google — 驗證的是「閘門擋誰、放誰」與「白名單比對」這層純邏輯，
以及啟用/停用 auth 時對既有路由的影響（停用＝零回歸）。
"""
import importlib

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from api import auth as auth_module


@pytest.fixture
def enable_auth(monkeypatch):
    """強制啟用 auth（不依賴 authlib 是否安裝，閘門本身不碰 authlib）。"""
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "dummy-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "dummy-secret")
    monkeypatch.setenv("CAPYSTOCK_ALLOWED_EMAILS", "cky1983@gmail.com, Other@Example.com")
    monkeypatch.setattr(auth_module, "_AUTHLIB_AVAILABLE", True)


# --- 純邏輯 ---

def test_allowed_emails_parse_and_normalize(monkeypatch):
    monkeypatch.setenv("CAPYSTOCK_ALLOWED_EMAILS", " A@b.com ,  c@D.com ,,")
    assert auth_module.allowed_emails() == {"a@b.com", "c@d.com"}


def test_is_email_allowed_case_insensitive(enable_auth):
    assert auth_module.is_email_allowed("CKY1983@GMAIL.com") is True
    assert auth_module.is_email_allowed("other@example.com") is True
    assert auth_module.is_email_allowed("intruder@evil.com") is False
    assert auth_module.is_email_allowed(None) is False
    assert auth_module.is_email_allowed("") is False


def test_auth_disabled_when_unconfigured(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("CAPYSTOCK_ALLOWED_EMAILS", raising=False)
    assert auth_module.auth_enabled() is False


def test_auth_disabled_when_no_allowlist(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "x")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "y")
    monkeypatch.delenv("CAPYSTOCK_ALLOWED_EMAILS", raising=False)
    monkeypatch.setattr(auth_module, "_AUTHLIB_AVAILABLE", True)
    assert auth_module.auth_enabled() is False


def test_public_paths(enable_auth):
    assert auth_module.is_public_path("/api/v1/health") is True
    assert auth_module.is_public_path("/auth/login") is True
    assert auth_module.is_public_path("/auth/callback") is True
    assert auth_module.is_public_path("/api/v1/scan/signals") is False
    assert auth_module.is_public_path("/") is False


# --- 閘門整合（最小 app，套用與 main.py 相同的中介層順序）---

def _build_app(auth_on: bool) -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/health")
    def health():
        return {"ok": True}

    @app.get("/api/v1/secret")
    def secret():
        return {"secret": 42}

    @app.get("/page")
    def page():
        return {"page": True}

    @app.get("/auth/test-login")
    def login(request: Request):  # 測試用：模擬 OAuth callback（/auth/* 為公開路徑）寫入 session
        request.session["user"] = {"email": "cky1983@gmail.com"}
        return {"logged_in": True}

    # 與 main.py 同序：先 Gate（內層）、再 Session（外層）
    if auth_on:
        app.add_middleware(auth_module.AuthGateMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret", same_site="lax")
    return app


def test_gate_blocks_api_without_login(enable_auth):
    client = TestClient(_build_app(auth_on=True))
    # 公開路徑放行
    assert client.get("/api/v1/health").status_code == 200
    # 受保護 API → 401 JSON
    r = client.get("/api/v1/secret")
    assert r.status_code == 401
    assert r.json()["detail"]


def test_gate_redirects_html_without_login(enable_auth):
    client = TestClient(_build_app(auth_on=True), follow_redirects=False)
    r = client.get("/page")
    assert r.status_code == 302
    assert r.headers["location"] == "/auth/login"


def test_gate_allows_after_login(enable_auth):
    client = TestClient(_build_app(auth_on=True))
    # 先「登入」寫 session（cookie 會被 TestClient 保留）
    assert client.get("/auth/test-login").json()["logged_in"] is True
    # 帶著 session 再打受保護 API → 放行
    r = client.get("/api/v1/secret")
    assert r.status_code == 200
    assert r.json()["secret"] == 42


def test_gate_rejects_non_allowlisted_session(enable_auth, monkeypatch):
    """session 帶了非白名單 email → 仍視為未授權。"""
    app = FastAPI()

    @app.get("/api/v1/secret")
    def secret():
        return {"secret": 42}

    @app.get("/auth/test-login-bad")
    def login_bad(request: Request):
        request.session["user"] = {"email": "intruder@evil.com"}
        return {"ok": True}

    app.add_middleware(auth_module.AuthGateMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    client = TestClient(app)
    client.get("/auth/test-login-bad")
    assert client.get("/api/v1/secret").status_code == 401


def test_auth_disabled_passes_everything(monkeypatch):
    """未設定 auth → 閘門根本不掛，所有路由照常（零回歸）。"""
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("CAPYSTOCK_ALLOWED_EMAILS", raising=False)
    client = TestClient(_build_app(auth_on=False))
    assert client.get("/api/v1/secret").status_code == 200
    assert client.get("/page").status_code == 200
