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
import sys
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "portal" / "site"))

import server as S  # noqa: E402

STATIC_DIR = S.STATIC_DIR


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

    # ---- 页面渲染（完整 server.py 渲染层）----
    try:
        page = S.render_path(path, qs)
    except Exception:
        import traceback
        body = ("查询失败\n" + traceback.format_exc()).encode("utf-8")
        await _asgi_send(send, 500, body, "text/plain; charset=utf-8")
        return
    if not page:
        await _asgi_send(send, 404, b"not found", "text/plain; charset=utf-8")
        return
    await _asgi_send(send, 200, page.encode("utf-8"), "text/html; charset=utf-8")
