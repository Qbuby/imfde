# FDE 垂直情报 / 信息产品调研

> 状态：正式报告 v1。配套传统线报告 `.zcode/research-traditional-intel.md` 与两份验收标准。
> 方法：逐站 curl 实抓正文（缓存 `.zcode/*.html`）；抓不到就标未取得，不把搜索摘要当页面事实。
> 调研日期：2026-11-11。

## 0. 先给结论

**这个赛道目前有四类玩家，但没有一家在做「判断的连续追踪」。**

| 类型 | 玩家 | 产品本体 | 有没有判断台账 |
|---|---|---|---|
| 知识库 / 媒体 + 撮合 | FDE Hub | 百科、专栏、周刊、报告、企业↔人才对接 | 无 |
| 岗位 / 薪资数据 | FDE Pulse、FDE Jobs JP | 结构化岗位、薪资、Brief、专栏 | 无 |
| 调查报告（厂商营销） | Perspective AI | 一次性大样本调查 + TL;DR + methodology | 无（单次报告） |
| 部署 tracker（公开层） | Agentic Daily、VeilStrat、Naftiko | 谁部署了什么 / 采用信号 | 无（本轮页面未取得，标未核实） |
| 社区 / 培训 / 人才 | FDE.community、FDE Agency、fde.academy、AI FDE School | 社群、课程、订阅制人才 | 无 |

**空位**：把「上期判断 → 本期核对 → 兑现/证伪/证据不足」做成产品界面，且独立于招聘、培训、撮合变现。

---

## 1. 逐家实抓

### 1.1 FDE Hub（fdehub.cc）— 最直接的中文同类
`https://fdehub.cc` 200 / 62.9 KB，正文已读。

**首屏（逐字）**
`搞懂 FDE，搞懂 AI 如何真正落地。` → 定位：聚合岗位、方法论、案例与行业动态，为想转型的工程师和正在落地 AI 的企业提供一站式入口 → 免费订阅（每周一封：岗位动态 · 案例拆解 · 海外编译）→ 4 个指标：

| 指标 | 标注 |
|---|---|
| `+729%` FDE 岗位一年增幅 | `Indeed · 2025.4 – 2026.4` |
| `42×` 三年内岗位数量增长 | `LinkedIn · 2023 – 2025` |
| `$174K` 美国 FDE 薪资中位数 | 头部实验室总包 `$350K+` |
| `50+` 正在组建 FDE 团队的公司 | `OpenAI · Anthropic · AWS…` |

**手艺点**：每个数字紧邻来源与时间窗，不写「行业爆发」这种判断。这是数据型首屏应有的克制。

**内容体系**：入门百科 6 篇（各标 8–15 分钟阅读）、能力自检（3 分钟 / 13 子维度 / 免费不留邮箱 / 出三档结论+能力三角图+差距清单+90 天计划）、数据报告（邮箱换 PDF，写「持续更新的数据观察」「拒绝二手观点」）、洞察专栏（行业解读 / 案例拆解 / 海外编译）、行业雷达、FAQ、周刊。

**变现（FAQ 原文）**
> 「百科、资源库、专栏全部免费。目前的商业化仅包括**招聘方推广位、报告赞助与对接撮合服务**——这些都不会影响编辑内容的独立性。」
企业侧：发布岗位、AI 落地组织设计咨询、品牌赞助；人才侧：候选人才库、定向岗位推送。页面标 `V2 · 人工撮合阶段`。

**判断**：产品本体是「中文知识库 + 双向撮合市场」，不是情报台。它有栏目「行业雷达」，但**没有看到证据等级、判断台账、兑现记录或跨期核对**。首屏指标是常驻营销数据，不是本期变化。护城河是入门内容与供需两端，不是对变化的连续加工。

### 1.2 FDE Pulse（fdepulse.com）— 岗位数据站
`https://fdepulse.com` 200 / 54.2 KB，正文已读。

首屏：`Tracking 50+ companies hiring FDEs` / `The Forward Deployed Engineer Job Market` / `Jobs, salaries, and market intelligence for the fastest-growing role in enterprise software` → 免费每周一 `FDE Brief`：`We read 1261+ Forward Deployed Engineer job postings so you don't have to. New roles, salary moves, and who's hiring, every Monday.`

数据呈现：
- `1261+ Open Positions` / `$185K Median Base` **带 `n=216 disclosed`** / `62% Remote Friendly` / `50+ Companies Hiring`。
- Brief 样例：`Active FDE Jobs 1261 updated weekly`、`Median Base Salary $185K n=216 disclosed`、`11% Remote / 24% Equity Offered / 21% AI GenAI`、Top hiring companies（Google 76 / Deloitte 67 / FDE Times 58 / Cloudflare 34 / Salesforce 24 / Databricks 18）、Salary by metro（New York 58 roles / $192K）。
- 导航：Jobs / Salaries / Companies / Interview / Career Insights / **For Employers** / About / Subscribe。

**手艺点**：`n=216 disclosed`、`updated weekly` 是口径纪律，比我前几版 demos 强。它把「读了多少岗位」直接写成价值主张（so you don't have to）——这是信息劳动代劳的正当表达。

**判断**：结构化岗位数据 + 免费 Brief + 雇主侧变现。有 `Career Insights` 栏目，但首页与 Brief 里看不到判断台账或证据等级。**它是数据产品，不是判断产品。**

### 1.3 FDE ジョブ（fde-jobs.jp）
`https://fde-jobs.jp` 200 / 272 KB，正文已读。

首屏：`国内97件を含む506件を毎日更新`（**总数与本国子集分开写**）、多语言（日/英/简中/韩）、按职种细分（FDE / Solution Engineer / AI 導入 Engineer / Customer Engineer）。用 10 问诊断（现职种、经验年数、LLM 实务、客户面向经验…）收集求职意图，落到「無料で登録する / 求人・案件の紹介を受ける（無料）」。

**判断**：招聘导流，不是内容付费。**值得学**：总数与子集分开标注，避免用全球数字冒充本地供给。

### 1.4 Perspective AI《State of Forward Deployed Engineering 2026》
`https://getperspective.ai/blog/state-of-forward-deployed-engineering-2026-survey-report-1500-fdes` 200 / 272 KB，正文已读。

- 标题带样本量：`Survey of 1,500 FDEs`；署名 `Perspective AI Team · May 18, 2026 · 17 min read`。
- 结构：`In this article` 目录 → **TL;DR** → 定义 / 薪酬带 / 一周时间分配 / 头部公司组织图 / 工具栈 / FAQ / 结论。
- **独立 methodology 段（原文）**：`We surveyed 1,500 forward deployed engineers (and equivalent titles — "applied AI engineer," "deployment engineer," "field engineer," "solutions engineer" with FDE-style scope) across 154 companies between February and April 2026. Respondents were 38% from frontier labs, 34% …`
- 判断示例：`only 6% ... mostly building greenfield product` 与 `64% ... deploying an existing product into a new customer environment with significant customization` → 推出 `FDE function is structurally a customer-discovery function with shipping privileges`。
- **利益立场**：TL;DR 把 `conversational customer-research platforms`（41% vs 9%）列为增长最快工具类别，而 Perspective AI 自己卖这类产品；报告免费、无付费墙，漏斗指向 Sign up / free trial。

**判断**：这是本次看到的**最接近情报产品形态**的一份——TL;DR、样本口径、等价职位定义、推理链都在。但它是**厂商内容营销**，不能当独立行业基准（对应来源码 C2 + 红线 R7）。且是单次报告，无跨期核对。

### 1.5 部署 tracker 类（本轮页面未取得，明确标未核实）
- `https://agenticdaily.ai/trackers/ai-enterprise-deployments` 抓取超时。
- VeilStrat、Naftiko Signals 本轮未取到一手页面正文；早前搜索结果描述 VeilStrat 卖「每周 30–100 家公司采用信号 + CSV」，Naftiko 追踪 311 家企业信号，**这些只作为待核线索，不写为已核实产品细节**。

### 1.6 社区 / 培训 / 人才（本轮未逐页实抓，只作分类）
FDE.community（NYC 私域）、FDE Agency（月订阅替代 placement fee）、fde.academy（32 周训练营、企业侧 16.66% CTC）、AI FDE School（$3,900/人）等，早前会话已列过价格与模式；本轮未重新抓页面，**不重复计为一手证据**。它们都不做判断台账。

---

## 2. 横向对照表

| 维度 | FDE Hub | FDE Pulse | FDE Jobs JP | Perspective | imfde 现状 |
|---|---|---|---|---|---|
| 首屏第一句 | 搞懂 FDE，搞懂 AI 如何真正落地 | The FDE Job Market | FDE 専門求人サイト | Survey of 1,500 FDEs | 「不是再读一条新闻，是看变化如何被证实」（情报台 demo） |
| 颗粒度 | 百科长文 + 周刊 + 报告 | 结构化岗位/薪资 + 周报 | 岗位列表 | 一次性调查 | 事件流 + 单条判断 |
| 事实/判断分离 | 未见显式 | 基本只给事实 | 只给事实 | 有（TL;DR + 分节 + methodology） | 标准已定，产品未落地 |
| 来源标注 | 指标旁标 Indeed/LinkedIn + 时间窗 | `n=216 disclosed`、`updated weekly` | 每日更新 | 方法论段 + 样本构成 | 源评级表已定，产品未落地 |
| 更新/连续性 | 周刊、报告「持续更新」 | 每周一 Brief、updated weekly | 每日更新 | 单次报告 | 台账为演示数据（R9 命中） |
| 证据等级 / 兑现记录 | 无 | 无 | 无 | 无 | 无（标准已定） |
| 变现 | 招聘位/赞助/撮合，**内容全免费** | 雇主侧（For Employers） | 招聘导流 | 免费报告 → SaaS 漏斗 | 无 |

---

## 3. 谁做了什么、谁没做什么

**已经做得好的**
- 数字旁标口径（FDE Hub 指标、FDE Pulse 的 n=216、Perspective 的样本/时间窗）。
- 「我们替你读完」的价值主张（FDE Pulse：We read 1261+ postings so you don't have to）。
- 免费内容换邮箱 / 换线索的漏斗（FDE Hub 报告、Pulse Brief）。
- 单次调查的 methodology 透明（Perspective）。

**全行业都还没做的**
1. **判断台账**：没有一家把上期判断的兑现/证伪做成可检索界面。Stratechery（传统线）只在正文里偶尔回指旧分析，未产品化。
2. **来源评级可见化**：没有一家在每条信息旁标 B1/C2/D2/F6 这类等级，也没标「这条是厂商自述 / 这篇是同源转述」。
3. **口径三件套**：大多只标了时间窗，没标样本与分母；不同来源的数字仍可能被读者混用。
4. **改判留痕**：没有产品公开写「我们上期判断错在哪、被什么新信息推翻」。
5. **独立立场披露**：Perspective 报告利好自己品类却未在产品层标注利益关系。

---

## 4. imfde 的差异化结论

不要去抢：岗位数据（Pulse 已有 1261+ 与每周更新）、中文百科（FDE Hub 已有 6 篇 + 自检）、一次性大调查（Perspective 已有 1500 人样本）、招聘撮合（Hub / Jobs / Academy 都在做）。

**可以占的那一格**：

> 独立、有来源批判、有跨期兑现记录的**判断型情报**。
> 不靠数据规模，不靠专家网络，不靠撮合。每期少量判断；每个判断带来源等级、口径、替代解释、下期核对指标；下期回来逐条核对并留改判记录。

变现切点按功能而非字数：免费给本期判断与事件档案；付费给**跨期台账、全库检索、来源快照、可判定的下期核对清单与方法论**。这与传统线结论一致（Forrester 付费层 = 全库检索 + 框架 + 分析师访问；没有一家锁公开摘要收费）。

**前置条件**（不能跳）：先按两份标准把一条情报从证据卡加工到 L1/L2/L3 并验收通过；连续 3 期 A 级前不设付费入口。

---

## 5. 对两份验收标准的修订建议

1. **C3 来源描述**增加一条市场对照要求：数字必须「紧邻」标来源与时间窗，禁止只放文末来源列表（FDE Hub / Pulse / Perspective 的共同做法）。
2. **D4 口径同屏**补「样本量与分母」为强制显示项（Pulse 的 `n=216 disclosed` 是最小可接受形态）。
3. **新增展示红线 P9**：不得把常驻营销指标（如「+729% 岗位增幅」）冒充「本期变化」。FDE Hub 首屏是常驻指标，若 imfde 照搬会混淆「本期判断」与「长期背景」。
4. **新增内容红线 R10**：厂商发布的关于自身品类的调查，必须在 L1 标注利益立场（Perspective 教训）。
5. **付费层门槛**补一条：付费层必须提供「功能」而非「更多同类文章」——跨期台账 / 全库检索 / 来源快照 / 方法论页，四选三。
6. **连续性最低形态**写入规范：即使没有台账系统，每期至少有一句公开回指旧判断（Stratechery 的 `affirms my initial analysis` 是最低成本做法）。

---

## 依据（本轮实际取得正文的页面）
- [FDE Hub](https://fdehub.cc)
- [FDE Pulse](https://fdepulse.com)
- [FDE ジョブ](https://fde-jobs.jp)
- [Perspective AI, State of FDE 2026](https://getperspective.ai/blog/state-of-forward-deployed-engineering-2026-survey-report-1500-fdes)
- [CB Insights Research（传统线，实抓）](https://www.cbinsights.com/research)
- [Forrester Signature Research（传统线，实抓）](https://www.forrester.com/research/)
- [Stratechery（传统线，实抓首页）](https://stratechery.com)

**未取得正文**：Agentic Daily tracker（超时）、Gartner / The Information / S&P / Bloomberg / DIGITIMES（403/404）、FDE.community / FDE Agency / fde.academy 等本轮未重抓，均不写为已核实产品细节。
