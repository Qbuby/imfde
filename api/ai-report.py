# -*- coding: utf-8 -*-
"""Vercel Serverless：AI 阶段报告（7/30/90 天窗口）。

POST /api/ai-report  { "range": 7 | 30 | 90 }
  → 对该时间窗内全部上轴事件生成一份解读报告（结论 + 每条结论的出处事件 id/标题/链接）。

缓存策略：进程内缓存（同一 Lambda 实例复用）；再叠加 Vercel 边缘缓存头。
预生成：部署后首次访问各窗口即生成并驻留；也可用 cron/手动 curl 预热
        （GET ?warm=7 触发生成，同 URL 多打几次即热）。

环境变量同 api/ai.py：AI_BASE_URL / AI_API_KEY / AI_MODEL。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qsl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "portal" / "site"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import server as S  # noqa: E402
from worldview import load_world  # noqa: E402
import ai_store  # noqa: E402

AI_BASE_URL = (os.environ.get("AI_BASE_URL") or "https://api.minimaxi.com/v1").rstrip("/")
AI_API_KEY = (os.environ.get("AI_API_KEY") or "").strip()
AI_MODEL = (os.environ.get("AI_MODEL") or "MiniMax-M3.1-Flash").strip()

_SYSTEM = """你是 Forward Deployed Engineering（FDE）领域的资深分析师。
给同一个时间窗（7/30/90 天）内的全部上轴事件（每条含结构化原文摘要），
输出一份该阶段的解读报告。要求：

一、阶段结论（5-8 条）：这个阶段 FDE 领域真正值得注意的变化与趋势。
   每条格式固定为：
   ### N. 结论标题
   一到三句阐述。
   **出处**：列出支持这条结论的具体事件（格式：`[事件标题](url)`，多条用顿号连接）。
   每条结论必须至少落到 1 个具体事件上，禁止没有出处的空泛结论。

二、数据速览：公司动作 / 部署 / 人物观点 / 方法岗位 四轨各发生了什么，各 1-2 句。

三、值得盯的下一步：基于窗口内信号，接下来 2-4 周值得验证的 2-3 个观察点。

只依据给到的事件材料，不编造。简体中文。不吹捧、不写套话。"""


def _events_for_range(data: dict, days: int) -> list:
    start = S.window_start(days) if hasattr(S, "window_start") else None
    snap = data.get("snapshot") or ""
    out = []
    for e in data.get("events", []):
        day = e.get("day") or ""
        if start and not (start <= day <= snap):
            continue
        out.append(e)
    return out


def _event_block(e: dict, idx: int) -> str:
    lines = [f"### 事件 {idx}：{e.get('title', '')}（{e.get('kicker', '')} · {e.get('day', '')} · {e.get('lane', '')}）"]
    for k in ("happened", "why", "enterprise", "practitioner"):
        v = e.get(k)
        if v:
            lines.append(f"- {k}: {v}")
    d = e.get("detail") or {}
    for k in ("业务问题", "实测结果", "失败与迭代", "评测", "部署形态", "交接给了谁", "客户"):
        if d.get(k):
            lines.append(f"- {k}: {d[k]}")
    url = e.get("url") or d.get("原文链接") or ""
    if url:
        lines.append(f"- 原文链接: {url}")
    return "\n".join(lines)


def _build_user(events: list, days: int, snapshot: str = "") -> str:
    snap = (snapshot or "").strip() or "未知"
    parts = [f"时间窗：过去 {days} 天（共 {len(events)} 条上轴事件，快照 {snap}）。", ""]
    for i, e in enumerate(events, 1):
        parts.append(_event_block(e, i))
    return "\n\n".join(parts)


def _call_ai(user_content: str) -> str:
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        AI_BASE_URL + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + AI_API_KEY},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()


# 进程内缓存：实例存活期内不重复生成（外层还有 ai_store 的磁盘/仓库持久化）
_CACHE: dict = {}


def _report(days: int) -> dict:
    if days in _CACHE:
        return _CACHE[days]
    with S.connect() as con:
        data = load_world(con.cursor())
    snapshot = data.get("snapshot") or ""
    events = _events_for_range(data, days)
    meta = [
        {
            "id": e.get("id"),
            "title": e.get("title"),
            "day": e.get("day"),
            "url": e.get("url") or (e.get("detail") or {}).get("原文链接") or "",
            "lane": e.get("lane"),
        }
        for e in events
    ]
    if not AI_API_KEY:
        out = {"enabled": False, "range": days, "error": "AI 未配置（缺少 AI_API_KEY）", "events": meta}
        _CACHE[days] = out
        return out

    # 持久化缓存命中（/tmp 实例盘 或 仓库内置）→ 零等待返回
    hit = ai_store.load("report", str(days), snapshot)
    if hit and hit.get("text"):
        out = {"enabled": True, "range": days, "snapshot": snapshot, "total": len(events),
               "text": hit["text"], "events": meta, "cached": True}
        _CACHE[days] = out
        return out

    text = _call_ai(_build_user(events, days, snapshot))
    out = {"enabled": True, "range": days, "snapshot": snapshot, "total": len(events),
           "text": text, "events": meta}
    # 生成成功 → 立即持久化
    try:
        ai_store.save("report", str(days), snapshot, {"text": text, "total": len(events)})
    except Exception:
        pass
    _CACHE[days] = out
    return out


async def _send(send, status: int, body: bytes):
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", b"application/json; charset=utf-8"],
            [b"content-length", str(len(body)).encode()],
            # 报告生成成本高：边缘缓存 10 分钟，后台过期刷新
            [b"cache-control", b"s-maxage=600, stale-while-revalidate=3600"],
        ],
    })
    await send({"type": "http.response.body", "body": body})


async def app(scope, receive, send):  # noqa: ANN001
    if scope["type"] != "http":
        return
    method = (scope.get("method") or "GET").upper()
    qs = dict(parse_qsl(scope.get("query_string", b"").decode("utf-8")))
    days = int(qs.get("range") or qs.get("warm") or 30)
    if days not in (7, 30, 90):
        days = 30

    if method not in ("GET", "POST"):
        await _send(send, 405, json.dumps({"error": "method not allowed"}).encode("utf-8"))
        return

    try:
        rep = _report(days)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        await _send(send, 502, json.dumps({"error": f"上游 AI 返回 {e.code}", "detail": detail}, ensure_ascii=False).encode("utf-8"))
        return
    except Exception as e:  # noqa: BLE001
        await _send(send, 502, json.dumps({"error": "报告生成失败", "detail": str(e)[:300]}, ensure_ascii=False).encode("utf-8"))
        return

    status = 200 if rep.get("enabled") else 503
    await _send(send, status, json.dumps(rep, ensure_ascii=False).encode("utf-8"))
