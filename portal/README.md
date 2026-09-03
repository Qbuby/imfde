# imfde 内容服务（学习社区 · 从 openfde-community 迁移）

这是 imfde「学习成长」板块的内容服务——开源 FDE 学习社区的每日入口（世界动态 + 案例证据库 + 方法论）。

## 是什么

内容区是从 `dapingzui/openfde-community` 的 `handoff/imfde-ai-2026-09-03` 分支整体迁入的 Python 内容服务。它承载《MVP目标》第三步「学习成长」所需的内容资产：

- **世界动态** `/` `/世界动态`：529 条观察按 7/30/90 天分窗（快照 2026-09-02）
- **部署证据** `/案例` `/案例/<id>`：559 条案例库
- **落地** `/落地`、**现场** `/现场`：同一数据的两种读法
- **方法** `/方法`：方法论与开放题目录
- **立体沙盘** `/world3d`：同一数据的三维视图

品牌已统一为 **imfde.ai**；「开源仓库」指向本平台仓库 `Qbuby/imfde`（已剥离交接方 aifde 私有源）。

## 启动

```bash
cd portal/site
python3 server.py
# 打开 http://127.0.0.1:8850/
```

纯 Python 标准库，无第三方依赖。绑定 `0.0.0.0:8850`。

## 数据

- `portal/fde.db`（SQLite，已含 world_* 动态层）：cases 559 · world_events 529 · 轴上 140 · questions 682 · sources 89
- 快照日：2026-09-02（`world_ingest_report.json`）

## 硬约束（继承交接方，违反即回归）

1. **不要新开厂商案例墙**（`do_not_start_a_new_vendor`），禁止无界 mine_loop
2. 上轴只要原文 `published` / `modified`，`collected` 永不上轴
3. 岗位是弱信号，不能当公司动作
4. 题库答案不在站内展示（许可=引用+链接）
5. 禁止用 `build_portal_db.py` 重建 fde.db 后不恢复动态层（该脚本会删库）。若必须重建：备份 → `schema.sql` → `world_schema.sql` → `ingest_world.py --backfill-copy`
6. 文案是「数据快照」，不是实时新闻

## 目录

```
portal/
  site/server.py       路由、品牌、导航、页面骨架
  site/worldview.py    世界动态首页数据与 HTML
  site/world3d.py      立体沙盘
  site/static/         样式、JS、three.js、icons
  site/ingest_world.py 抓取 + 中文四段（动态层维护）
  fde.db               查询真相（含 world_*）
  world_schema.sql     动态层 DDL
```
