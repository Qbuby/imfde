# -*- coding: utf-8 -*-
"""AI 解读持久化层 —— 三级缓存。

顺序：进程内存 → 磁盘文件（/tmp/ai-cache，Vercel /tmp 可写、实例间隔离）→ AI 生成。
生成成功后立即落盘；下次任何实例命中同 key 直接读盘，用户零等待。

Vercel 注意：serverless 文件系统只有 /tmp 可写且**不跨实例持久**。
要做到"部署完成就能秒开"，两条路：
  1. 预热：部署后对 /api/ai-report?range=N&warm=1 各打一次（Cron 或手动 curl）；
  2. 持久化到 git：跑 scripts/pregen_ai.py 把报告写进 portal/ai-cache/*.json 提交，
     启动时优先读仓库内缓存（本模块的 REPO_CACHE_DIR）。
本模块把两条路都打通。
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

# 仓库内缓存目录（随部署包分发，部署即可用）
REPO_CACHE_DIR = Path(__file__).resolve().parent.parent / "portal" / "ai-cache"
# 实例可写目录（生成后落盘，实例存活期内有效）
TMP_CACHE_DIR = Path(tempfile.gettempdir()) / "imfde-ai-cache"


def _ensure(d: Path):
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_key(kind: str, ident: str, snapshot: str = "") -> str:
    """kind: report | event；ident: 天数或事件 id；snapshot 参与散列，数据更新自动失效。"""
    raw = f"{kind}:{ident}:{snapshot}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _paths(key: str) -> tuple:
    return (
        REPO_CACHE_DIR / f"{key}.json",
        _ensure(TMP_CACHE_DIR) / f"{key}.json",
    )


def load(kind: str, ident: str, snapshot: str = "") -> dict | None:
    key = cache_key(kind, ident, snapshot)
    # 1) 进程内（由调用方维护，这里不管）
    # 2) /tmp 实例盘
    # 3) 仓库内置（部署即有）
    for p in _paths(key):
        try:
            if p.is_file():
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("text"):
                    return data
        except Exception:
            continue
    return None


def save(kind: str, ident: str, snapshot: str, payload: dict) -> None:
    """生成成功后立即持久化（写实例盘；仓库目录只在本地脚本场景可写）。"""
    payload = dict(payload)
    payload["cached_at_snapshot"] = snapshot
    body = json.dumps(payload, ensure_ascii=False)
    key = cache_key(kind, ident, snapshot)
    try:
        (_ensure(TMP_CACHE_DIR) / f"{key}.json").write_text(body, encoding="utf-8")
    except Exception:
        pass
    try:
        _ensure(REPO_CACHE_DIR)
        (REPO_CACHE_DIR / f"{key}.json").write_text(body, encoding="utf-8")
    except Exception:
        pass  # Vercel 线上只读，静默跳过
