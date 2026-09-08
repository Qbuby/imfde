# imfde 项目交接提示词（粘给 zcode 的开场）

你是 imfde 项目的新任开发代理。以下是完整交接，改代码前通读一遍。

---

## 1. 项目是什么

**imfde.ai =「世界动态」FDE 实时情报动态沙盘**：持续抓取行业内 FDE（Forward Deployed Engineer）相关的公司动作、真实部署、人物观点、方法与岗位，以 3D 沙盘 + 平面时间轴 + 案例/方法门户呈现。愿景是"全球首个 FDE 实时情报动态沙盘"。

**双仓库结构**：
| 仓库 | 路径 | 说明 |
|---|---|---|
| 主项目 | `D:\program\imfde` | GitHub `Qbuby/imfde`，main 分支，**push 即 Vercel 自动部署 imfde.ai**（约 1 分钟） |
| 上游同步源 | `D:\program\openfde-community` | 交接库（另一个团队的社区版），定期拉新、把功能同步进来（流程见 §6） |
| 只读历史快照 | `D:\program\openfde-community-handoff-imfde-ai-2026-09-03` | 参考用，别改 |

## 2. 架构（改代码前必读）

| 组件 | 位置 | 要点 |
|---|---|---|
| 动态渲染层 | `portal/site/server.py` | 单文件 Python 站点（mast/footer/render_path/品牌/路由）。本地起服务固定 127.0.0.1:8850 |
| Serverless 入口 | `api/portal.py` | ASGI 包装 render_path + OAuth 路由 + 静态资源 |
| Vercel 配置 | `vercel.json` | rewrites / crons / functions（`includeFiles: portal/site/**` 必须保留，否则新模块进不了函数包） |
| 本地完整库 | `portal/fde.db` | 682 题答案在内，**不入仓** |
| 生产库 | `portal/fde-public.db` | 入仓；= fde.db 副本 + questions.answer 置空。**无生成脚本**：fde.db 内容变更后必须手动重建（copy → UPDATE answer=''）并提交，否则线上看不到 |
| 静态导出 | `portal/build_static.py` | 在 `portal/` 目录下运行；生成 `portal/*.html`，部署后 Vercel 直接命中 |
| OAuth | `portal/site/auth.py` + `server.py/_handle_auth` + `api/portal.py` auth 段 | 见 §4 |
| 页面 | `/world3d`（首页 3D 沙盘）、`/世界动态`、`/落地`、`/现场`、`/案例`、`/方法` + 详情页 `/动态/<id>`、`/案例/<id>`、`/方法/<slug>` | 导航首项指向 /world3d |
| 旧静态门户 | `platform/`（经 /platform/ 访问，不暴露入口） | 低优先级维护 |
| 本地启动 | `启动imfde本地.bat` | 静态门户 :8080 + 内容服务 :8850 一键起 |

## 3. 铁律（违反 = 返工）

1. **所有修复和新代码，必须用 Playwright 有头模式跑通 UI 实测**（真实点击→跳转→回调→页面渲染），curl / 单测 / 假参数**不算完成**。登录测试用 `scripts/playwright_login_test.py`（真实 Chrome `channel="chrome"` + 持久 profile + 反自动化 flag——Playwright 自带 Chromium 会被 Google 拒登）
2. **portal 内禁止 `href="/"`**——回首页一律 `/world3d`。裸 `/` 在 `/portal/*` 服务下被前缀成 `/portal/`，Vercel 文件系统路由优先命中静态 portal/ 目录（返回 index.json），rewrite 不生效
3. **Python 用托管版**：`C:\Users\14798\.workbuddy\binaries\python\versions\3.13.12\python.exe`
4. `from urllib.parse import ...` ≠ `import urllib.parse`——混用出过线上 NameError 裸 ISE（2026-09-07 血案）
5. `.bat` 脚本必须 **CRLF + 纯 ASCII**（cmd 解析 UTF-8+LF 会行错乱）
6. git push 走代理 `HTTPS_PROXY=http://127.0.0.1:7890`；curl localhost 必须 `--noproxy '*'`
7. 改了 `portal/site/` 下任何渲染相关代码 → **重跑 `build_static.py`** 再提交

## 4. OAuth 登录（已上线，身份识别、不做限权）

- 入口 `/登录`；回调**纯 ASCII** `/oauth/<provider>/callback`（Google 拒绝中文/多段 redirect_uri）；`_handle_auth` 与 api 路由把 `/oauth/<p>[/callback]` 和 `/登录/<p>[/回调]` 归一化同处理
- 环境变量（Vercel 项目设置）：`GITHUB_CLIENT_ID/SECRET`、`GOOGLE_CLIENT_ID/SECRET`、`WECHAT_APPID/SECRET`、`SECRET_KEY`、`IMFOAUTHBASE=https://imfde.ai`；未配置的渠道自动隐藏
- **登录不写数据库**（Vercel 文件系统只读）：state 用自包含 HMAC 签名（`make_state`/`verify_state`），用户信息全在签名 cookie（30 天、HttpOnly）
- Google + GitHub 已 Playwright 全链路 PASS；**微信等开放平台审核**，凭据配好按钮自动出现
- 对接文档：`docs/oauth-login-setup.md`

## 5. 每日数据任务

- **Vercel cron** `0 16 * * *`（UTC，= 北京 0:00）→ `api/daily-refresh` 清缓存重生成解读报告
- **本地计划任务** `imfde-daily-update`（每天 00:00，StartWhenAvailable）→ `scripts/daily_local.bat`：ingest → pregen_ai → build_static → commit+push
- 抓取窗口：`BACKFILL_DAYS=30` 滚动回溯（防漏）；`hiring_census` 用快照日上轴；诊断看 `portal/world_state.json`（since_day/last_delta）、`world_ingest_report.json`（increment 计数），stale 异常大 = 窗口问题

## 6. 上游同步流程（openfde-community → imfde）

1. `cd /d/program/openfde-community && git pull`，看新增 commit（历史版本可用 `git show <commit>:portal/site/xxx` 提取）
2. `diff -rq --strip-trailing-cr`（排除 .git/__pycache__/*.db/world_raw）定位差异；换行符差异是假阳性
3. 迁移文件后**重打 imfde 补丁（8 项）**：① `brand_mark`/`brand_lockup` 纯 logo 版 ② NAV 首项 `/world3d`（上游是 `/`）③ "回沙盘"等文案 → "回世界动态" ④ `github_url` → Qbuby/imfde ⑤ `IMFDE_PORTAL_URL` 回门户链接 ⑥ footer 调整 ⑦ `world3d.js` 的"解读报告"悬浮块（上游常覆盖掉，从 imfde git 历史找回）⑧ 中文文案
4. fde.db 有内容变更 → 重建 fde-public.db 并提交
5. 重跑 `build_static.py` → Playwright 实测 → push

## 7. 品牌（当前定版）

- 帽子 logo（`brand_mark` 纯 img，`portal/site/static/icons/logo-mark.png`，256px）+ 右侧 **imfde.ai 三色字标**（`brand_wordmark`：im 主体色 / fde 青色 / .ai 灰）
- 首页（世界动态 HUD）字标后额外一行**「全球首个 FDE 实时情报动态沙盘」**（FDE 前后有空格）
- 各列表页的 hero 大标题/副标题块**已全删**（用户明确要求）；详情页标题是内容本体，保留

## 8. 坑速查表

| 症状 | 原因/修法 |
|---|---|
| 中文路由线上 404 | vercel.json 补百分号编码版 rewrite（多字节 source 匹配失败） |
| Vercel 连字符文件名 import 失败 | `importlib.util.spec_from_file_location` |
| 线上数据不更新 | 先查 fde-public.db 是否重建+提交 |
| 函数包缺新文件 | vercel.json `functions.includeFiles: portal/site/**` |
| 线上登录裸 ISE | auth 段 try 外代码（见 §3.6）；诊断时"裸 ISE vs 带堆栈 500"差异 = 崩溃点在 try 外 |
| 首页返回 JSON | href="/" 命中静态目录（见铁律 2） |

## 9. 首次上手动作（建议顺序）

1. `启动imfde本地.bat` 起本地环境，确认 ：8850 内容服务 + /world3d 渲染正常
2. 对照本文件把 `vercel.json`、`portal/site/server.py`、`portal/site/auth.py` 通读一遍
3. 跑一次 `scripts/playwright_login_test.py google` 验证登录链路（profile 有已授权会话，免密）
4. 之后再开始接需求；有任何上游同步先看 §6

—— 以上即全部上下文。有不明确的地方先查 imfde 的 git log（每个 commit message 都写了"为什么"）。
