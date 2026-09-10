# -*- coding: utf-8 -*-
"""预生成 AI 解读并持久化到仓库缓存（portal/ai-cache/）。

用法：
  python scripts/pregen_ai.py            # 生成 7/30/90 三份阶段报告（需要完整 fde.db + AI 环境变量）
  python scripts/pregen_ai.py --events   # 额外预生成当前窗口内全部单条事件解读

产物随 git 提交后，Vercel 部署即自带缓存——用户第一次点击就是秒开。
数据快照变化后重跑一次即可刷新（cache_key 含 snapshot，旧缓存自动失效）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "portal" / "site"))
sys.path.insert(0, str(ROOT / "api"))

import server as S  # noqa: E402
from worldview import load_world  # noqa: E402
import ai_store  # noqa: E402

WINDOWS = (7, 30, 90)


def main() -> None:
    # ai-report.py 文件名含连字符，不能常规 import；用 importlib 按路径加载
    import importlib.util
    spec = importlib.util.spec_from_file_location("ai_report_impl", ROOT / "api" / "ai-report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _call_ai, _build_user, _events_for_range = mod._call_ai, mod._build_user, mod._events_for_range

    if not (S.DB_PATH.is_file()):
        raise SystemExit(f"missing db: {S.DB_PATH}")
    with S.connect() as con:
        data = load_world(con.cursor())
    snapshot = data.get("snapshot") or ""
    print(f"快照 {snapshot} · 事件 {len(data.get('events', []))}")

    for days in WINDOWS:
        key = ai_store.cache_key("report", str(days), snapshot)
        if ai_store.load("report", str(days), snapshot):
            print(f"[report {days}d] 已有缓存，跳过（{key}）")
            continue
        events = [e for e in data.get("events", []) if days >= 90 or True]
        # 与线上 _events_for_range 同口径：直接复用
        events = _events_for_range(data, days)
        if not events:
            print(f"[report {days}d] 窗口内无事件，跳过")
            continue
        t0 = time.time()
        text = _call_ai(_build_user(events, days, snapshot))
        ai_store.save("report", str(days), snapshot, {"text": text, "total": len(events)})
        print(f"[report {days}d] 生成并落盘 {len(text)} 字，耗时 {time.time()-t0:.0f}s（{key}）")

    if "--events" in sys.argv:
        for e in data.get("events", []):
            ident = str(e.get("id") or e.get("url") or "")
            if ai_store.load("event", ident, snapshot):
                continue
            try:
                t0 = time.time()
                text = _call_ai(_build_user([e], 30, snapshot))
                ai_store.save("event", ident, snapshot, {"text": text, "title": e.get("title", "")})
                print(f"[event {ident}] {time.time()-t0:.0f}s")
            except Exception as exc:  # noqa: BLE001
                print(f"[event {ident}] 失败: {exc}", file=sys.stderr)

    print("完成。提交 portal/ai-cache/ 后 push 即随部署分发。")


if __name__ == "__main__":
    main()
