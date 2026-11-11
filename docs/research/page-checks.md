# 竞品页面核查补充（本人 curl 实抓，2026-11-11）

> 本文件是两份调研代理报告的补充与交叉核对。只记录**实际抓到页面正文**的事实，逐条给出抓取路径与状态。
> 反爬/超时/404 的页面明确标注「未取得」，不把搜索摘要当页面内容。抓取缓存位于 `.zcode/*.html`。

## 抓取状态

| 页面 | HTTP | 大小 | 用途 |
|---|---|---|---|
| https://fdehub.cc | 200 | 62.9 KB | 已读正文 |
| https://fdepulse.com | 200 | 54.2 KB | 已读正文 |
| https://fde-jobs.jp | 200 | 272 KB | 已读正文 |
| https://getperspective.ai/blog/state-of-forward-deployed-engineering-2026-survey-report-1500-fdes | 200 | 272 KB | 已读正文 |
| https://www.cbinsights.com/research | 200 | 118 KB | 已读正文 |
| https://stratechery.com | 200 | 626 KB | 已读正文 |
| https://www.gartner.com/en/products/gartner-research | 403 | — | **未取得**，Cloudflare 验证 |
| https://www.theinformation.com/subscribe | 403 | — | **未取得**，Cloudflare 拦截 |
| https://www.spglobal.com/market-intelligence/... | 403 | — | **未取得** |
| https://stratechery.com/subscribe/ | 404 | — | **未取得**（首页有 Subscribe / Stratechery Plus / Member Forum 入口） |
| https://www.eiu.com/n/why-subscribe-to-eiu/ | 404 | — | **未取得**；404 页仍可见其按客户类型组织：Financial Services / Corporates / Academic / Government，卖「independent macroeconomic and geopolitical insights」 |
| https://agenticdaily.ai/trackers/ai-enterprise-deployments | 超时 | — | **未取得** |

---

## 1. FDE Hub（中文，最直接的同类）

**首屏结构（逐字）**：
`搞懂 FDE，搞懂 AI 如何真正落地。` → 一句定位（聚合岗位、方法论、案例与行业动态，为想转型的工程师和落地 AI 的企业提供一站式入口）→ 免费订阅（每周一封：岗位动态 · 案例拆解 · 海外编译）→ **4 个数据指标**：`+729% 岗位一年增幅 Indeed 2025.4–2026.4`、`42× 三年内岗位数量增长 LinkedIn 2023–2025`、`$174K 美国 FDE 薪资中位数 头部实验室总包 $350K+`、`50+ 正在组建 FDE 团队的公司`。

**这值得我们抄的一点**：每个数字**紧邻标了来源与时间窗**（Indeed / LinkedIn / 时间区间）。它没写「行业爆发」这种判断，把数字摆出来让读者自己得结论——这是数据型首页的正确分寸。

**内容栏目**：入门百科 6 篇（每篇标阅读时长 8–15 分钟）、能力自检（3 分钟、13 个子维度、免费不要邮箱）、数据报告（邮箱换 PDF）、洞察专栏 / 行业雷达 / 合作对接 / 周刊。

**变现（FAQ 原文）**：
> 「百科、资源库、专栏全部免费。目前的商业化仅包括**招聘方推广位、报告赞助与对接撮合服务**——这些都不会影响编辑内容的独立性。」
> 企业侧：发布 FDE 岗位、AI 落地组织设计咨询、品牌赞助与内容合作；人才侧：候选人才库、定向岗位推送。页面标 `V2 · 人工撮合阶段`。

**关键判断**：它是**知识库 + 双向撮合市场**，不是情报产品。它有百科和专栏，但没有看到「判断台账 / 兑现记录 / 证据等级 / 跨期核对」。首屏数字是常驻营销指标，不是本期变化。它的护城河是中文入门内容与供需两端，不是对行业变化的连续加工。

---

## 2. FDE Pulse（岗位数据站）

**首屏**：`Tracking 50+ companies hiring FDEs` / `The Forward Deployed Engineer Job Market` / `Jobs, salaries, and market intelligence for the fastest-growing role in enterprise software` → 免费每周一 `FDE Brief`（"We read 1261+ Forward Deployed Engineer job postings so you don't have to. New roles, salary moves, and who's hiring, every Monday."）。

**数据呈现（这是它最值得学的地方）**：
- `1261+ Open Positions`、`$185K Median Base` **带 `n=216 disclosed`**、`62% Remote Friendly`、`50+ Companies Hiring`。
- Brief 样例里放：`Active FDE Jobs 1261 updated weekly`、`Median Base Salary $185K n=216 disclosed`、`11% Remote / 24% Equity Offered / 21% AI GenAI`、`Top hiring companies`（Google 76 / Deloitte 67 / FDE Times 58 / Cloudflare 34 / Salesforce 24 / Databricks 18）、`Salary by metro`（New York 58 roles / $192K …）。
- 导航：Jobs / Salaries / Companies / Interview / Career Insights / **For Employers** / About / Subscribe。

**判断**：它是**结构化岗位数据 + 免费周刊 + 雇主侧变现**，不是判断型情报。但它的 `n=216 disclosed`、`updated weekly` 就是口径纪律——这一点比我前几版 demos 做得好。它没有判断台账。

---

## 3. FDE ジョブ（日本）

首屏：`国内97件を含む506件を毎日更新`（**把总数与本国子集分开写**）、多语言（日/英/简中/韩）。求职意图用 10 问诊断收集（现职种、经验年数、LLM 实务经验、客户面向经验…），变现为「無料で登録する / 求人・案件の紹介を受ける」——是**招聘导流**，不是内容付费。

值得学：总数与子集分开标注，避免用全球数字冒充本地供给。

---

## 4. Perspective AI《State of Forward Deployed Engineering 2026》

**这是本次查到的「最接近情报产品形态」的一份**：

- 标题直接给样本量：`Survey of 1,500 FDEs`；`Perspective AI Team · May 18, 2026 · 17 min read`。
- 开头 `In this article` 目录 → **TL;DR** → 分节（定义、薪酬带、一周怎么花时间、头部公司组织图、工具栈、FAQ、结论）。
- 有**独立 methodology 段**（原文）：
  > "We surveyed 1,500 forward deployed engineers (and equivalent titles — 'applied AI engineer,' 'deployment engineer,' 'field engineer,' 'solutions engineer' with FDE-style scope) **across 154 companies between February and April 2026**. Respondents were 38% from frontier labs, 34% …"
- 判断有数字但也有推理：`only 6% ... mostly building greenfield product` 与 `64% ... deploying an existing product into a new customer environment with significant customization` → 推出 "FDE function is structurally a customer-discovery function with shipping privileges"。
- **但它是厂商内容营销**：TL;DR 里把「conversational customer-research platforms」列为增长最快的工具类别（41% vs 9%），而 Perspective AI 自己就卖这类产品；报告免费、无付费墙，漏斗指向 `Sign up / free trial`。

**对我们的启示（正反两面）**：
- 学：样本量、时间窗、受访者构成、等价职位定义、TL;DR 前置、目录式长文。
- 警惕：**利益立场必须标注**。厂商发布的「关于自己所在品类」的调查，不能当独立行业基准引用；这正好对应验收标准里的来源码 C2 与 R7。

---

## 5. CB Insights（数据终端 / 研究混合）

研究页可见要素：`10M+ companies`、`1,500+ markets`、`Double-verified, continually refreshed`、`Predictive data science`、`Personal briefing`（"Like a team of researchers working 24/7"）、`Personalized research library: Concise, precise visual research that drives decisions`、API & data feeds / Snowflake / Microsoft 365 Copilot / Salesforce 集成；报告样例 `State of Insurtech Q3'26 — Insurtech deal count fell to its lowest level since 2016. Here's what happened.`

**判断**：它把「**数据可信度**」直接做成产品卖点（Double-verified, continually refreshed），报告标题即一句有方向的判断 + 时间口径（Q3'26）+ 一句解释（Here's what happened）。这是「数据 → 判断」的成熟产品化写法，但它的底座是 1000 万家公司数据，imfde 照搬终端密度必死。

---

## 6. Stratechery（判断型通讯）

首页可见：`Stratechery by Ben Thompson – On the business, strategy, and impact of technology.`；导航 `About / Email / RSS / Explore Concepts / Companies / Topics / Stratechery Plus / Subscribe / Member Forum / Updates / Interviews / Year in Review / All Articles / Latest Podcast`。

正文里能看到作者**明确回指自己旧判断**：
> "I haven't written about Anthropic's updated S-1, but it strongly affirms my initial analysis."

**这是我们要学的「连续性」最小形态**：不是台账系统，而是作者公开承认「我以前怎么判断、新信息是否印证」。付费页未取得（404/反爬），因此**不写定价**；免费层与付费层的功能切点只能确认到「Plus / Member Forum / Daily Update 是会员向入口」。

---

## 7. 传统大厂未能取得正文的（如实记录）

Gartner Research、The Information、S&P Capital IQ 产品页均被 403/Cloudflare 拦截；EIU 订阅页 404。二手资料里的价格与象限方法论**不写进本报告**，等代理若能拿到可引用页面再补。

EIU 的 404 页仍可确认一点：它按**客户类型**（金融机构 / 跨国企业 / 学术 / 政府）组织「forecast / risk / insight」，说明传统情报产品的「读者相关性」是按角色分层，不是给所有人同一页。

---

## 8. 交叉核对后的 6 条结论

1. **成熟产品把「口径」放在数字旁边，不放在脚注里**：FDE Pulse 的 `n=216 disclosed`、FDE Hub 指标下紧邻的 `Indeed 2025.4–2026.4`、Perspective 的 `1,500 FDEs / 154 companies / Feb–Apr 2026`。这直接支持我们标准里的 R3 与 D4（口径同屏）。
2. **免费层给「事实与摘要」，付费层给「判断与连续性」**：FDE Hub 内容全免费、靠 B 端撮合变现；FDE Pulse 数据与 Brief 免费、雇主侧收费；Stratechery 免费文章与 Plus/Member Forum 分层。**没有一家靠「把公开新闻摘要锁起来」收费**。
3. **判断台账仍然是空位**：本次实际读到的 FDE 垂直产品里，没有一家做「上期判断 → 本期核对 → 兑现/证伪留痕」。Stratechery 只在正文里偶尔回指旧分析，未产品化。
4. **利益立场是行业情报的命门**：Perspective AI 的调查结论恰好利好它自己的产品品类。这解释了为什么我们的来源评级表必须独立成列，且厂商自述不能当独立基准。
5. **别照搬的**：CB Insights 的 10M+ 公司数据密度、Gartner 式机构席位与销售、评级象限（需要样本量与方法论背书）、FDE Hub 的「知识库 + 撮合」双市场（要供需两端运营）。
6. **必须学的**：数字旁标口径、方法论段公开、TL;DR 前置、按读者角色组织相关性、作者公开回指旧判断、把「已验证/持续刷新」做成可核查承诺而非形容词。
