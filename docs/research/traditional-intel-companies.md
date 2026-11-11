# 传统情报 / 商业信息公司产品形态调研

> 状态：正式报告 v1（含实抓页面与明确未取得项）。配套 `docs/imfde-intel-acceptance-standard.md`、`docs/imfde-intel-presentation-standard.md`。
> 方法：优先抓官方页面正文；反爬/超时/404 一律标注「未取得」，不把二手摘要冒充页面内容。逐页抓取缓存见 `.zcode/*.html`。
> 调研日期：2026-11-11。

## 0. 先拆开四种模式（混着抄必错）

| 模式 | 代表 | 卖什么 | 展示重心 | 信任来源 |
|---|---|---|---|---|
| A. 数据终端 / 数据集 | Bloomberg Terminal、S&P Capital IQ Pro、PitchBook、CB Insights | 可检索、筛选、导出的**结构化事实** + 工具 | 字段密度、口径一致、实时刷新 | 覆盖率、双重校验、集成能力 |
| B. 研究订阅与评级 | Gartner、Forrester、EIU、DIGITIMES | 判断、框架、预测、**公开方法论** | 执行摘要、评级/象限/预测、报告体系 | 方法论透明、分析师资质、品牌 |
| C. 判断型通讯 | Stratechery、The Information | 少数人的**解释与洞察**，有时含独家信源 | 一篇一判断、文风与论证链 | 作者本人、长期判断记录 |
| D. 专家网络 / 咨询附加 | Gartner 分析师访问、Forrester Consulting、各类 expert network | 人的判断背书与针对性问答 | 资质、利益冲突披露、问答记录 | 专家网络与机构背书 |

**imfde 属于 C 与 B 的交界，不具备 A 的数据规模，也不具备 D 的专家网络。** 之前 rounds 把页面做成「数据终端式罗列」，又想卖「研究订阅」的价，是错配。

---

## 1. 实抓页面与事实

### 1.1 CB Insights（A 为主，带 B 的报告层）— 已取得
`https://www.cbinsights.com/research`（200，118 KB）

页面可见要素逐条：
- `10M+ companies`、`1,500+ markets` — 用覆盖规模建立第一层信任。
- `Double-verified, continually refreshed` — **把「数据可信度」直接做成产品卖点**，不是藏在方法论页。
- `Personalized research library: Concise, precise visual research that drives decisions`。
- `Personal briefing: Like a team of researchers working 24/7 — just for you`。
- `Predictive data science: National science-backed data science on private companies`。
- 集成：API & data feeds / Snowflake / Microsoft 365 Copilot / Salesforce。
- 报告样例：`State of Insurtech Q3'26 — Insurtech deal count fell to its lowest level since 2016. Here's what happened.`

**展示手艺**：报告标题 = 一句有方向的判断 + 时间口径（Q3'26）+ 一句解释承诺（Here's what happened）。这是「数据 → 判断」的最短产品化写法。

**不能照搬**：1000 万家公司的数据密度、终端级检索、机构销售。

### 1.2 Forrester（B）— 已取得
`https://www.forrester.com/research/`（200，202 KB）

- 研究类型**固定分栏**：`Predictions / Budget Planning Guides / Market Forecasts / Forrester Landscapes / The Forrester Wave™ / Market Insights / Buyer Insights / Signature Research`。
- Wave 的表述：`Compare providers using Forrester's trusted evaluation methodology and detailed market analysis` — 评级不是 opinion，绑定**公开评估方法论**。
- 组织方式：按 `Who We Serve`（角色 × 行业）与 `What We Offer`（产品形态）双轴导航。
- 付费切点（原文）：`Clients access Forrester through its subscription-based dedicated platform. Using this platform, clients can search for reports, data, and frameworks. Licensed users can also access Forrester's research and insights directly within tools like Microsoft Teams and Copilot. They can use Forrester AI to get answers fast and connect with analysts to tailor insights to their specific priorities.`
- 转化入口：`Talk To Sales`（不是自助结账）。

**展示手艺**：把「报告类型」做成固定词表，读者知道自己在买哪一类判断；评级必须连着方法论；付费层 = 全库检索 + 框架 + 分析师访问，不是单篇。

### 1.3 Stratechery（C）— 已取得首页
`https://stratechery.com`（200，626 KB）

- 定位一句：`On the business, strategy, and impact of technology.`
- 分层入口：`Stratechery Plus / Subscribe / Member Forum / Updates / Interviews / Year in Review / All Articles / Latest Podcast`。
- **连续性的最小形态**：正文里作者公开回指旧判断——`I haven't written about Anthropic's updated S-1, but it strongly affirms my initial analysis.` 不是台账系统，但读者能看见「我以前怎么判断、新信息是否印证」。
- 文章正文形态：一篇一判断，长论证，不靠数据密度。

**未取得**：`https://stratechery.com/subscribe/` 返回 404；定价与免费/付费具体切点**不写**，只确认入口存在。

### 1.4 EIU（B）— 页面未取得，但有可确认残片
`https://www.eiu.com/n/why-subscribe-to-eiu/` 404；404 页仍可见：按客户类型组织（`Financial Services / Corporates / Academic institutions / Government`），卖点措辞 `independent macroeconomic and geopolitical insights`、`understand the world today and be prepared for the changes of tomorrow`。

**可确认**：传统情报的「读者相关性」是按角色分层，不是给所有人同一页。

### 1.5 明确未取得的页面（不得编造）
| 页面 | 状态 |
|---|---|
| Gartner Research 产品页 / methodologies | 403 Cloudflare 验证 |
| The Information 订阅页 / about | 403 Cloudflare 拦截 |
| S&P Capital IQ Pro 产品页 | 403 |
| PitchBook providers | 404 |
| Bloomberg Terminal 产品页 | 403 |
| DIGITIMES services | 403 |
| Economist Intelligence Unit | 403 |

二手资料里的 Gartner 象限方法论、S&P 席位价格、Bloomberg 终端价格、DIGITIMES 续约率，**本报告一律不引用为已核实事实**。若需，应另找可访问的一手 PDF 或年报。

### 1.6 同类参照（本会话早前已核，供交叉参考，不重复计为一手页面）
- Perspective AI《State of FDE 2026》已实抓原文：有 TL;DR、目录、独立 methodology 段（1,500 人 / 154 家公司 / 2026-02–04 / 受访者构成），但结论恰好利好厂商自己的工具品类 → 属**带利益立场的内容营销**。
- ICD 203 / ICD 206 / CIA Tradecraft Primer 已下载 PDF 并提取全文，作为规范依据，见两份标准文档。

---

## 2. 付费墙切点（只写能确证的）

| 产品 | 免费层 | 付费层 | 切点依据 |
|---|---|---|---|
| Forrester | 页面导航、部分公开内容 | 订阅平台全库检索 + 报告 + 框架 + Forrester AI + 分析师访问 + Teams/Copilot 集成 | 官方 research 页原文 |
| FDE Hub（垂直对照） | 百科、专栏、资源库、自检、周刊、报告 PDF 全免费 | 无内容付费；靠招聘推广位、报告赞助、撮合变现 | 官网 FAQ 原文 |
| FDE Pulse（垂直对照） | 岗位数据、薪资、免费每周 Brief | 雇主侧（For Employers）；具体价格未取得 | 官网导航与首屏 |
| Stratechery | 部分文章 / 播客 | Plus / Member Forum（具体切点未取得） | 首页入口 |
| CB Insights | 公开报告标题与部分内容 | 终端、API、personal briefing（价格未取得） | research 页 |

**结论：没有任何一家把「公开新闻摘要」锁起来收费。** 免费层给事实、数据或单篇洞察；付费层给全库检索、框架、方法论、专家访问、定制 briefing，或干脆靠 B 端变现。这直接否掉「做一页漂亮简报就能收费」的假设。

---

## 3. 展示与解释：成熟做法清单

1. **数字旁标口径**：FDE Pulse `n=216 disclosed`、FDE Hub 指标紧邻 `Indeed 2025.4–2026.4`、Perspective `1,500 / 154 companies / Feb–Apr 2026`；CB Insights `Double-verified, continually refreshed`。口径不是脚注，是展示元素。
2. **判断前置 + 承诺解释**：CB Insights 报告标题「deal count fell to its lowest since 2016. Here's what happened.」；Perspective 的 TL;DR；ICD 203 的 main analytic message up front。
3. **方法论独立成段/成页**：Perspective 的 Survey methodology；Forrester Wave 绑定 trusted evaluation methodology。**评级/判断不与方法论同框展示就不成立**。
4. **固定内容类型词表**：Forrester 的 Predictions / Forecasts / Landscapes / Wave / Guides；读者知道自己在看哪一类判断。
5. **按角色组织相关性**：EIU 按客户类型、Forrester 按 Who We Serve。
6. **连续性最低成本形态**：Stratechery 在正文回指「my initial analysis」→ 印证/证伪留痕，不需要先建系统。
7. **信任靠可核查承诺**：「Double-verified」「continually refreshed」「subscription-based dedicated platform」都是可验证的产品事实，不是「权威」「深度」这类形容词。

---

## 4. 对 imfde 的启示（分「学 / 不学」）

### 必须学
- 口径与数字同屏（强化 D4）；来源批判做成可见的产品事实，不是内部纪律。
- 判断前置 + 一句「凭什么」的承诺，但**解释必须真的给推理链**（我们标准 D7）。
- 内容类型固定词表：事实快讯 / 单条判断 / 跨期核对 / 专题研究，各自版式不同。
- 方法论页公开：源评级表、样本与时间窗定义、改判规则。
- 免费/付费切点按**功能**而不是按「字数」：免费给本期判断与事件档案，付费给跨期台账、全库检索、来源快照、可判定的下期核对清单。
- 厂商自述与独立来源分开评级（Perspective 的教训 → 来源码 C2 与 R7）。

### 不能照搬
- 终端级数据密度与覆盖率（CB Insights 10M+ 公司）：我们没有，硬做只会暴露稀薄。
- 评级象限 / Magic Quadrant：需要可验证样本量与公开打分方法论，否则就是编分数（违反 R3/R7）。
- 机构销售与席位定价：没有品牌与分析师网络。
- 双向撮合市场（FDE Hub 的知识库+人才库）：需要供需两端运营，会把情报本体拖成招聘业务。
- 把「Double-verified」当口号用：没有真做双重核验就是虚假宣传。

---

## 5. 市场上还没被满足的那一格（待 FDE 垂直报告交叉确认）

把 A–D 四种模式与 FDE 垂直玩家对照后，空位是：

> **一个只做「判断的连续追踪」的独立产品**：不靠数据规模，不靠专家网络，不靠招聘撮合；每期只给少量经过来源批判的判断，把上期判断的兑现/证伪留痕做成核心界面，方法论公开、口径固定、可回溯。

Stratechery 有「回指旧分析」但没有产品化；FDE Hub / FDE Pulse 有内容与数据但没有台账；Perspective 有 methodology 但是厂商营销。**这三者之间的空位，才是 imfde 可能的差异化。**

---

## 依据（本报告中实际取得正文的页面）
- [CB Insights Research](https://www.cbinsights.com/research)
- [Forrester Signature Research](https://www.forrester.com/research/)
- [Stratechery 首页](https://stratechery.com)
- [EIU 404 页残片（按客户类型组织）](https://www.eiu.com/n/why-subscribe-to-eiu/)
- [Perspective AI, State of FDE 2026（已实抓）](https://getperspective.ai/blog/state-of-forward-deployed-engineering-2026-survey-report-1500-fdes)
- [ICD 203 官方 PDF](https://www.dni.gov/files/documents/ICD/ICD-203.pdf)
- [CIA, A Tradecraft Primer](https://www.cia.gov/resources/csi/static/Tradecraft-Primer-apr09.pdf)
- [Kent, Words of Estimative Probability](https://www.cia.gov/resources/csi/static/Words-of-Estimative-Probability.pdf)

**未取得正文**：Gartner、The Information、S&P Capital IQ、PitchBook、Bloomberg Terminal、DIGITIMES（均 403/404/超时），本报告不对它们的产品细节下已核实结论。
