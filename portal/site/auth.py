# -*- coding: utf-8 -*-
"""OAuth 登录（GitHub / Google / 微信）——身份识别，不做任何内容限权。

流程（标准 Authorization Code）：
  /登录/github        → 302 到 GitHub 授权页
  /登录/github/回调    → 换 token → 拉用户信息 → upsert users → 发会话 cookie → 302 回原页
  /退出登录           → 清 cookie → 302 首页

凭据全部从环境变量读：GITHUB_CLIENT_ID/SECRET、GOOGLE_CLIENT_ID/SECRET、
WECHAT_APPID/SECRET。未配置的渠道在登录页自动隐藏。
线上跑在 imfde.ai 域；本地开发用 IMFOAUTHBASE 环境变量覆盖回调基地址。

会话：签名 cookie（itsdangerous 风格 HMAC-SHA256，自实现免依赖），
线上/本地共用 SECRET_KEY 环境变量。users/sessions 表建在现有 sqlite 库。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path

SESSION_COOKIE = "imfde_session"
SESSION_TTL = 60 * 60 * 24 * 30  # 30 天


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _secret_key() -> bytes:
    key = _env("SECRET_KEY")
    if not key:
        key = "imfde-dev-secret"  # 本地开发兜底；线上必须设 SECRET_KEY
    return key.encode("utf-8")


# ---------- 基地址（回调用） ----------
def base_url(host: str = "", scheme: str = "") -> str:
    env = _env("IMFOAUTHBASE")
    if env:
        return env.rstrip("/")
    if host:
        sch = scheme or ("https" if "imfde.ai" in host else "http")
        return f"{sch}://{host}"
    return "https://imfde.ai"


def callback_uri(base: str, provider: str) -> str:
    """OAuth 回调地址（纯 ASCII，供 Google 等严格要求 redirect_uri 的渠道）。

    Google 不接受含中文或多段路径的重定向 URI，故回调地址统一用 /oauth/<provider>/callback，
    与用户可见的 /登录/<provider> 入口解耦。回调进来的请求仍由 render_path 路由到 _handle_auth。
    """
    return f"{base}/oauth/{provider}/callback"


def providers_enabled() -> dict:
    return {
        "github": bool(_env("GITHUB_CLIENT_ID") and _env("GITHUB_CLIENT_SECRET")),
        "google": bool(_env("GOOGLE_CLIENT_ID") and _env("GOOGLE_CLIENT_SECRET")),
        "wechat": bool(_env("WECHAT_APPID") and _env("WECHAT_SECRET")),
    }


# ---------- 签名 cookie（HMAC，无第三方依赖） ----------
def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def sign_session(payload: dict) -> str:
    body = _b64e(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode())
    mac = hmac.new(_secret_key(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def verify_session(token: str) -> dict | None:
    if not token or "." not in token:
        return None
    body, mac = token.rsplit(".", 1)
    expect = hmac.new(_secret_key(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expect):
        return None
    try:
        payload = json.loads(_b64d(body))
    except (ValueError, TypeError):
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload


# ---------- users 表 ----------
def ensure_tables(con: sqlite3.Connection) -> None:
    con.execute(
        """CREATE TABLE IF NOT EXISTS users(
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             provider TEXT NOT NULL,
             provider_uid TEXT NOT NULL,
             name TEXT DEFAULT '',
             email TEXT DEFAULT '',
             avatar TEXT DEFAULT '',
             first_seen TEXT DEFAULT (datetime('now')),
             last_seen TEXT DEFAULT (datetime('now')),
             seen_count INTEGER DEFAULT 1,
             UNIQUE(provider, provider_uid))"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS oauth_states(
             state TEXT PRIMARY KEY,
             created REAL,
             next TEXT DEFAULT '/')"""
    )
    con.commit()


def upsert_user(con: sqlite3.Connection, provider: str, uid: str, name: str, email: str, avatar: str) -> int:
    ensure_tables(con)
    con.execute(
        """INSERT INTO users(provider, provider_uid, name, email, avatar)
           VALUES(?,?,?,?,?)
           ON CONFLICT(provider, provider_uid) DO UPDATE SET
             name=excluded.name, email=excluded.email, avatar=excluded.avatar,
             last_seen=datetime('now'), seen_count=seen_count+1""",
        (provider, str(uid), name or "", email or "", avatar or ""),
    )
    row = con.execute(
        "SELECT id FROM users WHERE provider=? AND provider_uid=?", (provider, str(uid))
    ).fetchone()
    con.commit()
    return int(row[0])


def put_state(con: sqlite3.Connection, state: str, nxt: str) -> None:
    ensure_tables(con)
    con.execute("INSERT OR REPLACE INTO oauth_states(state, created, next) VALUES(?,?,?)", (state, time.time(), nxt))
    con.execute("DELETE FROM oauth_states WHERE created < ?", (time.time() - 3600,))
    con.commit()


def pop_state(con: sqlite3.Connection, state: str) -> str | None:
    ensure_tables(con)
    row = con.execute("SELECT next FROM oauth_states WHERE state=?", (state,)).fetchone()
    if row:
        con.execute("DELETE FROM oauth_states WHERE state=?", (state,))
        con.commit()
        return row[0]
    return None


# ---------- 自包含 state（Vercel serverless 只读，无法写 oauth_states 表） ----------
# state = base64url(next) + "." + hmac 签名；回调验签还原 next，不依赖数据库。
def make_state(nxt: str) -> str:
    body = _b64e((nxt or "/").encode())
    mac = hmac.new(_secret_key(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def verify_state(state: str) -> str | None:
    """返回合法的 next；非法/篡改返回 None。"""
    if not state or "." not in state:
        return None
    body, mac = state.rsplit(".", 1)
    expect = hmac.new(_secret_key(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expect):
        return None
    try:
        return _b64d(body).decode()
    except Exception:
        return None


# ---------- 各渠道授权 URL / token / userinfo ----------
def _http_json(url: str, data: dict | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data or {}).encode() if data else None,
                                 headers=headers or {"User-Agent": "imfde.ai"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"{url} HTTP {e.code}: {body[:300]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"{url} 网络错误: {e.reason}") from e


def _http_token(url: str, data: dict, auth: tuple | None = None, accept_json: bool = True) -> dict:
    headers = {"Accept": "application/json" if accept_json else "application/x-www-form-urlencoded",
               "User-Agent": "imfde.ai"}
    if auth:
        import base64 as b
        headers["Authorization"] = "Basic " + b.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"{url} HTTP {e.code}: {body_txt[:300]}") from e
    try:
        obj = json.loads(text)
    except ValueError:
        obj = dict(urllib.parse.parse_qsl(text))
    # GitHub 等换 token 失败时返回 200 + error 字段，不是 HTTP 错误 —— 显式抛出便于定位
    if isinstance(obj, dict) and obj.get("error"):
        raise RuntimeError(f"{url} OAuth error: {obj.get('error')}: {obj.get('error_description', '')}")
    return obj


def authorize_url(provider: str, redirect_uri: str, state: str) -> str:
    if provider == "github":
        q = urllib.parse.urlencode({"client_id": _env("GITHUB_CLIENT_ID"), "redirect_uri": redirect_uri,
                                    "scope": "read:user user:email", "state": state})
        return f"https://github.com/login/oauth/authorize?{q}"
    if provider == "google":
        q = urllib.parse.urlencode({
            "client_id": _env("GOOGLE_CLIENT_ID"), "redirect_uri": redirect_uri,
            "response_type": "code", "scope": "openid email profile", "state": state,
            "access_type": "online", "prompt": "select_account"})
        return "https://accounts.google.com/o/oauth2/v2/auth?" + q
    if provider == "wechat":
        q = urllib.parse.urlencode({"appid": _env("WECHAT_APPID"), "redirect_uri": redirect_uri,
                                    "response_type": "code", "scope": "snsapi_login", "state": state})
        return "https://open.weixin.qq.com/connect/qrconnect?" + q
    raise ValueError(provider)


def fetch_user(provider: str, code: str, redirect_uri: str) -> dict:
    """code → {uid, name, email, avatar}"""
    if provider == "github":
        tok = _http_token("https://github.com/login/oauth/access_token",
                          {"client_id": _env("GITHUB_CLIENT_ID"), "client_secret": _env("GITHUB_CLIENT_SECRET"),
                           "code": code, "redirect_uri": redirect_uri})
        access = tok.get("access_token") or ""
        headers = {"Authorization": f"Bearer {access}", "User-Agent": "imfde.ai", "Accept": "application/vnd.github+json"}
        info = _http_json("https://api.github.com/user", headers=headers)
        email = info.get("email") or ""
        if not email:
            try:
                emails = _http_json("https://api.github.com/user/emails", headers=headers)
                email = next((e.get("email", "") for e in emails if e.get("primary")), "")
            except Exception:
                pass
        return {"uid": info.get("id"), "name": info.get("name") or info.get("login") or "",
                "email": email, "avatar": info.get("avatar_url") or ""}
    if provider == "google":
        tok = _http_token("https://oauth2.googleapis.com/token",
                          {"code": code, "client_id": _env("GOOGLE_CLIENT_ID"),
                           "client_secret": _env("GOOGLE_CLIENT_SECRET"), "redirect_uri": redirect_uri,
                           "grant_type": "authorization_code"})
        access = tok.get("access_token") or ""
        info = _http_json("https://www.googleapis.com/oauth2/v3/userinfo",
                          headers={"Authorization": f"Bearer {access}"})
        return {"uid": info.get("sub"), "name": info.get("name") or "", "email": info.get("email") or "",
                "avatar": info.get("picture") or ""}
    if provider == "wechat":
        tok = _http_token("https://api.weixin.qq.com/sns/oauth2/access_token",
                          {"appid": _env("WECHAT_APPID"), "secret": _env("WECHAT_SECRET"),
                           "code": code, "grant_type": "authorization_code"})
        access = tok.get("access_token") or ""
        openid = tok.get("openid") or ""
        info = _http_json(f"https://api.weixin.qq.com/sns/userinfo?access_token={access}&openid={openid}")
        return {"uid": openid, "name": info.get("nickname") or "", "email": "",
                "avatar": info.get("headimgurl") or ""}
    raise ValueError(provider)


# ---------- 会话读取（供页面渲染用） ----------
def current_user_cookie(cookies: dict) -> dict | None:
    token = cookies.get(SESSION_COOKIE)
    return verify_session(token) if token else None


def parse_cookies(header: str) -> dict:
    out = {}
    for part in (header or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = urllib.parse.unquote(v.strip())
    return out


def login_page_html(next_path: str, providers: dict, base: str) -> str:
    """极简登录页（不做限权，仅身份入口）。"""
    next_q = urllib.parse.quote(next_path or "/", safe="/")
    btns = []
    if providers.get("github"):
        btns.append(
            f'<a class="auth-btn auth-gh" href="{base}/login/github?next={next_q}">GitHub 登录</a>')
    if providers.get("google"):
        btns.append(
            f'<a class="auth-btn auth-google" href="{base}/login/google?next={next_q}">Google 登录</a>')
    if providers.get("wechat"):
        btns.append(
            f'<a class="auth-btn auth-wechat" href="{base}/login/wechat?next={next_q}">微信登录</a>')
    if not btns:
        btns.append('<p class="auth-empty">登录渠道未配置（需在部署环境设置 OAuth 凭据环境变量）。</p>')
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>登录 · imfde.ai</title>
<style>
body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
  background:#020a12;color:#eeebe5;font:16px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}}
.auth-card{{text-align:center;padding:48px 56px;border:1px solid rgba(143,178,196,.2);border-radius:16px;
  background:rgba(7,19,30,.8)}}
.auth-card h1{{font-size:20px;margin:0 0 8px}}
.auth-card p.k{{font-size:13px;color:#7f8b93;margin:0 0 28px}}
.auth-btn{{display:block;width:240px;margin:0 auto 12px;padding:12px 0;border-radius:10px;
  text-decoration:none;font-weight:650;font-size:14px;border:1px solid rgba(143,178,196,.3);color:#eeebe5;
  transition:border-color .15s,background .15s}}
.auth-btn:hover{{border-color:#3fc0c0;background:rgba(63,192,192,.08)}}
.auth-gh{{background:#0d1117}}
.auth-google{{background:#fff;color:#1f2328}}
.auth-wechat{{background:#07c160;color:#fff;border-color:#07c160}}
.auth-empty{{color:#7f8b93;font-size:14px}}
</style>
</head>
<body>
<div class="auth-card">
  <h1>登录 imfde.ai</h1>
  <p class="k">登录后内容不变 —— 全站依然免费开放，仅用于展示头像与昵称。</p>
  {''.join(btns)}
</div>
</body>
</html>"""
