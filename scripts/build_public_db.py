# -*- coding: utf-8 -*-
"""从完整库 portal/fde.db 重建线上公开库 portal/fde-public.db（剥离题库答案）。

线上（Vercel）没有 gitignore 掉的 fde.db，server.py 会回退用这份公开库；
日常任务在 ingest 之后调用本脚本，保证推送即发布最新数据。
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "portal" / "fde.db"
DST = ROOT / "portal" / "fde-public.db"

if not SRC.is_file():
    raise SystemExit(f"missing {SRC}")

if DST.is_file():
    DST.unlink()

src = sqlite3.connect(SRC)
dst = sqlite3.connect(DST)
src.backup(dst)
src.close()

dst.execute("UPDATE questions SET answer = ''")
dst.commit()
dst.execute("VACUUM")

total = dst.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
stripped = dst.execute("SELECT COUNT(*) FROM questions WHERE answer = ''").fetchone()[0]
snap = dst.execute("SELECT snapshot FROM world_ingest_runs ORDER BY id DESC LIMIT 1").fetchone()[0]
dst.close()
print(f"OK fde-public.db: {total} questions, answers stripped {stripped}, snapshot {snap}")
