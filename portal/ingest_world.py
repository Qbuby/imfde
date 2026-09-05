# -*- coding: utf-8 -*-
"""Dynamics-layer ingest for the world homepage.

Reads portal/world_sources.json, writes world_* tables in portal/fde.db.
Does NOT recrawl vendor case-study walls and does not start mine_loop.

Usage:
  python3 portal/ingest_world.py --daily
  python3 portal/ingest_world.py --feeds --since 2026-09-01
  python3 portal/ingest_world.py --migrate-only
"""
from __future__ import annotations

import argparse
import html as H
import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = HERE / "fde.db"
SCHEMA_PATH = HERE / "world_schema.sql"
CATALOG_PATH = HERE / "world_sources.json"
DATES_JSON = HERE / "source_dates.json"
RAW_DIR = HERE / "world_raw"
REPORT_PATH = HERE / "world_ingest_report.json"
STATE_PATH = HERE / "world_state.json"
# Snapshot day = the day this run happened (override with --snapshot). The site
# reads it back from world_ingest_report.json so the 7/30/90 windows end today.
SNAPSHOT = date.today().isoformat()
COLLECTED_ON = SNAPSHOT
MAX_NEW_AXIS = 16
FRESH_DAYS = 7  # a fresh ATS posting = first_published within this many days
# 增量回溯窗口：收发布日期不早于 (快照日 - N 天) 的条目。
# 不能用「上次运行日」当 since——新闻室/博客文章的发布日几乎总早于上次运行，
# 会被整批判 stale 永久丢失（peek 的 20 个列表源因此长期抓不到东西）。
# 放宽窗口只是多查一遍，已在库的走 dup 去重，不会重复上轴。
BACKFILL_DAYS = 30
PEEK_CANDIDATES = 8  # per list_index source per run: how many candidate links to open and date-check
FRESH_PER_BOARD = 4  # unique folded titles per board per run; 7-day window needs these weak signals

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
}

CS_PATH_RE = re.compile(
    r"/(customers?|customer-stories|case-stud(?:y|ies)|impact|success-stor)(/|$)",
    re.I,
)
CS_STORY_RE = re.compile(
    r"/(customers?|customer-stories|case-stud(?:y|ies)|impact|success-stor)/.+"
    r"|customer-story",
    re.I,
)
CS_PER_HUB = 2
FDE_RE = re.compile(
    r"forward[\s\-]*deployed|FDE\b|deployment company|openai frontier|frontier company|enterprise ai services",
    re.I,
)
DAY_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
ISO_RE = re.compile(r"(\d{4}-\d{2}-\d{2})[T\s]")
EN_MONTH = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
EN_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),\s+(\d{4})\b",
    re.I,
)

# Frozen Chinese labels. Evidence URLs stay the source record.
TITLE_ZH = {
    "openai-deployment-company": "OpenAI 发布 Deployment Company",
    "openai-frontier": "OpenAI 发布 Frontier",
    "openai-frontier-product": "OpenAI Frontier 产品页",
    "cohere-fde-capability": "Cohere：FDE 建能力，不制造依赖",
    "blend360-fde-750": "Blend360：FDE 编制扩到 750 人",
    "a16z-services-led": "a16z：用毛利换护城河",
    "pe-heats-up": "Pragmatic Engineer：FDE 再次升温",
    "pe-what-are-fdes": "Pragmatic Engineer：FDE 为何抢手",
    "fdei-how-fdes-work": "FDE 交付生命周期",
    "fdei-day-in-life": "FDE 的一天",
    "fdepod-101": "FDE 101：何时需要编制",
    "openai-fde-seattle": "OpenAI 招聘 FDE",
    "reddit-levels": "Reddit：什么是 FDE",
    "reddit-openings": "Reddit：到处都是 FDE 岗位",
    "reddit-role": "Reddit：FDE 这个岗位",
    "reddit-scam": "Reddit：FDE 是不是坑",
    "nabeel-reflections": "Nabeel：对 Palantir 的反思",
    "barry-fde-culture": "Barry：FDE 文化",
    "ted-mabrey-linkedin": "Ted Mabrey：那不是 FDE",
    "bob-mcgrew-yc": "Bob McGrew：AI 创业公司的 FDE 手册",
    "marty-cagan-fde": "Marty Cagan：前向部署工程师",
    "natalie-meurer-latent": "Natalie Meurer：前向部署工程师",
    "natalie-meurer-aiewf": "Natalie Meurer：FDE 的脏秘密",
    "kevin-bai-aiewf": "Kevin Bai：FDE 101",
    "palantir-q2-2026-letter": "Palantir 2026 Q2 股东信",
    "palantir-q2-2026-pr": "Palantir 2026 Q2 业绩稿",
    "aws-fde-partners": "AWS 宣布伙伴 Forward Deployed Engineering",
    "aws-fde-computerworld": "AWS：FDE 怎么做",
    "posthog-wtf-fde": "PostHog：什么是 Forward Deployed Engineer",
    "vannevar-fde": "Vannevar：怎么建 FDE 组",
    "a16z-fde-fellowship": "a16z FDE Fellowship",
    "plank-fde-census-2026-07-04": "Plank：FDE 岗位市场普查",
    "anthropic-fde-gh": "Anthropic 招聘 FDE",
    "palantir-fdai-lever": "Palantir 招聘 Forward Deployed AI Engineer",
    "xai-fde-xapi": "xAI 招聘 FDE",
    "scale-fde-enterprise": "Scale 招聘 FDE",
    "databricks-fde-org": "Databricks 成立 Forward Deployed Engineering",
    "microsoft-frontier-company": "Microsoft 发布 Frontier Company",
    "anthropic-enterprise-services": "Anthropic 成立企业 AI 服务公司",
    "deployco-northslope": "Deployment Company 收购 Northslope",
    "colin-jarvis-eng-leadership": "Colin Jarvis：OpenAI 的 FDE 岗位",
    "washtech-fde-talent-2026-09-01": "Ross Wilkers：FDE 人才短缺",
    "plank-fde-brief-august-2026": "Plank：2026 年 8 月 FDE 简报",
}

HAPPENED_ZH = {
    "openai-deployment-company": "OpenAI 把面向企业的部署能力写成独立产品公司 Deployment Company。",
    "openai-frontier": "OpenAI 发布 Frontier，把部署现场能力做成一条命名产品线。",
    "cohere-fde-capability": "Cohere 公开写 FDE 的职责是帮客户建能力，而不是制造对厂商的长期依赖。",
    "nabeel-reflections": "Nabeel Qureshi 以个人身份回顾在 Palantir 做 Forward Deployed 的工作方式。",
    "barry-fde-culture": "Barry McCardel 以个人身份写 FDE 文化：现场工程师如何做判断、如何跟客户共处。",
    "ted-mabrey-linkedin": "Ted Mabrey 公开区分「真正的 FDE」和被误标成 FDE 的岗位。",
    "bob-mcgrew-yc": "Bob McGrew 在 YC 讲 AI 创业公司如何组 FDE、何时该组、现场怎么交付。",
    "marty-cagan-fde": "Marty Cagan 从产品发现角度讨论 Forward Deployed Engineers 这个角色。",
    "natalie-meurer-latent": "Sierra 的 Natalie Meurer 在 Latent Space 谈 FDE 在 Agent 工程里怎么干活。",
    "natalie-meurer-aiewf": "Natalie Meurer 在 AIEWF 讲 Forward Deployed Engineering 现场里不写进招聘启事的部分。",
    "kevin-bai-aiewf": "Kevin Bai 在 AIEWF 做 FDE 101。台上数字不当审计测量。",
    "palantir-q2-2026-letter": "Palantir 2026 年第二季度股东信里，继续把 Forward Deployed 编制写成经营口径。",
    "palantir-q2-2026-pr": "同一天的 SEC 新闻稿佐证 Q2 业绩口径。不当第二条独立「变化」。",
    "aws-fde-partners": "AWS 官方宣布面向伙伴的 Forward Deployed Engineering 组织，并写了配套投入。",
    "aws-fde-computerworld": "AWS 高管接受访谈，解释 AWS 怎么理解和使用 FDE。次于官方 APN 文。",
    "posthog-wtf-fde": "PostHog 工程博客解释他们为什么招、怎么用 Forward Deployed Engineer。",
    "vannevar-fde": "Vannevar Labs 写防务场景里如何建 Forward Deployed Engineering 组。",
    "a16z-fde-fellowship": "a16z 公开 FDE Fellowship 页，说明他们怎么培养现场部署人才。",
    "plank-fde-census-2026-07-04": "Plank 发布一则 FDE 岗位市场普查。这是一篇观察，不是 1200 条岗位事件。",
    "a16z-services-led": "a16z 讨论以服务换增长、用毛利换护城河，FDE 被放进这条增长叙事。",
    "pe-heats-up": "Pragmatic Engineer 记录 FDE 岗位再次升温，以及哪些公司在招。",
    "pe-what-are-fdes": "Pragmatic Engineer 解释 FDE 为什么突然抢手。",
    "fdei-how-fdes-work": "FDEInterviews 把 FDE 的交付生命周期写成可核对的工作步骤。",
    "fdei-day-in-life": "FDEInterviews 写 FDE 的一天，用来理解现场节奏，不是某家客户的交付证明。",
    "fdepod-101": "The FDE Pod 讨论何时需要 FDE 编制。",
    "openai-fde-seattle": "OpenAI 公开招聘西雅图 Forward Deployed Engineer。",
    "databricks-fde-org": "Databricks 官方宣布成立 Forward Deployed Engineering 组织，把现场交付收成一条编制。稿里的客户名不拆成部署节点。",
    "microsoft-frontier-company": "Microsoft 发布 Frontier Company，投入资金并把数千名行业与工程人员嵌进客户现场。自称超过 FDE 标签，仍是部署编制宣布。",
    "anthropic-enterprise-services": "Anthropic 与 Blackstone、Hellman & Friedman、Goldman Sachs 成立企业 AI 服务公司，把 Claude 的现场部署做成独立载体。",
    "deployco-northslope": "OpenAI Deployment Company 宣布收购 Northslope，用来扩大现场部署编制。不是客户交付故事。",
    "colin-jarvis-eng-leadership": "Engineering Leadership 访谈 OpenAI Global Head of FDE Colin Jarvis，讲 FDE 这个岗位实际怎么干活。",
    "washtech-fde-talent-2026-09-01": (
        "9 月 1 日 Washington Technology 把 FDE 写成「技术人才短缺里的短缺」。"
        "引 Christian & Timbers：美国约 1.7 万名 FDE，约 2000 人被称作 Elite（企业 AI 做成有记录回报）。"
        "扩法是初级跟 Elite 做规模题；国防 / A&D 被写成同一困境。"
    ),
    "plank-fde-brief-august-2026": "Plank 8 月 FDE 简报：人才供给大约 2000 人、Palantir Q2、以及买方是自建还是外购现场工程师。",
}

WHY_BY_KIND = {
    "org_announcement": "这是头部厂商把部署写成独立组织或业务的公开动作，不是客户故事。",
    "product_line": "这是把部署能力命名成产品线的官方宣布，标志着 FDE 从支持角色走向业务中心。",
    "earnings_letter": "股东信是经营口径。点名 FDE 说明编制已经进入对外叙事，仍需回到原文核对数字。",
    "press_release": "官方新闻稿用来佐证同一天的经营口径，不单独当成第二条变化。",
    "named_essay": "具名评论。先核文中主张、数字口径和说话人身份，不要自动当成雇主官方。",
    "interview": "有日期、有具名受访者的访谈。提供从业者怎么理解 FDE 的语境。",
    "conference_talk": "有发布日的演讲或官方录像。台上数字不当审计测量。",
    "podcast_episode": "有发布日的单期播客，用来理解方法共识，不证明某家客户已照此执行。",
    "discussion": "公开讨论帖。一帖一条；无发布日则只收录、不进窗口。",
    "methodology": "方法或手册材料，帮助理解 FDE 如何工作；不证明某家客户已照此执行。",
    "engineering_blog": "工程团队写怎么建 FDE 组。这是方法信号，不是交付故事。",
    "job_posting": "官方招聘是弱信号：说明有人在建这支队伍，不证明编制已经落地。",
    "hiring_census": "有采集日的公开普查，一篇一篇进方法轨，不把岗位列表铺进窗口。",
    "dated_case_study": "具名客户且原文有发布或修改日，可作为交付现场样本；仍需回到原文核对口径。",
}

# Homepage four fields. Purpose = 行业发展有多快, not source-hygiene theater.
# happened: 原文里哪件可核对的事（谁、何时、主张/数字带口径）
# why: 这条让本窗的「快」多了哪一层，要能和窗内其他形体并读；「不是官方」只能当从句
# enterprise: 决策者这窗要改的判断（买/建/等）
# practitioner: 从业者这窗要改的动作（投递/范围/别混岗位）
# Do not invent KPIs. Hygiene (猎头≠普查) goes in a clause, never as the conclusion.
DEPLOY_NO_FDE = (
    "原文没有写 Forward Deployed 头衔。可核的是客户侧结果和现场做法，不是编制样板。"
)

EVENT_COPY = {
    "blend360-fde-750": {
        "happened": "Blend360 宣布把 Forward Deployed AI Engineering 编制扩到 2027 年 750 人，理由是企业要把 AI 嵌进生产。",
        "enterprise": "这是服务商扩编目标，不是买方自己的 FDE 组织，也还不是已经到岗的人数。",
        "practitioner": "信号是现场工程岗位还在扩。工作方式不能自动等同 Palantir 或 OpenAI 的 FDE。",
    },
    "washtech-fde-talent-2026-09-01": {
        "happened": (
            "9 月 1 日 Washington Technology 把 FDE 写成「技术人才短缺里的短缺」。"
            "引 Christian & Timbers：美国约 1.7 万名 FDE，约 2000 人被称作 Elite（企业 AI 做成有记录回报）。"
            "JC Christian 给的扩法是初级跟 Elite 做「有把握能赢」的规模题。"
            "国防承包商被写成同一困境；A&D 更偏政府关系和驱动消费，文中写不一定亲自实施。"
        ),
        "why": (
            "这窗沙盘上同时有厂商在招（Databricks、OpenAI、Cohere）和服务商扩编目标（Blend360 说到 2027 年 750 人）。"
            "这条是人物轨把「还在招」翻成「能出回报的人很少」。"
            "公开叙事从「FDE 是什么」转到「Elite 不够用」——这才是它出现在这窗里的理由。"
            "1.7 万 / 2000 仍是猎头口径，不是普查。"
        ),
        "enterprise": (
            "和这窗扩招、扩编并读：若买方接受「Elite 约 2000」，自己招齐能出回报的人更难，更可能继续买驻场 / 服务商。"
            "A&D 还被说成关系驱动。买之前问清楚买的是驻场交付还是政府关系。"
        ),
        "practitioner": (
            "这窗岗位从 TPM、经理到初级都在挂。"
            "文中把「头衔人数」和「能出回报」拆开，晋升叙事是跟 Elite 做规模题。"
            "投递时对着 JD 分清是写系统还是推消费。"
        ),
    },
    "cohere-fde-capability": {
        "enterprise": "Cohere 把 FDE 写成帮客户建能力、不制造依赖。买驻场前要问：撤场后自己的人能不能接着跑。",
        "practitioner": "诊断根因、改 agent 和底层工具，并判断问题该走部署侧还是产品侧。这是职责描述，不是某一单 KPI。",
    },
    "colin-jarvis-eng-leadership": {
        "enterprise": "OpenAI 的 Global Head of FDE 公开讲这个岗位怎么干活。可用来对照自己买的是驻场，还是产品支持。",
        "practitioner": "一线口径，用来理解 OpenAI FDE 的日常，不是招聘承诺。",
    },
    "palantir-q2-2026-letter": {
        "enterprise": "股东信把 Forward Deployed 写成经营口径。可读的是编制是否进入对外叙事；信里的数字要回原文，不能当某一单客户 KPI。",
        "practitioner": "公开市场把 FDE 写进 Palantir 增长故事，不等于下一份 JD 会做同样的事。",
    },
    "palantir-q2-2026-pr": {
        "enterprise": "与股东信同一天的业绩稿，用来佐证口径，不应当成第二条独立变化。",
        "practitioner": "没有新的岗位工作方式；回信文即可。",
    },
    "aws-fde-partners": {
        "enterprise": "AWS 官方宣布面向伙伴的 FDE 组织及配套投入。这是伙伴运动，不是 AWS 替你交付某一单。稿里点到的客户名不拆成部署节点。",
        "practitioner": "伙伴侧会出现 FDE 编制。岗位在生态里，不自动等于进入 AWS 本体。",
    },
    "aws-fde-computerworld": {
        "enterprise": "访谈是 APN 文的补充口径，次于官方宣布。",
        "practitioner": "听 AWS 怎么定义这个角色，用来对照伙伴 JD，不当录用标准。",
    },
    "microsoft-frontier-company": {
        "enterprise": "Microsoft 把数千名行业与工程人员嵌进客户现场，并命名 Frontier Company。自称超过 FDE 标签，仍是部署编制宣布。投入数字要回原文。",
        "practitioner": "大厂把驻场写成公司级运动。岗位名可能不叫 FDE，工作方式仍是嵌进客户。",
    },
    "databricks-fde-org": {
        "enterprise": "Databricks 把现场交付收成一条 Forward Deployed Engineering 编制。客户名留在原文，不当第二条部署事件。",
        "practitioner": "平台厂商开始设 FDE 组。现场工作会更靠近数据平台落地，而不是纯咨询。",
    },
    "deployco-northslope": {
        "enterprise": "Deployment Company 用收购扩现场编制，不是某一单客户上线。要问买到的是人，还是产品接口。",
        "practitioner": "编制在靠并购变大。个人路径会碰到整合后的角色重划。",
    },
    "natalie-meurer-latent": {
        "enterprise": "Sierra 的人从 Agent 工程讲 FDE。可对照：你要的是客服 agent 现场，还是平台编制。",
        "practitioner": "具名访谈，用来听一线怎么带 agent 进客户，不是 Sierra 官方组织公告。",
    },
    "natalie-meurer-aiewf": {
        "enterprise": "台上讲招聘启事里不写的现场部分。只按 JD 招，会漏掉驻场里真正耗时间的协调和脏数据。",
        "practitioner": "用来校准对 FDE 日常的预期。台上数字不当审计。",
    },
    "kevin-bai-aiewf": {
        "enterprise": "FDE 101 面向何时需要这支队伍。先问有没有值得嵌人的现场，再谈编制。",
        "practitioner": "入门框架。台上数字不当测量。",
    },
    "plank-fde-brief-august-2026": {
        "enterprise": "简报把人才供给、Palantir Q2 和「自建还是外购现场工程师」放在一起。要分开读，不要把普查当编制事实。",
        "practitioner": "8 月市场速览。岗位热度和自己能不能入职不是同一件事。",
    },
    "plank-fde-census-2026-07-04": {
        "enterprise": "一篇市场普查，不是把岗位列表铺进窗口。不能把列表长度读成需求已兑现。",
        "practitioner": "看供给和职级分布，不要把聚合板当投递清单。",
    },
    "fdei-how-fdes-work": {
        "enterprise": "生命周期写成可核对的步骤。企业可对照自己有没有「真实数据上的细切片」，还是停留在样例 Demo。",
        "practitioner": "八个阶段里只有两段主要在写代码。只刷算法题覆盖不了发现、评测和交接。",
    },
    "fdei-day-in-life": {
        "enterprise": "用来理解驻场节奏和沟通密度，不是某家客户已经照此执行的证明。",
        "practitioner": "编码与对话随阶段剧烈摆动。上线期会有与代码无关、但决定能不能上线的会议。",
    },
    "fdepod-101": {
        "enterprise": "讨论何时需要 FDE 编制。合同价值和编制规模是播客里的对照，不当审计。",
        "practitioner": "FDE 被写成面向客户的软件工程师：顾问、产品和工程三顶帽子轮着戴。",
    },
    "openai-deployment-company": {
        "enterprise": "把面向企业的部署能力写成独立产品公司。企业要问对接的是产品线，还是驻场编制。",
        "practitioner": "编制从「支持角色」被写成业务主体。岗位会更靠近客户现场，而不是内部平台。",
    },
    "openai-frontier": {
        "enterprise": "把部署现场能力命名成产品线。这是产品化信号，不是某一单交付完成。",
        "practitioner": "现场工作可能被收进命名产品。职责边界要回产品页，不要只看 FDE 头衔。",
    },
    "anthropic-enterprise-services": {
        "enterprise": "与投资方成立企业 AI 服务公司，把 Claude 的现场部署做成独立载体。不是客户故事。",
        "practitioner": "现场部署被放到独立公司。雇主和客户界面可能与 Anthropic 本体分开。",
    },
    "nabeel-reflections": {
        "enterprise": "个人回顾，不是 Palantir 官方组织说明。可当现场工作方式的旁证。",
        "practitioner": "用来理解 Palantir 式 Forward Deployed 怎么做判断，不当现行 JD。",
    },
    "barry-fde-culture": {
        "enterprise": "讲现场文化与共处方式。企业若只招「会写代码的驻场」，会漏掉判断和客户关系。",
        "practitioner": "个人文。用来对照自己所在组的文化，不是雇主手册。",
    },
    "posthog-wtf-fde": {
        "enterprise": "工程博客解释他们为什么招、怎么用 FDE。这是一家产品公司的方法，不是行业标准。",
        "practitioner": "看产品工程组如何吸收现场角色，不要直接复制成大厂驻场路径。",
    },
    "vannevar-fde": {
        "enterprise": "防务场景里如何建 FDE 组。约束（权限、驻场、交付物）与商业 SaaS 不同。",
        "practitioner": "方法信号。防务现场的节奏和合规，不能当成普通企业 AI 驻场。",
    },
    "pe-heats-up": {
        "happened": "Pragmatic Engineer Pulse 记录 Forward Deployed Engineering 再次升温，以及哪些公司在招。",
        "enterprise": "这是行业通讯，不是组织宣布。可当「岗位变热」的旁证，不能当成某家已经建好编制。",
        "practitioner": "看哪些公司被点名在招。具体要求仍要回官方 JD，通讯不是投递清单。",
    },
    "pe-what-are-fdes": {
        "enterprise": "解释 FDE 为何抢手。企业可读成需求叙事，不是某一单交付证明。",
        "practitioner": "用来建立角色地图：现场写生产代码、又要面对客户。不是面试题答案。",
    },
    "ted-mabrey-linkedin": {
        "enterprise": "公开区分真 FDE 和被误标的岗位。买驻场前要问：人是不是在客户现场写生产代码并 own 结果。",
        "practitioner": "头衔通胀的一线判断。简历上的 FDE 三个字母，不等于这份工作。",
    },
    "bob-mcgrew-yc": {
        "enterprise": "面向 AI 创业公司：何时该组 FDE、现场怎么交付。台上数字不当审计，也不是客户 KPI。",
        "practitioner": "入门手册口径。用来想「要不要组这支队伍」，不是某一家的入职培训。",
    },
    "marty-cagan-fde": {
        "enterprise": "从产品发现谈 FDE。企业若把驻场只当交付外包，会漏掉发现问题和定义范围。",
        "practitioner": "产品人视角。用来对照自己是在发现，还是只在客户现场赶工。",
    },
    "a16z-fde-fellowship": {
        "happened": "a16z 公开 FDE Fellowship 页，说明他们怎么培养现场部署人才。无事件日则只收录。",
        "enterprise": "培养项目页，不是某家客户上线。不能当成编制已经进买方组织。",
        "practitioner": "看他们如何定义前线 FDE 和部门负责人的搭配。申请条件要回原页。",
    },
    "a16z-services-led": {
        "enterprise": "把 FDE 放进「用服务换增长、用毛利换护城河」的叙事。这是投资人框架，不是客户结果。",
        "practitioner": "理解为什么这个角色被写成增长杠杆。职业路径仍取决于你进的是哪家现场。",
    },
    "openai-frontier-product": {
        "happened": "OpenAI Frontier 产品页，把部署现场能力写成命名产品线。可能没有单独事件日。",
        "enterprise": "产品页上的规模数字（如资本开支）要回原文核对口径，不能当某一单客户 KPI。",
        "practitioner": "页上写与 Forward Deployed Engineers 结对。职责以产品页为准，不是招聘承诺。",
    },
    "reddit-levels": {
        "happened": "r/levels_fyi 讨论什么是 Forward Deployed Engineer。公开帖，无可靠发布日则不进窗口。",
        "enterprise": "不能当组织宣布或客户结果。最多说明这个头衔已经进入职业讨论。",
        "practitioner": "帖里把 FDE 写成部署项目上的「CTO」：写生产代码并 own 结果。匿名讨论，不当录用标准。",
    },
    "reddit-openings": {
        "happened": "r/ExperiencedDevs 讨论到处可见的 FDE 岗位，以及典型背景。",
        "enterprise": "岗位变多不等于编制已经落地。这是从业者见闻，不是官方扩编。",
        "practitioner": "匿名总结常见画像（数年 SWE、能进陌生代码库）。用来对照，不是准入门槛。",
    },
    "reddit-role": {
        "happened": "r/ExperiencedDevs 讨论 Forward Deployed Engineer 这个岗位实际在干什么。",
        "enterprise": "一线见闻，不是官方组织说明。",
        "practitioner": "有人写团队几乎都是前 SWE，持续为客户写定制代码、用客户 API 搭 demo。一帖一条，不当行业调查。",
    },
    "reddit-scam": {
        "happened": "r/cscareerquestions 有帖把 Forward Deployed Engineer 岗位说成像坑。公开讨论，不是调查结论。",
        "enterprise": "头衔争议进入职业论坛。不能据此否定或肯定某家的编制。",
        "practitioner": "用来听对出差、售前伪装、头衔通胀的抱怨。回官方 JD 和现场范围，不要只看帖标题。",
    },
    "cohere-home": {
        "happened": "Cohere 站点首页。证据弱，只作入口，不当进展头条。",
        "enterprise": "营销壳页，没有可核对的组织宣布或客户结果。",
        "practitioner": "不要把首页当 FDE 工作说明。能力建设文在博客那条。",
    },
}

COPY_BY_NEEDLE = (
    ("subset-tech-talent-supply-crunch-watch-out", EVENT_COPY["washtech-fde-talent-2026-09-01"]),
    (
        "fde-exit-options-career-trajectory",
        {
            "happened": "FDEInterviews 写 FDE 做完一轮现场之后常见的退出路径，不是某家客户的交付证明。",
            "why": WHY_BY_KIND["methodology"],
            "enterprise": "如果把 FDE 当长期编制，要考虑这批人两三年后往产品、核心工程还是下一家现场走。",
            "practitioner": "用来判断这条职业路径怎么转，不用来准备某一场面试题。",
        },
    ),
    (
        "negotiating-forward-deployed-engineer-offer",
        {
            "happened": "FDEInterviews 写怎么谈 FDE offer：范围、出差、驻场周期和职级往往比底薪更能决定这份工作。",
            "why": WHY_BY_KIND["methodology"],
            "enterprise": "编制报价要写清驻场深度和交接，否则薪资数字对不上现场成本。",
            "practitioner": "谈 offer 时把出差比例、客户现场天数和「谁拥有代码」问清楚，不要只看 title。",
        },
    ),
    (
        "fde-war-stories-nine-patterns",
        {
            "happened": "FDEInterviews 把现场反复出现的九种套路写成可对照的模式，不是某一单的战报。",
            "why": WHY_BY_KIND["methodology"],
            "enterprise": "可当风险清单：范围漂、数据进不去、交接失败，都会在公开模式里重复。",
            "practitioner": "用来识别自己是不是又走进同一类现场坑，不是 KPI 证明。",
        },
    ),
    (
        "what-does-a-forward-deployed-engineer-do",
        {
            "happened": "FDEInterviews 写 FDE 实际在做什么：出差比例常见 30–50%，编码与客户对话来回切换。",
            "why": WHY_BY_KIND["methodology"],
            "enterprise": "驻场密度会进成本。只按办公室工程师编制估算现场，会低估沟通和出差。",
            "practitioner": "做得好的人把客户对话当成工程的一部分。出差幅度很宽，入职前要问清楚。",
        },
    ),
    (
        "what-is-a-forward-deployed-engineer",
        {
            "happened": "FDEInterviews 定义 FDE：通常说法是半个工程师、半个顾问、完完全全的所有者。定义页不是客户交付。",
            "why": WHY_BY_KIND["methodology"],
            "enterprise": "文中引用的招聘量增长用来说明角色变热，不是你这家公司必须建编制的证明。",
            "practitioner": "不同于售前，FDE 一周大部分时间在写生产代码；不同于核心产品，人要在客户现场做完。",
        },
    ),
    (
        "what-it-means-to-be-a-forward-deployed",
        {
            "happened": "The FDE Pod 用 Rippling 的编制扩张讲 FDE 如何变成增长引擎：从作者 1 人到 20 人以上。",
            "why": WHY_BY_KIND["methodology"],
            "enterprise": "编制扩张是一家公司的故事。可当「现场能否变成增长杠杆」的对照，不是行业均值。",
            "practitioner": "一个 FDE 戴三顶帽子：顾问、产品经理、工程师。缺任何一顶都会在现场露馅。",
        },
    ),
    (
        "hire-forward-deployed-engineers",
        {
            "happened": "FDE Academy 写怎么招 FDE：Python 与 SQL、把 ML/LLM 系统送上线的经验。这是招聘指南，不是官方 JD。",
            "why": WHY_BY_KIND["methodology"],
            "enterprise": "可当筛选清单草稿，不能代替你自己的职级体系和现场范围。",
            "practitioner": "技术门槛写得很具体，用来对照自己缺哪一块。来源是课程站，不是雇主。",
        },
    ),
    (
        "the-pulse-forward-deployed-engineering",
        {
            "happened": "Pragmatic Engineer Pulse 记录 Forward Deployed Engineering 再次升温，以及哪些公司在招。",
            "why": WHY_BY_KIND["named_essay"],
            "enterprise": "这是行业通讯，不是组织宣布。可当「岗位变热」的旁证，不能当成某家已经建好编制。",
            "practitioner": "看哪些公司被点名在招。具体要求仍要回官方 JD，通讯不是投递清单。",
        },
    ),
    (
        "insights-for-enterprise-ai-builders",
        {
            "happened": "a16z 写从 Demo 到成交：有价值的企业 AI 必须理解客户上下文，模型开箱并不具备。",
            "why": WHY_BY_KIND["named_essay"],
            "enterprise": "投资人观察：要把工程和实施资源投进客户现场。这不是某一单 KPI，也不是官方编制宣布。",
            "practitioner": "解释为什么现场要懂企业逻辑。用来理解角色存在的原因，不是入职手册。",
        },
    ),
    (
        "8-tactical-insights-from-current-former-forward",
        {
            "happened": "LinkedIn 圆桌：现任和前任 Palantir 等处 FDE 的 8 条经验。个人文，不标成雇主官方。",
            "why": WHY_BY_KIND["methodology"],
            "enterprise": "强调 FDE 应直接贡献产品，而不是孤立地给客户救火。可当组织设计对照，不是客户结果。",
            "practitioner": "最成功的组里主力是能写代码的现场的人。用来对照自己是不是「业务里的 coding entity」。",
        },
    ),
    (
        "openai.com/index/replit",
        {
            "happened": "OpenAI 客户页写 Replit 与 GPT 的交付故事。本条没有能进窗口的发布日，只作收录。",
            "why": WHY_BY_KIND["dated_case_study"],
            "enterprise": "页面是产品故事。没有独立发布日则不上时间轴；数字要回原文。",
            "practitioner": "原文没有写 Forward Deployed 头衔。可核的是客户侧叙述，不是编制样板。",
        },
    ),
    (
        "professional-network-ai-onboarding",
        {
            "happened": "Moveworks 该 URL 标题是职业网络 onboarding，正文对上的是已收录的另一客户故事。CMS 错页，不当第二条部署。",
            "why": WHY_BY_KIND["dated_case_study"],
            "enterprise": "不要引用这个 URL 的 KPI。去已核对的客户页。",
            "practitioner": "原文没有写 Forward Deployed 头衔。这条不能当现场样本。",
        },
    ),
    (
        "fde.academy/",
        {
            "happened": "FDE Academy 课程首页。证据弱，不是一篇方法文，也不是官方 JD。",
            "why": WHY_BY_KIND["methodology"],
            "enterprise": "课程站壳页，不能当编制或交付证明。",
            "practitioner": "若要看怎么招，用站内那篇 How to Hire，不要把首页当工作说明。",
        },
    ),
)

DEPLOY_COPY = {
    "devin.ai/customers/comun": {
        "happened": "Común 公开 13 人工程组用 Devin 把后端 PR 从每周约 50 提到约 170 的交付故事。",
        "enterprise": "四周内后端产出约 3 倍；页面还写新项目估计 2–3 倍加速。口径是厂商客户故事里的实测叙述，不是第三方审计。",
        "practitioner": DEPLOY_NO_FDE,
    },
    "devin.ai/customers/rohlikgroup": {
        "happened": "Rohlik Group 公开用 Devin 提高工程吞吐、并加快仓库自动化对接的交付故事。",
        "enterprise": "页面写工程吞吐约 2 倍，AutoStore 对接 8 个月（对照行业常见 2–3 年）。这是厂商叙述，要回原文看口径。",
        "practitioner": DEPLOY_NO_FDE,
    },
    "devin.ai/customers/compiledhealth": {
        "happened": "Compiled Health 公开四个人的团队用 Devin 把临床指南编译成可检查软件的交付故事。",
        "enterprise": "两周约 430 个计量工程小时、约 17 美元/小时；一个 sprint 17 天大约等于此前九周的量。口径在厂商页上。",
        "practitioner": DEPLOY_NO_FDE,
    },
    "devin.ai/customers/ebanx": {
        "happened": "EBANX 公开用 Devin 做支付机构对接和平台现代化的交付故事。",
        "enterprise": "核心支付平台约 92% 已合并 PR 由 Devin 创建；一条原估六周的工作流约 12 小时完成。页面另有「150 名工程师产出」的注脚，要回原文。",
        "practitioner": DEPLOY_NO_FDE,
    },
    "devin.ai/customers/geaerospace": {
        "happened": "GE Aerospace 公开在航司软件上用 Devin 补工程产能的交付故事。",
        "enterprise": "页面写过去三个月用户故事产出大约 2 倍，对象是此前产能受限的较小团队。",
        "practitioner": DEPLOY_NO_FDE,
    },
    "devin.ai/customers/ahead": {
        "happened": "AHEAD 先把 Devin 用在自己的工程组织，再把手册卖给客户。",
        "enterprise": "8 个生产用例相对手工基线 8x–40x；三条 API 一天完成（对照约四周）。这是厂商客户故事。",
        "practitioner": DEPLOY_NO_FDE,
    },
    "devin.ai/customers/hippo": {
        "happened": "Hippo 的 Devin 客户页讲保险软件在五十州的构建与测试，但没有给出 Hippo 自己的工时或周期数字。",
        "enterprise": "页面没有 Hippo 实测工时或缺陷周期。出现的约 90% 是 McKinsey 行业估计，不能当这家客户的 KPI。",
        "practitioner": DEPLOY_NO_FDE,
    },
    "writer.com/blog/vanguard-customer-story": {
        "happened": "Vanguard 公开用 Writer 重做营销邮件工作流的交付故事：基线是 37 步、16 次人工交接。",
        "enterprise": "早期小组两天做出过去三周的量。页面也写了尚未改变工作方式的桌面用户数，不要只读加速比。",
        "practitioner": DEPLOY_NO_FDE,
    },
    "writer.com/blog/beauty-pie-customer-story": {
        "happened": "Beauty Pie 公开用 Writer 让业务人员自建 playbook 的交付故事。",
        "enterprise": "248 个 playbook、38 个活动触发器覆盖五个部门；月活用户增长 135%。口径是厂商客户故事。",
        "practitioner": DEPLOY_NO_FDE,
    },
    "factory.ai/case-studies/comarch": {
        "happened": "Comarch 公开用 Factory 做内部软件工厂、把迁移和现代化收成 Mission 的交付故事。",
        "enterprise": "工程师效率约 40%、团队速度约 30–34%；XSLT 现代化从估 1 万人天收到 45 天。这是厂商叙述。",
        "practitioner": DEPLOY_NO_FDE,
    },
    "factory.ai/case-studies/you-com": {
        "happened": "You.com 公开用 Factory/Droid 诊断跨栈 MCP 超时的交付故事。",
        "enterprise": "原本可能要数天才能复现的超时，当天下午在隔离环境里定位到客户端原因。没有给出全公司吞吐 KPI。",
        "practitioner": DEPLOY_NO_FDE,
    },
    "decagon.ai/case-studies/ng-cash": {
        "happened": "NG.CASH 公开用 Decagon agent 做客服自动化的交付故事。",
        "enterprise": "自主解决率从 13% 到 70%；免雇 35 名以上额外 agent；账户到 600 万未扩支持团队。口径是厂商客户故事。",
        "practitioner": DEPLOY_NO_FDE,
    },
    "decagon.ai/case-studies/fourthwall": {
        "happened": "Fourthwall 公开用 Decagon 做客服的交付故事：创作者社区、知识库加历史工单。",
        "enterprise": "70% 以上工单无需人眼解决。CSAT 与解决率是页面叙述，要回原文看口径。",
        "practitioner": "Decagon 团队快速处理功能请求（协作式）。原文未明确 FDE 职衔。",
    },
}


def job_four(org: str, role: str) -> dict:
    org = (org or "该公司").strip() or "该公司"
    role = (role or "FDE").strip() or "FDE"
    return {
        "happened": f"{org} 在官方招聘板上新挂出「{role}」。这是岗位发布，不是组织宣布。原文标题见本页。",
        "why": WHY_BY_KIND["job_posting"],
        "enterprise": f"只能读成 {org} 仍在招这个方向的现场编制。单岗不能当成交付结果，也不能当成已经扩编落地。",
        "practitioner": f"标题能看出方向和职级（{role}）。具体职责以原文摘录为准。有人在招，不证明录用标准已经改写。",
    }


def census_four(org: str, n: int) -> dict:
    org = (org or "该公司").strip() or "该公司"
    return {
        "happened": f"{org} 本轮公开板上能识别出 {n} 个 FDE 相关岗位。这是一篇普查，不是 {n} 条事件。",
        "why": WHY_BY_KIND["hiring_census"],
        "enterprise": "列表长度不能读成需求已兑现，也不能当成组织宣布。",
        "practitioner": "看供给和方向分布，不要把招聘板索引当投递清单。",
    }


def pack_from_needle(url: str) -> dict:
    blob = (url or "").lower()
    for needle, pack in COPY_BY_NEEDLE:
        if needle in blob:
            return dict(pack)
    for needle, pack in DEPLOY_COPY.items():
        if needle.lower() in blob:
            return dict(pack)
    return {}


def editorial_pack(seed_id: str, info_kind: str, title: str, url: str = "", org: str = "", role: str = "") -> dict:
    pack = dict(EVENT_COPY.get(seed_id) or {})
    pack.update({k: v for k, v in pack_from_needle(url).items() if v})
    if info_kind == "job_posting" and not pack.get("enterprise"):
        pack.update(job_four(org, role or title))
    if info_kind == "hiring_census" and not pack.get("enterprise"):
        pack.update(census_four(org, 0))
    happened = pack.get("happened") or HAPPENED_ZH.get(seed_id) or ((title or "") + "。")
    why = pack.get("why") or WHY_BY_KIND.get(info_kind) or "这是动态层收录的公开材料，需回到原文核对。"
    return {
        "happened": happened,
        "why": why,
        "enterprise": pack.get("enterprise") or None,
        "practitioner": pack.get("practitioner") or None,
    }

KIND_FROM_DOC = {
    "case_study": "dated_case_study",
    "opinion": "named_essay",
    "methodology": "methodology",
    "job_posting": "job_posting",
    "discussion": "discussion",
}

OPENAI_COMPANY = (
    "openai.com/index/openai-launches-the-deployment-company",
    "openai.com/index/introducing-openai-frontier",
    "openai.com/zh-hans-cn/index/introducing-openai-frontier",
)

SKIP_HOSTS_FETCH = set()  # filled if we decide a host is blocked mid-run


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def norm_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    text = text.split("#", 1)[0]
    try:
        parts = urllib.parse.urlsplit(text)
        path = urllib.parse.unquote(parts.path or "")
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        host = (parts.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return urllib.parse.urlunsplit((parts.scheme.lower(), host, path, parts.query, ""))
    except ValueError:
        return text.rstrip("/").lower()


def host_of(url: str) -> str:
    try:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def slugify(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    host = (parts.netloc or "").replace("www.", "")
    path = (parts.path or "").strip("/").replace("/", "__") or "home"
    path = re.sub(r"[^A-Za-z0-9_.%-]", "_", path)[:110]
    qs = urllib.parse.parse_qs(parts.query or "")
    extra = []
    for key in ("gh_jid", "jid", "v", "p", "id"):
        vals = qs.get(key) or []
        if vals:
            extra.append(re.sub(r"[^A-Za-z0-9_.%-]", "_", vals[0])[:48])
    if extra:
        path = path + "__" + "__".join(extra)
    return f"{host}__{path}"


def valid_day(value) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            date.fromisoformat(text)
        except ValueError:
            return ""
        if text < "1990-01-01" or text > "2027-12-31":
            return ""
        return text
    return ""


def day_from_any(value) -> str:
    text = str(value or "").strip()
    full = valid_day(text[:10]) if len(text) >= 10 else ""
    if full:
        return full
    m = DAY_RE.search(text)
    if m:
        return valid_day(m.group(1))
    m = EN_DATE_RE.search(text)
    if m:
        month = EN_MONTH[m.group(1).lower()]
        return valid_day(f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(2)):02d}")
    try:
        parsed = parsedate_to_datetime(text)
        if parsed:
            return parsed.date().isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    return ""


def hint_day(hint: str) -> str:
    """Only accept a complete YYYY-MM-DD hint as an axis candidate."""
    return valid_day((hint or "").strip())


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def apply_schema(db: sqlite3.Connection) -> None:
    db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    db.commit()


def seed_catalog(db: sqlite3.Connection, catalog: dict) -> None:
    for kind in catalog.get("info_kinds") or []:
        db.execute(
            """INSERT INTO world_info_kinds(id, lane, name_zh, name_en, accept_note, reject_note)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 lane=excluded.lane, name_zh=excluded.name_zh, name_en=excluded.name_en,
                 accept_note=excluded.accept_note, reject_note=excluded.reject_note""",
            (
                kind["id"],
                kind["lane"],
                kind.get("zh") or kind["id"],
                kind.get("en"),
                kind.get("accept"),
                kind.get("reject"),
            ),
        )
    for ent in catalog.get("entities") or []:
        db.execute(
            """INSERT INTO world_entities(slug, kind, name, host, notes)
               VALUES(?,?,?,?,?)
               ON CONFLICT(slug) DO UPDATE SET
                 kind=excluded.kind, name=excluded.name, host=excluded.host, notes=excluded.notes""",
            (ent["slug"], ent["kind"], ent["name"], ent.get("host"), None),
        )
    def put_source(row: tuple) -> None:
        try:
            db.execute(
                """INSERT INTO world_sources(id, role, url, host, lane, info_kind, fetch_mode, status, priority, entity_slug, date_hint, notes)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     url=excluded.url, host=excluded.host, lane=excluded.lane, info_kind=excluded.info_kind,
                     fetch_mode=excluded.fetch_mode, status=excluded.status, priority=excluded.priority,
                     entity_slug=excluded.entity_slug, date_hint=excluded.date_hint, notes=excluded.notes""",
                row,
            )
        except sqlite3.IntegrityError:
            # url is unique; a feed and a seed may share one page
            db.execute(
                """UPDATE world_sources SET lane=COALESCE(?, lane), info_kind=COALESCE(?, info_kind),
                   entity_slug=COALESCE(?, entity_slug), date_hint=COALESCE(?, date_hint),
                   notes=COALESCE(?, notes) WHERE url=?""",
                (row[4], row[5], row[9], row[10], row[11], row[2]),
            )

    for feed in catalog.get("feeds") or []:
        info_kind = (feed.get("info_kinds") or [None])[0]
        put_source(
            (
                feed["id"],
                "feed",
                feed["url"],
                feed.get("host") or host_of(feed["url"]),
                feed.get("lane"),
                info_kind,
                feed.get("fetch_mode") or "list_index",
                feed.get("status") or "watch",
                int(feed.get("priority") or 3),
                feed.get("entity_slug"),
                feed.get("date_hint"),
                feed.get("notes"),
            )
        )
    for seed in catalog.get("seeds") or []:
        put_source(
            (
                seed["id"],
                "seed",
                seed["url"],
                host_of(seed["url"]),
                seed.get("lane"),
                seed.get("info_kind"),
                "youtube" if "youtube.com" in seed["url"] else "single_page",
                seed.get("status") or "missing",
                int(seed.get("priority") or 3),
                seed.get("entity_slug"),
                seed.get("date_hint"),
                seed.get("notes"),
            )
        )
    for exc in catalog.get("exclude") or []:
        db.execute(
            """INSERT INTO world_sources(id, role, url, host, lane, info_kind, fetch_mode, status, priority, notes)
               VALUES(?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET url=excluded.url, notes=excluded.notes, status=excluded.status""",
            (
                exc["id"],
                "exclude",
                exc["url"],
                host_of(exc["url"]),
                None,
                None,
                "manual",
                "skip",
                9,
                exc.get("reason"),
            ),
        )
    db.commit()


def load_dates_json() -> dict:
    if not DATES_JSON.is_file():
        return {}
    data = json.loads(DATES_JSON.read_text(encoding="utf-8"))
    idx = {}
    for key, rec in (data.get("by_url") or {}).items():
        idx[norm_url(key)] = rec
        idx[norm_url(key.rstrip("/"))] = rec
    return idx


def meta_content(html: str, prop: str) -> str:
    patterns = (
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(prop)}["\']',
    )
    for pat in patterns:
        m = re.search(pat, html, re.I)
        if m:
            return H.unescape(m.group(1)).strip()
    return ""


def jsonld_dates(html: str) -> dict:
    out = {"published": "", "modified": ""}
    for blob in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I | re.S):
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            if "@graph" in item and isinstance(item["@graph"], list):
                stack.extend(item["@graph"])
            if not out["published"]:
                out["published"] = day_from_any(item.get("datePublished") or item.get("dateCreated"))
            if not out["modified"]:
                out["modified"] = day_from_any(item.get("dateModified"))
    return out


def nextjs_dates(html: str) -> dict:
    """OpenAI (and similar) ship publicationDate in an escaped RSC payload."""
    blob = html.replace('\\"', '"')
    published = ""
    m = re.search(
        r'"pageType"\s*:\s*"Article".{0,800}?"publicationDate(?:Text)?"\s*:\s*"([^"]+)"',
        blob,
        re.S,
    )
    if m:
        published = day_from_any(m.group(1))
    if not published:
        m = re.search(r'"publicationDateText"\s*:\s*"([^"]+)"', blob)
        published = day_from_any(m.group(1) if m else "")
    if not published:
        m = re.search(r'"publicationDate"\s*:\s*"([^"]+)"', blob)
        published = day_from_any(m.group(1) if m else "")
    return {"published": published}


def unique_time_day(html: str) -> str:
    """Use <time datetime> only when the page has a single distinct day."""
    found = []
    for raw in re.findall(r"<time[^>]+datetime=[\"']([^\"']+)[\"']", html, re.I):
        day = day_from_any(raw)
        if day and day not in found:
            found.append(day)
    return found[0] if len(found) == 1 else ""


def extract_dates(html: str) -> dict:
    published = (
        day_from_any(meta_content(html, "article:published_time"))
        or day_from_any(meta_content(html, "og:published_time"))
        or day_from_any(meta_content(html, "pubdate"))
        or day_from_any(meta_content(html, "publish-date"))
        or day_from_any(meta_content(html, "date"))
    )
    modified = (
        day_from_any(meta_content(html, "article:modified_time"))
        or day_from_any(meta_content(html, "og:updated_time"))
        or day_from_any(meta_content(html, "last-modified"))
    )
    ld = jsonld_dates(html)
    nx = nextjs_dates(html)
    published = published or ld.get("published") or nx.get("published") or ""
    modified = modified or ld.get("modified") or ""
    if not published:
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html.replace('\\"', '"'))
        published = day_from_any(m.group(1) if m else "")
    if not modified:
        m = re.search(r'"dateModified"\s*:\s*"([^"]+)"', html.replace('\\"', '"'))
        modified = day_from_any(m.group(1) if m else "")
    # <time> is last and only if unique — related-article times must not become the event day
    if not published:
        published = unique_time_day(html)
    return {"published": published, "modified": modified}


def extract_title(html: str) -> str:
    title = meta_content(html, "og:title") or meta_content(html, "twitter:title")
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    title = H.unescape(title).split("|")[0].split("—")[0].split("–")[0].strip()
    return title[:180]


def html_to_text(raw: str) -> str:
    t = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
    t = re.sub(r"<style[\s\S]*?</style>", " ", t, flags=re.I)
    t = re.sub(r"<noscript[\s\S]*?</noscript>", " ", t, flags=re.I)
    t = re.sub(r"</(p|div|h[1-6]|li|section|article|br)>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = H.unescape(t)
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n\n", t)
    return t.strip()


def fetch_bytes(url: str, tries: int = 3, timeout: int = 45):
    req_url = url
    if "reddit.com" in url and not url.endswith(".json"):
        req_url = url.rstrip("/") + ".json"
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(req_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                final = resp.geturl()
                ctype = resp.headers.get("Content-Type", "")
            return body, final, ctype, None
        except urllib.error.HTTPError as exc:
            last = str(exc.code)
            if exc.code in (401, 403, 404, 410, 429):
                return None, url, "", last
            time.sleep(1.4 * (i + 1))
        except Exception as exc:
            last = str(exc)[:80]
            time.sleep(1.4 * (i + 1))
    return None, url, "", last or "ERR"


def save_raw(url: str, body: bytes, ctype: str) -> str:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".json" if "json" in (ctype or "") or url.endswith(".json") else ".html"
    if url.lower().endswith(".pdf") or "pdf" in (ctype or ""):
        ext = ".pdf"
    path = RAW_DIR / (slugify(url) + ext)
    path.write_bytes(body)
    return str(path.relative_to(HERE))


def fetch_page(url: str) -> dict:
    host = host_of(url)
    if host in SKIP_HOSTS_FETCH:
        return {"url": url, "status": "blocked", "html": "", "raw_file": ""}
    body, final, ctype, err = fetch_bytes(url)
    if not body:
        if err in ("401", "403") and host:
            SKIP_HOSTS_FETCH.add(host)
        return {"url": url, "status": err or "ERR", "html": "", "raw_file": "", "final": final}
    raw_file = save_raw(url, body, ctype)
    text = ""
    if "pdf" not in (ctype or "") and not url.lower().endswith(".pdf"):
        try:
            text = body.decode("utf-8", errors="replace")
        except Exception:
            text = body.decode("latin-1", errors="replace")
    return {
        "url": url,
        "final": final,
        "status": "ok",
        "html": text,
        "ctype": ctype,
        "raw_file": raw_file,
    }


def youtube_id(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    if parts.path.startswith("/watch"):
        return urllib.parse.parse_qs(parts.query).get("v", [""])[0]
    if parts.netloc.endswith("youtu.be"):
        return parts.path.strip("/")
    return ""


def fetch_youtube(url: str) -> dict:
    vid = youtube_id(url)
    title = ""
    published = ""
    oembed = f"https://www.youtube.com/oembed?url={urllib.parse.quote(url, safe='')}&format=json"
    body, _, ctype, err = fetch_bytes(oembed, tries=2, timeout=20)
    if body:
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
            title = (data.get("title") or "").strip()
        except json.JSONDecodeError:
            pass
    watch = fetch_page(url if "watch" in url else f"https://www.youtube.com/watch?v={vid}")
    html = watch.get("html") or ""
    dates = extract_dates(html) if html else {}
    published = dates.get("published") or ""
    if not published:
        m = re.search(r'"publishDate"\s*:\s*"([^"]+)"', html)
        published = day_from_any(m.group(1) if m else "")
    if not published:
        m = re.search(r'"uploadDate"\s*:\s*"([^"]+)"', html)
        published = day_from_any(m.group(1) if m else "")
    if not title:
        title = extract_title(html)
    return {
        "url": url,
        "status": "ok" if (title or published or watch.get("status") == "ok") else (watch.get("status") or err or "ERR"),
        "title": title,
        "published": published,
        "modified": dates.get("modified") or "",
        "html": html,
        "raw_file": watch.get("raw_file") or "",
    }


def job_api_url(url: str) -> str:
    m = re.search(r"[?&]gh_jid=(\d+)", url or "")
    if m and "databricks" in (url or "").lower():
        return f"https://boards-api.greenhouse.io/v1/boards/databricks/jobs/{m.group(1)}"
    m = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url or "")
    if m:
        return f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}"
    m = re.search(r"jobs\.lever\.co/([^/]+)/([0-9a-f-]+)", url or "", re.I)
    if m:
        return f"https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}"
    return ""


def job_html_page(title: str, content: str, source_url: str) -> bytes:
    body = H.unescape(H.unescape(content or ""))
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'/>"
        f"<title>{H.escape(title or '')}</title></head><body>"
        f"<p>Local backup of {H.escape(source_url or '')}</p>"
        f"<h1>{H.escape(title or '')}</h1>{body}</body></html>"
    ).encode("utf-8")


def capture_missing_job_originals(db) -> int:
    """Bounded: only job_posting rows already on the axis, missing local raw."""
    n = 0
    rows = list(
        db.execute(
            "SELECT id, url, title FROM world_events "
            "WHERE info_kind='job_posting' AND url IS NOT NULL AND url!=''"
        )
    )
    ashby_boards: dict[str, dict] = {}
    for r in rows:
        url = r["url"]
        slug = slugify(url)
        if (RAW_DIR / (slug + ".html")).is_file() or (RAW_DIR / (slug + ".json")).is_file():
            continue
        api = job_api_url(url)
        data = None
        if api:
            body, _, _, err = fetch_bytes(api, tries=2, timeout=25)
            time.sleep(0.35)
            if not body:
                print("  miss", r["id"], err, url[:90], flush=True)
                continue
            save_raw(url, body, "application/json")
            try:
                data = json.loads(body.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                data = {}
        else:
            m = re.search(r"jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]+)", url, re.I)
            if not m:
                continue
            board, jid = m.group(1), m.group(2).lower()
            if board not in ashby_boards:
                burl = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
                body, _, _, err = fetch_bytes(burl, tries=2, timeout=25)
                time.sleep(0.4)
                if not body:
                    print("  miss ashby", board, err, flush=True)
                    ashby_boards[board] = {}
                    continue
                try:
                    ashby_boards[board] = json.loads(body.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    ashby_boards[board] = {}
            payload = ashby_boards.get(board) or {}
            job = None
            for item in payload.get("jobs") or []:
                blob = ((item.get("id") or "") + " " + (item.get("jobUrl") or "")).lower()
                if jid in blob:
                    job = item
                    break
            if not job:
                print("  miss ashby job", r["id"], jid, flush=True)
                continue
            data = job
            save_raw(url, json.dumps(job, ensure_ascii=False).encode("utf-8"), "application/json")
        title = (data.get("title") or data.get("text") or r["title"] or "") if isinstance(data, dict) else (r["title"] or "")
        content = ""
        if isinstance(data, dict):
            content = data.get("content") or data.get("descriptionPlain") or data.get("descriptionHtml") or ""
            if isinstance(content, dict):
                content = content.get("html") or content.get("plain") or ""
        (RAW_DIR / (slug + ".html")).write_bytes(job_html_page(title, str(content or ""), url))
        n += 1
        print("  saved", r["id"], (title or "")[:60], flush=True)
    return n


def fetch_ats(url: str) -> dict:
    """Greenhouse / Lever / Ashby job pages. Only keep first_published / createdAt / publishedAt."""
    html_page = fetch_page(url)
    published = ""
    title = ""
    if html_page.get("html"):
        dates = extract_dates(html_page["html"])
        published = dates.get("published") or ""
        title = extract_title(html_page["html"])
    m = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if m:
        api = f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}"
        body, _, _, err = fetch_bytes(api, tries=2, timeout=20)
        if body:
            try:
                data = json.loads(body.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                data = {}
            title = title or (data.get("title") or "")
            published = published or day_from_any(data.get("first_published") or data.get("updated_at"))
            raw = save_raw(api, body, "application/json")
            return {
                "url": url,
                "status": "ok",
                "title": title,
                "published": published,
                "modified": "",
                "raw_file": raw,
                "html": html_page.get("html") or "",
            }
    m = re.search(r"jobs\.lever\.co/([^/]+)/([0-9a-f-]+)", url, re.I)
    if m:
        api = f"https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}"
        body, _, _, err = fetch_bytes(api, tries=2, timeout=20)
        if body:
            try:
                data = json.loads(body.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                data = {}
            title = title or (data.get("text") or "")
            created = data.get("createdAt")
            if isinstance(created, (int, float)):
                published = published or datetime.fromtimestamp(created / 1000, tz=timezone.utc).date().isoformat()
            raw = save_raw(api, body, "application/json")
            return {
                "url": url,
                "status": "ok",
                "title": title,
                "published": published,
                "modified": "",
                "raw_file": raw,
                "html": html_page.get("html") or "",
            }
    m = re.search(r"jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]+)", url, re.I)
    if m:
        api = f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}"
        body, _, _, err = fetch_bytes(api, tries=2, timeout=20)
        if body:
            try:
                data = json.loads(body.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                data = {}
            want = m.group(2).lower()
            for job in data.get("jobs") or []:
                job_url = (job.get("jobUrl") or "") + " " + (job.get("id") or "")
                if want in job_url.lower() or (job.get("id") or "").lower() == want:
                    title = title or (job.get("title") or "")
                    published = published or day_from_any(job.get("publishedAt") or "")
                    break
            raw = save_raw(api, body, "application/json")
            return {
                "url": url,
                "status": "ok" if (title or published) else "ERR",
                "title": title,
                "published": published,
                "modified": "",
                "raw_file": raw,
                "html": html_page.get("html") or "",
            }
    return {
        "url": url,
        "status": html_page.get("status") or "ERR",
        "title": title,
        "published": published,
        "modified": "",
        "raw_file": html_page.get("raw_file") or "",
        "html": html_page.get("html") or "",
    }


def reddit_meta(html_or_json: str, url: str) -> dict:
    title = ""
    published = ""
    try:
        data = json.loads(html_or_json)
        post = data[0]["data"]["children"][0]["data"]
        title = post.get("title") or ""
        created = post.get("created_utc")
        if created:
            published = datetime.fromtimestamp(float(created), tz=timezone.utc).date().isoformat()
    except Exception:
        title = extract_title(html_or_json)
        published = extract_dates(html_or_json).get("published") or ""
    return {"title": title, "published": published}


def upsert_source_date(db, url, published, modified, collected, best, best_kind, case_id, raw_file):
    db.execute(
        """INSERT INTO source_dates(url, published, modified, collected, sitemap_lastmod, best, best_kind, case_id, raw_file, extracted_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(url) DO UPDATE SET
             published=COALESCE(excluded.published, source_dates.published),
             modified=COALESCE(excluded.modified, source_dates.modified),
             collected=COALESCE(excluded.collected, source_dates.collected),
             best=excluded.best, best_kind=excluded.best_kind,
             case_id=COALESCE(excluded.case_id, source_dates.case_id),
             raw_file=COALESCE(excluded.raw_file, source_dates.raw_file),
             extracted_at=excluded.extracted_at""",
        (
            url,
            published or None,
            modified or None,
            collected or None,
            None,
            best or None,
            best_kind or None,
            case_id,
            raw_file,
            now_iso(),
        ),
    )


def pick_axis(published: str, modified: str) -> tuple[str, str]:
    if published:
        return published, "published"
    if modified:
        return modified, "modified"
    return "", "collected"


def trunc(text: str, n: int = 180) -> str:
    text = " ".join(str(text or "").split()).strip()
    if "�" in text:
        return ""
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


def copy_for(seed_id: str, info_kind: str, title: str, url: str = "") -> tuple[str, str, str | None, str | None]:
    pack = editorial_pack(seed_id, info_kind, title, url=url)
    return pack["happened"], pack["why"], pack["enterprise"], pack["practitioner"]


def _is_stub_happened(text: str, title: str, title_zh: str) -> bool:
    hap = (text or "").strip()
    if not hap.endswith("。"):
        return False
    head = hap[:-1]
    return head in ((title or "").strip(), (title_zh or "").strip()) and bool(head)


def signal_for(lane: str, info_kind: str, host: str, date_kind: str) -> str:
    if info_kind in ("job_posting", "discussion", "hiring_census"):
        return "weak"
    if lane == "company" and info_kind in ("org_announcement", "product_line", "earnings_letter"):
        return "hard"
    if date_kind == "published":
        return "hard"
    return "weak"


def upsert_event(db, payload: dict) -> int:
    url = payload["url"]
    existing = db.execute("SELECT * FROM world_events WHERE url=?", (url,)).fetchone()
    if existing:
        for key in ("happened_zh", "why_zh", "enterprise_zh", "practitioner_zh", "title_zh"):
            incoming = (payload.get(key) or "").strip()
            stored = (existing[key] or "").strip()
            if not incoming and stored:
                payload[key] = stored
            elif key == "happened_zh" and stored and _is_stub_happened(
                incoming, payload.get("title") or "", payload.get("title_zh") or ""
            ):
                payload[key] = stored
    fields = (
        "url",
        "lane",
        "info_kind",
        "title",
        "title_zh",
        "day",
        "date_kind",
        "collected_on",
        "host",
        "entity_slug",
        "signal",
        "happened_zh",
        "why_zh",
        "enterprise_zh",
        "practitioner_zh",
        "evidence",
        "source_case_id",
        "ingest_note",
    )
    values = [payload.get(k) for k in fields]
    if existing:
        assignments = ", ".join(f"{k}=?" for k in fields if k != "url")
        db.execute(
            f"UPDATE world_events SET {assignments} WHERE url=?",
            [payload.get(k) for k in fields if k != "url"] + [url],
        )
        event_id = existing["id"]
    else:
        placeholders = ",".join("?" * len(fields))
        cur = db.execute(
            f"INSERT INTO world_events({','.join(fields)}) VALUES({placeholders})",
            values,
        )
        event_id = cur.lastrowid
    slug = payload.get("entity_slug")
    if slug:
        role = "author" if payload.get("lane") == "people" else "actor"
        db.execute(
            """INSERT OR IGNORE INTO world_event_entities(event_id, entity_slug, role)
               VALUES(?,?,?)""",
            (event_id, slug, role),
        )
    return event_id


def case_rows(db) -> list[sqlite3.Row]:
    sql = """
      SELECT x.id, x.source_url, x.source_title, x.doc_type, x.evidence_quality,
             x.kpi_scope, x.measured_outcome, x.product, x.quote, x.fde_role,
             x.deployment, x.productization, x.business_problem, x.hero_use_case,
             x.raw_company_text,
             cu.name AS customer, cu.named AS customer_named,
             (SELECT group_concat(c.slug, ',') FROM case_companies cc
                JOIN companies c ON c.slug=cc.company_slug
               WHERE cc.case_id=x.id AND cc.role='vendor') AS vendor_slugs,
             (SELECT group_concat(c.name, ',') FROM case_companies cc
                JOIN companies c ON c.slug=cc.company_slug
               WHERE cc.case_id=x.id AND cc.role='vendor') AS vendor_names
        FROM cases x
        LEFT JOIN customers cu ON cu.id=x.customer_id
    """
    return list(db.execute(sql))


def classify_inventory(row, seed_by_url: dict) -> tuple[str, str, str] | None:
    url = row["source_url"] or ""
    key = norm_url(url)
    seed = seed_by_url.get(key)
    if seed:
        return seed["id"], seed["lane"], seed["info_kind"]
    blob = (url + " " + (row["source_title"] or "")).lower()
    if any(needle in blob for needle in OPENAI_COMPANY):
        kind = "org_announcement" if "deployment-company" in blob else "product_line"
        return "", "company", kind
    doc = row["doc_type"] or ""
    if doc == "case_study":
        if not row["customer_named"]:
            return None
        return "", "deploy", "dated_case_study"
    if doc == "opinion":
        return "", "people", "named_essay"
    if doc == "methodology":
        return "", "method", "methodology"
    if doc == "job_posting":
        return "", "method", "job_posting"
    if doc == "discussion":
        return "", "people", "discussion"
    return None


def mapped_case_title(row) -> str:
    blob = ((row["source_url"] or "") + " " + (row["source_title"] or "")).lower()
    for needle, label in (
        ("openai.com/index/openai-launches-the-deployment-company", "OpenAI 发布 Deployment Company"),
        ("openai.com/zh-hans-cn/index/introducing-openai-frontier", "OpenAI 发布 Frontier"),
        ("openai.com/index/introducing-openai-frontier", "OpenAI 发布 Frontier"),
        ("cohere.com/blog/forward-deployed-engineers-capability-building", "Cohere：FDE 建能力，不制造依赖"),
        ("fdeinterviews.com/blog/how-forward-deployed-engineers-work", "FDE 交付生命周期"),
        ("fdeinterviews.com/blog/day-in-the-life-forward-deployed-engineer", "FDE 的一天"),
        ("fdeinterviews.com/guide/what-is-a-forward-deployed-engineer", "FDE 是什么"),
        ("fdeinterviews.com/guide/what-does-a-forward-deployed-engineer-do", "FDE 实际在做什么"),
        ("fdepod.substack.com/p/fde-101", "FDE 101：何时需要编制"),
        ("fdepod.substack.com/p/what-it-means-to-be-a-forward-deployed", "FDE 是增长引擎"),
        ("fde.academy/blog/hire-forward-deployed-engineers", "怎么招 FDE"),
        ("a16z.com/services-led-growth", "a16z：用毛利换护城河"),
        ("fourthage.substack.com/p/what-is-a-forward-deployed-engineer", "什么是 Forward Deployed Engineer"),
        ("blog.pragmaticengineer.com/the-pulse-forward-deployed-engineering-heats-up-again", "Pragmatic Engineer：FDE 再次升温"),
        ("newsletter.pragmaticengineer.com/p/forward-deployed-engineers", "Pragmatic Engineer：FDE 为何抢手"),
        ("openai.com/careers/forward-deployed-engineer", "OpenAI 招聘 FDE"),
    ):
        if needle in blob:
            return label
    if row["customer_named"] and row["customer"]:
        return str(row["customer"]).strip()
    raw = (row["source_title"] or "").split("|")[0].strip()
    return trunc(raw, 44) or host_of(row["source_url"] or "") or "未命名来源"


def migrate_inventory(db, catalog, dates_idx) -> dict:
    seed_by_url = {norm_url(s["url"]): s for s in catalog.get("seeds") or []}
    stats = {"migrated": 0, "skipped_no_lane": 0, "skipped_index": 0, "axis": 0, "collected_only": 0}
    seen_urls = set()
    for row in case_rows(db):
        url = row["source_url"] or ""
        if not url:
            continue
        key = norm_url(url)
        if key in seen_urls:
            continue
        classified = classify_inventory(row, seed_by_url)
        if not classified:
            stats["skipped_no_lane"] += 1
            continue
        seed_id, lane, info_kind = classified
        rec = dates_idx.get(key) or dates_idx.get(norm_url(url.rstrip("/"))) or {}
        published = valid_day(rec.get("published"))
        modified = valid_day(rec.get("modified"))
        # sitemap lastmod never becomes axis day
        day, date_kind = pick_axis(published, modified)
        if not day:
            hint = hint_day((seed_by_url.get(key) or {}).get("date_hint") or "")
            if hint:
                day, date_kind = hint, "published"
            else:
                date_kind = "collected"
        seen_urls.add(key)
        title = TITLE_ZH.get(seed_id) or mapped_case_title(row)
        happened, why, enterprise, practitioner = copy_for(seed_id, info_kind, title, url)
        if not enterprise:
            outcome = row["measured_outcome"] or row["deployment"] or ""
            enterprise = trunc(outcome, 180) or None
        if not practitioner:
            practitioner = trunc(row["fde_role"] or "", 180) or (DEPLOY_NO_FDE if lane == "deploy" else None)
        if info_kind == "dated_case_study":
            happened = trunc(row["measured_outcome"] or row["hero_use_case"] or row["business_problem"] or title, 160)
        entity = (seed_by_url.get(key) or {}).get("entity_slug")
        if not entity and lane == "deploy":
            slugs = [s for s in (row["vendor_slugs"] or "").split(",") if s]
            names = [s for s in (row["vendor_names"] or "").split(",") if s]
            if slugs:
                entity = ensure_entity(db, slugs[0], names[0] if names else slugs[0], "org", host_of(url))
        upsert_source_date(
            db,
            url,
            published,
            modified,
            COLLECTED_ON,
            day or COLLECTED_ON,
            date_kind if day else "collected",
            row["id"],
            rec.get("raw_file"),
        )
        upsert_event(
            db,
            {
                "url": url,
                "lane": lane,
                "info_kind": info_kind,
                "title": (row["source_title"] or title)[:240],
                "title_zh": title,
                "day": day or None,
                "date_kind": date_kind,
                "collected_on": COLLECTED_ON,
                "host": host_of(url),
                "entity_slug": entity if entity_exists(db, entity) else None,
                "signal": signal_for(lane, info_kind, host_of(url), date_kind),
                "happened_zh": happened,
                "why_zh": why,
                "enterprise_zh": enterprise,
                "practitioner_zh": practitioner,
                "evidence": row["evidence_quality"],
                "source_case_id": row["id"],
                "ingest_note": f"migrated from cases id={row['id']} seed={seed_id or '-'}",
            },
        )
        stats["migrated"] += 1
        if day:
            stats["axis"] += 1
        else:
            stats["collected_only"] += 1
    db.commit()
    return stats


def entity_exists(db, slug) -> bool:
    if not slug:
        return False
    return db.execute("SELECT 1 FROM world_entities WHERE slug=?", (slug,)).fetchone() is not None


def ensure_entity(db, slug: str, name: str, kind: str = "org", host: str = "") -> str | None:
    if not slug or slug in ("unknown", "anonymous", "unknown-anonymous", "other"):
        return None
    if not entity_exists(db, slug):
        db.execute(
            "INSERT OR IGNORE INTO world_entities(slug, kind, name, host) VALUES(?,?,?,?)",
            (slug, kind, name or slug, host or None),
        )
    return slug


def fold_locale_mirrors(db) -> int:
    """Keep one OpenAI Frontier event; drop zh locale duplicate if both exist."""
    dropped = 0
    zh = list(db.execute("SELECT id, url FROM world_events WHERE url LIKE '%openai.com/zh-%'"))
    for row in zh:
        db.execute("DELETE FROM world_events WHERE id=?", (row["id"],))
        dropped += 1
    # title+day+lane duplicates: keep the lowest id
    rows = list(db.execute("SELECT id, title_zh, day, lane FROM world_events ORDER BY id"))
    seen = set()
    for row in rows:
        key = (row["title_zh"], row["day"], row["lane"])
        if key in seen:
            db.execute("DELETE FROM world_events WHERE id=?", (row["id"],))
            dropped += 1
        else:
            seen.add(key)
    db.commit()
    return dropped


def fetch_missing(db, catalog) -> dict:
    stats = {"ok": 0, "blocked": 0, "err": 0, "axis": 0, "collected": 0, "details": []}
    seeds = sorted(
        [s for s in catalog.get("seeds") or [] if s.get("status") == "missing"],
        key=lambda s: (int(s.get("priority") or 9), s["id"]),
    )
    for seed in seeds:
        url = seed["url"]
        host = host_of(url)
        print(f"  fetch {seed['id']}  {url}", flush=True)
        if "linkedin.com" in host:
            page = {"status": "blocked", "html": "", "title": "", "published": "", "modified": "", "raw_file": ""}
        elif "youtube.com" in host or "youtu.be" in host:
            page = fetch_youtube(url)
        elif "greenhouse.io" in host or "jobs.lever.co" in host or "ashbyhq.com" in host:
            page = fetch_ats(url)
        else:
            page = fetch_page(url)
            html = page.get("html") or ""
            dates = extract_dates(html) if html else {}
            title = extract_title(html) if html else ""
            if "reddit.com" in host and html:
                meta = reddit_meta(html, url)
                title = meta["title"] or title
                dates["published"] = meta["published"] or dates.get("published")
            page.update(
                {
                    "title": title,
                    "published": dates.get("published") or "",
                    "modified": dates.get("modified") or "",
                }
            )
        time.sleep(0.7)

        published = valid_day(page.get("published"))
        modified = valid_day(page.get("modified"))
        hint = hint_day(seed.get("date_hint") or "")
        if not published and hint:
            published = hint
        day, date_kind = pick_axis(published, modified)
        status = page.get("status") or "ERR"
        new_status = "in_db"
        if status in ("401", "403", "blocked"):
            new_status = "blocked"
            stats["blocked"] += 1
        elif status not in ("ok",) and not day:
            new_status = "missing"
            stats["err"] += 1
        else:
            stats["ok"] += 1

        title_zh = TITLE_ZH.get(seed["id"]) or trunc(page.get("title") or seed["id"], 44)
        happened, why, enterprise, practitioner = copy_for(
            seed["id"], seed["info_kind"], title_zh, url
        )
        note = f"fetch status={status} raw={page.get('raw_file') or '-'}"
        if new_status == "blocked" and not day:
            # still store as collected so the seed is not silently lost
            date_kind = "collected"
        upsert_source_date(
            db,
            url,
            published,
            modified,
            COLLECTED_ON,
            day or COLLECTED_ON,
            date_kind if day else "collected",
            None,
            page.get("raw_file"),
        )
        upsert_event(
            db,
            {
                "url": url,
                "lane": seed["lane"],
                "info_kind": seed["info_kind"],
                "title": trunc(page.get("title") or title_zh, 240),
                "title_zh": title_zh,
                "day": day or None,
                "date_kind": date_kind if day else "collected",
                "collected_on": COLLECTED_ON,
                "host": host,
                "entity_slug": seed.get("entity_slug") if entity_exists(db, seed.get("entity_slug")) else None,
                "signal": signal_for(seed["lane"], seed["info_kind"], host, date_kind if day else "collected"),
                "happened_zh": happened,
                "why_zh": why,
                "enterprise_zh": enterprise,
                "practitioner_zh": practitioner,
                "evidence": None,
                "source_case_id": None,
                "ingest_note": note,
            },
        )
        db.execute("UPDATE world_sources SET status=? WHERE id=?", (new_status, seed["id"]))
        stats["details"].append(
            {
                "id": seed["id"],
                "url": url,
                "fetch": status,
                "day": day,
                "date_kind": date_kind if day else "collected",
                "status": new_status,
            }
        )
        if day:
            stats["axis"] += 1
        else:
            stats["collected"] += 1
        db.commit()
        print(f"    → {new_status} day={day or '—'} kind={date_kind if day else 'collected'}", flush=True)
    return stats


def queue_review(db, url, title, day, lane, info_kind, reason):
    db.execute(
        """INSERT OR IGNORE INTO world_review(url, title, day, lane, info_kind, reason, seen_at)
           VALUES(?,?,?,?,?,?,?)""",
        (url, title, day, lane, info_kind, reason, now_iso()),
    )


def axis_title_key(title, day, lane):
    return ((title or "").strip(), day or "", lane or "")


def existing_axis_keys(db):
    return {
        axis_title_key(r["title_zh"] or r["title"], r["day"], r["lane"])
        for r in db.execute("SELECT title, title_zh, day, lane FROM world_events")
    }


def parse_rss_items(body: bytes) -> list[dict]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    items = []
    ns_atom = "{http://www.w3.org/2005/Atom}"
    for item in list(root.iter("item")):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate") or item.findtext("date") or ""
        guid = item.findtext("guid") or link
        desc = item.findtext("description") or ""
        items.append({"title": title, "url": link or guid, "published": day_from_any(pub), "blob": title + " " + desc})
    for entry in root.iter(ns_atom + "entry"):
        title = "".join(entry.findtext(ns_atom + "title") or "").strip()
        link = ""
        for child in entry:
            if child.tag == ns_atom + "link" and child.attrib.get("rel") in (None, "alternate"):
                link = child.attrib.get("href") or link
        published = entry.findtext(ns_atom + "published") or entry.findtext(ns_atom + "updated") or ""
        summary = entry.findtext(ns_atom + "summary") or ""
        items.append({"title": title, "url": link, "published": day_from_any(published), "blob": title + " " + summary})
    return [it for it in items if it.get("url")]


def bump(run, key):
    run.setdefault("delta", {})
    run["delta"][key] = run["delta"].get(key, 0) + 1


def insert_feed_event(db, *, url, lane, info_kind, title, title_zh, published, entity_slug, note, run):
    if CS_PATH_RE.search(urllib.parse.urlsplit(url).path or ""):
        bump(run, "skip_cs")
        return "skip_cs"
    nurl = norm_url(url)
    if nurl in (run.get("existing_urls") or set()):
        bump(run, "already")
        return "dup"
    since = run.get("since") or ""
    if published and since and published < since:
        bump(run, "stale")
        return "stale"
    key = axis_title_key(title_zh or title, published, lane)
    if key in run["axis_keys"]:
        bump(run, "already")
        return "dup"
    if published and run["new_axis"] >= MAX_NEW_AXIS:
        queue_review(db, url, title_zh or title, published, lane, info_kind, "axis cap %s" % MAX_NEW_AXIS)
        bump(run, "review")
        db.commit()
        return "review"
    day, date_kind = pick_axis(published, "")
    upsert_source_date(db, url, published, "", COLLECTED_ON, day or COLLECTED_ON, date_kind if day else "collected", None, None)
    label = title_zh or title or ""
    org, role = "", label
    if "：" in label:
        org, role = label.split("：", 1)
    pack = editorial_pack("", info_kind, label, url=url, org=org, role=role)
    if info_kind == "hiring_census":
        m = re.search(r"(\d+)\s*个", label)
        pack = census_four(org or entity_slug or "", int(m.group(1)) if m else 0)
    upsert_event(
        db,
        {
            "url": url,
            "lane": lane,
            "info_kind": info_kind,
            "title": trunc(title or title_zh, 240),
            "title_zh": title_zh or trunc(title, 44),
            "day": day or None,
            "date_kind": date_kind if day else "collected",
            "collected_on": COLLECTED_ON,
            "host": host_of(url),
            "entity_slug": entity_slug if entity_exists(db, entity_slug) else None,
            "signal": signal_for(lane, info_kind, host_of(url), date_kind if day else "collected"),
            "happened_zh": pack["happened"],
            "why_zh": pack["why"],
            "enterprise_zh": pack["enterprise"],
            "practitioner_zh": pack["practitioner"],
            "evidence": None,
            "source_case_id": None,
            "ingest_note": note,
        },
    )
    if day:
        run["new_axis"] += 1
        run["axis_keys"].add(key)
        bump(run, "added_axis")
    else:
        bump(run, "collected")
    run.setdefault("existing_urls", set()).add(nurl)
    db.commit()
    return "axis" if day else "collected"


def rss_url_for(feed_url: str) -> str:
    u = feed_url.rstrip("/")
    if u.endswith("/feed") or u.endswith(".xml") or "feeds/" in u:
        return feed_url
    return u + "/feed"


def fetch_rss_feeds(db, catalog, run) -> dict:
    stats = {"feeds": 0, "hits": 0, "added": 0, "already": 0, "stale": 0, "details": []}
    feeds = [f for f in catalog.get("feeds") or [] if f.get("fetch_mode") == "rss" and f.get("status") in ("watch", "in_db")]
    for feed in feeds:
        url = rss_url_for(feed["url"])
        print(f"  rss {feed['id']}  {url}", flush=True)
        body, _, ctype, err = fetch_bytes(url, tries=2, timeout=30)
        stats["feeds"] += 1
        time.sleep(0.5)
        if not body:
            stats["details"].append({"id": feed["id"], "status": err or "ERR"})
            continue
        items = parse_rss_items(body)
        run.setdefault("delta", {})
        run["delta"]["scanned"] = run["delta"].get("scanned", 0) + len(items)
        lane = feed.get("lane") or "people"
        kind = (feed.get("info_kinds") or ["named_essay"])[0]
        added = already = stale = hits = 0
        for item in items:
            blob = item.get("blob") or ""
            if not FDE_RE.search(item.get("title") or "") and not FDE_RE.search(blob):
                continue
            hits += 1
            stats["hits"] += 1
            bump(run, "fde_hits")
            if not item.get("published"):
                continue
            st = insert_feed_event(
                db,
                url=item["url"],
                lane=lane,
                info_kind=kind if "podcast" not in (feed.get("id") or "") else "podcast_episode",
                title=item["title"],
                title_zh=trunc(item["title"], 44),
                published=item["published"],
                entity_slug=feed.get("entity_slug"),
                note=f"rss {feed['id']}",
                run=run,
            )
            if st in ("axis", "collected"):
                added += 1
            elif st == "dup":
                already += 1
            elif st == "stale":
                stale += 1
        stats["added"] += added
        stats["already"] += already
        stats["stale"] += stale
        stats["details"].append({"id": feed["id"], "status": "ok", "items": len(items), "fde": hits, "added": added, "already": already, "stale": stale})
        print(f"    → items={len(items)} fde={hits} added={added} already={already} stale={stale}", flush=True)
    return stats


def youtube_channel_feed(html: str, page_url: str) -> str:
    m = re.search(r'"channelId"\s*:\s*"(UC[^"]+)"', html)
    if not m:
        m = re.search(r"channel_id=(UC[0-9A-Za-z_-]+)", html)
    if m:
        return "https://www.youtube.com/feeds/videos.xml?channel_id=" + m.group(1)
    return ""


def fetch_youtube_feeds(db, catalog, run) -> dict:
    stats = {"feeds": 0, "hits": 0, "added": 0, "details": []}
    feeds = [f for f in catalog.get("feeds") or [] if f.get("fetch_mode") == "youtube" and f.get("status") in ("watch", "in_db")]
    for feed in feeds:
        print(f"  youtube {feed['id']}  {feed['url']}", flush=True)
        page = fetch_page(feed["url"])
        stats["feeds"] += 1
        time.sleep(0.5)
        atom = youtube_channel_feed(page.get("html") or "", feed["url"])
        if not atom:
            stats["details"].append({"id": feed["id"], "status": "no channel id"})
            continue
        body, _, _, err = fetch_bytes(atom, tries=2, timeout=30)
        time.sleep(0.5)
        if not body:
            stats["details"].append({"id": feed["id"], "status": err or "ERR"})
            continue
        items = parse_rss_items(body)
        added = 0
        for item in items:
            if not FDE_RE.search(item.get("title") or ""):
                continue
            stats["hits"] += 1
            if not item.get("published"):
                continue
            st = insert_feed_event(
                db,
                url=item["url"],
                lane=feed.get("lane") or "people",
                info_kind="conference_talk",
                title=item["title"],
                title_zh=trunc(item["title"], 44),
                published=item["published"],
                entity_slug=feed.get("entity_slug"),
                note=f"youtube {feed['id']}",
                run=run,
            )
            if st in ("axis", "collected"):
                added += 1
        stats["added"] += added
        stats["details"].append({"id": feed["id"], "status": "ok", "atom": atom, "added": added})
        print(f"    → added {added}", flush=True)
    return stats


def ats_job_rows(jobs: list) -> list[dict]:
    """Normalise Greenhouse / Lever / Ashby postings to {title, url, published}."""
    rows = []
    for job in jobs:
        title = re.sub(r"\s+", " ", (job.get("title") or job.get("text") or "")).strip()
        if not title or not (FDE_RE.search(title) or re.search(r"applied ai engineer", title, re.I)):
            continue
        published = ""
        if job.get("first_published"):
            published = day_from_any(job.get("first_published"))
        elif job.get("createdAt"):
            try:
                published = datetime.fromtimestamp(int(job["createdAt"]) / 1000, tz=timezone.utc).date().isoformat()
            except (TypeError, ValueError, OSError):
                published = ""
        elif job.get("publishedAt"):
            published = day_from_any(job.get("publishedAt"))
        url = job.get("absolute_url") or job.get("hostedUrl") or job.get("jobUrl") or ""
        rows.append({"title": title, "url": url, "published": published})
    return rows


def compact_job_role(title: str) -> str:
    """Drop expanded FDE tautology; keep the bit that distinguishes the req."""
    t = re.sub(r"\s+", " ", title or "").strip()
    t = re.sub(r"Palantir Technologies\s*[-–]\s*", "", t, flags=re.I)
    t = re.sub(r"\s*\(\s*Forward Deployed Engineer\s*\)", "", t, flags=re.I)
    t = re.sub(r"\s*\(\s*FDE\s*\)", "", t, flags=re.I)
    t = re.sub(r"Engineering Manager,\s*FDE Infrastructure(?:\s*\([^)]+\))?", "FDE 经理, Infra", t, flags=re.I)
    t = re.sub(r"Engineering Manager,\s*FDE Agentic Platform", "FDE 经理, Agentic", t, flags=re.I)
    t = re.sub(r"Sr\.\s*Manager,\s*AI Forward Deployed Engineering(?:\s*\(AI-FDE\))?", "AI-FDE 经理", t, flags=re.I)
    t = re.sub(r"Manager,\s*Applied AI Engineering", "Applied AI 经理", t, flags=re.I)
    t = re.sub(r"Sr\.\s*Field Technical Program Manager,\s*FDE", "FDE TPM", t, flags=re.I)
    t = re.sub(r"Forward Deployed Infrastructure Engineer", "FDE Infra", t, flags=re.I)
    t = re.sub(r"Forward Deployed Engineer,\s*Infrastructure Specialist", "FDE, Infra", t, flags=re.I)
    t = re.sub(r"Forward Deployed Engineer,\s*Agentic Platform", "FDE, Agentic", t, flags=re.I)
    t = re.sub(r"Forward Deployed AI Engineer", "FDE", t, flags=re.I)
    t = re.sub(r"Forward Deployed Engineer(?!ing)", "FDE", t, flags=re.I)
    t = re.sub(r"Sr\.\s*AI Engineer\s*[-–]\s*FDE", "Sr. AI FDE", t, flags=re.I)
    t = re.sub(r"AI Engineer\s*[-–]\s*FDE", "AI FDE", t, flags=re.I)
    t = re.sub(r"\s*[-–]\s*U\.S\.\s*Federal(?:\s*Sector)?", ", Federal", t, flags=re.I)
    t = re.sub(r",\s*New Grad\s*[-–]\s*(UK|US)\s+Government", ", New Grad", t, flags=re.I)
    t = re.sub(r"\s*\((North America|NORAM|West Coast|Public Sector)\)", "", t, flags=re.I)
    t = re.sub(r"\((\w[\w /+-]*)\)", lambda m: f"（{m.group(1)}）", t)
    t = re.sub(r"\s+（", "（", t)
    t = re.sub(r"\s+", " ", t).strip(" ,-–")
    return t or "FDE"


def job_axis_label(ent: str, title: str) -> str:
    role = compact_job_role(title)
    if ent and role.lower().startswith(ent.lower()):
        role = role[len(ent):].lstrip(" -:–—") or "FDE"
    return f"{ent}：{role}" if ent else role


def fold_title(title: str) -> str:
    """Same role across cities/regions is one posting."""
    t = re.sub(
        r"\s*[-–—|(]\s*(US|UK|EU|AUS|SGP|New York|London|Washington|Denver|"
        r"Palo Alto|Seattle|San Francisco|Remote|Foster City|Singapore)"
        r"[^-–—|)]*\)?\s*$",
        "",
        title,
        flags=re.I,
    )
    t = re.sub(
        r"\s*\((North America|NORAM|West Coast|Public Sector|EMEA|APAC|ANZ|"
        r"UAE|Poland|Switzerland|Legal-SF)\)\s*$",
        "",
        t,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", t).strip().lower()


def fetch_ats_census(db, catalog, run) -> dict:
    """Per board: one hiring_census row (collected), plus at most FRESH_PER_BOARD
    single postings whose first_published falls inside the last FRESH_DAYS.
    Those carry a real publishedAt, so they go on the method axis as weak signals."""
    stats = {"boards": 0, "jobs": 0, "added": 0, "fresh": 0, "details": []}
    feeds = [f for f in catalog.get("feeds") or [] if f.get("fetch_mode") == "ats_api" and f.get("status") in ("watch", "in_db")]
    fresh_since = (date.fromisoformat(SNAPSHOT) - timedelta(days=FRESH_DAYS)).isoformat()
    if run.get("since") and run["since"] > fresh_since:
        fresh_since = run["since"]
    for feed in feeds:
        url = feed["url"]
        print(f"  ats {feed['id']}  {url}", flush=True)
        api = url
        m = re.search(r"greenhouse\.io/([^/]+)", url)
        if m and "boards-api" not in url:
            api = f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs?content=true"
        m = re.search(r"jobs\.lever\.co/([^/]+)", url)
        if m:
            api = f"https://api.lever.co/v0/postings/{m.group(1)}?mode=json"
        m = re.search(r"(?:jobs\.ashbyhq\.com|api\.ashbyhq\.com/posting-api/job-board)/([^/?#]+)", url)
        if m:
            api = f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}"
        body, _, _, err = fetch_bytes(api, tries=2, timeout=30)
        stats["boards"] += 1
        time.sleep(0.5)
        if not body:
            stats["details"].append({"id": feed["id"], "status": err or "ERR"})
            continue
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            stats["details"].append({"id": feed["id"], "status": "bad json"})
            continue
        jobs = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            jobs = []
        rows = ats_job_rows(jobs)
        titles = {r["title"] for r in rows}
        stats["jobs"] += len(titles)
        if not titles:
            stats["details"].append({"id": feed["id"], "status": "ok", "n": 0})
            continue

        # fresh single postings → axis (weak). Fold cities, prefer senior/lead titles, cap per board.
        fresh = {}
        for r in rows:
            if not r["published"] or r["published"] < fresh_since or r["published"] > SNAPSHOT or not r["url"]:
                continue
            k = fold_title(r["title"])
            if k not in fresh or r["published"] > fresh[k]["published"]:
                fresh[k] = dict(r, n=1)
            else:
                fresh[k]["n"] += 1
        # a board that re-publishes everything on one day is not N events
        same_day = {}
        for r in fresh.values():
            same_day[r["published"]] = same_day.get(r["published"], 0) + 1
        bulk_days = {d for d, n in same_day.items() if n > 6}
        ranked = sorted(
            [r for r in fresh.values() if r["published"] not in bulk_days] or list(fresh.values()),
            key=lambda r: (
                0 if re.search(r"head|director|manager|lead|staff|principal", r["title"], re.I) else 1,
                r["published"],
            ),
        )
        ent = feed.get("entity_slug") or feed["id"]
        ent_name = next(
            (e.get("name") for e in (catalog.get("entities") or []) if e.get("slug") == ent and e.get("name")),
            None,
        ) or (ent.replace("-", " ").title() if ent else feed["id"])
        for r in ranked[:FRESH_PER_BOARD]:
            title_zh = job_axis_label(ent_name, r["title"])
            st = insert_feed_event(
                db,
                url=r["url"],
                lane="method",
                info_kind="job_posting",
                title=r["title"],
                title_zh=title_zh,
                published=r["published"],
                entity_slug=feed.get("entity_slug"),
                note="ats fresh posting first_published=%s cities=%s board_fde_total=%s%s"
                % (r["published"], r["n"], len(titles), " bulk-republish-day-skipped" if bulk_days else ""),
                run=run,
            )
            if st == "axis":
                stats["fresh"] += 1
            print(f"    fresh {r['published']} {r['title'][:50]} → {st}", flush=True)

        census_url = feed["url"].rstrip("/") + "/#fde-census-" + COLLECTED_ON
        # one census per board: the latest run replaces earlier snapshots
        db.execute(
            "DELETE FROM world_events WHERE url LIKE ? AND url != ?",
            (feed["url"].rstrip("/") + "/#fde-census-%", census_url),
        )
        title_zh = f"{ent_name}：{len(titles)} 个 FDE 相关岗位"
        st = insert_feed_event(
            db,
            url=census_url,
            lane="method",
            info_kind="hiring_census",
            title=title_zh,
            title_zh=title_zh,
            published=COLLECTED_ON,
            entity_slug=feed.get("entity_slug"),
            note="ats census n=%s sample=%s" % (len(titles), "; ".join(list(titles)[:4])),
            run=run,
        )
        # census uses snapshot day — that's collection, not a real publishedAt. Force collected.
        if st in ("axis", "collected"):
            db.execute(
                "UPDATE world_events SET day=NULL, date_kind='collected' WHERE url=?",
                (census_url,),
            )
            db.commit()
            stats["added"] += 1
        stats["details"].append({"id": feed["id"], "status": st, "n": len(titles)})
        print(f"    → {len(titles)} titles folded, {st}", flush=True)
    return stats


def fetch_feeds(db, catalog, run) -> dict:
    print("== feeds rss", flush=True)
    rss = fetch_rss_feeds(db, catalog, run)
    print("== feeds youtube", flush=True)
    yt = fetch_youtube_feeds(db, catalog, run)
    print("== feeds ats census", flush=True)
    ats = fetch_ats_census(db, catalog, run)
    return {"rss": rss, "youtube": yt, "ats": ats}


def extract_json_dated_links(html: str, base: str) -> list[tuple[str, str]]:
    """Anthropic-style pages hide articles in JSON with publishedOn, not in <a>."""
    blob = html.replace('\\/', "/").replace('\\"', '"')
    found = []
    seen = set()
    patterns = (
        r'"publishedOn"\s*:\s*"(\d{4}-\d{2}-\d{2})[^"]*".{0,600}?"(?:canonicalUrl|url|slug)"\s*:\s*"([^"]+)"',
        r'"(?:canonicalUrl|url)"\s*:\s*"(https?://[^"]+|/[A-Za-z][^"]{0,180})".{0,600}?"publishedOn"\s*:\s*"(\d{4}-\d{2}-\d{2})',
    )
    for pat in patterns:
        for m in re.finditer(pat, blob, re.S):
            if pat.startswith('"publishedOn'):
                day, ref = m.group(1), m.group(2)
            else:
                ref, day = m.group(1), m.group(2)
            if ref.startswith("http"):
                url = ref
            elif ref.startswith("/"):
                url = urllib.parse.urljoin(base, ref)
            else:
                url = urllib.parse.urljoin(base, "/news/" + ref)
            key = norm_url(url)
            if key in seen:
                continue
            seen.add(key)
            found.append((url, day))
    return found


def extract_links(html: str, base: str) -> list[str]:
    out = []
    seen = set()
    for href in re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', html, re.I):
        href = H.unescape(href).split("#")[0].strip()
        if not href or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        abs_url = urllib.parse.urljoin(base, href)
        key = norm_url(abs_url)
        if key in seen:
            continue
        seen.add(key)
        out.append(abs_url)
    return out


def peek_newsrooms(db, catalog, run, cap: int = 8) -> dict:
    """Fetch org/method indexes; keep FDE-related pages with a strong date. Never follow CS walls."""
    stats = {"indexes": 0, "candidates": 0, "added": 0, "review": 0, "details": []}
    feeds = [
        f
        for f in catalog.get("feeds") or []
        if f.get("status") == "watch"
        and f.get("fetch_mode") == "list_index"
        and int(f.get("priority") or 9) <= 2
    ]
    existing = {norm_url(r["url"]) for r in db.execute("SELECT url FROM world_events")}
    added = 0
    for feed in feeds:
        if added >= cap:
            break
        url = feed["url"]
        print(f"  peek {feed['id']}  {url}", flush=True)
        page = fetch_page(url)
        stats["indexes"] += 1
        time.sleep(0.7)
        if page.get("status") != "ok":
            stats["details"].append({"feed": feed["id"], "status": page.get("status")})
            continue
        html = page.get("html") or ""
        host = host_of(url)
        candidates = []
        for link in extract_links(html, page.get("final") or url):
            if host_of(link) != host and not host_of(link).endswith(host):
                continue
            if CS_PATH_RE.search(urllib.parse.urlsplit(link).path or ""):
                continue
            path = urllib.parse.urlsplit(link).path or ""
            if path in ("", "/"):
                continue
            if re.search(r"\.(png|jpe?g|gif|webp|svg|css|js)$", path, re.I):
                continue
            blob = link
            # Need FDE-ish path or we'll inspect later
            if FDE_RE.search(link) or FDE_RE.search(path.replace("-", " ").replace("/", " ")):
                candidates.append(link)
        # also scan nearby link text via crude window
        if not candidates:
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
                href, text = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2))
                if FDE_RE.search(href) or FDE_RE.search(text):
                    abs_url = urllib.parse.urljoin(page.get("final") or url, href.split("#")[0])
                    if CS_PATH_RE.search(urllib.parse.urlsplit(abs_url).path or ""):
                        continue
                    if host_of(abs_url) == host:
                        candidates.append(abs_url)
        json_dated = {}
        for link, day in extract_json_dated_links(html, page.get("final") or url):
            if CS_PATH_RE.search(urllib.parse.urlsplit(link).path or ""):
                continue
            blob = link
            if not (FDE_RE.search(link) or FDE_RE.search(blob)):
                # keep org-ish JSON rows even if slug has no FDE (Anthropic services company)
                if not re.search(r"enterprise|deployment|forward|fde|frontier", link, re.I):
                    continue
            json_dated[norm_url(link)] = (link, day)
            candidates.append(link)
        uniq = []
        seen = set()
        for link in candidates:
            key = norm_url(link)
            if key in seen or key in existing:
                continue
            seen.add(key)
            uniq.append(link)
        stats["candidates"] += len(uniq)
        since = run.get("since") or ""
        for link in uniq[:PEEK_CANDIDATES]:
            if added >= cap:
                break
            print(f"    candidate {link}", flush=True)
            art = fetch_page(link)
            time.sleep(0.7)
            html_art = art.get("html") or ""
            text = html_to_text(html_art)[:4000]
            if not FDE_RE.search(html_art) and not FDE_RE.search(text):
                stats["details"].append({"url": link, "skip": "no FDE match"})
                continue
            dates = extract_dates(html_art)
            hint = (json_dated.get(norm_url(link)) or (None, None))[1]
            published = valid_day(dates.get("published")) or valid_day(hint)
            if not published:
                stats["details"].append({"url": link, "skip": "no strong date"})
                continue
            if since and published < since:
                bump(run, "stale")
                stats["details"].append({"url": link, "skip": "stale", "day": published})
                continue
            title = extract_title(html_art) or host
            title_zh = trunc(title, 44)
            info_kind = (feed.get("info_kinds") or ["org_announcement"])[0]
            low = (title + " " + link).lower()
            if "letter" in low or "shareholder" in low:
                info_kind = "earnings_letter"
            lane = feed.get("lane") or "company"
            st = insert_feed_event(
                db,
                url=link,
                lane=lane,
                info_kind=info_kind,
                title=title,
                title_zh=title_zh,
                published=published,
                entity_slug=feed.get("entity_slug"),
                note=f"list_index peek from {feed['id']}",
                run=run,
            )
            existing.add(norm_url(link))
            if st == "review":
                stats["review"] += 1
            elif st in ("axis", "collected"):
                added += 1
                stats["added"] += 1
            stats["details"].append({"url": link, "day": published, "title": title_zh, "status": st})
            print(f"      {st} day={published}", flush=True)
    return stats


def customer_from_title(title: str, host: str) -> str:
    text = re.sub(r"\s+", " ", title or "").strip()
    text = text.split("|")[0].split("—")[0].split("–")[0].strip()
    for junk in ("customer story", "case study", "success story", "customers", host.split(".")[0]):
        text = re.sub(r"(?i)\b" + re.escape(junk) + r"\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -·,:")
    return trunc(text, 40)


def fetch_cs_hubs(db, catalog, run) -> dict:
    """Bounded recrawl of existing vendor story walls. New vendor hubs are not allowed."""
    stats = {"hubs": 0, "new_links": 0, "added": 0, "no_date": 0, "details": []}
    hubs = catalog.get("cs_hubs") or []
    existing = set(run.get("existing_urls") or set())
    since = run.get("since") or ""
    per_hub = int(catalog.get("cs_per_hub_per_run") or CS_PER_HUB)
    for hub in hubs:
        hub_url = hub.get("url") or ""
        host = hub.get("host") or host_of(hub_url)
        print(f"  cs {hub.get('id')}  {hub_url}", flush=True)
        page = fetch_page(hub_url)
        stats["hubs"] += 1
        time.sleep(0.6)
        if page.get("status") != "ok":
            stats["details"].append({"id": hub.get("id"), "status": page.get("status")})
            continue
        html = page.get("html") or ""
        base = page.get("final") or hub_url
        links = []
        seen = set()
        for href in extract_links(html, base):
            if host_of(href) != host:
                continue
            path = urllib.parse.urlsplit(href).path or ""
            if path in ("", "/") or path.rstrip("/") == urllib.parse.urlsplit(hub_url).path.rstrip("/"):
                continue
            if re.search(r"\.(png|jpe?g|gif|webp|svg|pdf)$", path, re.I):
                continue
            if not CS_STORY_RE.search(path) and "customer-story" not in path.lower():
                continue
            key = norm_url(href)
            if key in seen or key in existing:
                continue
            seen.add(key)
            links.append(href)
        stats["new_links"] += len(links)
        added_here = 0
        for link in links[:per_hub]:
            art = fetch_page(link)
            time.sleep(0.5)
            html_art = art.get("html") or ""
            dates = extract_dates(html_art)
            published = valid_day(dates.get("published")) or valid_day(dates.get("modified"))
            title = extract_title(html_art) or host
            if not published:
                stats["no_date"] += 1
                stats["details"].append({"url": link, "skip": "no strong date"})
                continue
            if since and published < since:
                bump(run, "stale")
                continue
            customer = customer_from_title(title, host)
            if not customer or len(customer) < 2:
                stats["details"].append({"url": link, "skip": "no customer name"})
                continue
            ensure_entity(db, hub.get("entity_slug") or host.split(".")[0], hub.get("entity_slug") or host, "org", host)
            st = insert_feed_event(
                db,
                url=link,
                lane="deploy",
                info_kind="dated_case_study",
                title=title,
                title_zh=customer,
                published=published,
                entity_slug=hub.get("entity_slug"),
                note=f"cs hub {hub.get('id')}",
                run=run,
            )
            if st in ("axis", "collected"):
                added_here += 1
                stats["added"] += 1
            print(f"    {st} {published} {customer}", flush=True)
        stats["details"].append({"id": hub.get("id"), "new_links": len(links), "added": added_here})
    return stats


def write_links(db) -> int:
    """same_org successive dated events. Visual association, not causality."""
    db.execute("DELETE FROM world_links")
    rows = list(
        db.execute(
            """SELECT id, entity_slug, day, lane FROM world_events
               WHERE day IS NOT NULL AND entity_slug IS NOT NULL
               ORDER BY entity_slug, day, id"""
        )
    )
    n = 0
    by = {}
    for row in rows:
        by.setdefault(row["entity_slug"], []).append(row)
    for group in by.values():
        for left, right in zip(group, group[1:]):
            kind = "direct" if left["lane"] == right["lane"] else "indirect"
            db.execute(
                """INSERT OR IGNORE INTO world_links(from_id, to_id, kind, basis, note)
                   VALUES(?,?,?,?,?)""",
                (left["id"], right["id"], kind, "same_org", "same entity successive dated items"),
            )
            n += 1
    db.commit()
    return n


ENTITY_NAME_ZH = {
    "a16z": "Andreessen Horowitz",
    "abridge": "Abridge",
    "anthropic": "Anthropic",
    "augment": "Augment",
    "aws": "AWS",
    "blend360": "Blend360",
    "c3-ai": "C3 AI",
    "cognition": "Cognition",
    "cohere": "Cohere",
    "cresta": "Cresta",
    "cursor": "Cursor",
    "databricks": "Databricks",
    "decagon": "Decagon",
    "elevenlabs": "ElevenLabs",
    "factory": "Factory",
    "glean": "Glean",
    "google-cloud": "Google Cloud",
    "harvey": "Harvey",
    "hebbia": "Hebbia",
    "intercom": "Intercom",
    "microsoft": "微软",
    "moveworks": "Moveworks",
    "openai": "OpenAI",
    "palantir": "Palantir",
    "perplexity": "Perplexity",
    "plank": "Plank",
    "posthog": "PostHog",
    "replit": "Replit",
    "rippling": "Rippling",
    "scale-ai": "Scale AI",
    "sierra": "Sierra",
    "sourcegraph": "Sourcegraph",
    "vannevar": "Vannevar Labs",
    "writer": "Writer",
    "xai": "xAI",
    "alex-karp": "Alex Karp",
    "barry-mccardel": "Barry McCardel",
    "bob-mcgrew": "Bob McGrew",
    "colin-jarvis": "Colin Jarvis",
    "gergely-orosz": "Gergely Orosz",
    "kevin-bai": "Kevin Bai",
    "marty-cagan": "Marty Cagan",
    "nabeel-qureshi": "Nabeel Qureshi",
    "natalie-meurer": "Natalie Meurer",
    "ross-wilkers": "Ross Wilkers",
    "shyam-sankar": "Shyam Sankar",
    "ted-mabrey": "Ted Mabrey",
}


def fill_entity_names(db) -> int:
    n = 0
    for slug, name_zh in ENTITY_NAME_ZH.items():
        cur = db.execute(
            "UPDATE world_entities SET name_zh=? WHERE slug=? AND (name_zh IS NULL OR name_zh='')",
            (name_zh, slug),
        )
        n += cur.rowcount or 0
    db.commit()
    return n


def apply_editorial_copy(db) -> int:
    """Fill happened/why/enterprise/practitioner for existing events. Safe to re-run."""
    seed_by_url = {norm_url(r["url"]): r["id"] for r in db.execute("SELECT id, url FROM world_sources")}
    n = 0
    rows = list(db.execute("SELECT * FROM world_events"))
    for row in rows:
        url = row["url"] or ""
        seed_id = seed_by_url.get(norm_url(url)) or ""
        title = row["title_zh"] or row["title"] or ""
        org, role = "", title
        if "：" in title:
            org, role = title.split("：", 1)
        pack = editorial_pack(seed_id, row["info_kind"] or "", title, url=url, org=org, role=role)
        if row["info_kind"] == "hiring_census":
            m = re.search(r"(\d+)\s*个", title)
            pack = census_four(org or row["entity_slug"] or "", int(m.group(1)) if m else 0)
        if row["info_kind"] == "dated_case_study" and not pack.get("practitioner"):
            pack["practitioner"] = DEPLOY_NO_FDE
        happened = pack["happened"]
        old_hap = row["happened_zh"] or ""
        keep_old = (
            _is_stub_happened(happened, row["title"] or "", row["title_zh"] or "")
            and not EVENT_COPY.get(seed_id)
            and not pack_from_needle(url)
            and old_hap
            and not _is_stub_happened(old_hap, row["title"] or "", row["title_zh"] or "")
            and "…" not in old_hap
        )
        if keep_old:
            happened = old_hap
        new = (
            happened,
            pack["why"],
            pack.get("enterprise") or row["enterprise_zh"],
            pack.get("practitioner") or row["practitioner_zh"],
        )
        old = (row["happened_zh"], row["why_zh"], row["enterprise_zh"], row["practitioner_zh"])
        if new == old:
            continue
        db.execute(
            """UPDATE world_events
                  SET happened_zh=?, why_zh=?, enterprise_zh=?, practitioner_zh=?
                WHERE id=?""",
            (*new, row["id"]),
        )
        n += 1
    n += fill_entity_names(db)
    db.commit()
    return n


def update_catalog_file(catalog: dict, db) -> None:
    status_by_id = {r["id"]: r["status"] for r in db.execute("SELECT id, status FROM world_sources WHERE role='seed'")}
    for seed in catalog.get("seeds") or []:
        if seed["id"] in status_by_id:
            seed["status"] = status_by_id[seed["id"]]
    n_events = db.execute("SELECT count(*) FROM world_events").fetchone()[0]
    catalog["homepage_still_reads"] = "world_events" if n_events else "cases"
    catalog["crawl_paused"] = False
    catalog["do_not_recrawl_vendor_case_studies"] = False
    catalog["do_not_start_a_new_vendor"] = True
    catalog["last_ingest"] = now_iso()
    catalog["note"] = (
        "Dynamics + bounded case-study hubs. No new vendor, no unbounded mine_loop. "
        "Homepage reads world_events."
    )
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def since_day_from(catalog: dict, explicit: str) -> str:
    if explicit and valid_day(explicit):
        return explicit
    # 滚动回溯窗口（见 BACKFILL_DAYS 说明）：不用 last_ingest 当天，避免漏抓永久丢失
    try:
        return (date.fromisoformat(SNAPSHOT) - timedelta(days=BACKFILL_DAYS)).isoformat()
    except (ValueError, TypeError):
        pass
    if STATE_PATH.is_file():
        try:
            day = json.loads(STATE_PATH.read_text(encoding="utf-8")).get("since_day") or ""
            if valid_day(day):
                return day
        except (OSError, ValueError):
            pass
    return "1970-01-01"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrate-only", action="store_true")
    parser.add_argument("--no-peek", action="store_true")
    parser.add_argument("--feeds", action="store_true", help="run rss/youtube/ats + peek; skip missing-seed recrawl")
    parser.add_argument("--daily", action="store_true", help="incremental run: --feeds --cases --since last_ingest, snapshot=today")
    parser.add_argument("--cases", action="store_true", help="bounded recrawl of catalog cs_hubs")
    parser.add_argument("--since", help="YYYY-MM-DD; skip items published before this (default last_ingest)")
    parser.add_argument("--snapshot", help="YYYY-MM-DD; default = today. Windows on the site end on this day")
    parser.add_argument("--backfill-copy", action="store_true", help="rewrite Chinese four-field copy and exit")
    args = parser.parse_args()
    if args.backfill_copy:
        db = connect()
        apply_schema(db)
        n = apply_editorial_copy(db)
        print(f"backfill_copy updated={n}", flush=True)
        return 0
    if args.daily:
        args.feeds = True
        args.cases = True
    if args.snapshot:
        global SNAPSHOT, COLLECTED_ON
        SNAPSHOT = valid_day(args.snapshot) or SNAPSHOT
        COLLECTED_ON = SNAPSHOT
    catalog = load_catalog()
    since = since_day_from(catalog, args.since or "")
    print(f"== snapshot {SNAPSHOT} since {since}", flush=True)

    dates_idx = load_dates_json()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    db = connect()
    apply_schema(db)
    seed_catalog(db, catalog)
    existing_urls = {norm_url(r["url"]) for r in db.execute("SELECT url FROM world_events")}
    run = {
        "new_axis": 0,
        "axis_keys": existing_axis_keys(db),
        "existing_urls": existing_urls,
        "since": since,
        "delta": {"scanned": 0, "fde_hits": 0, "already": 0, "stale": 0, "added_axis": 0, "collected": 0, "review": 0},
    }

    mig = {"migrated": 0, "axis": 0, "collected_only": 0}
    dropped = 0
    if not args.feeds:
        print("== migrate inventory", flush=True)
        mig = migrate_inventory(db, catalog, dates_idx)
        dropped = fold_locale_mirrors(db)
        print(f"   migrated={mig['migrated']} axis={mig['axis']} collected={mig['collected_only']} folded={dropped}", flush=True)
        run["axis_keys"] = existing_axis_keys(db)
        run["existing_urls"] = {norm_url(r["url"]) for r in db.execute("SELECT url FROM world_events")}

    fetch_stats = {"ok": 0, "blocked": 0, "err": 0, "axis": 0, "collected": 0, "details": []}
    peek_stats = {"indexes": 0, "candidates": 0, "added": 0, "details": []}
    feed_stats = {}
    cs_stats = {}
    if args.feeds:
        feed_stats = fetch_feeds(db, catalog, run)
        if not args.no_peek:
            print("== peek list_index (p1–p2, FDE-only, strong date)", flush=True)
            peek_stats = peek_newsrooms(db, catalog, run)
    if args.cases:
        print("== case-study hubs (existing vendors, dated only)", flush=True)
        cs_stats = fetch_cs_hubs(db, catalog, run)
    elif not args.migrate_only:
        print("== fetch missing seeds", flush=True)
        fetch_stats = fetch_missing(db, catalog)
        if not args.no_peek:
            print("== peek newsrooms (FDE-only, not CS walls)", flush=True)
            peek_stats = peek_newsrooms(db, catalog, run)

    filled = apply_editorial_copy(db)
    print(f"== editorial copy updated={filled}", flush=True)
    n_links = write_links(db)
    n_events = db.execute("SELECT count(*) FROM world_events").fetchone()[0]
    n_axis = db.execute("SELECT count(*) FROM world_events WHERE day IS NOT NULL AND date_kind IN ('published','modified')").fetchone()[0]
    n_review = db.execute("SELECT count(*) FROM world_review").fetchone()[0]
    by_lane = {
        r["lane"]: r["c"]
        for r in db.execute(
            "SELECT lane, count(*) c FROM world_events WHERE day IS NOT NULL AND date_kind IN ('published','modified') GROUP BY lane"
        )
    }
    update_catalog_file(catalog, db)
    delta = run.get("delta") or {}
    db.execute(
        """INSERT INTO world_ingest_runs(started_at, snapshot, since_day, scanned, fde_hits, already, stale, added_axis, review, note)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (
            now_iso(),
            SNAPSHOT,
            since,
            int(delta.get("scanned") or 0),
            int(delta.get("fde_hits") or 0),
            int(delta.get("already") or 0),
            int(delta.get("stale") or 0),
            int(run.get("new_axis") or 0),
            int(delta.get("review") or 0),
            "daily" if args.daily else ("feeds" if args.feeds else "full"),
        ),
    )
    db.commit()
    state = {
        "snapshot": SNAPSHOT,
        "last_ingest": now_iso(),
        "since_day": SNAPSHOT,
        "last_delta": delta,
        "new_axis_this_run": run.get("new_axis") or 0,
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "written_at": now_iso(),
        "snapshot": SNAPSHOT,
        "since_day": since,
        "increment": {
            "scanned": int(delta.get("scanned") or 0),
            "fde_hits": int(delta.get("fde_hits") or 0),
            "already_in_db": int(delta.get("already") or 0),
            "stale": int(delta.get("stale") or 0),
            "added_axis": int(run.get("new_axis") or 0),
            "collected": int(delta.get("collected") or 0),
            "review": int(delta.get("review") or 0),
        },
        "n_events": n_events,
        "n_axis": n_axis,
        "n_review": n_review,
        "new_axis_this_run": run["new_axis"],
        "by_lane_axis": by_lane,
        "n_links": n_links,
        "migrate": mig,
        "folded_locale": dropped,
        "fetch": {k: v for k, v in fetch_stats.items() if k != "details"},
        "fetch_details": fetch_stats.get("details") or [],
        "feeds": feed_stats,
        "cs_hubs": cs_stats,
        "peek": peek_stats,
        "vendor_cs_recrawl": False,
        "crawl_paused_file_left_in_place": True,
        "openai_dates_corrected": {
            "introducing-openai-frontier": "2026-02-05",
            "openai-launches-the-deployment-company": "2026-05-11",
        },
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("== increment", json.dumps(report["increment"], ensure_ascii=False), flush=True)
    print("== done", json.dumps({k: report[k] for k in ("n_events", "n_axis", "by_lane_axis", "n_links")}, ensure_ascii=False), flush=True)
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
