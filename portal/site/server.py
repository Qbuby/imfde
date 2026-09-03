# -*- coding: utf-8 -*-
"""imfde.ai portal. Stdlib only. GET queries fde.db. Bind 0.0.0.0:8850.

Routes:
  /           world-dynamics homepage (portal/fde.png)
  /世界动态   alias of /
  /world      alias of /
  /落地       boss reading of the same snapshot
  /现场       practitioner reading + dated commentary
  /案例       item-by-item catalog (nav label: 部署证据)
  /案例/<id>  case detail (落地读法 / 现场读法)
  /方法       methodology, opinion, L1 loop
"""
from __future__ import annotations

import html
import json
import mimetypes
import re
import sqlite3
import traceback
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

HOST = "0.0.0.0"
PORT = 8850
SITE_DOMAIN = "imfde.ai"
SITE_ORIGIN = "https://imfde.ai"
SITE_NAME = "imfde.ai"
SITE_TAGLINE = "The Open Framework for Forward-Deployed AI"
SITE_DIR = Path(__file__).resolve().parent
PORTAL_DIR = SITE_DIR.parent
AI_DIR = PORTAL_DIR.parent
DB_PATH = PORTAL_DIR / "fde.db"
STATIC_DIR = SITE_DIR / "static"
CSS_PATH = STATIC_DIR / "home.css"
SNAPSHOT_PATH = AI_DIR / "FDE门户.html"
DATES_PATH = PORTAL_DIR / "source_dates.json"

REPORT_PATH = PORTAL_DIR / "world_ingest_report.json"


def _snapshot_day() -> str:
    """Snapshot day = last ingest run (world_ingest_report.json); windows end here."""
    try:
        day = json.loads(REPORT_PATH.read_text(encoding="utf-8")).get("snapshot") or ""
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            return day
    except (OSError, ValueError):
        pass
    return "2026-08-29"


SNAPSHOT = _snapshot_day()
CORE_VENDORS = (
    "palantir",
    "openai",
    "harvey",
    "c3-ai",
    "cognition",
    "databricks",
    "anthropic",
    "sierra",
    "hebbia",
    "glean",
)
PRODUCT_STORY_VENDORS = ("intercom", "writer", "cresta", "moveworks", "abridge")
KPI_LABELS = {
    "narrative": "实测结果",
    "hero_only": "hero 条",
    "goal": "目标",
    "projected": "预测",
    "system_scale_not_kpi": "系统规模",
}
DIRTY_FLAGS = frozenset({"leftover_template", "hub_kpi_not_on_page"})
INDUSTRY_BUCKETS = (
    ("医疗健康", ("health", "hospital", "clinic", "medical", "pharma", "pediatric", "physician", "wellness", "life science", "医疗", "医院", "药房", "儿科", "临床", "医生")),
    ("金融保险", ("financ", "fintech", "bank", "insur", "credit", "金融", "银行", "保险", "证券", "支付")),
    ("法律合规", ("law", "legal", "attorney", "律师", "法律", "合规")),
    ("零售电商", ("retail", "e-commerce", "ecommerce", "commerce", "零售", "电商")),
    ("教育", ("educat", "university", "school", "教育", "大学")),
    ("政府公共", ("govern", "public sector", "defense", "federal", "政府", "国防", "公共")),
    ("能源", ("energy", "oil", "gas", "utility", "petroleum", "能源", "石油", "电力")),
    ("制造工业", ("manufactur", "industrial", "supply chain", "aviation", "automotive", "制造", "工业", "供应链", "航空", "汽车")),
    ("软件科技", ("software", "technolog", "saas", "cyber", "cloud", "软件", "科技", "网络安全")),
)
CRAFT_HOSTS = (
    "fdeinterviews.com",
    "fdepod.substack.com",
    "fourthage.substack.com",
    "linkedin.com",
    "www.linkedin.com",
    "fde.academy",
)
NAV = (
    ("世界动态", "/世界动态"),
    ("落地", "/落地"),
    ("现场", "/现场"),
    ("部署证据", "/案例"),
    ("方法", "/方法"),
)
CASE_FIELDS = """
    x.id, x.source_url, x.source_title, x.tier, x.doc_type,
    x.industry, x.business_problem, x.existing_workflow, x.pain_point,
    x.discovery_method, x.why_ai, x.hero_use_case, x.data_sources,
    x.integration, x.ai_model, x.agent_workflow, x.human_in_the_loop,
    x.evaluation, x.deployment, x.time_to_production, x.business_kpi,
    x.measured_outcome, x.failure_iteration, x.productization,
    x.customer_handoff, x.fde_role, x.quote, x.evidence_quality,
    x.evidence_note, x.product, x.kpi_scope, x.raw_company_text,
    cu.name AS customer, cu.named AS customer_named,
    (
      SELECT GROUP_CONCAT(c.slug, ',')
      FROM case_companies cc JOIN companies c ON c.slug=cc.company_slug
      WHERE cc.case_id=x.id AND cc.role='vendor'
    ) AS vendor_slugs,
    (
      SELECT GROUP_CONCAT(c.name, ',')
      FROM case_companies cc JOIN companies c ON c.slug=cc.company_slug
      WHERE cc.case_id=x.id AND cc.role='vendor'
    ) AS vendor_names
"""


def esc(value) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def trunc(text, n=140) -> str:
    s = " ".join((text or "").split())
    if len(s) <= n:
        return s
    cut = s[:n]
    for sep in ("。", "；", ";", ".", "，", ",", " "):
        i = cut.rfind(sep)
        if i >= n // 2:
            cut = cut[: i + (0 if sep == " " else 1)]
            break
    return cut.rstrip("，,;；、 ") + "…"


def nonempty(value) -> bool:
    return bool(value and str(value).strip())


def host_of(url: str) -> str:
    if not url:
        return ""
    try:
        h = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    if h.startswith("www."):
        h = h[4:]
    return h


def is_craft_host(url: str) -> bool:
    h = host_of(url)
    return h in CRAFT_HOSTS or h.endswith(".linkedin.com")


def connect():
    uri = "file:" + DB_PATH.as_posix() + "?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def qs_get(qs, *keys, default=""):
    for key in keys:
        vals = qs.get(key) or []
        if vals and str(vals[0]).strip():
            return str(vals[0]).strip()
    return default


def qs_int(qs, *keys, default=1):
    raw = qs_get(qs, *keys, default="")
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return default
    return n if n > 0 else default


def href(path: str, **params) -> str:
    clean = {k: v for k, v in params.items() if v not in (None, "", False)}
    if not clean:
        return path
    return path + "?" + urlencode(clean, encoding="utf-8", safe="")


def bucket_of(industry: str | None) -> str:
    s = (industry or "").lower()
    if not s:
        return "其他"
    for name, kws in INDUSTRY_BUCKETS:
        if any(k.lower() in s for k in kws):
            return name
    return "其他"


def in_bucket(industry: str | None, bucket: str) -> bool:
    if not bucket:
        return True
    return bucket_of(industry) == bucket


def kpi_class(scope) -> str:
    return scope if scope in KPI_LABELS else "none"


def kpi_label(scope) -> str:
    return KPI_LABELS.get(scope) or "未标口径"


def vendor_slug(row) -> str:
    slugs = (row.get("vendor_slugs") or "").split(",")
    return slugs[0] if slugs and slugs[0] else ""


def vendor_name(row) -> str:
    names = (row.get("vendor_names") or "").split(",")
    if names and names[0]:
        return names[0]
    return row.get("raw_company_text") or "未标厂商"


def has_fde_role(row) -> bool:
    return nonempty(row.get("fde_role"))


def annotate(rows):
    out = []
    for raw in rows:
        row = dict(raw)
        row["host"] = host_of(row.get("source_url") or "")
        row["bucket"] = bucket_of(row.get("industry"))
        out.append(row)
    return out


def dedupe_by_url(rows):
    seen = set()
    out = []
    for r in rows:
        u = (r.get("source_url") or "").strip().lower()
        key = u if u else "id:%s" % r.get("id")
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def load_flags(cur, ids) -> dict:
    if not ids:
        return {}
    q = ",".join("?" * len(ids))
    flags = {}
    for r in cur.execute(
        "SELECT case_id, flag, reason FROM clean_flags WHERE case_id IN (%s)" % q,
        ids,
    ):
        flags.setdefault(r["case_id"], []).append(dict(r))
    return flags


def outcome_ok(row, flags_map) -> bool:
    dirty = {f["flag"] for f in flags_map.get(row.get("id"), [])}
    return not (dirty & DIRTY_FLAGS)


def fetch_cases(cur, where="1=1", args=(), order="x.id"):
    sql = (
        "SELECT %s FROM cases x LEFT JOIN customers cu ON cu.id=x.customer_id WHERE %s ORDER BY %s"
        % (CASE_FIELDS, where, order)
    )
    return annotate([dict(r) for r in cur.execute(sql, args)])


def pick_peers(rows, n=3):
    ranked = sorted(
        rows,
        key=lambda r: (0 if r.get("kpi_scope") == "narrative" else 1, r.get("id") or 0),
    )
    picked = []
    used = set()
    for r in ranked:
        b = r.get("bucket") or "其他"
        if b in used:
            continue
        picked.append(r)
        used.add(b)
        if len(picked) == n:
            return picked
    for r in ranked:
        if r in picked:
            continue
        picked.append(r)
        if len(picked) == n:
            break
    return picked


def github_url(cur) -> str:
    # 内容区已并入 imfde 门户仓库；开源仓库指向本平台仓库，不再指向交接方私有源。
    return "https://github.com/Qbuby/imfde"


def load_counts(cur) -> dict:
    n_cases = cur.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    n_cs = cur.execute("SELECT COUNT(*) FROM cases WHERE doc_type='case_study'").fetchone()[0]
    n_named = cur.execute("SELECT COUNT(*) FROM customers WHERE named=1").fetchone()[0]
    n_community = cur.execute(
        "SELECT COUNT(*) FROM cases WHERE doc_type IN ('discussion','methodology','opinion')"
    ).fetchone()[0]
    n_fde = cur.execute(
        "SELECT COUNT(*) FROM cases WHERE doc_type='case_study' AND TRIM(IFNULL(fde_role,''))!=''"
    ).fetchone()[0]
    placeholders = ",".join("?" * len(CORE_VENDORS))
    n_core = cur.execute(
        """
        SELECT COUNT(*) FROM cases x
        JOIN customers cu ON cu.id=x.customer_id
        WHERE x.doc_type='case_study'
          AND cu.named=1
          AND x.evidence_quality='high'
          AND TRIM(IFNULL(x.measured_outcome,''))!=''
          AND EXISTS (
            SELECT 1 FROM case_companies cc
            WHERE cc.case_id=x.id AND cc.role='vendor'
              AND cc.company_slug IN (%s)
          )
        """
        % placeholders,
        CORE_VENDORS,
    ).fetchone()[0]
    return {
        "n_cases": n_cases,
        "n_case_study": n_cs,
        "n_named": n_named,
        "n_community": n_community,
        "n_fde_role": n_fde,
        "n_core": n_core,
    }


def load_featured(cur, *, vendors=CORE_VENDORS, evidence="high", named=True):
    placeholders = ",".join("?" * len(vendors)) if vendors else ""
    where = ["x.doc_type='case_study'"]
    args = []
    if named:
        where.append("cu.named=1")
    if evidence:
        where.append("x.evidence_quality=?")
        args.append(evidence)
    where.append("TRIM(IFNULL(x.measured_outcome,''))!=''")
    if vendors:
        where.append(
            "EXISTS (SELECT 1 FROM case_companies cc WHERE cc.case_id=x.id "
            "AND cc.role='vendor' AND cc.company_slug IN (%s))" % placeholders
        )
        args.extend(vendors)
    order = "CASE x.kpi_scope WHEN 'narrative' THEN 0 ELSE 1 END, x.id"
    return fetch_cases(cur, " AND ".join(where), args, order)


def load_briefing(cur):
    rows = annotate(
        dedupe_by_url(
            [
                dict(r)
                for r in cur.execute(
                    """
            SELECT id, source_url, source_title, business_problem, doc_type, quote
            FROM cases
            WHERE doc_type IN ('opinion', 'methodology')
              AND (
                source_url LIKE '%a16z%'
                OR source_url LIKE '%pragmatic%'
                OR source_url LIKE '%openai%'
                OR source_url LIKE '%palantir%'
                OR source_title LIKE '%Frontier%'
                OR source_title LIKE '%heats up%'
                OR source_title LIKE '%Deployment%'
              )
            ORDER BY CASE doc_type WHEN 'opinion' THEN 0 ELSE 1 END, id
            """
                )
            ]
        )
    )
    return [r for r in rows if not is_craft_host(r.get("source_url") or "")]


def load_discussions(cur):
    return annotate(
        dedupe_by_url(
            [
                dict(r)
                for r in cur.execute(
                    """
            SELECT id, source_url, source_title, business_problem, doc_type
            FROM cases WHERE doc_type='discussion' ORDER BY id
            """
                )
            ]
        )
    )


def load_framing(cur):
    rows = annotate(
        dedupe_by_url(
            [
                dict(r)
                for r in cur.execute(
                    """
            SELECT id, source_url, source_title, business_problem, doc_type
            FROM cases
            WHERE doc_type IN ('methodology','opinion','job_posting')
            ORDER BY CASE doc_type
              WHEN 'opinion' THEN 0
              WHEN 'methodology' THEN 1
              ELSE 2 END, id
            """
                )
            ]
        )
    )
    prefer = []
    rest = []
    keys = (
        "forward-deployed-engineers",
        "demos-to-deals",
        "services-led-growth",
        "trading-margin",
        "deployment-company",
        "deployment-lifecycle",
        "what-is-a-forward-deployed",
        "what-it-means-to-be",
        "hire-forward-deployed",
        "introducing-openai-frontier",
        "openai.com/business/frontier",
    )
    for r in rows:
        url = (r.get("source_url") or "").lower()
        if any(k in url for k in keys):
            prefer.append(r)
        else:
            rest.append(r)
    return (prefer + rest)[:8]


def load_topics(cur):
    return [
        dict(r)
        for r in cur.execute(
            "SELECT slug, name_zh, name_en, level FROM topics "
            "WHERE taxonomy='aifde' ORDER BY level, sort, slug"
        )
    ]


def load_job_postings(cur):
    return annotate(
        dedupe_by_url(
            [
                dict(r)
                for r in cur.execute(
                    """
            SELECT id, source_url, source_title, business_problem, doc_type
            FROM cases WHERE doc_type='job_posting' ORDER BY id
            """
                )
            ]
        )
    )


def load_fde_role_cases(cur, limit=8):
    return fetch_cases(
        cur,
        "x.doc_type='case_study' AND TRIM(IFNULL(x.fde_role,''))!=''",
        (),
        "x.id",
    )[:limit]


def load_vendors(cur):
    return [
        dict(r)
        for r in cur.execute(
            """
        SELECT cc.company_slug AS slug, c.name, COUNT(*) AS n
        FROM case_companies cc
        JOIN cases x ON x.id=cc.case_id
        JOIN companies c ON c.slug=cc.company_slug
        WHERE x.doc_type='case_study' AND cc.role='vendor'
        GROUP BY 1
        ORDER BY n DESC, slug
        """
        )
    ]


def load_case(cur, case_id: int):
    rows = fetch_cases(cur, "x.id=?", (case_id,))
    if not rows:
        return None
    row = rows[0]
    row["mentioned"] = [
        dict(r)
        for r in cur.execute(
            """
            SELECT cc.role, cc.company_slug, c.name
            FROM case_companies cc JOIN companies c ON c.slug=cc.company_slug
            WHERE cc.case_id=? ORDER BY cc.role DESC, c.name
            """,
            (case_id,),
        )
    ]
    row["flags"] = [
        dict(r)
        for r in cur.execute(
            "SELECT flag, reason FROM clean_flags WHERE case_id=?",
            (case_id,),
        )
    ]
    slug = vendor_slug(row)
    related = []
    if slug:
        related = [
            dict(r)
            for r in cur.execute(
                """
                SELECT q.id, q.title, q.kind, q.difficulty, q.canonical_url
                FROM questions q
                JOIN question_companies qc ON qc.question_id=q.id
                WHERE qc.company_slug=? AND q.kind='open'
                ORDER BY q.id LIMIT 3
                """,
                (slug,),
            )
        ]
    row["related_questions"] = related
    return row


def filter_industry(rows, bucket: str):
    if not bucket:
        return rows
    return [r for r in rows if in_bucket(r.get("industry"), bucket)]


def ext_link(url, text) -> str:
    if not url:
        return esc(text)
    return (
        f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">'
        f"{esc(text)}</a>"
    )


def kpi_span(scope) -> str:
    return f'<span class="kpi {esc(kpi_class(scope))}">{esc(kpi_label(scope))}</span>'


def fde_flag(row) -> str:
    if has_fde_role(row):
        return '<span class="tg">现场编制</span>'
    return '<span class="flag">原文未自称 FDE</span>'


def case_card(row, flags_map, *, lead=False) -> str:
    cid = row.get("id")
    title = row.get("customer") or row.get("source_title") or "未具名客户"
    k = " · ".join(
        x for x in (vendor_name(row), row.get("bucket"), row.get("product")) if x
    )
    blurb = trunc(row.get("business_problem"), 110)
    outcome = ""
    if outcome_ok(row, flags_map) and nonempty(row.get("measured_outcome")):
        outcome = (
            f'<p class="outcome">{kpi_span(row.get("kpi_scope"))} '
            f"{esc(trunc(row.get('measured_outcome'), 110))}</p>"
        )
    else:
        outcome = f'<p class="outcome">{kpi_span(row.get("kpi_scope"))}</p>'
    url = href("/案例/%s" % cid)
    host = row.get("host") or ""
    cls = "card lead" if lead else "card"
    evid = row.get("evidence_quality") or ""
    return (
        f'<article class="{cls}">'
        f'<p class="k">{esc(k)}</p>'
        f'<h2><a href="{esc(url)}">{esc(title)}</a></h2>'
        + (f'<p class="blurb">{esc(blurb)}</p>' if blurb else "")
        + outcome
        + '<div class="meta">'
        + (f'<span class="tg">{esc(evid)}</span>' if evid else "")
        + kpi_span(row.get("kpi_scope"))
        + (f'<span class="host">{esc(host)}</span>' if host else "")
        + fde_flag(row)
        + "</div></article>"
    )


def frame_item(row) -> str:
    url = row.get("source_url") or ""
    title = row.get("source_title") or url or "条目"
    dtype = row.get("doc_type") or ""
    host = row.get("host") or host_of(url)
    sub = " · ".join(x for x in (dtype, host) if x)
    inner = f"<b>{esc(title)}</b>" + (f"<span>{esc(sub)}</span>" if sub else "")
    if url:
        return (
            f'<a class="frame-item" href="{esc(url)}" target="_blank" '
            f'rel="noopener noreferrer">{inner}</a>'
        )
    return f'<div class="frame-item">{inner}</div>'


def row_link(row, extra="") -> str:
    url = row.get("source_url") or href("/案例/%s" % row.get("id"))
    title = row.get("source_title") or row.get("customer") or "条目"
    host = row.get("host") or extra
    sub = " · ".join(x for x in (row.get("doc_type"), host) if x)
    ext = ' target="_blank" rel="noopener noreferrer"' if row.get("source_url") else ""
    return (
        f'<a class="row" href="{esc(url)}"{ext}>{esc(title)}'
        + (f'<span class="s">{esc(sub)}</span>' if sub else "")
        + "</a>"
    )


def chip(href_val, label, on=False, n=None) -> str:
    cls = "chip on" if on else "chip"
    extra = f'<span class="n">{int(n)}</span>' if n is not None else ""
    return f'<a class="{cls}" href="{esc(href_val)}">{esc(label)}{extra}</a>'


def industry_chips(base, current) -> str:
    parts = [chip(href(base), "全部行业", on=not current)]
    for name, _kws in INDUSTRY_BUCKETS:
        parts.append(chip(href(base, 行业=name), name, on=current == name))
    parts.append(chip(href(base, 行业="其他"), "其他", on=current == "其他"))
    return '<div class="filters">' + "".join(parts) + "</div>"


def brand_mark() -> str:
    """Official wordmark: imfde.ai"""
    return (
        '<span class="brand-mark">'
        '<span class="brand-im">im</span>'
        '<span class="brand-fde">fde</span>'
        '<span class="brand-tld">.ai</span>'
        "</span>"
    )


def abs_url(path: str = "/") -> str:
    text = (path or "/").strip() or "/"
    if not text.startswith("/"):
        text = "/" + text
    return SITE_ORIGIN + text


def mast(active: str, gh_url: str = "") -> str:
    links = []
    for label, path in NAV:
        cls = "on" if active == label else ""
        aria = ' aria-current="page"' if cls else ""
        links.append(f'<a class="{cls}" href="{esc(path)}"{aria}>{esc(label)}</a>')
    if gh_url:
        links.append(
            f'<a class="gh" href="{esc(gh_url)}" target="_blank" rel="noopener noreferrer">'
            '<img class="mast-gh-icon" src="/static/icons/github-small.svg" alt="" aria-hidden="true"/>GitHub</a>'
        )
    brand = brand_mark()
    return f"""<div class="mast"><div class="mast-in">
  <a class="brand" href="/" aria-label="{esc(SITE_NAME)} — {esc(SITE_TAGLINE)}">
    {brand}
    <span class="brand-tag">{esc(SITE_TAGLINE)}</span>
  </a>
  <span class="snap">数据快照 {esc(SNAPSHOT)}</span>
  <nav>{''.join(links)}</nav>
</div></div>"""


def footer(gh_url: str, extra="") -> str:
    gh = ext_link(gh_url, "github.com/Qbuby/imfde") if gh_url else ""
    lib = ""
    if (AI_DIR / "FDE案例库.html").is_file():
        lib = f'<a href="/library/{quote("FDE案例库.html")}">案例证据库 HTML</a>'
    return f"""<footer class="ft">
  <p><b>{esc(SITE_NAME)}</b> · {esc(SITE_TAGLINE)}</p>
  <p>{esc(SITE_DOMAIN)} · 数据快照 {esc(SNAPSHOT)} · 本期收录，不是实时资讯。</p>
  <p>数字带口径（实测 / 目标 / 预测 / 系统规模 / hero 条）。原文未写 Forward Deployed 头衔的，会标「原文未自称 FDE」。</p>
  <p>{"开源仓库 " + gh if gh else ""}{" · " if gh and lib else ""}{lib}{(" · " + extra) if extra else ""}</p>
  <p>面试题答案不在此站展示。第三方材料仅供私有研究对照，链回原页。从业者怎么读这份库，见 <a href="/现场">现场读法</a>。</p>
</footer>"""


def shell(
    title: str,
    active: str,
    inner: str,
    gh_url: str,
    extra_foot="",
    extra_head="",
    body_class="",
    skip_wrap=False,
    skip_mast=False,
    skip_foot=False,
    home_css=True,
    page_path="/",
) -> str:
    css = '<link rel="stylesheet" href="/static/tokens.css"/>'
    if home_css:
        css += '<link rel="stylesheet" href="/static/home.css"/>'
    body_attr = f' class="{esc(body_class)}"' if body_class else ""
    foot = "" if skip_foot else footer(gh_url, extra_foot)
    mast_html = "" if skip_mast else mast(active, gh_url)
    skip_html = "" if skip_mast else '<a class="skip" href="#main">跳到正文</a>\n'
    if skip_wrap:
        main = inner if skip_foot else f'<div id="main">\n{inner}\n{foot}\n</div>'
    else:
        main = f'<div class="wrap" id="main">\n{inner}\n{foot}\n</div>'
    canon = abs_url(page_path)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{esc(title)}</title>
<meta name="description" content="{esc(SITE_TAGLINE)}"/>
<link rel="canonical" href="{esc(canon)}"/>
<meta property="og:site_name" content="{esc(SITE_NAME)}"/>
<meta property="og:title" content="{esc(title)}"/>
<meta property="og:description" content="{esc(SITE_TAGLINE)}"/>
<meta property="og:url" content="{esc(canon)}"/>
{css}
{extra_head}
</head>
<body{body_attr}>
{skip_html}{mast_html}
{main}
</body>
</html>
"""


_DATES_CACHE = None


def load_dates() -> dict:
    global _DATES_CACHE
    if _DATES_CACHE is not None:
        return _DATES_CACHE
    if not DATES_PATH.is_file():
        _DATES_CACHE = {"by_url": {}, "_idx": {}}
        return _DATES_CACHE
    data = json.loads(DATES_PATH.read_text(encoding="utf-8"))
    idx = {}
    for key, rec in (data.get("by_url") or {}).items():
        idx[key] = rec
        idx[key.rstrip("/")] = rec
    data["_idx"] = idx
    _DATES_CACHE = data
    return data


def date_rec(url: str) -> dict:
    if not url:
        return {}
    idx = load_dates().get("_idx") or {}
    return idx.get(url) or idx.get(url.rstrip("/")) or {}


def published_on(url: str) -> str:
    rec = date_rec(url)
    return rec.get("published") or ""


def best_day(url: str) -> tuple[str, str]:
    rec = date_rec(url)
    if rec.get("published"):
        return rec["published"], "published"
    if rec.get("modified"):
        return rec["modified"], "modified"
    return "", ""


def pct(n, d) -> str:
    if not d:
        return "—"
    return "%.1f%%" % (100.0 * n / d)


def mix_line(pairs, limit=8) -> str:
    bits = []
    for name, n in pairs[:limit]:
        bits.append(f"<b>{esc(name)}</b> {int(n)}")
    return " · ".join(bits)


def case_cite(row) -> str:
    cid = row.get("id")
    title = row.get("customer") or row.get("source_title") or "条目"
    sub = " · ".join(
        x
        for x in (vendor_name(row), row.get("bucket"), kpi_label(row.get("kpi_scope")))
        if x
    )
    return (
        f'<a class="row" href="{esc(href("/案例/%s" % cid))}">{esc(title)}'
        f'<span class="s">{esc(sub)}</span></a>'
    )


def claim_block(num, title, body_html, cites_html="") -> str:
    cites = f'<div class="cites list">{cites_html}</div>' if cites_html else ""
    return f"""<article class="claim">
  <p class="num">{esc(num)}</p>
  <div class="claim-body">
    <h2>{esc(title)}</h2>
    {body_html}
    {cites}
  </div>
</article>"""


def catalog_door(href_val, label, note) -> str:
    return f"""<p class="catalog-door">
  <a href="{esc(href_val)}">{esc(label)}</a>
  <span>{esc(note)}</span>
</p>"""


def study_pack(rows) -> dict:
    n = len(rows)
    n_fde = sum(1 for r in rows if has_fde_role(r))
    n_named = sum(1 for r in rows if r.get("customer_named"))
    n_high = sum(1 for r in rows if r.get("evidence_quality") == "high")
    n_outcome = sum(1 for r in rows if nonempty(r.get("measured_outcome")))
    kpi = Counter(r.get("kpi_scope") or "未标" for r in rows)
    buckets = Counter(r.get("bucket") or "其他" for r in rows)
    vendors = Counter(vendor_name(r) for r in rows)
    core_set = set(CORE_VENDORS)
    product_set = set(PRODUCT_STORY_VENDORS)
    n_core = sum(1 for r in rows if vendor_slug(r) in core_set)
    n_product = sum(1 for r in rows if vendor_slug(r) in product_set)
    years = Counter()
    n_published = 0
    for r in rows:
        day = published_on(r.get("source_url") or "")
        if day:
            n_published += 1
            years[day[:4]] += 1
    fill = {}
    for field in (
        "integration",
        "time_to_production",
        "customer_handoff",
        "failure_iteration",
        "productization",
        "human_in_the_loop",
        "fde_role",
    ):
        fill[field] = sum(1 for r in rows if nonempty(r.get(field)))
    return {
        "n": n,
        "n_fde": n_fde,
        "n_named": n_named,
        "n_high": n_high,
        "n_outcome": n_outcome,
        "kpi": kpi,
        "buckets": buckets,
        "vendors": vendors,
        "n_core": n_core,
        "n_product": n_product,
        "n_published": n_published,
        "years": years,
        "fill": fill,
    }


def commentary_timeline(cur):
    rows = annotate(
        dedupe_by_url(
            [
                dict(r)
                for r in cur.execute(
                    """
            SELECT id, source_url, source_title, business_problem, doc_type, quote
            FROM cases
            WHERE doc_type IN ('opinion', 'methodology')
            ORDER BY id
            """
                )
            ]
        )
    )
    dated = []
    undated = []
    seen = set()
    for r in rows:
        url = r.get("source_url") or ""
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        day, kind = best_day(url)
        r = dict(r)
        r["day"] = day
        r["date_kind"] = kind
        if day:
            dated.append(r)
        else:
            undated.append(r)
    dated.sort(key=lambda x: x.get("day") or "")
    return dated, undated


def timeline_html(items) -> str:
    if not items:
        return '<p class="empty">这批方法/观点页没有回填到发布日。</p>'
    bits = []
    for r in items:
        url = r.get("source_url") or ""
        title = r.get("source_title") or url or "条目"
        host = r.get("host") or host_of(url)
        blurb = trunc(r.get("business_problem") or r.get("quote"), 140)
        kind = "原文发布" if r.get("date_kind") == "published" else "页上修改日"
        bits.append(
            f'<div class="tl">'
            f'<p class="when">{esc(r.get("day"))} · {esc(kind)}</p>'
            f"<p class='tl-title'>{ext_link(url, title)}</p>"
            + (f'<p class="blurb">{esc(blurb)}</p>' if blurb else "")
            + f'<p class="tl-meta">{esc(r.get("doc_type") or "")} · {esc(host)}</p>'
            f"</div>"
        )
    return '<div class="timeline">' + "".join(bits) + "</div>"


def year_line(years: Counter) -> str:
    if not years:
        return "没有原文发布日"
    return "、".join(f"{y} 年 {years[y]} 条" for y in sorted(years))


def render_home(cur) -> str:
    counts = load_counts(cur)
    studies = fetch_cases(cur, "x.doc_type='case_study'", (), "x.id")
    pack = study_pack(studies)
    dated, _undated = commentary_timeline(cur)
    gh = github_url(cur)
    top_v = pack["vendors"].most_common(5)
    year_txt = year_line(pack["years"])
    first_dated = dated[0] if dated else None
    last_dated = dated[-1] if dated else None
    span = ""
    if first_dated and last_dated:
        span = f"{first_dated.get('day')} 到 {last_dated.get('day')}"
    claims = "".join(
        [
            claim_block(
                "01",
                "公开材料里的落地，绝大多数不是编制故事",
                f"<p>{pack['n']} 条交付现场里，原文写了现场编制的只有 <b>{pack['n_fde']}</b> 条（{pct(pack['n_fde'], pack['n'])}）。"
                "能同时满足核心厂商、具名客户、证据 high、有结果的，更窄到 "
                f"<b>{counts['n_core']}</b> 条。先读这批结构，再决定要不要逐条翻。</p>",
            ),
            claim_block(
                "02",
                "FDE 岗位的变化写在评论时间线里，不在客户故事墙上",
                f"<p>观点和方法页有原文发布日的，从 {esc(span) or '少量标注页'}。"
                "客户故事 503 条里，只有 "
                f"<b>{pack['n_published']}</b> 条从已抓 HTML 回填到发布日（{year_txt}）。"
                "sitemap 的 lastmod 大多是 2026，那是页面触碰时间，不当事件日。</p>",
            ),
            claim_block(
                "03",
                "条数被产品营销页拉开，不是「谁在做 FDE」的排行",
                f"<p>厂商密度：{mix_line(top_v, 6)}。"
                f"Intercom / Writer / Cresta / Moveworks / Abridge 合计 {pack['n_product']} 条；"
                f"核心厂商 {pack['n_core']} 条。多不等于编制样本。</p>",
            ),
        ]
    )
    inner = f"""
<section class="hero">
  <p class="k">本期观察 · 结构化输出</p>
  <h1>先看这批材料在变什么，逐条翻是另一扇门</h1>
  <p class="lead">同一份 {esc(SNAPSHOT)} 快照。AI 抽出的是整体结构：编制几乎不出现、岗位讨论有时间线、库内条数被产品故事拉开。不是实时资讯，也不是编制咨询。</p>
  <p class="meta-line">数据快照 {esc(SNAPSHOT)} · {counts['n_cases']} 条观察 · 本期收录 · 发布日从已抓 HTML 回填</p>
  <div class="stats">
    <span><b>{pack['n']}</b> 交付现场</span>
    <span><b>{pack['n_fde']}</b> / {pack['n']} 原文写了编制</span>
    <span><b>{counts['n_core']}</b> 条可作落地样板</span>
    <span><b>{pack['n_published']}</b> 条客户故事有原文发布日</span>
    <span><b>{len(dated)}</b> 条观点/方法标了日期</span>
  </div>
</section>
<section class="brief">{claims}</section>
<div class="doors">
  <article class="door">
    <p class="k">落地读法</p>
    <h2>要实施，先看结构再看样板</h2>
    <p>编制在原文里有多薄、什么样板算数、结果带什么口径。行业切面改的是这些句子里的数字，不是先铺一墙卡片。</p>
    <a class="go" href="/落地">用落地读法看本期 <span>给负责人</span></a>
  </article>
  <article class="door">
    <p class="k">现场读法</p>
    <h2>近态是评论时间线 + 现场密度</h2>
    <p>a16z / Pragmatic Engineer / OpenAI Frontier 排成一条有发布日的线；客户故事按厂商密度读，不当新闻 feed。</p>
    <a class="go" href="/现场">用现场读法看本期 <span>给从业者</span></a>
  </article>
</div>
{catalog_door("/案例", "逐条看案例", "503 条目录、筛选、分页。两种读法的证据都在这里。")}
"""
    return shell("%s · 本期观察" % SITE_NAME, "", inner, gh, page_path="/")


def render_deploy(cur, qs) -> str:
    industry = qs_get(qs, "行业", "industry")
    valid = {name for name, _ in INDUSTRY_BUCKETS} | {"其他"}
    if industry not in valid:
        industry = ""
    studies = filter_industry(
        fetch_cases(cur, "x.doc_type='case_study'", (), "x.id"), industry
    )
    pack = study_pack(studies)
    featured = filter_industry(load_featured(cur), industry)
    flags = load_flags(cur, [r["id"] for r in featured[:8]])
    peers = pick_peers(featured, 3)
    role_cases = (
        [r for r in studies if has_fde_role(r)][:8]
        if industry
        else load_fde_role_cases(cur)
    )
    gh = github_url(cur)
    slice_note = f"行业切面「{industry}」" if industry else "全库"
    n_narr = pack["kpi"].get("narrative", 0)
    fill = pack["fill"]
    bucket_txt = mix_line(pack["buckets"].most_common(8), 8)
    vendor_txt = mix_line(pack["vendors"].most_common(6), 6)
    peer_cites = "".join(case_cite(r) for r in peers)
    if not peer_cites:
        peer_cites = '<p class="empty">这个切面下没有同时满足「具名 · high · 核心厂商 · 有结果」的条目。</p>'
    role_html = "".join(case_cite(r) for r in role_cases) or '<p class="empty">这个切面下没有写编制的案例。</p>'
    more_n = max(0, len(featured) - len(peers))
    more = ""
    if more_n:
        more = (
            f'<p class="hint">同条件还有 {more_n} 单，不在这页摊开。'
            f'<a href="{esc(href("/案例", 厂商="核心", 证据="high", 行业=industry))}">逐条看</a></p>'
        )
    claims = "".join(
        [
            claim_block(
                "01",
                "先把编制从第一步拿掉",
                f"<p>{slice_note} {pack['n']} 条交付现场，原文写了现场编制的 "
                f"<b>{pack['n_fde']}</b> 条（{pct(pack['n_fde'], pack['n'])}）。"
                "买产品、嵌进旧流程、厂商驻场、自建编制，在公开页上不是同一件事。"
                "库里几乎没有「如何组建 FDE 团队」的完整样本。</p>",
            ),
            claim_block(
                "02",
                "能当样板的条件很窄，行业切面改的是这句话里的数字",
                f"<p>核心厂商 × 具名客户 × 证据 high × 有结果：<b>{len(featured)}</b> 条。"
                f"切面内厂商：{vendor_txt or '无'}。"
                f"{'行业分布：' + bucket_txt if not industry else ''}</p>"
                "<p>下面只留三单作证据，不是本页主菜。</p>",
                peer_cites + more,
            ),
            claim_block(
                "03",
                "结果几乎都有，口径和交接才是薄的地方",
                f"<p>有 measured_outcome 的 {pack['n_outcome']} / {pack['n']}；"
                f"kpi_scope=实测叙述 {n_narr} 条。"
                f"集成 {pct(fill['integration'], pack['n'])} 有写，"
                f"上线周期 {pct(fill['time_to_production'], pack['n'])}，"
                f"交接 {pct(fill['customer_handoff'], pack['n'])}，"
                f"失败迭代 {pct(fill['failure_iteration'], pack['n'])}。"
                "数字带实测 / 目标 / 预测 / 系统规模 / hero 条，点进单条才能核对。</p>",
            ),
        ]
    )
    inner = f"""
<section class="desk-lede">
  <p class="k">落地读法 · 数据快照 {esc(SNAPSHOT)}</p>
  <h1>实施前先读结构，不要先翻 503 张卡</h1>
  <p>观察站的判断层，给要落地的负责人。公开交付材料上的结构，不是咨询方案，也不是第二套新闻。</p>
  {industry_chips("/落地", industry)}
</section>
<section class="brief">{claims}</section>
<section class="section" id="问题">
  <h2>先把问题说清楚</h2>
  <p class="note">落地页只定范围，不当结果证明。方法全文在目录里。</p>
  <ol class="scope-q">
    <li>
      <h3>买产品，还是买驻场？</h3>
      <p>公开页上「嵌进旧流程」和「厂商驻场」不是同一件事。别把产品故事当成编制样本。</p>
    </li>
    <li>
      <h3>要不要为此建编制？</h3>
      <p>库里几乎没有「如何组建 FDE 团队」的完整样本。原文写了现场编制的比例见上面 01。</p>
    </li>
    <li>
      <h3>公开口径能不能当样板？</h3>
      <p>有结果的多，写清实测 / 目标 / 预测 / 交接的少。点进单条才能核对。</p>
    </li>
  </ol>
  <p class="hint"><a href="/方法">方法目录看全文</a></p>
</section>
<section class="section" id="编制">
  <h2>编制附录</h2>
  <p class="note">岗位变化是弱信号，只在世界动态的方法轨上轴，这里不重复列表。<a href="/世界动态">看世界动态</a></p>
  <h3 class="note" style="margin-top:0">原文写了编制的案例</h3>
  <div class="list">{role_html}</div>
</section>
{catalog_door(href("/案例", 厂商="核心", 行业=industry, 证据="high"), "逐条看这个切面的样板", "卡片、筛选、分页都在案例库。产品故事（Intercom / Writer 等）也在那里，默认不当编制样本。")}
"""
    return shell("落地 · %s" % SITE_NAME, "落地", inner, gh, page_path="/落地")


def render_field(cur, qs) -> str:
    studies = fetch_cases(cur, "x.doc_type='case_study'", (), "x.id")
    pack = study_pack(studies)
    dated, undated = commentary_timeline(cur)
    discussions = load_discussions(cur)
    gh = github_url(cur)
    dates_meta = load_dates()
    n_sitemap = int(dates_meta.get("n_sitemap") or 0)
    vendor_txt = mix_line(pack["vendors"].most_common(8), 8)
    year_txt = year_line(pack["years"])
    noise_html = "".join(row_link(r) for r in discussions) or '<p class="empty">没有讨论帖。</p>'
    undated_html = "".join(row_link(r) for r in undated[:8])
    first = dated[0] if dated else None
    last = dated[-1] if dated else None
    span = ""
    if first and last:
        span = f"{first.get('day')} → {last.get('day')}"
    claims = "".join(
        [
            claim_block(
                "01",
                "岗位在升温的是评论层，不是客户故事层",
                f"<p>观点 6 + 方法 17 + 讨论去重后几帖，对比 {pack['n']} 条厂商客户故事。"
                "近态要读有发布日的评论线，不要把 503 张营销页当成「本周 FDE 动态」。</p>",
            ),
            claim_block(
                "02",
                "有原文发布日的评论，已经排得成一条线",
                f"<p>{len(dated)} 条方法/观点回填到了发布日或修改日"
                f"{'（' + esc(span) + '）' if span else ''}。"
                "这是从已抓 HTML 补的历史时间线，不是新开厂商抓取。</p>",
                timeline_html(dated),
            ),
            claim_block(
                "03",
                "库内密度被产品故事拉开",
                f"<p>{vendor_txt}。"
                f"产品故事五家合计 {pack['n_product']} / {pack['n']}；"
                f"核心厂商 {pack['n_core']} / {pack['n']}。"
                "多是营销页库存，不是驻场编制排行。</p>",
            ),
            claim_block(
                "04",
                "客户故事大多本来就没写发布日",
                f"<p>交付现场有原文 published 的 {pack['n_published']} / {pack['n']}（{year_txt}）。"
                f"全库任意日期标记 {dates_meta.get('n_with_any_date') or '—'} 条，其中 sitemap lastmod {n_sitemap} 条——触碰时间，不当事件日。"
                "Sierra / Decagon / Rippling 等本地 HTML 没对上的，以后按 URL 补抓就能再涨一截，不必新开厂商。</p>",
            ),
        ]
    )
    inner = f"""
<section class="desk-lede">
  <p class="k">现场读法 · 数据快照 {esc(SNAPSHOT)}</p>
  <h1>近态是时间线，不是 24 张雷达卡</h1>
  <p>给从业者，用来避免误读这份库。不写「今日」或「刚刚」。发布日从已抓 HTML 回填；没有发布日的，不假装有。</p>
</section>
<section class="brief" id="简报">{claims}</section>
<section class="section" id="还在吵">
  <h2>还在吵</h2>
  <p class="note">Reddit 等讨论去重后 {len(discussions)} 帖，撑不起头条，也不进入上面的时间线。</p>
  <div class="list">{noise_html}</div>
</section>
{f'<section class="section"><h2>方法/观点未标日期</h2><div class="list">{undated_html}</div></section>' if undated_html else ''}
{catalog_door("/案例", "逐条看部署现场", "按厂商 / 行业 / 证据筛选、分页。雷达卡不再占现场桌。")}
"""
    return shell("现场 · %s" % SITE_NAME, "现场", inner, gh, page_path="/现场")


def render_library(cur, qs) -> str:
    industry = qs_get(qs, "行业", "industry")
    vendor = qs_get(qs, "厂商", "vendor")
    evidence = qs_get(qs, "证据", "evidence")
    page = qs_int(qs, "页", "page", default=1)
    valid_ind = {name for name, _ in INDUSTRY_BUCKETS} | {"其他"}
    if industry not in valid_ind:
        industry = ""
    if evidence not in ("high", "medium", "low"):
        evidence = ""
    vendors = load_vendors(cur)
    slugs = {v["slug"] for v in vendors}
    vendor_filter = CORE_VENDORS if vendor == "核心" else ((vendor,) if vendor in slugs else None)

    where = ["x.doc_type='case_study'"]
    args = []
    if evidence:
        where.append("x.evidence_quality=?")
        args.append(evidence)
    if vendor_filter:
        ph = ",".join("?" * len(vendor_filter))
        where.append(
            "EXISTS (SELECT 1 FROM case_companies cc WHERE cc.case_id=x.id "
            "AND cc.role='vendor' AND cc.company_slug IN (%s))" % ph
        )
        args.extend(vendor_filter)
    rows = filter_industry(
        fetch_cases(
            cur,
            " AND ".join(where),
            args,
            "CASE x.evidence_quality WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, x.id",
        ),
        industry,
    )
    per = 36
    total = len(rows)
    pages = max(1, (total + per - 1) // per)
    if page > pages:
        page = pages
    shown = rows[(page - 1) * per : page * per]
    flags = load_flags(cur, [r["id"] for r in shown])
    gh = github_url(cur)

    vchips = [
        chip(href("/案例", 行业=industry, 证据=evidence), "全部厂商", on=not vendor),
        chip(href("/案例", 厂商="核心", 行业=industry, 证据=evidence), "核心厂商", on=vendor == "核心"),
    ]
    for v in vendors[:12]:
        vchips.append(
            chip(
                href("/案例", 厂商=v["slug"], 行业=industry, 证据=evidence),
                v["name"],
                on=vendor == v["slug"],
                n=v["n"],
            )
        )
    evid_chips = [
        chip(href("/案例", 厂商=vendor, 行业=industry), "全部证据", on=not evidence),
        chip(href("/案例", 厂商=vendor, 行业=industry, 证据="high"), "high", on=evidence == "high"),
        chip(href("/案例", 厂商=vendor, 行业=industry, 证据="medium"), "medium", on=evidence == "medium"),
        chip(href("/案例", 厂商=vendor, 行业=industry, 证据="low"), "low", on=evidence == "low"),
    ]
    base = {"厂商": vendor, "证据": evidence}
    ind_chips = [chip(href("/案例", **base), "全部行业", on=not industry)]
    for name, _kws in INDUSTRY_BUCKETS:
        ind_chips.append(chip(href("/案例", 行业=name, **base), name, on=industry == name))
    ind_chips.append(chip(href("/案例", 行业="其他", **base), "其他", on=industry == "其他"))

    grid = "".join(case_card(r, flags) for r in shown) or '<p class="empty">没有匹配的案例。</p>'
    prev_h = href("/案例", 厂商=vendor, 行业=industry, 证据=evidence, 页=page - 1) if page > 1 else ""
    next_h = href("/案例", 厂商=vendor, 行业=industry, 证据=evidence, 页=page + 1) if page < pages else ""
    pager = f'<div class="pager">{esc(str(page))} / {pages} 页 · 共 {total} 单'
    if prev_h:
        pager += f' · <a href="{esc(prev_h)}">上一页</a>'
    if next_h:
        pager += f' · <a href="{esc(next_h)}">下一页</a>'
    pager += "</div>"

    inner = f"""
<section class="desk-lede">
  <p class="k">部署证据 · 数据快照 {esc(SNAPSHOT)}</p>
  <h1>部署证据</h1>
  <p>共用目录。落地和现场筛过的切面，都可以回到这里看全量。点进一单后有两种读法。</p>
</section>
<section class="section">
  <div class="filters">{''.join(vchips)}</div>
  <div class="filters">{''.join(ind_chips)}</div>
  <div class="filters">{''.join(evid_chips)}</div>
  <div class="grid-3">{grid}</div>
  {pager}
</section>
"""
    return shell("部署证据 · %s" % SITE_NAME, "部署证据", inner, gh, page_path="/案例")


def dl_row(label, value) -> str:
    if nonempty(value):
        return f"<dt>{esc(label)}</dt><dd>{esc(value).replace(chr(10), '<br/>')}</dd>"
    return f'<dt>{esc(label)}</dt><dd class="empty">原文未写</dd>'


def render_case(cur, case_id: int, qs) -> str:
    row = load_case(cur, case_id)
    gh = github_url(cur)
    if not row:
        inner = '<section class="desk-lede"><h1>没有这条案例</h1><p><a href="/案例">回到案例</a></p></section>'
        return shell("未找到 · %s" % SITE_NAME, "部署证据", inner, gh, page_path="/案例")
    view = qs_get(qs, "读法", "view")
    if view not in ("落地", "现场"):
        view = ""
    title = row.get("customer") or row.get("source_title") or "案例"
    k = " · ".join(x for x in (vendor_name(row), row.get("bucket"), row.get("product")) if x)
    src = row.get("source_url") or ""
    on_d = " on" if view == "落地" else ""
    on_f = " on" if view == "现场" else ""
    flags_html = ""
    if row.get("flags"):
        flags_html = "<div class='list' style='margin-top:12px'>" + "".join(
            f'<div class="row">{esc(f["flag"])}<span class="s">{esc(f["reason"])}</span></div>'
            for f in row["flags"]
        ) + "</div>"
    related = ""
    if row.get("related_questions"):
        items = []
        for q in row["related_questions"]:
            url = q.get("canonical_url") or ""
            label = q.get("title") or q.get("id")
            if url:
                items.append(
                    f'<a class="row" href="{esc(url)}" target="_blank" rel="noopener noreferrer">'
                    f"{esc(label)}<span class='s'>开放题 · 答案不在此站展示</span></a>"
                )
            else:
                items.append(f'<div class="row">{esc(label)}<span class="s">开放题</span></div>')
        related = (
            '<section class="section"><h2>相关开放题</h2>'
            '<p class="note">附录。面试准备用，不是落地依据。</p>'
            f'<div class="list">{"".join(items)}</div></section>'
        )
    quote = ""
    if nonempty(row.get("quote")):
        quote = f'<blockquote class="quote">{esc(row["quote"])}</blockquote>'
    inner = f"""
<section class="desk-lede case-top">
  <p class="k">{esc(k)}</p>
  <h1>{esc(title)}</h1>
  <p class="source-line">
    {ext_link(src, src or "无来源 URL")}
    · {esc(row.get("doc_type") or "")}
    · 收录于 {esc(SNAPSHOT)}
  </p>
  <div class="meta" style="display:flex;gap:8px;flex-wrap:wrap">
    {kpi_span(row.get("kpi_scope"))}
    <span class="tg">{esc(row.get("evidence_quality") or "")}</span>
    {fde_flag(row)}
    <a href="{esc(href("/案例/"+str(case_id), 读法="落地"))}">落地读法</a>
    <a href="{esc(href("/案例/"+str(case_id), 读法="现场"))}">现场读法</a>
  </div>
</section>
<div class="pair">
  <section class="col{on_d}" id="落地读法">
    <h2>落地读法</h2>
    <dl class="anatomy">
      {dl_row("经营问题", row.get("business_problem"))}
      {dl_row("结果", row.get("measured_outcome"))}
      {dl_row("口径", kpi_label(row.get("kpi_scope")))}
      {dl_row("集成", row.get("integration"))}
      {dl_row("数据", row.get("data_sources"))}
      {dl_row("人在环内", row.get("human_in_the_loop"))}
      {dl_row("上线周期", row.get("time_to_production"))}
      {dl_row("交接", row.get("customer_handoff"))}
      {dl_row("编制", row.get("fde_role"))}
    </dl>
  </section>
  <section class="col{on_f}" id="现场读法">
    <h2>现场读法</h2>
    <dl class="anatomy">
      {dl_row("主场景", row.get("hero_use_case"))}
      {dl_row("旧流程", row.get("existing_workflow"))}
      {dl_row("卡点", row.get("pain_point"))}
      {dl_row("模型", row.get("ai_model"))}
      {dl_row("工作流", row.get("agent_workflow"))}
      {dl_row("评测", row.get("evaluation"))}
      {dl_row("部署", row.get("deployment"))}
      {dl_row("失败迭代", row.get("failure_iteration"))}
      {dl_row("产品化", row.get("productization"))}
    </dl>
  </section>
</div>
{quote}
<section class="section">
  <h2>证据与卫生旗</h2>
  <p class="note">{esc(row.get("evidence_note") or "无证据备注。")}</p>
  {flags_html or '<p class="hint">没有 clean_flags。</p>'}
</section>
{related}
<p class="hint"><a href="/落地">回落地</a> · <a href="/现场">回现场</a> · <a href="/案例">案例目录</a></p>
"""
    return shell("%s · %s" % (title, SITE_NAME), "部署证据", inner, gh, page_path="/案例/%s" % case_id)


def render_methods(cur) -> str:
    topics = load_topics(cur)
    rows = annotate(
        dedupe_by_url(
            [
                dict(r)
                for r in cur.execute(
                    """
            SELECT id, source_url, source_title, business_problem, doc_type
            FROM cases
            WHERE doc_type IN ('methodology','opinion')
            ORDER BY CASE doc_type WHEN 'opinion' THEN 0 ELSE 1 END, id
            """
                )
            ]
        )
    )
    craft = [r for r in rows if is_craft_host(r.get("source_url") or "")]
    other = [r for r in rows if r not in craft]
    gh = github_url(cur)
    l1 = [t for t in topics if t.get("level") == "L1"]
    l2 = [t for t in topics if t.get("level") == "L2"]

    def topic_chip(t):
        zh = (t.get("name_zh") or "").strip()
        for prefix in ("L1 ", "L2 "):
            if zh.startswith(prefix):
                zh = zh[len(prefix):]
        return f'<span class="chip"><b>{esc(zh or t.get("slug"))}</b><span class="n">{esc(t.get("slug") or "")}</span></span>'

    inner = f"""
<section class="desk-lede">
  <p class="k">方法 · 数据快照 {esc(SNAPSHOT)}</p>
  <h1>方法</h1>
  <p>FDE 怎么工作、业界怎么谈编制。这是薄目录，不是课程首页。岗位变化看世界动态方法轨。</p>
</section>
<section class="section">
  <h2>观点与方法</h2>
  <div class="list">{''.join(row_link(r) for r in other)}</div>
</section>
<section class="section">
  <h2>手艺页</h2>
  <p class="note">FDEInterviews / FDE Pod 等讲解页。</p>
  <div class="list">{''.join(row_link(r) for r in craft)}</div>
</section>
<section class="section">
  <h2>L1 循环</h2>
  <div class="filters">{''.join(topic_chip(t) for t in l1)}</div>
  <h2 style="margin-top:18px">L2</h2>
  <div class="filters">{''.join(topic_chip(t) for t in l2)}</div>
</section>
<section class="section">
  <h2>岗位变化</h2>
  <p class="note">招聘是弱信号，只在世界动态的方法轨上轴，这里不重复列表。<a href="/世界动态">看世界动态</a></p>
</section>
"""
    return shell("方法 · %s" % SITE_NAME, "方法", inner, gh, page_path="/方法")


def render_path(path: str, qs) -> str:
    with connect() as con:
        cur = con.cursor()
        if path in ("/", "/index.html", "/世界动态", "/world"):
            from worldview import render_world

            return render_world(cur)
        if path == "/world3d":
            from world3d import render_world3d

            return render_world3d(cur)
        if path == "/落地":
            return render_deploy(cur, qs)
        if path == "/现场":
            return render_field(cur, qs)
        if path == "/案例":
            return render_library(cur, qs)
        if path == "/方法":
            return render_methods(cur)
        m = re.fullmatch(r"/案例/(\d+)", path)
        if m:
            return render_case(cur, int(m.group(1)), qs)
    return ""


def normalize_path(path: str) -> str:
    aliases = {
        "/deploy": "/落地",
        "/field": "/现场",
        "/cases": "/案例",
        "/method": "/方法",
        "/methods": "/方法",
        "/world": "/世界动态",
        "/立体世界": "/world3d",
        "/沙盘": "/world3d",
    }
    if path in aliases:
        return aliases[path]
    m = re.fullmatch(r"/cases/(\d+)", path)
    if m:
        return "/案例/" + m.group(1)
    return path


def write_snapshot(dest: Path | None = None) -> Path:
    page = render_path("/", {})
    tokens_path = STATIC_DIR / "tokens.css"
    if tokens_path.is_file():
        tokens_css = tokens_path.read_text(encoding="utf-8")
        page = page.replace(
            '<link rel="stylesheet" href="/static/tokens.css"/>',
            f"<style>\n{tokens_css}\n</style>",
            1,
        )
    css = CSS_PATH.read_text(encoding="utf-8") if CSS_PATH.is_file() else ""
    page = page.replace(
        '<link rel="stylesheet" href="/static/home.css"/>',
        f"<style>\n{css}\n</style>",
        1,
    )
    world_css_path = STATIC_DIR / "world.css"
    if world_css_path.is_file():
        wcss = world_css_path.read_text(encoding="utf-8")
        page = page.replace(
            '<link rel="stylesheet" href="/static/world.css"/>',
            f"<style>\n{wcss}\n</style>",
            1,
        )
    world_js_path = STATIC_DIR / "world.js"
    if world_js_path.is_file():
        wjs = world_js_path.read_text(encoding="utf-8")
        page = page.replace(
            '<script src="/static/world.js" defer></script>',
            f"<script>\n{wjs}\n</script>",
            1,
        )
    path = dest or SNAPSHOT_PATH
    path.write_text(page, encoding="utf-8")
    return path


class Handler(BaseHTTPRequestHandler):
    server_version = "NOW-FDE/1.0"

    def log_message(self, fmt, *args):
        import sys

        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code, body: bytes, content_type: str, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type=None):
        if not path.is_file():
            self._send(404, "not found".encode("utf-8"), "text/plain; charset=utf-8")
            return
        ctype = content_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if ctype.startswith("text/") and "charset" not in ctype:
            ctype = ctype + "; charset=utf-8"
        extra = {}
        if path.suffix.lower() in {".html", ".htm", ".css", ".js"}:
            extra["Cache-Control"] = "no-store"
        self._send(200, path.read_bytes(), ctype, extra)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path != "/":
            path = path.rstrip("/") or "/"
        path = normalize_path(path)
        qs = parse_qs(parsed.query, keep_blank_values=False)

        if path == "/static/home.css":
            self._send_file(CSS_PATH, "text/css; charset=utf-8")
            return
        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            target = (STATIC_DIR / rel).resolve()
            root = STATIC_DIR.resolve()
            if root not in target.parents and target != root:
                self._send(403, b"forbidden", "text/plain; charset=utf-8")
                return
            self._send_file(target)
            return
        if path.startswith("/library/"):
            rel = path[len("/library/") :]
            if (not rel) or ("\\" in rel) or rel.startswith("/"):
                self._send(400, b"bad path", "text/plain; charset=utf-8")
                return
            target = (AI_DIR / rel).resolve()
            ai_res = AI_DIR.resolve()
            if target != ai_res and ai_res not in target.parents:
                self._send(403, b"forbidden", "text/plain; charset=utf-8")
                return
            self._send_file(target)
            return
        if path == "/api/world.json":
            try:
                from worldview import load_world

                with connect() as con:
                    payload = load_world(con.cursor())
            except Exception:
                self._send(
                    500,
                    ("查询失败\n" + traceback.format_exc()).encode("utf-8"),
                    "text/plain; charset=utf-8",
                )
                return
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8", {"Cache-Control": "no-store"})
            return

        try:
            page = render_path(path, qs)
        except Exception:
            self._send(
                500,
                ("查询失败\n" + traceback.format_exc()).encode("utf-8"),
                "text/plain; charset=utf-8",
            )
            return
        if not page:
            self._send(404, "not found".encode("utf-8"), "text/plain; charset=utf-8")
            return
        self._send(
            200,
            page.encode("utf-8"),
            "text/html; charset=utf-8",
            {"Cache-Control": "no-store"},
        )


def main():
    import sys

    if not DB_PATH.is_file():
        raise SystemExit("missing db: %s" % DB_PATH)
    if "--snapshot" in sys.argv[1:]:
        path = write_snapshot()
        print("snapshot %s" % path, flush=True)
        return
    class ReuseServer(ThreadingHTTPServer):
        allow_reuse_address = True

    httpd = ReuseServer((HOST, PORT), Handler)
    print("%s portal http://%s:%s/  db=%s" % (SITE_NAME, HOST, PORT, DB_PATH), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstop", flush=True)
        httpd.server_close()


if __name__ == "__main__":
    main()
