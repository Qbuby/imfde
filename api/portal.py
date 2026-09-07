# -*- coding: utf-8 -*-
"""Vercel Python Serverless 入口 —— 完整动态内容服务。

包装 portal/site/server.py 的渲染层为 ASGI app：
- rewrites 把 /portal/* 打到本函数，真实路径经 ?__path= 传入
- /portal/static/* → 服务内 /static/*（CSS/JS/three.js/icons）
- 其余 /portal/*   → S.render_path()（世界动态/落地/现场/案例/案例/<id>/方法/world3d）

本地等价：python portal/site/server.py（0.0.0.0:8850）
"""
from __future__ import annotations

import mimetypes
import secrets
import sys
import time
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "portal" / "site"))

import server as S  # noqa: E402

STATIC_DIR = S.STATIC_DIR


import re

import auth as A  # 登录（/登录、/oauth）与页脚头像解析共用；放在模块级，避免函数内局部导入的 UnboundLocalError

# 内链前缀改写：页面在 /portal/* 下服务，服务端生成的站内绝对路径需要加 /portal 前缀。
# 只改站内根相对路径（href="/..."、src="/..."），不动外链（https://）、协议相对（//）、锚点。
_LINK_RE = re.compile(
    r'''(href|src|action)=(["'])/(?!/)([^"']*)\2''',
)


def _add_prefix(m: "re.Match") -> str:
    attr, quote, rest = m.group(1), m.group(2), m.group(3)
    # 已是 /portal 或 /api 之外的一律加前缀；/static、/案例、/落地、/世界动态 等
    return f'{attr}={quote}/portal/{rest}{quote}'


def _rewrite_links(html: str) -> str:
    # importmap JSON 内的模块路径（不是 HTML 属性，需单独改写）
    html = html.replace('"/static/vendor/', '"/portal/static/vendor/')
    return _LINK_RE.sub(_add_prefix, html)


async def _asgi_send(send, status: int, body: bytes, content_type: str, extra_headers: dict | None = None):
    headers = [
        [b"content-type", content_type.encode()],
        [b"content-length", str(len(body)).encode()],
        [b"cache-control", b"no-store"],
    ]
    for k, v in (extra_headers or {}).items():
        headers.append([k.lower().encode(), str(v).encode()])
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


async def app(scope, receive, send):  # noqa: ANN001
    if scope["type"] != "http":
        return
    method = scope.get("method", "GET")
    if method != "GET":
        await _asgi_send(send, 405, b"method not allowed", "text/plain; charset=utf-8")
        return

    # 真实路径：优先 ?__path=（rewrites 传入），回退 scope path
    import json as _json
    from urllib.parse import parse_qsl

    qs_pairs = parse_qsl(scope.get("query_string", b"").decode("utf-8"), keep_blank_values=True)
    qs = {}
    inner_path = None
    for k, v in qs_pairs:
        if k == "__path":
            inner_path = v
        else:
            qs.setdefault(k, []).append(v)

    if not inner_path:
        raw = unquote(scope.get("path", "/"))
        # 直接访问 /api/portal/* 的形式
        prefix = "/api/portal"
        if raw.startswith(prefix):
            inner_path = raw[len(prefix):] or "/"
        else:
            inner_path = raw

    path = unquote(inner_path)
    path = S.normalize_path(path.rstrip("/") or "/")

    # ---- 静态资源 ----
    if path.startswith("/static/"):
        rel = path[len("/static/"):]
        target = (STATIC_DIR / rel).resolve()
        root = STATIC_DIR.resolve()
        if root not in target.parents and target != root:
            await _asgi_send(send, 403, b"forbidden", "text/plain; charset=utf-8")
            return
        if not target.is_file():
            await _asgi_send(send, 404, b"not found", "text/plain; charset=utf-8")
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") and "charset" not in ctype:
            ctype += "; charset=utf-8"
        await _asgi_send(send, 200, target.read_bytes(), ctype)
        return

    # ---- API ----
    if path == "/api/world.json":
        import json
        from worldview import load_world
        with S.connect() as con:
            payload = load_world(con.cursor())
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        await _asgi_send(send, 200, body, "application/json; charset=utf-8")
        return

    # ---- 登录/退出（身份识别，不做限权）----
    if path.startswith("/登录") or path == "/退出登录" or path.startswith("/oauth/") or path == "/oauth":
        try:
            host = ""
            scheme = ""
            for h in scope.get("headers") or []:
                name = h[0].decode().lower()
                if name == "host":
                    host = h[1].decode()
                elif name == "x-forwarded-proto":
                    scheme = h[1].decode()
            base = A.base_url(host, scheme)
            cookies = A.parse_cookies(next((h[1].decode() for h in scope.get("headers") or [] if h[0].decode().lower() == "cookie"), ""))

            if path == "/退出登录":
                nxt = (qs.get("next") or ["/"])[0]
                await _asgi_send(send, 302, b"", "text/plain; charset=utf-8",
                                 {"Location": nxt, "Set-Cookie": f"{A.SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"})
                return

            # 归一化 /oauth/<p>[/callback] → 与 /登录/<p>[/回调] 同等处理
            m = re.fullmatch(r"/oauth/([A-Za-z0-9]+)(/callback)?", path)
            if m:
                provider_hit = m.group(1).lower()
                is_callback = bool(m.group(2))
                parts = ["", "登录", provider_hit] + (["回调"] if is_callback else [])
            else:
                parts = path.split("/")  # ['', '登录', 'github', '回调']
            if len(parts) < 3 or not parts[2]:
                page = A.login_page_html((qs.get("next") or ["/"])[0], A.providers_enabled(), base)
                await _asgi_send(send, 200, page.encode("utf-8"), "text/html; charset=utf-8")
                return

            provider = parts[2].lower()
            enabled = A.providers_enabled()
            nxt = (qs.get("next") or ["/"])[0]
            if not nxt.startswith("/"):
                nxt = "/"

            if len(parts) < 4 or parts[3] != "回调":
                # 第一步：发 state 并 302 到授权页（state 自包含，无需写库）
                if not enabled.get(provider):
                    page = A.login_page_html(nxt, enabled, base)
                    await _asgi_send(send, 200, page.encode("utf-8"), "text/html; charset=utf-8")
                    return
                state = A.make_state(nxt)
                redirect_uri = A.callback_uri(base, provider)
                await _asgi_send(send, 302, b"", "text/plain; charset=utf-8",
                                 {"Location": A.authorize_url(provider, redirect_uri, state)})
                return
            # 第二步：回调换用户信息
            code = (qs.get("code") or [""])[0]
            state = (qs.get("state") or [""])[0]
            stored_next = A.verify_state(state)
            if not code or not stored_next:
                await _asgi_send(send, 400, "登录状态失效，请重试".encode("utf-8"), "text/plain; charset=utf-8")
                return
            info = A.fetch_user(provider, code, A.callback_uri(base, provider))
            uid = info.get("uid") or ""
            token = A.sign_session({"uid": str(uid), "provider": provider, "name": info.get("name") or "",
                                    "avatar": info.get("avatar") or "", "exp": time.time() + A.SESSION_TTL})
        except Exception:
            import traceback
            await _asgi_send(send, 500, ("登录失败\n" + traceback.format_exc()).encode("utf-8"), "text/plain; charset=utf-8")
            return
        await _asgi_send(send, 302, b"", "text/plain; charset=utf-8",
                         {"Location": stored_next or "/",
                          "Set-Cookie": f"{A.SESSION_COOKIE}={urllib.parse.quote(token)}; Path=/; Max-Age={A.SESSION_TTL}; HttpOnly; SameSite=Lax"})
        return

    # ---- 页面渲染（完整 server.py 渲染层）----
    try:
        cookie_header = next((h[1].decode() for h in scope.get("headers") or [] if h[0].decode().lower() == "cookie"), "")
        S.set_request_cookies(A.parse_cookies(cookie_header))
        page = S.render_path(path, qs)
    except Exception:
        import traceback
        body = ("查询失败\n" + traceback.format_exc()).encode("utf-8")
        await _asgi_send(send, 500, body, "text/plain; charset=utf-8")
        return
    if not page:
        await _asgi_send(send, 404, b"not found", "text/plain; charset=utf-8")
        return
    await _asgi_send(send, 200, _rewrite_links(page).encode("utf-8"), "text/html; charset=utf-8")
