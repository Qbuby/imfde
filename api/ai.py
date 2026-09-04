# -*- coding: utf-8 -*-
"""Vercel Serverless：AI 解读代理。

为什么走服务端：AI_API_KEY 只存在于环境变量（Vercel 项目设置里配置），
绝不进浏览器、绝不入仓。前端把这个函数当作 /api/ai 调用。

环境变量（Vercel → Settings → Environment Variables）：
  AI_BASE_URL  默认 https://api.airy.work/v1
  AI_API_KEY   必填，留空则本接口返回 503 且前端隐藏 AI 入口
  AI_MODEL     默认 gpt-5.6-luna
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_store  # noqa: E402

AI_BASE_URL = (os.environ.get("AI_BASE_URL") or "https://api.airy.work/v1").rstrip("/")
AI_API_KEY = (os.environ.get("AI_API_KEY") or "").strip()
AI_MODEL = (os.environ.get("AI_MODEL") or "gpt-5.6-luna").strip()

SYSTEM_PROMPT = """你是 Forward Deployed Engineering（FDE）领域的资深分析师。
给用户一段「可核对的公开原文材料」（含结构化字段），输出两部分：

1) 结论（3-5 条）：这条材料真正在说什么，对 FDE 从业者/企业决策者分别意味着什么。
   每条一句话，先说事实再说含义，不空谈。
2) 原文内容解读：基于下面的字段，把原文讲清楚——
   业务问题是什么、原来怎么做、卡在哪、AI 怎么接进去、怎么评测的、
   实测结果有哪些数字、失败与迭代是什么、最后有没有沉淀成产品能力。
   只依据给到的字段，不许编造；字段没写的明确说「原文未提」。

要求：简体中文。不吹捧、不写套话。直接给要点，不要复述我的提示词。"""


def _build_user(item: dict) -> str:
    lines = []
    for key in ("title", "kicker", "host", "day", "date_kind", "lane", "info_kind", "doc_label"):
        val = item.get(key)
        if val:
            lines.append(f"{key}: {val}")
    for key in ("happened", "why", "enterprise", "practitioner"):
        val = item.get(key)
        if val:
            lines.append(f"{key}: {val}")
    detail = item.get("detail") or {}
    if detail:
        lines.append("")
        lines.append("【原文结构化字段】")
        for k, v in detail.items():
            lines.append(f"- {k}: {v}")
    url = item.get("url") or detail.get("原文链接") or ""
    if url:
        lines.append("")
        lines.append(f"原文链接: {url}")
    return "\n".join(lines)


def _call_ai(user_content: str) -> str:
    if not AI_API_KEY:
        raise RuntimeError("AI_API_KEY 未配置")
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        AI_BASE_URL + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + AI_API_KEY,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=55) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (
        (data.get("choices") or [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )


async def _send(send, status: int, body: bytes, content_type: str = "application/json; charset=utf-8"):
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


async def app(scope, receive, send):  # noqa: ANN001
    if scope["type"] != "http":
        return
    method = (scope.get("method") or "GET").upper()

    # GET：探测 AI 是否可用（前端据此决定是否显示入口）
    if method == "GET":
        await _send(send, 200, json.dumps(
            {"enabled": bool(AI_API_KEY), "model": AI_MODEL}, ensure_ascii=False
        ).encode("utf-8"))
        return

    if method != "POST":
        await _send(send, 405, json.dumps({"error": "method not allowed"}).encode("utf-8"))
        return

    if not AI_API_KEY:
        await _send(send, 503, json.dumps(
            {"error": "AI 未配置（缺少 AI_API_KEY 环境变量）"}, ensure_ascii=False
        ).encode("utf-8"))
        return

    # 读请求体
    body = b""
    more = True
    while more:
        msg = await receive()
        body += msg.get("body", b"")
        more = msg.get("more_body", False)

    try:
        item = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        await _send(send, 400, json.dumps({"error": "请求体不是合法 JSON"}).encode("utf-8"))
        return
    if not isinstance(item, dict):
        await _send(send, 400, json.dumps({"error": "请求体应为 JSON 对象"}).encode("utf-8"))
        return

    # 持久化缓存命中 → 直接返回，零等待
    ident = str(item.get("id") or item.get("url") or json.dumps(
        {k: item.get(k) for k in ("title", "day", "lane")}, ensure_ascii=False
    ))
    snap = str(item.get("snapshot") or "")
    hit = ai_store.load("event", ident, snap)
    if hit and hit.get("text"):
        await _send(send, 200, json.dumps(
            {"text": hit["text"], "cached": True}, ensure_ascii=False
        ).encode("utf-8"))
        return

    try:
        text = _call_ai(_build_user(item))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        await _send(send, 502, json.dumps(
            {"error": f"上游 AI 返回 {e.code}", "detail": detail}, ensure_ascii=False
        ).encode("utf-8"))
        return
    except Exception as e:  # noqa: BLE001
        await _send(send, 502, json.dumps(
            {"error": "AI 调用失败", "detail": str(e)[:300]}, ensure_ascii=False
        ).encode("utf-8"))
        return

    # 生成成功 → 立即持久化（下次秒回）
    try:
        ai_store.save("event", ident, snap, {"text": text, "title": item.get("title", "")})
    except Exception:
        pass

    await _send(send, 200, json.dumps({"text": text, "cached": False}, ensure_ascii=False).encode("utf-8"))
