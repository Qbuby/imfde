# 世界动态观察名单

首页四轨不从 503 条 `case_study` 挤。本名单是动态层的源：公告、股东信、具名文章、演讲、方法、岗位。

机器可读副本：`portal/world_sources.json`。运行时表：`portal/world_schema.sql`（附加在 `fde.db`，不改 `cases`）。

抓取仍暂停（`CRAWL_PAUSED.txt`）。本文件只列该看什么，不启动新厂商案例墙。客户故事继续留在 `/案例`。首页目前仍读 `cases`，切 `world_events` 是下一步。

状态：`in_db` 已在 `cases` 里 · `missing` 库中没有对应动态页 · `watch` 只观察入口 · `skip` / `blocked` 不抓。

日期：上轴只用原文 `published` 或页上 `modified`。没有就标 `collected`（仅收录）。sitemap `lastmod` 不当事件日。

---

## 信息类型（相对 `cases.doc_type` 扩开）

`cases` 只有 case_study / methodology / opinion / job_posting / discussion / index / unusable。动态层用 `info_kind`，写入时就定 `lane`，不再靠 URL 白名单猜。

| info_kind | 默认轨 | 收 | 不收 |
| --- | --- | --- | --- |
| `org_announcement` | 公司 | 成立部署业务、扩编制、官方组织说明 | 普通产品点、招聘板首页 |
| `product_line` | 公司 | 命名部署平台（Frontier、Deployment Company） | 无事件日的营销页（可 collected） |
| `earnings_letter` | 公司 | 官方股东信、点名 FDE 的财报口径 | 聚合站转写当系统记录 |
| `press_release` | 公司 | 组织级新闻稿 | 一客一页 impact |
| `named_essay` | 人物 | 作者标个人的博客/长文 | 公司新闻室代笔、个人文标成官方 |
| `interview` | 人物 | 有日期、有具名受访者 | 面试题库答题页 |
| `conference_talk` | 人物 | 有发布日的演讲/官方录像 | 无日期口播、议程索引 |
| `podcast_episode` | 人物/方法 | 有发布日的单期 | 播客首页 |
| `discussion` | 人物 | Reddit 等公开帖，一帖一条 | 一帖拆多行 |
| `methodology` | 方法 | 如何做 FDE、角色定义 | 招聘广告伪装成指南 |
| `engineering_blog` | 方法 | 工程团队写怎么建 FDE 组 | 客户案例、SEO 职业合集 |
| `job_posting` | 方法 | 官方 ATS 上有 `publishedAt` 的单岗 | 把 300 条岗位铺满轴 |
| `hiring_board` | 方法 | ATS 索引当观察源 | 索引页当事件 |
| `hiring_census` | 方法 | 有采集日的公开普查（一篇） | 无方法说明的薪资 SEO |
| `dated_case_study` | 部署 | **已在库**且原文有 published/modified | 再 mine 案例墙；无日期 CS 留 `/案例` |

`cases.doc_type` 对照：opinion → named_essay；methodology 拆成 methodology / engineering_blog / podcast；job_posting 保留；discussion 保留但去重；case_study 只有带日期的进部署轨。

---

## 0. 先吃库存（不新开站）

去重后约这些 URL。下一步是补日期、写死 `lane` + `info_kind`、写中文四段。

### 公司动作 · in_db

| URL | info_kind | 备注 |
| --- | --- | --- |
| https://openai.com/index/openai-launches-the-deployment-company/ | org_announcement | Deployment Company。发布日 2026-08-28 |
| https://openai.com/index/introducing-openai-frontier | product_line | Frontier。中英多行，按 title+day 折成一条 |
| https://openai.com/business/frontier/ | product_line | 产品页，可能无事件日 → collected |

### 人物与观点 · in_db

| URL | info_kind | 备注 |
| --- | --- | --- |
| https://cohere.com/blog/forward-deployed-engineers-capability-building | named_essay | 2026-08-27，应进 30 天人物轨 |
| https://a16z.com/services-led-growth/ | named_essay | 2025-06，窗口外，90 天可见 |
| https://a16z.com/insights-for-enterprise-ai-builders/ | named_essay | 同主题重复行，折一条 |
| https://blog.pragmaticengineer.com/the-pulse-forward-deployed-engineering-heats-up-again/ | named_essay | 2026-05，30 天外 |
| https://newsletter.pragmaticengineer.com/p/the-pulse-forward-deployed-engineering-887 | named_essay | 上条 newsletter 镜像，折一条 |
| https://www.reddit.com/r/levels_fyi/comments/1qczm99/whats_a_forward_deployed_engineer/ | discussion | 无发布日 → collected |
| https://www.reddit.com/r/ExperiencedDevs/comments/1u1ytv7/i_keep_seeing_forward_deployed_engineer_openings/ | discussion | 4 帖去重为 4 条，不要 10 行 |
| https://www.reddit.com/r/ExperiencedDevs/comments/1qxtynq/forward_deployed_engineer_role/ | discussion | |
| https://www.reddit.com/r/cscareerquestions/comments/1vxnrie/forward_deployed_engineer_roles_seem_like_a_scam/ | discussion | |

### 方法与岗位 · in_db

| URL | info_kind | 备注 |
| --- | --- | --- |
| https://www.fdeinterviews.com/blog/how-forward-deployed-engineers-work | methodology | 有发布日 |
| https://www.fdeinterviews.com/blog/day-in-the-life-forward-deployed-engineer | methodology | |
| https://www.fdeinterviews.com/guide/what-is-a-forward-deployed-engineer | methodology | 修改日 |
| https://www.fdeinterviews.com/guide/what-does-a-forward-deployed-engineer-do | methodology | 修改日 |
| https://fdepod.substack.com/p/fde-101 | podcast_episode | |
| https://fdepod.substack.com/p/what-it-means-to-be-a-forward-deployed | podcast_episode | |
| https://fourthage.substack.com/p/what-is-a-forward-deployed-engineer | methodology | |
| https://fde.academy/blog/hire-forward-deployed-engineers | methodology | |
| https://openai.com/careers/forward-deployed-engineer-(fde)-seattle-seattle/ | job_posting | 常无发布日 → collected |
| https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers | named_essay | 与 opinion 重复，折一条 |
| https://www.linkedin.com/pulse/8-tactical-insights-from-current-former-forward-modal-porras-reyes-cwage | named_essay | 有发布日则上轴 |
| https://www.fdepulse.com/ | — | index，不当事件 |

跳过：Cohere 首页、Palantir 首页/AIP 平台页（`unusable` / index）。

---

## 1. 具名文章与演讲（人物轨缺口）

审计和稿面点过、库里几乎没有。作者身份必须标个人，不标成雇主官方。

| 状态 | 作者 | 类型 | URL | 日期线索 |
| --- | --- | --- | --- | --- |
| missing | Nabeel Qureshi | named_essay | https://nabeelqu.co/reflections-on-palantir | 原文约 2024-10；转载 Pirate Wires 2025-02。用作者站日期 |
| missing | Barry McCardel | named_essay | https://www.barry.ooo/posts/fde-culture | FDE Culture |
| missing | Ted Mabrey | named_essay | https://www.linkedin.com/posts/ted-mabrey_sorry-that-isnt-an-fde-activity-7242923007172640768-L10X | 2024-09-20。若找到博客 canonical 再用博客 |
| missing | Bob McGrew / YC | conference_talk | https://www.youtube.com/watch?v=Zyw-YA0k3xo | 2025-09-08《The FDE Playbook for AI Startups》 |
| missing | Marty Cagan | named_essay | https://www.svpg.com/forward-deployed-engineers/ | 2025-09-17 |
| missing | Natalie Meurer | interview | https://www.latent.space/p/forward-deployed-engineers-aiewf | 2026-07-01，90 天窗 |
| missing | Natalie Meurer | conference_talk | https://www.youtube.com/watch?v=Byv311hdoHE | 2026-07-28 AIEWF |
| missing | Kevin Bai | conference_talk | https://www.youtube.com/watch?v=KwhgfwOSToQ | AIEWF 2026-06《FDE 101》。台上数字不当审计 |

---

## 2. 公司动作观察名单（新源）

只收「成立部署业务、扩编制、独立产品线、官方组织说明、点名 FDE 的股东信」。不收 customer story。

### 入口（list_index，先列后选）

| 状态 | 对象 | 入口 | 说明 |
| --- | --- | --- | --- |
| in_db | OpenAI | newsroom / Frontier / Deployment Company / careers | 已有 2 条硬节点 |
| watch | Palantir | https://www.palantir.com/newsroom/ 、股东信、IR | 库里主要是 Impact 案例，首页不当公司动作 |
| watch | Anthropic | https://www.anthropic.com/news | 组织/部署能力公告才收 |
| watch | Cognition | https://cognition.ai/blog | 案例页仍走部署轨且不新抓 |
| watch | Databricks | https://www.databricks.com/blog | 只要 FDE/部署组织 |
| watch | Cohere | 博客已有 1 条；新闻室新公告继续收 | |
| watch | AWS | https://aws.amazon.com/blogs/ | FDE 组织/伙伴运动，不是客户案例 |
| watch | Google Cloud | https://cloud.google.com/blog | PE 提到 2026-05 招 FDE；没有官方页就空着 |
| watch | Shopify / Netflix / Duolingo | 官方新闻或工程博客 | **稿面示意。没有公开页就空着，不写假节点** |

### 窗口内缺的硬节点（missing，优先于再扫新闻室）

| 对象 | 类型 | URL | 日期 | 备注 |
| --- | --- | --- | --- | --- |
| Palantir | earnings_letter | https://www.palantir.com/q2-2026-letter/en/ | 2026-08-03 | Karp 信。落在快照 **30 天**。SoR=官方信，不是 Channel Dive |
| Palantir | press_release | SEC exhibit 99.1 | 2026-08-03 | 与信同一天，`same_org` 链，不要两条都当独立「变化」 |
| AWS | org_announcement | https://aws.amazon.com/blogs/apn/introducing-forward-deployed-engineering-for-partners-winning-the-future-of-enterprise-ai/ | 2026-06-30 | 官方宣布 FDE 组织 + $1B。**90 天**窗。稿里出现的 NFL 等不要拆成部署节点 |

---

## 3. 方法补充

| 状态 | URL | 类型 | 备注 |
| --- | --- | --- | --- |
| missing | https://posthog.com/blog/forward-deployed-engineer | engineering_blog | 2026-02-11 |
| missing | https://vannevarlabs.com/blog/forward-deployed-engineering/ | engineering_blog | 防务场景怎么建 FDE 组 |
| in_db / 见上 | AWS APN 文 | org_announcement | 公司轨优先；方法向内容不要再复制一条 |
| missing | https://build.a16z.com/fellowships/fde | methodology | 无事件日则 collected |
| watch | FDEInterviews 博客、FDE Pod、Fourth Age | methodology / podcast | 题库 `/q` 不进动态 |

---

## 4. 招聘板（弱信号）

`lane=method`。仅当官方写「我们在建 FDE 团队」才升到 `company`。

- OpenAI / Anthropic / Palantir careers（已有 OpenAI 西雅图一条）
- Ashby / Greenhouse / Lever 公开 FDE 职位的 `publishedAt`
- 已核到的单岗（missing，不当 300 行时间轴）：
  - Anthropic Greenhouse `jobs/4985877008`
  - Palantir Lever Forward Deployed AI Engineer
  - Scale AI Greenhouse Forward Deployed AI Engineer, Enterprise
  - xAI Greenhouse X Developer Platform FDE
- 聚合板只作发现，回链官方 ATS：https://fdejobslist.com/
- 普查当一篇方法事件，不是 1206 条岗位：https://joinplank.com/fde-job-market （2026-07-04）

---

## 5. 真实部署（收紧，不扩）

现有 Intercom / Writer / Cognition / Factory 等 customer story **只有原文 published 才进「真实部署」轨**。其余留 `/案例`。

不要：再 mine 一轮客户故事、sitemap lastmod、把稿面公司名写进前端。

---

## 不要收

- 厂商案例墙重抓 / 新开 vendor `mine_loop`（`CRAWL_PAUSED`）
- Palantir 首页、AIP 平台页、`fdepulse.com` 索引
- Channel Dive / Seeking Alpha 当系统记录
- 面试题库答题页、无日期 Twitter
- GSDC / Dexity 一类 SEO 职业合集
- 同一厂商连续 CS 当因果链

---

## 执行顺序

1. 库存 URL 去重 + 补 `published`/`modified`/`collected` + 写死 `lane`/`info_kind`。人物轨应先出现 Cohere，而不是空轨。
2. 具名文章与演讲（Nabeel / Barry / Ted / Bob McGrew / Cagan / Meurer）。
3. 窗口内公司缺口：Palantir Q2 2026 信、AWS FDE 组织。
4. Palantir / Anthropic / Cognition / Databricks 新闻室，只收组织动作。
5. Shopify / Netflix / Duolingo：找到官方页再收；找不到就空。
6. 招聘板保持弱信号，禁止铺轴。
7. 抓取恢复前，文案仍是「数据快照 / 本期收录」。**先确认本名单，再抓 HTML。**

首页目标读 `world_events`，不再每次扫 559 行 `cases`。
