# imfde.ai 数据模型设计

> 版本：2026-09-03 · 路线 A（撮合交易平台为主 + 学习成长板块）
> 目标库：Supabase (PostgreSQL) · MVP 阶段
> 状态：草稿，待评审

---

## 0. 边界：什么在本库，什么不在

| 数据 | 位置 | 说明 |
|---|---|---|
| 交易层（需求/项目/贡献/分账/认证） | **本库（Supabase）** | 平台自研，本次设计范围 |
| 内容层（559 案例 / 606 题 / 529 世界观察） | **交接仓库 `portal/fde.db`** | 不迁移、不重建（`build_portal_db.py` 会删库，禁用） |
| 学习进度 | 本库 | 只存 `source_ref` 引用内容层 ID，不复制内容 |

内容层独立部署为 `learn.imfde.ai`，本库只记「谁学到了哪」。

---

## 1. 实体关系

```
enterprises ──1:N── demands ──1:N── proposals
                       │
                       └──1:1── projects ──1:N── contributions
                                    │  └──1:N── payouts
fdes ──1:N── proposals / contributions / certifications / learning_progress
```

---

## 2. 表结构

### `fdes` — FDE 人才池

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | |
| github_login | text UNIQUE | GitHub 登录名 |
| display_name | text | 展示名（可化名，实名仅对已认证企业开放） |
| city | text | 常驻城市（线下可达性） |
| onsite_scope | text | 驻场范围，如「浙江省内，48h 响应」 |
| contact_email | text | |
| contact_verified | bool | 线上可联系（平台核验） |
| offline_verified | bool | 线下能找到（平台核验） |
| bio | text | 履历门面 |
| skills | jsonb | 技术栈标签数组 |
| level | enum('L1','L2','L3') | 当前认证等级 |
| created_at | timestamptz | |

> 约束：`contact_verified AND offline_verified` 同时为真才授予接单资格。

### `enterprises` — 企业

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | |
| name | text | |
| industry | text | 主营业务领域 |
| website | text | |
| contact_email | text | |
| verified | bool | 平台核验后开通 |
| archived_count | int | 已归档需求数（交付信誉） |
| created_at | timestamptz | |

### `demands` — 需求池

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | |
| enterprise_id | uuid FK | |
| title | text | 脱敏后标题 |
| description | text | 脱敏后描述 |
| industry | text | 行业标签 |
| difficulty | enum('S','A','B') | **难度**（企业填写） |
| budget_min / budget_max | int | 预算区间（公开） |
| tech_fields | jsonb | 技术领域 |
| required_level | enum('L1','L2','L3') | **FDE 级别要求** |
| required_headcount | int | **人数要求** |
| cycle_weeks | int | 交付周期 |
| acceptance_criteria | jsonb | **逐条量化验收标准**（立项锁定） |
| revenue_share_rule | jsonb | **分账规则**（企业填写，立项锁定） |
| status | enum | open / claiming / teamed / done / archived |
| published_at | timestamptz | |

### `proposals` — 认领方案

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | |
| demand_id | uuid FK | |
| fde_id | uuid FK | 提案人（未来主理人） |
| tech_plan | text | 技术方案（1 页） |
| milestones | jsonb | 周级里程碑 |
| share_table | jsonb | 分账表 |
| risks | jsonb | 风险清单（≥3 条） |
| votes | int | 社区投票数 |
| status | enum | pending / won / lost |
| created_at | timestamptz | |

### `projects` — 项目

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | |
| demand_id | uuid FK | |
| lead_fde_id | uuid FK | FDE 主理人 |
| license | enum('MIT','Apache-2.0','AGPL') | **立项锁定，不可改为闭源** |
| stage | enum | claimed / teamed / building / acceptance / settled |
| repo_url | text | 开源内核仓库 |
| share_table | jsonb | **锁定分账表**（投票通过后不可改） |
| locked_at | timestamptz | 锁定时间 |
| accepted_at / paid_at | timestamptz | 验收 / 回款 |

### `contributions` — 贡献记账

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | |
| project_id | uuid FK | |
| fde_id | uuid FK | |
| role | text | FDE 主理人 / 前端 / 后端 / 测试 / 文档 |
| kind | enum('code','req','test','doc','design') | **非代码贡献同样记账** |
| pr_count | int | PR 数（代码类） |
| entries | jsonb | 贡献明细（方案数、用例数、文档数…） |
| share_pct | numeric(5,2) | 锁定占比 |
| recorded_at | timestamptz | |

> 约束：`SUM(share_pct) + 平台 10% = 100`

### `payouts` — 分账公示

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | |
| project_id | uuid FK | |
| amount | int | 回款金额（分） |
| breakdown | jsonb | 分配明细 |
| status | enum('pending','public') | |
| paid_at / public_at | timestamptz | 回款后 **72 小时内**公示 |

### `certifications` — 认证记录

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | |
| fde_id | uuid FK | |
| level | enum('L1','L2','L3') | |
| granted_at | timestamptz | |
| evidence | jsonb | 交付记录 / 答辩材料 / 复盘链接 |

### `learning_progress` — 学习进度（引用内容层）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid PK | |
| fde_id | uuid FK | |
| module | enum('落地','现场','案例','方法','世界动态') | |
| source_ref | text | 内容层条目 ID（**不复制内容**） |
| completed_at | timestamptz | |

---

## 3. 状态机

**需求**：`open`（待认领）→ `claiming`（有方案投票中）→ `teamed`（方案胜出组队）→ `done`（验收）→ `archived`（归档进企业档案，累计交付信誉）

**项目五阶段**（首页见证时间线）：`claimed` → `teamed` → `building` → `acceptance` → `settled`

---

## 4. 三条不可妥协机制的技术约束

| 机制 | 实现方式 |
|---|---|
| 01 协议锁定 | `projects.license` 写入后应用层禁止 UPDATE；需变更须新建记录并留审计日志 |
| 02 分账前置 | `demands.revenue_share_rule` 必填才能进池；`projects.share_table` 锁定后只读 |
| 03 贡献全记账 | 代码走 GitHub PR webhook 自动写 `contributions`；非代码贡献人工录入同样入库 |

---

## 5. 索引建议

- `demands(status, difficulty, required_level)` — 需求池筛选（首页 tab + 难度/级别过滤）
- `contributions(project_id)` — 项目贡献表
- `proposals(demand_id, status)` — 方案投票
- `fdes(level, city)` — 人才池检索
- `learning_progress(fde_id, module)` — 认证前置校验

---

## 6. 待定

- [ ] 分账资金流合规：代收款须走持牌机构分账能力，**不能做资金池 + 二次清算**（二清风险）
- [ ] `payouts` 是否需要对接支付网关回调
- [ ] 内容层 `source_ref` 的 ID 规范（等克隆后看 `world_events` 主键）
