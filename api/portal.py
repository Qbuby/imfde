# -*- coding: utf-8 -*-
"""Vercel Python Serverless 入口 —— 完整动态内容服务。

把 portal/site/server.py 的渲染层包装为 Vercel Serverless Function：
- /api/portal/<路由>   → 动态渲染（世界动态/落地/现场/案例/方法/world3d）
- /api/portal/static/* → 静态资源（CSS/JS/three.js/icons）

本地等价命令：python portal/site/server.py（0.0.0.0:8850）

Vercel Python runtime 会自动注入 asgi_app。
"""
from __future__ import annotations

import mimetypes
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

# 让 api/ 目录能 import portal/site
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "portal" / "site"))

import server as S  # noqa: E402

STATIC_DIR = S.STATIC_DIR

CACHE_HTML = {"Cache-Type": "text/html", "Cache-Control": "no-store"}


def _resp(status: int, body: bytes, content_type: str, extra: dict | None = None):
    headers = {"Content-Type": content_type}
    if extra:
        headers.update(extra)
    return Response(body, status_code=status, headers=headers, media_type=content_type)


async def asgi_app(scope, receive, send):  # noqa: ANN001
    """ASGI 入口：Vercel Python runtime 直接调用。"""
    if scope["type"] != "http":
        return
    raw_path = scope.get("path", "/")
    method = scope.get("method", "GET")

    # /api/portal/xxx → 服务内路径 /xxx
    prefix = "/api/portal"
    path = unquote(raw_path)
    if path.startswith(prefix):
        path = path[len(prefix):] or "/"
    else:
        # 非本入口路径（如 /、/portal/*.html 静态导出）不在此处理
        path = None

    headers = {}
    if path is None or method != "GET":
        body = b"not found"
        await _asgi_send(send, 404, body, "text/plain; charset=utf-8")
        return

    path = S.normalize_path(path.rstrip("/") or "/")
    query = scope.get("query_string", b"").decode("utf-8")
    qs = parse_qs(query, keep_blank_values=False)

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
        from worldview import load_world
        with S.connect() as con:
            payload = load_world(con.cursor())
        import json
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        await _asgi_send(send, 200, body, "application/json; charset=utf-8")
        return

    # ---- 页面渲染 ----
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


async def _asgi_send(send, status: int, body: bytes, content_type: str):
    from http import HTTPStatus
    reason = HTTPStatus(status).phrase
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", content_type.encode()],
            [b"content-length", str(len(body)).encode()],
            [b"cache-control", b"no-store"],
        ],
    })
    await send({"type": "http.response.body", "body": body})


app = asgi_app
