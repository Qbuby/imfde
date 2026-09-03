# imfde 内容服务（学习社区 · 完整迁移自 openfde-community）

这是 imfde「学习成长」板块的内容服务——开源 FDE 学习社区的每日入口（世界动态 + 案例证据库 + 方法论）。**完整 Python 服务已入仓**，非纯静态项目。

## 是什么

从 `dapingzui/openfde-community` 的 `handoff/imfde-ai-2026-09-03` 分支完整迁入。承载《MVP目标》第三步「学习成长」的内容资产：

- **世界动态** `/` `/世界动态`：529 条观察按 7/30/90 天分窗（快照 2026-09-02）
- **部署证据** `/案例` `/案例/<id>`：559 条案例库
- **落地** `/落地`、**现场** `/现场`：同一数据的两种读法
- **方法** `/方法`：方法论与开放题目录
- **立体沙盘** `/world3d`：同一数据的三维视图（three.js）

品牌统一 **imfde.ai**；「开源仓库」指向本平台仓库（已剥离交接方私有源）。

## 双形态运行

### 1. Python 服务（完整动态版）

```bash
cd portal/site
python3 server.py          # http://0.0.0.0:8850/
```

纯标准库，无第三方依赖。支持全部路由、案例筛选分页、URL 查询参数。

### 2. 静态导出（Vercel 部署用）

```bash
python portal/build_static.py
```

把 7 类路由预渲染成 `portal/*.html`（案例详情为 `案例.html?id=N` 客户端渲染）+ `cases.json`。产物入库，Vercel 直接服务 `/portal/<路由>`。**数据更新流程：跑 ingest → 跑 build_static → 提交产物 → push**。

## 数据

- `fde.db`（SQLite，含 world_* 动态层）：**不入仓**（questions 表含 682 道题答案，硬约束禁止公开）。缺失时从交接仓库或备份恢复。
- 快照日：2026-09-02（`world_ingest_report.json`）
- `tables/*.csv`：案例/公司/主题的 CSV 视图

## 日更抓取

```bash
python3 portal/ingest_world.py --daily    # 或 portal/daily_world.sh
```

## 硬约束（继承交接方，违反即回归）

1. **不要新开厂商案例墙**（`CRAWL_PAUSED.txt`：`do_not_start_a_new_vendor: true`），禁止无界 mine_loop
2. 上轴只要原文 `published` / `modified`，`collected` 永不上轴
3. 岗位是弱信号，不能当公司动作
4. 题库答案不在站内展示（fde.db 也不公开）
5. 禁止用 `build_portal_db.py` 重建 fde.db 后不恢复动态层（会删库）。若必须：备份 → `schema.sql` → `world_schema.sql` → `ingest_world.py --backfill-copy`
6. 文案是「数据快照」，不是实时新闻

## 目录

```
portal/
  site/server.py        路由、品牌、导航、页面骨架（8850）
  site/worldview.py     世界动态首页数据与 HTML
  site/world3d.py       立体沙盘
  site/static/          样式、JS、three.js、icons
  ingest_world.py       抓取 + 中文四段（动态层维护）
  clean_pass.py         清洗维护
  daily_world.sh        日更入口
  build_static.py       静态导出（Vercel 部署产物）
  fde.db                查询真相（不入仓，含题库答案）
  schema.sql / world_schema.sql   建库 DDL
  world_sources.json / world_watchlist.md   观察源目录与名单
  tables/               CSV 数据视图
  *.html + cases.json   静态导出产物（入库，Vercel 服务）
```
