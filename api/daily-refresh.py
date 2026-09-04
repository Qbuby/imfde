# -*- coding: utf-8 -*-
"""Vercel Cron 入口：每日 0 点（北京时间）自动刷新解读报告缓存。

vercel.json crons: "0 16 * * *"（UTC 16:00 = 北京 0:00）→ GET /api/daily-refresh

职责：清空本函数实例的持久化缓存读取（强制重新查库），
并对 7/30/90 三个窗口重新生成解读报告（数据若有更新，报告随之更新）。
注意：原始抓取（ingest_world.py）需要写 fde.db，在 serverless 里不可行，
由本地计划任务（scripts/daily_local.bat，每天 0 点）完成 ingest + pregen + push。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "portal" / "site"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import server as S  # noqa: E402


async def _send(send, status: int, payload: dict):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", b"application/json; charset=utf-8"],
            [b"content-length", str(len(body)).encode()],
            [b"cache-control", b"no-store"],
        ],
    })
    await send({"type": "http.response.body", "body": body})


async def app(scope, receive, send):  # noqa: ANN001
    if scope["type"] != "http":
        return
    # Vercel Cron 会带 Authorization: Bearer $CRON_SECRET（若配置了环境变量）
    results = {}
    db_state = "完整库" if S.DB_PATH.name == "fde.db" else "公开库(fde-public.db)"

    # 1. 确认数据可读
    try:
        with S.connect() as con:
            n_events = con.execute("SELECT COUNT(*) FROM world_events").fetchone()[0]
            n_cases = con.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        results["db"] = {"ok": True, "world_events": n_events, "cases": n_cases, "db": db_state}
    except Exception as e:  # noqa: BLE001
        await _send(send, 500, {"ok": False, "error": f"数据库不可读: {e}"})
        return

    # 2. 逐窗口刷新报告（ai-report 内部会读 ai_store 持久化缓存；数据变了报告重生成）
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ai_report_impl", Path(__file__).resolve().parent / "ai-report.py"
        )
        R = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(R)
        R._CACHE.clear()  # 强制重新生成（数据可能已更新）
        for days in (7, 30, 90):
            try:
                rep = R._report(days)
                results[f"report_{days}d"] = {
                    "ok": True,
                    "total": rep.get("total"),
                    "chars": len(rep.get("text", "")),
                }
            except Exception as e:  # noqa: BLE001
                results[f"report_{days}d"] = {"ok": False, "error": str(e)[:200]}
    except Exception as e:  # noqa: BLE001
        results["reports"] = {"ok": False, "error": str(e)[:200]}

    results["message"] = "解读报告已按当前数据刷新。原始数据抓取由本地 ingest 计划任务负责。"
    await _send(send, 200, results)
