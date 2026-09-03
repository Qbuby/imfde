# -*- coding: utf-8 -*-
"""OpenFDE world-dynamics homepage.

The page is deliberately a dated snapshot rather than a news reader. The
timeline is built from the local database and ``source_dates.json``; an item
is eligible only when its source has an explicit publication or modification
date. Sitemap touch dates and collection dates never become event dates.
"""
from __future__ import annotations

import json
import re
from collections import Counter, OrderedDict
from datetime import date, timedelta

import server as S


WINDOW_DAYS = (7, 30, 90)
DEPLOY_HOST_CAP = 4
WORLD_BRAND = S.SITE_NAME
LANES = (
    ("company", "公司动作", "Company Moves"),
    ("deploy", "真实部署", "Real Deployments"),
    ("people", "人物与观点", "People & Perspectives"),
    ("method", "方法与岗位", "Methods & Roles"),
)
LANE_ORDER = {key: index for index, (key, _zh, _en) in enumerate(LANES)}
DOC_LABEL = {
    "case_study": "交付故事",
    "methodology": "方法",
    "opinion": "观点",
    "job_posting": "岗位",
}
KIND_LABEL = {
    "org_announcement": "组织公告",
    "product_line": "产品线",
    "earnings_letter": "股东信",
    "press_release": "新闻稿",
    "named_essay": "观点",
    "interview": "访谈",
    "conference_talk": "演讲",
    "podcast_episode": "播客",
    "discussion": "讨论",
    "methodology": "方法",
    "engineering_blog": "工程博客",
    "job_posting": "岗位",
    "hiring_board": "招聘板",
    "hiring_census": "岗位普查",
    "dated_case_study": "交付故事",
}
HOST_VOICE = {
    "openai.com": "OpenAI",
    "cohere.com": "Cohere",
    "a16z.com": "Andreessen Horowitz",
    "blog.pragmaticengineer.com": "Pragmatic Engineer",
    "newsletter.pragmaticengineer.com": "Pragmatic Engineer",
    "fdepod.substack.com": "The FDE Pod",
    "fourthage.substack.com": "Fourth Age",
    "fdeinterviews.com": "FDEInterviews",
    "fde.academy": "FDE Academy",
    "linkedin.com": "LinkedIn",
    "palantir.com": "Palantir",
    "aws.amazon.com": "AWS",
    "sec.gov": "Palantir",
    "nabeelqu.co": "Nabeel Qureshi",
    "barry.ooo": "Barry McCardel",
    "svpg.com": "Marty Cagan",
    "latent.space": "Latent Space",
    "youtube.com": "YouTube",
    "posthog.com": "PostHog",
    "vannevarlabs.com": "Vannevar Labs",
    "joinplank.com": "Plank",
    "computerworld.com": "Computerworld",
    "anthropic.com": "Anthropic",
    "build.a16z.com": "Andreessen Horowitz",
    "databricks.com": "Databricks",
    "microsoft.com": "Microsoft",
    "blogs.microsoft.com": "Microsoft",
}
OFFICIAL_HOSTS = {
    "openai.com",
    "cohere.com",
    "a16z.com",
    "c3.ai",
    "cognition.com",
    "databricks.com",
    "anthropic.com",
    "sierra.ai",
    "palantir.com",
    "writer.com",
    "factory.ai",
    "decagon.ai",
    "devin.ai",
    "aws.amazon.com",
    "sec.gov",
    "microsoft.com",
    "blogs.microsoft.com",
}
ALLOWED_DOC_TYPES = frozenset({"case_study", "methodology", "opinion", "job_posting"})
BAD_VENDOR_KEYS = frozenset({"unknown", "anonymous", "unknown-anonymous", "other"})

# These are translations of titles that exist in the local source list. They
# are labels only; evidence, dates, and URLs remain the source record.
TITLE_MAP = (
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
    ("a16z.com/insights-for-enterprise-ai-builders", "a16z：从 Demo 到成交"),
    ("blog.pragmaticengineer.com/the-pulse-forward-deployed-engineering-heats-up-again", "Pragmatic Engineer：FDE 再次升温"),
    ("newsletter.pragmaticengineer.com/p/the-pulse-forward-deployed-engineering-887", "Pragmatic Engineer：FDE 再次升温"),
    ("newsletter.pragmaticengineer.com/p/forward-deployed-engineers", "Pragmatic Engineer：FDE 为何抢手"),
    ("openai.com/careers/forward-deployed-engineer", "OpenAI 招聘 FDE"),
    ("nabeelqu.co/reflections-on-palantir", "Nabeel：对 Palantir 的反思"),
    ("barry.ooo/posts/fde-culture", "Barry：FDE 文化"),
    ("svpg.com/forward-deployed-engineers", "Marty Cagan：前向部署工程师"),
    ("latent.space/p/forward-deployed-engineers-aiewf", "Natalie Meurer：前向部署工程师"),
    ("palantir.com/q2-2026-letter", "Palantir 2026 Q2 股东信"),
    ("aws.amazon.com/blogs/apn/introducing-forward-deployed-engineering", "AWS 宣布伙伴 Forward Deployed Engineering"),
    ("posthog.com/blog/forward-deployed-engineer", "PostHog：什么是 Forward Deployed Engineer"),
    ("vannevarlabs.com/blog/forward-deployed-engineering", "Vannevar：怎么建 FDE 组"),
    ("joinplank.com/fde-job-market", "Plank：FDE 岗位市场普查"),
    ("databricks.com/blog/forward-deployed-engineering", "Databricks 成立 Forward Deployed Engineering"),
    ("blogs.microsoft.com/blog/2026/07/02/microsoft-frontier-company", "Microsoft 发布 Frontier Company"),
    ("anthropic.com/news/enterprise-ai-services-company", "Anthropic 成立企业 AI 服务公司"),
    ("deploy.co/news/the-openai-deployment-company-to-acquire-northslope", "Deployment Company 收购 Northslope"),
    ("inside-openais-forward-deployed-engineer", "Colin Jarvis：OpenAI 的 FDE 岗位"),
    ("fde-war-stories-nine-patterns", "FDE 现场的九种套路"),
    ("fde-exit-options-career-trajectory", "FDE 的退出路径"),
    ("negotiating-forward-deployed-engineer-offer", "怎么谈 FDE offer"),
    ("joinplank.com/fde-news/august-2026", "Plank：8 月 FDE 简报"),
    ("subset-tech-talent-supply-crunch-watch-out", "Ross Wilkers：FDE 人才短缺"),
    ("8-tactical-insights-from-current-former-forward", "Palantir FDE 的 8 条经验"),
)
TITLE_SHORT = (
    ("openai.com/index/openai-launches-the-deployment-company", "OpenAI · 部署公司"),
    ("openai.com/index/introducing-openai-frontier", "OpenAI · Frontier"),
    ("palantir.com/q2-2026-letter", "Palantir · 股东信"),
    ("a2026q2ex991", "Palantir · 业绩稿"),
    ("databricks.com/blog/forward-deployed-engineering", "Databricks · FDE"),
    ("microsoft-frontier-company", "微软 · Frontier"),
    ("introducing-forward-deployed-engineering-for-partners", "AWS · 成立 FDE"),
    ("forward-deployed-engineers-capability-building", "Cohere · 建能力"),
    ("forward-deployed-engineers-aiewf", "Natalie · 访谈"),
    ("watch?v=Byv311hdoHE", "Natalie · AIEWF"),
    ("watch?v=KwhgfwOSToQ", "Kevin Bai · FDE 101"),
    ("deploy.co/news/the-openai-deployment-company-to-acquire-northslope", "Deploy Co · Northslope"),
    ("inside-openais-forward-deployed-engineer", "Colin Jarvis · OpenAI FDE"),
    ("computerworld.com", "AWS · 访谈"),
    ("joinplank.com/fde-job-market", "Plank · 普查"),
    ("joinplank.com/fde-news/august-2026", "Plank · 8 月简报"),
    ("how-forward-deployed-engineers-work", "FDE 交付周期"),
    ("day-in-the-life-forward-deployed-engineer", "FDE 的一天"),
    ("what-is-a-forward-deployed-engineer", "FDE 是什么"),
    ("what-does-a-forward-deployed-engineer-do", "FDE 在做什么"),
    ("fdepod.substack.com/p/fde-101", "FDE 101"),
    ("hire-forward-deployed-engineers", "怎么招 FDE"),
    ("fde-war-stories-nine-patterns", "FDE 九种套路"),
    ("fde-exit-options-career-trajectory", "FDE 退出路径"),
    ("negotiating-forward-deployed-engineer-offer", "谈 FDE offer"),
    ("subset-tech-talent-supply-crunch-watch-out", "Ross · 人才短缺"),
    ("8-tactical-insights-from-current-former-forward", "FDE 8 条经验"),
    ("the-pulse-forward-deployed-engineering", "PE · FDE 升温"),
    ("insights-for-enterprise-ai-builders", "a16z · Demo 到成交"),
)


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


def title_from_url(url: str) -> str:
    blob = (url or "").lower()
    for needle, label in TITLE_MAP:
        if needle.lower() in blob:
            return label
    return ""


def short_title_for(title: str, url: str, lane: str, customer: str) -> str:
    blob = (url or "").lower()
    for needle, label in TITLE_SHORT:
        if needle.lower() in blob:
            return label
    if lane == "deploy" and customer:
        return customer
    text = (title or "").strip()
    if "：" in text:
        left, right = text.split("：", 1)
        head = left.split()[0][:12]
        right = right.strip()
        right = re.sub(r"^20\d{2}\s*年\s*", "", right)
        m = re.search(r"[（(]([^）)]+)[）)]\s*$", right)
        if m and 2 <= len(m.group(1)) <= 16:
            return f"{head} · {m.group(1)}"
        if "," in right:
            tail = right.rsplit(",", 1)[-1].strip()
            if 2 <= len(tail) <= 16:
                return f"{head} · {tail}"
        if len(right) <= 16:
            return f"{head} · {right}"
        return f"{head} · {S.trunc(right, 16)}"
    if len(text) <= 16:
        return text
    return S.trunc(text, 16)


def _snap() -> date:
    return date.fromisoformat(S.SNAPSHOT)


def window_start(days: int) -> str:
    return (_snap() - timedelta(days=days - 1)).isoformat()


def valid_day(value) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            date.fromisoformat(text)
        except ValueError:
            return ""
        return text
    return ""


def date_status(row) -> tuple[str, str]:
    rec = S.date_rec(row.get("source_url") or "")
    published = valid_day(rec.get("published"))
    if published:
        return published, "published"
    modified = valid_day(rec.get("modified"))
    if modified:
        return modified, "modified"
    return "", ""


def clean_text(value) -> str:
    """Drop visibly corrupted extracts instead of putting mojibake in UI."""
    text = " ".join(str(value or "").split()).strip()
    if not text or "�" in text:
        return ""
    if any(ord(ch) < 9 for ch in text):
        return ""
    return text


def source_host(row) -> str:
    return row.get("host") or S.host_of(row.get("source_url") or "")


def source_blob(row) -> str:
    return ((row.get("source_url") or "") + " " + (row.get("source_title") or "")).lower()


def classify_lane(row) -> str:
    blob = source_blob(row)
    doc_type = row.get("doc_type") or ""
    if (
        "openai.com/index/openai-launches-the-deployment-company" in blob
        or "openai.com/zh-hans-cn/index/introducing-openai-frontier" in blob
        or "openai.com/index/introducing-openai-frontier" in blob
    ):
        return "company"
    if doc_type == "case_study":
        return "deploy"
    if doc_type == "opinion":
        return "people"
    if doc_type in ("methodology", "job_posting"):
        return "method"
    return ""


def mapped_title(row) -> str:
    blob = source_blob(row)
    for needle, label in TITLE_MAP:
        if needle in blob:
            return label
    if row.get("customer_named"):
        customer = clean_text(row.get("customer"))
        if customer:
            return customer
    raw = clean_text(row.get("source_title"))
    if raw:
        return S.trunc(raw.split("|")[0].strip(), 44)
    host = source_host(row)
    return HOST_VOICE.get(host) or host or "未命名来源"


def entity_for(row, lane: str) -> tuple[str, str]:
    if lane == "deploy":
        slug = (S.vendor_slug(row) or "").strip().lower()
        name = clean_text(S.vendor_name(row))
        if slug and slug not in BAD_VENDOR_KEYS and name:
            return slug, name
    host = source_host(row)
    voice = HOST_VOICE.get(host)
    if voice:
        return host, voice
    return host, host


def signal_of(row, lane: str, kind: str) -> str:
    if lane == "deploy":
        if row.get("evidence_quality") == "high" and row.get("customer_named"):
            return "high"
        if row.get("evidence_quality") in ("high", "medium"):
            return "mid"
        return "low"
    if source_host(row) in OFFICIAL_HOSTS:
        return "high"
    return "mid" if kind == "published" else "low"


def summary_for(row, lane: str) -> str:
    fields = {
        "company": ("deployment", "productization", "business_problem"),
        "deploy": ("measured_outcome", "hero_use_case", "business_problem"),
        "people": ("quote", "business_problem", "hero_use_case"),
        "method": ("business_problem", "quote", "hero_use_case"),
    }
    for field in fields.get(lane, ()):
        value = clean_text(row.get(field))
        if value:
            return S.trunc(value, 96)
    return "原文摘要当前未提取。"


def explanation_for(row, lane: str) -> dict:
    title = mapped_title(row)
    happened = summary_for(row, lane)
    if lane == "company":
        happened = title + "。这是厂商把部署能力写成独立组织或产品线的公开动作。"
        why = "这是头部厂商将「部署」作为一条业务的明确信号，标志着 FDE 从支持角色走向战略中心。"
    elif lane == "deploy":
        if row.get("customer_named") and row.get("evidence_quality") == "high":
            why = "具名客户且证据等级为 high，可作为交付现场样本；仍需回到原文核对口径。"
        else:
            why = "这是客户交付材料。案例数量不等于 FDE 编制证据，需结合字段和证据等级阅读。"
    elif lane == "people":
        why = "这是观点材料，不是企业部署声明；它提供行业参与者如何理解 FDE 的语境。"
    else:
        why = "这是方法或岗位材料，帮助理解 FDE 如何工作、如何招；不证明某家客户已照此执行。"
    enterprise = ""
    for field in ("measured_outcome", "deployment", "productization"):
        enterprise = clean_text(row.get(field))
        if enterprise:
            enterprise = S.trunc(enterprise, 180)
            break
    practitioner = clean_text(row.get("fde_role"))
    if not practitioner and lane == "method":
        practitioner = "原文讨论 FDE 的工作方式或岗位要求；具体职责需回到原始材料核对。"
    return {
        "happened": happened,
        "why": why,
        "enterprise": enterprise,
        "practitioner": practitioner,
    }


def event_from_row(row, lane: str, day: str, kind: str) -> dict:
    explanation = explanation_for(row, lane)
    entity_key, entity_name = entity_for(row, lane)
    vendor_slug = (S.vendor_slug(row) or "").strip().lower()
    return {
        "id": int(row["id"]),
        "lane": lane,
        "day": day,
        "date_kind": kind,
        "signal": signal_of(row, lane, kind),
        "title": mapped_title(row),
        "title_short": short_title_for(mapped_title(row), row.get("source_url") or "", lane, clean_text(row.get("customer"))),
        "kicker": entity_name,
        "sub": summary_for(row, lane),
        "host": source_host(row),
        "url": row.get("source_url") or "",
        "doc_type": row.get("doc_type") or "",
        "doc_label": DOC_LABEL.get(row.get("doc_type") or "", row.get("doc_type") or ""),
        "vendor": clean_text(S.vendor_name(row)) if vendor_slug and vendor_slug not in BAD_VENDOR_KEYS else "",
        "vendor_slug": vendor_slug if vendor_slug not in BAD_VENDOR_KEYS else "",
        "customer": clean_text(row.get("customer")),
        "customer_named": bool(row.get("customer_named")),
        "evidence": row.get("evidence_quality") or "",
        "kpi": row.get("kpi_scope") or "",
        "kpi_label": S.kpi_label(row.get("kpi_scope")) if row.get("kpi_scope") else "",
        "outcome": S.trunc(clean_text(row.get("measured_outcome")), 180),
        "product": clean_text(row.get("product")),
        "quote": S.trunc(clean_text(row.get("quote")), 200),
        "href": "/案例/%s" % row["id"],
        "happened": explanation["happened"],
        "why": explanation["why"],
        "enterprise": explanation["enterprise"],
        "practitioner": explanation["practitioner"],
        "entity_key": entity_key,
        "entity_name": entity_name,
    }


def pick_chain(events, predicate, limit=5) -> list[dict]:
    """Most recent `limit` matching events, returned oldest → newest so the chain reads as a timeline."""
    out = []
    for event in sorted(events, key=lambda item: (item.get("day") or "", item["id"]), reverse=True):
        if predicate(event):
            out.append({
                "id": event["id"],
                "title": event["title"],
                "lane": event["lane"],
                "day": event.get("day") or "",
                "entity": event.get("entity_name") or event.get("kicker") or event.get("host") or "",
                "entity_key": event.get("entity_key") or "",
                "short": event.get("title_short") or event["title"],
            })
        if len(out) >= limit:
            break
    out.reverse()
    return out


def _win(events: list[dict], days: int) -> list[dict]:
    start = window_start(days)
    return [event for event in events if event.get("day") and start <= event["day"] <= S.SNAPSHOT]


def pick_default_id(events: list[dict]):
    if not events:
        return None
    non_job = [event for event in events if event.get("info_kind") != "job_posting"]
    pool = non_job or events
    for lane in ("company", "people", "deploy", "method"):
        cand = [event for event in pool if event["lane"] == lane]
        if cand:
            cand.sort(key=lambda event: (event.get("day") or "", event["id"]))
            return cand[-1]["id"]
    return pool[-1]["id"]


def build_changes(events: list[dict], counts: dict, n_fde: int, n_case_study: int) -> list[dict]:
    """30-day default; window-specific copies live in build_changes_by_range."""
    return build_changes_by_range(events, counts, n_fde, n_case_study).get("30") or []


def build_changes_by_range(events: list[dict], counts: dict, n_fde: int, n_case_study: int) -> dict:
    dated = [event for event in events if event.get("day")]
    out = {}
    for days in WINDOW_DAYS:
        win = _win(dated, days)
        jobs = [event for event in win if event.get("info_kind") == "job_posting"]
        company = pick_chain(win, lambda event: event["lane"] == "company", 4)
        deploy = pick_chain(win, lambda event: event["lane"] == "deploy", 5)
        people = pick_chain(
            win,
            lambda event: event["lane"] == "people" or event.get("info_kind") in ("methodology", "engineering_blog", "podcast_episode"),
            4,
        )
        method_jobs = pick_chain(win, lambda event: event.get("info_kind") == "job_posting", 4)
        if days == 7:
            out["7"] = [
                {
                    "num": "1",
                    "title": "这 7 天能上轴的主要是新岗",
                    "body": f"窗口内 {len(win)} 条有日期信号，其中 {len(jobs)} 条是官方招聘板。岗位是弱信号：说明还在招现场编制，不是组织已经落地。",
                    "lanes": ["method"],
                    "chain": method_jobs,
                    "n": len(jobs),
                    "skip_jobs": False,
                },
                {
                    "num": "2",
                    "title": "人才供给被写成公开议题",
                    "body": "Washington Technology 引用 Christian & Timbers：约 1.7 万名 FDE 里，能稳定交出企业 AI 回报的大约 2000 人。Cohere 同期仍在写「建能力、不制造依赖」。",
                    "lanes": ["people"],
                    "chain": pick_chain(win, lambda event: event["lane"] == "people", 4),
                    "n": sum(1 for event in win if event["lane"] == "people"),
                    "skip_jobs": True,
                },
                {
                    "num": "3",
                    "title": "公司动作轨是空的",
                    "body": "这 7 天没有新的组织宣布，部署轨也是空的。30 天窗里是 Blend360 扩编；Palantir 股东信要放到 90 天。",
                    "lanes": ["company", "deploy"],
                    "chain": deploy,
                    "n": len(deploy),
                    "skip_jobs": True,
                },
            ]
        elif days == 30:
            out["30"] = [
                {
                    "num": "1",
                    "title": "窗口内的公司动作是服务商扩编",
                    "body": "Blend360 给出 2027 年 750 人编制目标，这是服务商扩编，不是买方 FDE 组织。Palantir Q2 股东信已滑出这 30 天，见 90 天窗。",
                    "lanes": ["company"],
                    "chain": company,
                    "n": len(company),
                    "skip_jobs": True,
                },
                {
                    "num": "2",
                    "title": "有日期的客户故事集中在工程产能和客服",
                    "body": "窗口内部署轨是 Devin / Writer 的具名客户页。全库交付故事仍是库存营销页居多；只有带发布日的才上轴。",
                    "lanes": ["deploy"],
                    "chain": deploy,
                    "n": len(deploy),
                    "skip_jobs": True,
                },
                {
                    "num": "3",
                    "title": "方法从定义角色写到职业周期",
                    "body": "FDEInterviews 补了退出路径、谈 offer 和九种现场套路。招聘板新岗仍是弱信号，不与这些方法文混成同一条变化。",
                    "lanes": ["people", "method"],
                    "chain": people,
                    "n": len(people),
                    "skip_jobs": True,
                },
            ]
        else:
            out["90"] = [
                {
                    "num": "1",
                    "title": "多家把驻场写成独立编制或伙伴运动",
                    "body": "90 天里 AWS、Microsoft、Databricks 和 OpenAI Deployment Company 收购，都是组织/产品载体宣布。库内 "
                    f"{n_case_study} 条交付故事中，原文写出 FDE 角色的只有 {n_fde} 条。",
                    "lanes": ["company"],
                    "chain": company,
                    "n": len(company),
                },
                {
                    "num": "2",
                    "title": "企业把现场能力用在核心经营环节",
                    "body": "有日期的客户故事落在支付、航司软件、临床指南、营销工作流和客服。这是窗口内样本，不是全行业调查。",
                    "lanes": ["deploy"],
                    "chain": deploy,
                    "n": len(deploy),
                },
                {
                    "num": "3",
                    "title": "从业者口径从定义角色转向现场脏活",
                    "body": "Natalie、Kevin Bai、Colin Jarvis 和 Cohere 把驻场里不写进 JD 的部分讲出来。方法轨上的岗位仍只作弱信号。",
                    "lanes": ["people", "method"],
                    "chain": people,
                    "n": len(people),
                    "skip_jobs": True,
                },
            ]
    return out


def build_ledes(events: list[dict], window_counts: dict) -> dict:
    def n_jobs(days):
        start = window_start(days)
        return sum(
            1
            for event in events
            if event.get("day")
            and start <= event["day"] <= S.SNAPSHOT
            and event.get("info_kind") == "job_posting"
        )

    c7 = window_counts.get("7") or {}
    c30 = window_counts.get("30") or {}
    c90 = window_counts.get("90") or {}
    return {
        "7": (
            f"过去 7 天，有日期的信号共 {c7.get('total', 0)} 条，其中 {n_jobs(7)} 条是招聘板新岗。"
            "硬节点是人才短缺报道和 Cohere 的能力建设文；公司动作轨没有新宣布。"
        ),
        "30": (
            f"过去 30 天共 {c30.get('total', 0)} 条有日期信号。"
            "Blend360 给出 2027 年 750 人编制目标，Cohere 写建能力、不制造依赖；"
            "轴上同时出现有发布日的客户故事和一批官方新岗——岗位仍是弱信号。"
        ),
        "90": (
            f"过去 90 天共 {c90.get('total', 0)} 条有日期信号。"
            "AWS、Microsoft、Databricks 把 FDE 写成组织或伙伴运动；"
            "人物轨补上现场口径；部署轨只收带发布日的客户故事，不是 503 条案例墙。"
        ),
    }


def build_entities(events: list[dict]) -> list[dict]:
    """Return entity seeds; counts and recency are recomputed for the selected window in JS."""
    buckets: dict[str, OrderedDict[str, dict]] = {
        "company": OrderedDict(),
        "voice": OrderedDict(),
        "method": OrderedDict(),
        "role": OrderedDict(),
    }
    for event in events:
        if event["lane"] == "deploy" and event.get("vendor_slug"):
            key = event["vendor_slug"]
            buckets["company"].setdefault(key, {"tab": "company", "key": key, "name": event["vendor"] or key, "event_ids": []})
            buckets["company"][key]["event_ids"].append(event["id"])
        elif event["lane"] == "company":
            key = event.get("entity_key") or event.get("host")
            if key:
                buckets["company"].setdefault(key, {"tab": "company", "key": key, "name": event.get("entity_name") or key, "event_ids": []})
                buckets["company"][key]["event_ids"].append(event["id"])
        elif event["lane"] == "people":
            key = event.get("host") or event.get("entity_key")
            if key:
                buckets["voice"].setdefault(key, {"tab": "voice", "key": key, "name": event.get("entity_name") or key, "event_ids": []})
                buckets["voice"][key]["event_ids"].append(event["id"])
        elif event["lane"] == "method":
            tab = "role" if event["doc_type"] == "job_posting" else "method"
            key = str(event["id"])
            buckets[tab][key] = {"tab": tab, "key": key, "name": event["title"], "event_ids": [event["id"]]}
    return [item for bucket in buckets.values() for item in bucket.values()]


def build_links(events: list[dict]) -> list[dict]:
    """Same-vendor successive dated items. Visual association, not a causal claim."""
    links = []
    seen = set()
    by_vendor: dict[str, list[dict]] = {}
    for event in events:
        # vendor_slug covers company/deploy rows; entity_slug also covers the same org's
        # job postings and people posts, so a Databricks blog can link to Databricks postings.
        slug = (event.get("vendor_slug") or event.get("entity_slug") or "").strip().lower()
        if not slug or slug in BAD_VENDOR_KEYS or not event.get("day"):
            continue
        by_vendor.setdefault(slug, []).append(event)
    for group in by_vendor.values():
        group = sorted(group, key=lambda item: (item["day"], item["id"]))
        for left, right in zip(group, group[1:]):
            key = (left["id"], right["id"])
            if key in seen:
                continue
            seen.add(key)
            kind = "direct" if left["lane"] == right["lane"] else "indirect"
            links.append({"from": left["id"], "to": right["id"], "kind": kind})
    return links


def _world_event_count(cur) -> int:
    try:
        return int(cur.execute("SELECT count(*) FROM world_events").fetchone()[0])
    except Exception:
        return 0


def ui_signal(lane: str, stored: str, host: str, evidence: str, customer_named: bool) -> str:
    if lane == "deploy":
        if evidence == "high" and customer_named:
            return "high"
        if evidence in ("high", "medium"):
            return "mid"
        return "low"
    if stored == "hard" or host in OFFICIAL_HOSTS:
        return "high" if host in OFFICIAL_HOSTS else "mid"
    return "low"


def event_from_world(row, case: dict | None, entity_name: str) -> dict:
    lane = row["lane"]
    host = row["host"] or S.host_of(row["url"] or "")
    info_kind = row["info_kind"] or ""
    title = (row["title_zh"] or row["title"] or HOST_VOICE.get(host) or host or "未命名来源").strip()
    mapped = title_from_url(row["url"] or "")
    if mapped:
        title = mapped
    slug = (row["entity_slug"] or "").strip()
    vendor_slug = ""
    vendor = ""
    customer = ""
    customer_named = False
    evidence = row["evidence"] or ""
    kpi = ""
    outcome = ""
    product = ""
    quote = ""
    case_id = row["source_case_id"]
    if case:
        customer = clean_text(case.get("customer"))
        customer_named = bool(case.get("customer_named"))
        evidence = evidence or (case.get("evidence_quality") or "")
        kpi = case.get("kpi_scope") or ""
        outcome = S.trunc(clean_text(case.get("measured_outcome")), 180)
        product = clean_text(case.get("product"))
        quote = S.trunc(clean_text(case.get("quote")), 200)
        vendor_slug = (S.vendor_slug(case) or "").strip().lower()
        if vendor_slug in BAD_VENDOR_KEYS:
            vendor_slug = ""
        vendor = clean_text(S.vendor_name(case)) if vendor_slug else ""
    if not vendor_slug and slug and lane in ("company", "deploy"):
        vendor_slug = slug
        vendor = entity_name or HOST_VOICE.get(host) or slug
    entity_key = vendor_slug or slug or host
    name = entity_name or vendor or HOST_VOICE.get(host) or host
    if info_kind == "job_posting" and not mapped:
        title = job_axis_label(name, row["title"] or title)
    href = ("/案例/%s" % case_id) if case_id else (row["url"] or "")
    doc_type = "case_study" if info_kind == "dated_case_study" else info_kind
    signal = ui_signal(lane, row["signal"] or "", host, evidence, customer_named)
    return {
        "id": int(row["id"]),
        "lane": lane,
        "day": row["day"],
        "date_kind": row["date_kind"],
        "signal": signal,
        "title": title,
        "title_short": short_title_for(title, row["url"] or "", lane, customer),
        "kicker": name,
        "sub": S.trunc(clean_text(row["happened_zh"]), 96) or "原文摘要当前未提取。",
        "host": host,
        "url": row["url"] or "",
        "doc_type": doc_type,
        "doc_label": KIND_LABEL.get(info_kind) or DOC_LABEL.get(doc_type) or info_kind,
        "vendor": vendor,
        "vendor_slug": vendor_slug,
        "customer": customer,
        "customer_named": customer_named,
        "evidence": evidence,
        "kpi": kpi,
        "kpi_label": S.kpi_label(kpi) if kpi else "",
        "outcome": outcome,
        "product": product,
        "quote": quote,
        "href": href,
        "happened": clean_text(row["happened_zh"]) or title,
        "why": clean_text(row["why_zh"]) or "",
        "enterprise": clean_text(row["enterprise_zh"] or "") or outcome,
        "practitioner": clean_text(row["practitioner_zh"] or ""),
        "entity_key": entity_key,
        "entity_slug": slug,
        "entity_name": name,
        "info_kind": info_kind,
    }


# 屏蔽来源：这些 host 的事件不上世界动态轴 / 3D 沙盘（平台运营决策 2026-09-03）。
# 只影响展示出口（worldview.load_world），原始库与 ingest 不动。
EXCLUDED_HOSTS = (
    "fdeinterviews.com",
    "databricks.com",
    "job-boards.greenhouse.io/databricks",
)


def _host_excluded(host: str | None) -> bool:
    h = (host or "").lower()
    return any(h == x or h.endswith("." + x) or x in h for x in EXCLUDED_HOSTS)


def load_world_from_events(cur) -> list[dict]:
    start = window_start(90)
    rows = list(
        cur.execute(
            """SELECT e.*, ent.name AS entity_name
               FROM world_events e
               LEFT JOIN world_entities ent ON ent.slug=e.entity_slug
               WHERE e.day IS NOT NULL
                 AND e.date_kind IN ('published','modified')
                 AND e.day >= ? AND e.day <= ?
               ORDER BY e.day, e.id""",
            (start, S.SNAPSHOT),
        )
    )
    rows = [r for r in rows if not _host_excluded(r["host"])]
    case_ids = [r["source_case_id"] for r in rows if r["source_case_id"]]
    cases = {}
    if case_ids:
        fetched = S.fetch_cases(
            cur,
            "x.id IN (%s)" % ",".join("?" * len(case_ids)),
            tuple(case_ids),
            "x.id",
        )
        cases = {int(r["id"]): r for r in fetched}
    events = []
    for row in rows:
        case = cases.get(int(row["source_case_id"])) if row["source_case_id"] else None
        if row["lane"] == "deploy" and case and not case.get("customer_named"):
            continue
        events.append(event_from_world(row, case, row["entity_name"] or ""))
    return cap_deploy_hosts(events)


def cap_deploy_hosts(events: list[dict], cap: int = DEPLOY_HOST_CAP) -> list[dict]:
    """Keep the newest `cap` deploy events per host so one vendor cannot fill the lane."""
    deploy = [e for e in events if e.get("lane") == "deploy"]
    other = [e for e in events if e.get("lane") != "deploy"]
    deploy.sort(key=lambda e: (e.get("day") or "", e.get("id") or 0), reverse=True)
    kept = []
    counts: dict[str, int] = {}
    for event in deploy:
        host = event.get("host") or event.get("vendor_slug") or ""
        if counts.get(host, 0) >= cap:
            continue
        counts[host] = counts.get(host, 0) + 1
        kept.append(event)
    return other + kept


def load_world_from_cases(cur) -> tuple[list[dict], int]:
    rows = S.fetch_cases(cur, "x.doc_type IN ('case_study','methodology','opinion','job_posting')", (), "x.id")
    rows = S.dedupe_by_url(rows)
    events = []
    eligible = 0
    for row in rows:
        doc_type = row.get("doc_type") or ""
        if doc_type not in ALLOWED_DOC_TYPES:
            continue
        lane = classify_lane(row)
        if not lane:
            continue
        if lane == "deploy" and not row.get("customer_named"):
            continue
        day, kind = date_status(row)
        if not day or day < window_start(90) or day > S.SNAPSHOT:
            continue
        eligible += 1
        events.append(event_from_row(row, lane, day, kind))
    return events, eligible


def load_world(cur) -> dict:
    counts = S.load_counts(cur)
    studies = S.fetch_cases(cur, "x.doc_type='case_study'", (), "x.id")
    pack = S.study_pack(studies)
    if _world_event_count(cur):
        events = load_world_from_events(cur)
        eligible = len(events)
    else:
        events, eligible = load_world_from_cases(cur)

    events.sort(key=lambda event: (event.get("day") or "9999-99-99", LANE_ORDER.get(event["lane"], 9), event["id"]))
    collapsed = []
    seen = set()
    for event in events:
        key = (event["title"], event["day"], event["lane"])
        if key in seen:
            continue
        seen.add(key)
        collapsed.append(event)
    events = collapsed

    n_people_method = sum(1 for event in events if event["lane"] in ("people", "method"))
    window_counts = {}
    default_by_range = {}
    for days in WINDOW_DAYS:
        start = window_start(days)
        window_counts[str(days)] = {
            "total": sum(1 for event in events if start <= event["day"] <= S.SNAPSHOT),
            "by_lane": {
                lane: sum(1 for event in events if event["lane"] == lane and start <= event["day"] <= S.SNAPSHOT)
                for lane, _zh, _en in LANES
            },
        }
        default_by_range[str(days)] = pick_default_id(_win(events, days))
    default_id = default_by_range.get("30") or default_by_range.get("90") or (
        events[-1]["id"] if events else None
    )
    changes_by_range = build_changes_by_range(
        events, {"n_core": counts["n_core"], "n_people_method": n_people_method}, pack["n_fde"], counts["n_case_study"]
    )
    ledes = build_ledes(events, window_counts)
    dates_meta = S.load_dates()
    n_any_dates = int(dates_meta.get("n_with_any_date") or 0)
    try:
        n_undated = int(
            cur.execute(
                "SELECT count(*) FROM world_events WHERE day IS NULL OR date_kind='collected'"
            ).fetchone()[0]
        )
    except Exception:
        n_undated = max(0, counts["n_cases"] - eligible)
    return {
        "snapshot": S.SNAPSHOT,
        "windows": {str(days): window_start(days) for days in WINDOW_DAYS},
        "window_counts": window_counts,
        "counts": {
            "n_cases": counts["n_cases"],
            "n_case_study": counts["n_case_study"],
            "n_named": counts["n_named"],
            "n_fde": pack["n_fde"],
            "n_core": counts["n_core"],
            "n_dated_events": len(events),
            "n_published_cs": pack["n_published"],
            "n_any_dates": n_any_dates,
            "n_undated": n_undated,
            "n_people_method": n_people_method,
        },
        "github": S.github_url(cur),
        "lanes": [{"id": key, "zh": zh, "en": en} for key, zh, en in LANES],
        "events": events,
        "links": build_links(events),
        "changes": changes_by_range.get("30") or [],
        "changes_by_range": changes_by_range,
        "ledes": ledes,
        "entities": build_entities(events),
        "default_id": default_id,
        "default_by_range": default_by_range,
    }


def json_tag(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    raw = raw.replace("<", "\\u003c")
    return f'<script type="application/json" id="world-data">{raw}</script>'


METHOD_NEEDLES = (
    "fde-war-stories-nine-patterns",
    "how-forward-deployed-engineers-work",
    "hire-forward-deployed",
    "fdepod.substack.com/p/fde-101",
    "fde-exit-options-career-trajectory",
    "what-it-means-to-be-a-forward-deployed",
)


def reading_item(row, *, internal=False) -> str:
    title = mapped_title(row)
    if internal:
        url = S.href("/案例/%s" % row.get("id"))
        ext = ""
    else:
        url = row.get("source_url") or S.href("/案例/%s" % row.get("id"))
        ext = ' target="_blank" rel="noopener noreferrer"' if row.get("source_url") else ""
    sub = " · ".join(
        x for x in (row.get("day"), DOC_LABEL.get(row.get("doc_type") or ""), row.get("host")) if x
    )
    return (
        f'<a class="wm-item" href="{S.esc(url)}"{ext}><b>{S.esc(title)}</b>'
        + (f"<span>{S.esc(sub)}</span>" if sub else "")
        + "</a>"
    )


def pick_by_url(rows, needles, limit=4):
    picked = []
    rest = []
    for row in rows:
        url = (row.get("source_url") or "").lower()
        if any(needle in url for needle in needles):
            picked.append(row)
        else:
            rest.append(row)
        if len(picked) >= limit:
            return picked[:limit]
    for row in rest:
        picked.append(row)
        if len(picked) >= limit:
            break
    return picked[:limit]


def reading_layer(cur, counts) -> str:
    studies = S.fetch_cases(cur, "x.doc_type='case_study'", (), "x.id")
    pack = S.study_pack(studies)
    featured = S.load_featured(cur)
    peers = S.pick_peers(featured, 3)
    dated, undated = S.commentary_timeline(cur)
    methods = pick_by_url(
        [
            r
            for r in dated + undated
            if r.get("doc_type") != "job_posting"
            and any(needle in source_blob(r) for needle, _label in TITLE_MAP)
        ],
        METHOD_NEEDLES,
        4,
    )
    field = list(reversed(dated))[:4]
    peer_html = "".join(S.case_cite(r) for r in peers)
    if not peer_html:
        peer_html = '<p class="wm-empty">没有同时满足「具名 · high · 核心厂商 · 有结果」的条目。</p>'
    method_html = "".join(reading_item(r) for r in methods) or '<p class="wm-empty">方法目录是空的。</p>'
    field_html = "".join(reading_item(r) for r in field) or '<p class="wm-empty">没有带发布日的评论。</p>'
    n = pack["n"]
    n_fde = pack["n_fde"]
    n_feat = len(featured)
    n_out = pack["n_outcome"]
    handoff = S.pct(pack["fill"]["customer_handoff"], n)
    return f"""
  <section class="world-more" id="world-more" aria-labelledby="world-more-title">
    <header class="world-more-head">
      <p class="world-more-k">观察站 · 开源学习社区</p>
      <h2 id="world-more-title">这份库对落地意味着什么</h2>
      <p>上面的时间轴只收录有发布日的公开变化。下面是同一份 {S.esc(S.SNAPSHOT)} 快照上的判断，不是第二套新闻，也不是咨询方案。</p>
    </header>
    <div class="world-read">
      <article class="wm-col">
        <p class="k">给负责人</p>
        <h3>落地：先定范围</h3>
        <p>全库 <b>{n}</b> 条交付现场，原文写了现场编制的 <b>{n_fde}</b> 条（{S.pct(n_fde, n)}）。能当样板的（核心厂商 × 具名客户 × 证据 high × 有结果）<b>{n_feat}</b> 条。</p>
        <ol class="wm-q">
          <li>买产品，还是买驻场？公开页上不是同一件事。</li>
          <li>要不要为此建编制？库里几乎没有完整组队样本。</li>
          <li>口径能不能当样板？有结果 {n_out} / {n}，交接只写了 {handoff}。</li>
        </ol>
        <p class="wm-label">三单样板，点进去核对原文</p>
        <div class="list">{peer_html}</div>
        <p class="wm-go"><a href="/落地">落地读法全文</a></p>
      </article>
      <article class="wm-col">
        <p class="k">怎么被写出</p>
        <h3>方法：角色和流程</h3>
        <p>岗位变化仍在本页方法轨上轴，这里不重复招聘列表。下面是库里已有的讲解页。</p>
        <div class="list">{method_html}</div>
        <p class="wm-go"><a href="/方法">方法目录</a></p>
      </article>
      <article class="wm-col">
        <p class="k">给从业者</p>
        <h3>别把营销页当本周动态</h3>
        <p>近态要读有发布日的评论线。{counts['n_case_study']} 条客户故事大多是库存营销页，{counts['n_fde']} 条原文自称编制。</p>
        <div class="list">{field_html}</div>
        <p class="wm-go"><a href="/现场">现场读法</a></p>
      </article>
    </div>
    <p class="world-more-field">社区启动期只走 GitHub 提交来源 / 补日期，不编活跃。题库练习还没做成站内产品。</p>
  </section>
"""


def render_world(cur) -> str:
    data = load_world(cur)
    counts = data["counts"]
    github = data.get("github") or ""
    issue_url = (github.rstrip("/") + "/issues/new") if github else ""
    more_html = reading_layer(cur, counts)
    inner = f"""
<div class="world">
  <div class="world-layout">
    <main class="world-main">
      <section class="world-intro" aria-labelledby="world-title">
        <div class="world-intro-copy">
          <p class="world-tagline">{S.esc(S.SITE_TAGLINE)}</p>
          <h1 id="world-title">FDE 世界正在发生什么</h1>
          <p class="lede" data-world-lede>过去 30 天，Blend360 给出扩编目标，Cohere 写建能力、不制造依赖；轴上同时出现有发布日的客户故事和官方新岗——岗位仍是弱信号。</p>
        </div>
        <div class="world-intro-tools">
          <div class="range" role="radiogroup" aria-label="时间窗口">
            <button type="button" data-range="7" aria-pressed="false">7 天</button>
            <button type="button" data-range="30" class="on" aria-pressed="true">30 天</button>
            <button type="button" data-range="90" aria-pressed="false">90 天</button>
          </div>
          <p class="world-note"><span class="signal-dot" aria-hidden="true"></span>本期快照 {S.esc(S.SNAPSHOT)} <span class="info-dot" title="无明确日期的材料不进入时间轴">i</span><a class="world-3d-link" href="/world3d" title="同一份数据的立体沙盘">立体视图 <img src="/static/icons/arrow-right.svg" alt="" aria-hidden="true"/></a><a class="world-read-link" href="#world-rooms">其他内容</a></p>
        </div>
      </section>

      <p class="ask-hit" id="world-hit" hidden></p>
      <section class="world-board-wrap" aria-label="FDE 世界动态时间轴">
        <div class="world-board" id="world-board">
          <div class="lanes" id="world-lanes"></div>
          <svg class="world-links" id="world-links" aria-hidden="true"></svg>
          <div class="axis" id="world-axis" aria-hidden="true"></div>
        </div>
        <div class="legend" aria-label="时间轴说明">
          <span class="legend-label">信号强度</span>
          <span><i class="sg sg-lo"></i>低</span>
          <span><i class="sg sg-mid"></i>中</span>
          <span><i class="sg sg-hi"></i>高</span>
          <span class="legend-sep"></span>
          <span class="legend-label">关联影响</span>
          <span><i class="ln ln-direct"></i>直接影响</span>
          <span><i class="ln ln-indirect"></i>间接影响</span>
          <span class="legend-sep"></span>
          <span class="legend-label">来源状态</span>
          <span><i class="st st-pub"></i>已发布日期</span>
          <span><i class="st st-mod"></i>发布日期待补</span>
          <span><i class="st st-col"></i>仅收录日期</span>
        </div>
      </section>

      <section class="world-askbar" aria-label="本地快照提问">
        <form class="ask" id="world-ask" action="#" method="get">
          <label class="ask-q" for="world-q"><img class="ask-spark" src="/static/icons/sparkles.svg" alt="" aria-hidden="true"/><input id="world-q" name="q" maxlength="200" placeholder="问这个世界：例如，哪些公司正在把 FDE 做成长周期组织能力？"/></label>
          <button type="submit" class="ask-go" aria-label="在本地快照中查找"><img src="/static/icons/arrow-right.svg" alt="" aria-hidden="true"/></button>
        </form>
        <div class="ask-lens" role="radiogroup" aria-label="AI 解释视角">
          <span class="ask-lens-k">AI 解释视角</span>
          <button type="button" data-lens="boss" class="on" aria-pressed="true">决策者</button>
          <button type="button" data-lens="field" aria-pressed="false">从业者</button>
        </div>
      </section>
    </main>

    <aside class="world-panel" id="world-panel" aria-label="动态证据详情"></aside>
  </div>

  <nav class="world-rooms" id="world-rooms" aria-label="站内其他内容">
    <p class="world-rooms-k">沙盘到此为止。落地、现场、案例、方法从这里进：</p>
    <div class="world-rooms-list">
      <a href="/落地"><b>落地</b><span>给负责人：先定范围，再翻样板</span></a>
      <a href="/现场"><b>现场</b><span>给从业者：有发布日的评论和方法</span></a>
      <a href="/案例"><b>部署证据</b><span>559 条案例目录，一单两种读法</span></a>
      <a href="/方法"><b>方法</b><span>FDE 是什么、怎么干活、怎么招</span></a>
      <a href="/world3d"><b>立体沙盘</b><span>同一份动态数据的 3D 视图，不是另一套库</span></a>
    </div>
  </nav>

  <section class="world-below">
    <article class="below-col changes">
      <h2>AI 识别的三条变化</h2>
      <p class="below-note">基于 30 天动态信号的结构化洞察</p>
      <ol class="change-list" id="world-changes"></ol>
    </article>
    <article class="below-col entities">
      <h2>关注实体 <span>（自定义关注与追踪）</span></h2>
      <div class="ent-tabs" role="tablist" aria-label="关注实体分类">
        <button type="button" data-ent="company" class="on" role="tab" aria-selected="true">公司</button>
        <button type="button" data-ent="voice" role="tab" aria-selected="false">人物</button>
        <button type="button" data-ent="method" role="tab" aria-selected="false">方法/框架</button>
        <button type="button" data-ent="role" role="tab" aria-selected="false">岗位</button>
      </div>
      <div class="ent-list" id="world-entities"></div>
      <p class="ent-manage"><a href="/案例">管理关注列表 <img src="/static/icons/arrow-right.svg" alt="" aria-hidden="true"/></a></p>
    </article>
    <article class="below-col cobuild">
      <h2>共同建设 {S.esc(WORLD_BRAND)}</h2>
      <ul class="cobuild-list">
        <li><span class="cobuild-icon ico-submit" aria-hidden="true"><img src="/static/icons/file-plus-2.svg" alt=""/></span><div><b>提交动态来源</b><span>推荐官方页面、实践文章、部署故事、招聘页、视频等。</span></div>{S.ext_link(issue_url, "去提交") if issue_url else '<span class="link-muted">GitHub 地址未配置</span>'}</li>
        <li><span class="cobuild-icon ico-date" aria-hidden="true"><img src="/static/icons/calendar-days.svg" alt=""/></span><div><b>补充发布日期</b><span>帮助补全缺失的「原始发布日期」与「收录日期」。</span></div>{S.ext_link(issue_url, "去补充") if issue_url else '<span class="link-muted">GitHub 地址未配置</span>'}</li>
        <li><span class="cobuild-icon ico-fix" aria-hidden="true"><img src="/static/icons/circle-check.svg" alt=""/></span><div><b>纠正实体关系</b><span>修正公司、方法、岗位、人物之间的关系。</span></div>{S.ext_link(issue_url, "去纠正") if issue_url else '<span class="link-muted">GitHub 地址未配置</span>'}</li>
      </ul>
    </article>
  </section>

{more_html}

  <section class="world-foot" aria-label="来源与边界说明">
    <div class="foot-title"><h2>来源与边界说明</h2></div>
    <div><h3>当前静态资料库（本地）</h3><p><b>{counts['n_case_study']}</b> 个客户 / 交付故事；仅 <b>{counts['n_fde']}</b> 条明确提及 FDE。</p></div>
    <div class="foot-dynamic"><img src="/static/icons/share-2.svg" alt="" aria-hidden="true"/><div><h3>动态层（本页）</h3><p>持续抓取官方页面、实践文章、部署故事、招聘页、演讲 / 视频等，并由 AI 聚成有意义的变化与关系。</p></div></div>
    <div><h3>数据口径</h3><p data-world-window>时间窗口：最近 30 天（{S.esc(data['windows']['30'])} – {S.esc(S.SNAPSHOT)}）<br/>时区：UTC+8<br/><a class="foot-link" href="/落地">落地读法</a> · <a class="foot-link" href="/现场">现场读法</a> · <a class="foot-link" href="/方法">方法目录</a></p></div>
  </section>
</div>
{json_tag(data)}
<script src="/static/world.js" defer></script>
"""
    return S.shell(
        "世界动态 · %s" % WORLD_BRAND,
        "世界动态",
        inner,
        github,
        extra_head='<link rel="stylesheet" href="/static/world.css"/>',
        body_class="world-page",
        skip_wrap=True,
        page_path="/",
    )
