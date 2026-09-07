# -*- coding: utf-8 -*-
"""imfde.ai portal. Stdlib only. GET queries fde.db. Bind 0.0.0.0:8850.

Routes:
  /           3D world sandbox (industry pace)
  /世界动态   alias of /
  /world3d    alias of /
  /平面       2D timeline of the same snapshot
  /落地       boss reading of this window's change
  /现场       practitioner reading of the moving role
  /案例       dated deploys + catalog
  /案例/<id>  case detail
  /方法       methods that are shifting
"""
from __future__ import annotations

import html
import json
import mimetypes
import re
import secrets
import sqlite3
import time
import traceback
import urllib.parse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

HOST = "0.0.0.0"
PORT = 8850
SITE_DOMAIN = "imfde.ai"
SITE_ORIGIN = "https://imfde.ai"
# imfde 交易门户首页。内容服务作为「学习成长」子区并入 imfde 平台，
# 提供返回平台门户的导航。部署时设为门户实际地址；留空则不显示。
IM_FDE_PORTAL_URL = (__import__("os").environ.get("IMFDE_PORTAL_URL") or "").strip()
SITE_NAME = "imfde.ai"
SITE_CLUB = "AI 实战进化社"
SITE_SLOGAN = "在现场里进化"
SITE_TAGLINE = "AI 实战进化社 · 在现场里进化"
SITE_DIR = Path(__file__).resolve().parent
PORTAL_DIR = SITE_DIR.parent
AI_DIR = PORTAL_DIR.parent
DB_PATH = PORTAL_DIR / "fde.db"
# 完整库（含题库答案）只在本地/私有部署存在；线上用剥离答案的公开库。
if not DB_PATH.is_file():
    DB_PATH = PORTAL_DIR / "fde-public.db"
STATIC_DIR = SITE_DIR / "static"
CSS_PATH = STATIC_DIR / "home.css"
SNAPSHOT_PATH = AI_DIR / "FDE门户.html"
DATES_PATH = PORTAL_DIR / "source_dates.json"

REPORT_PATH = PORTAL_DIR / "world_ingest_report.json"
RAW_DIR = PORTAL_DIR / "world_raw"
CORPUS_RAW = AI_DIR / "fde_corpus" / "raw"
FDEI_DIR = AI_DIR / "fdeinterviews.com"
_ORIG_EXTS = (".html", ".json", ".pdf", ".txt")
_ORIG_FILE_CACHE: dict[str, Path | None] = {}
_SOURCES_LOCAL_MAP: dict[str, str] | None = None


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


def day_zh(day: str | None) -> str:
    text = (day or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if not m:
        return text
    return "%d年%d月%d日" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
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
    "narrative": "公司自己讲的数字",
    "hero_only": "只讲了一个例子",
    "goal": "目标（还没发生）",
    "projected": "预估",
    "system_scale_not_kpi": "规模（不是效果）",
}
EVIDENCE_ZH = {"high": "比较可靠", "medium": "一般", "low": "不太够"}
DOC_TYPE_ZH = {
    "case_study": "客户故事",
    "methodology": "怎么做",
    "opinion": "看法",
    "job_posting": "招聘",
    "discussion": "讨论",
    "index": "目录",
    "unusable": "不可用",
}
CASE_ZH_FIELDS = (
    "source_title",
    "industry",
    "business_problem",
    "existing_workflow",
    "pain_point",
    "discovery_method",
    "why_ai",
    "hero_use_case",
    "data_sources",
    "integration",
    "ai_model",
    "agent_workflow",
    "human_in_the_loop",
    "evaluation",
    "deployment",
    "time_to_production",
    "business_kpi",
    "measured_outcome",
    "failure_iteration",
    "productization",
    "customer_handoff",
    "fde_role",
    "quote",
    "evidence_note",
    "product",
)
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
    ("世界动态", "/world3d"),
    ("负责人", "/落地"),
    ("从业者", "/现场"),
    ("案例", "/案例"),
    ("学习", "/方法"),
)
LANE_ZH = {
    "company": "公司",
    "deploy": "客户故事",
    "people": "人物",
    "method": "招聘",
}
LANE_SHORT = {
    "company": "公司",
    "deploy": "客户",
    "people": "人物",
    "method": "招聘",
}
CASE_FIELDS = """
    x.id, x.source_url, x.source_title, x.tier, x.doc_type,
    x.industry, x.business_problem, x.existing_workflow, x.pain_point,
    x.discovery_method, x.why_ai, x.hero_use_case, x.data_sources,
    x.integration, x.ai_model, x.agent_workflow, x.human_in_the_loop,
    x.evaluation, x.deployment, x.time_to_production, x.business_kpi,
    x.measured_outcome, x.failure_iteration, x.productization,
    x.customer_handoff, x.fde_role, x.quote, x.evidence_quality,
    x.evidence_note, x.product, x.kpi_scope, x.raw_company_text,
    cu.name AS customer_en, cu.named AS customer_named,
    COALESCE(NULLIF(cz.name_zh, ''), cu.name) AS customer,
    (
      SELECT GROUP_CONCAT(c.slug, ',')
      FROM case_companies cc JOIN companies c ON c.slug=cc.company_slug
      WHERE cc.case_id=x.id AND cc.role='vendor'
    ) AS vendor_slugs,
    (
      SELECT GROUP_CONCAT(COALESCE(NULLIF(c.name_zh, ''), c.name), ',')
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


def connect_rw():
    """可写连接（登录 users/oauth_states 表用）。公开读保持只读 connect()。"""
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def url_slug(url: str) -> str:
    parts = urlparse(url)
    host = (parts.netloc or "").replace("www.", "")
    path = (parts.path or "").strip("/").replace("/", "__") or "home"
    path = re.sub(r"[^A-Za-z0-9_.%-]", "_", path)[:110]
    qs = parse_qs(parts.query or "")
    extra = []
    for key in ("gh_jid", "jid", "v", "p", "id"):
        vals = qs.get(key) or []
        if vals:
            extra.append(re.sub(r"[^A-Za-z0-9_.%-]", "_", vals[0])[:48])
    if extra:
        path = path + "__" + "__".join(extra)
    return "%s__%s" % (host, path)


def _norm_orig_url(url: str) -> str:
    u = (url or "").strip()
    u = re.sub(r"^https?://www\.", "https://", u, flags=re.I)
    u = re.sub(r"^http://", "https://", u, flags=re.I)
    return u.rstrip("/")


def _orig_safe(path: Path) -> Path | None:
    try:
        resolved = path.resolve()
    except OSError:
        return None
    if not resolved.is_file():
        return None
    for root in (RAW_DIR, CORPUS_RAW, FDEI_DIR, AI_DIR):
        try:
            rr = root.resolve()
        except OSError:
            continue
        if resolved == rr or rr in resolved.parents:
            return resolved
    return None


def _sources_local_map() -> dict[str, str]:
    global _SOURCES_LOCAL_MAP
    if _SOURCES_LOCAL_MAP is not None:
        return _SOURCES_LOCAL_MAP
    mapping: dict[str, str] = {}
    try:
        with connect() as con:
            for r in con.execute(
                "SELECT url, local_raw FROM sources "
                "WHERE local_raw IS NOT NULL AND TRIM(local_raw) != ''"
            ):
                rel = str(r["local_raw"] or "").strip()
                if not rel:
                    continue
                nu = _norm_orig_url(r["url"] or "")
                if nu and nu not in mapping:
                    mapping[nu] = rel
    except sqlite3.Error:
        mapping = {}
    _SOURCES_LOCAL_MAP = mapping
    return mapping


def find_orig_file(url: str) -> Path | None:
    key = _norm_orig_url(url)
    if not key:
        return None
    if key in _ORIG_FILE_CACHE:
        return _ORIG_FILE_CACHE[key]
    found = _lookup_orig_file(url, key)
    _ORIG_FILE_CACHE[key] = found
    return found


def _lookup_orig_file(url: str, key: str) -> Path | None:
    rel = _sources_local_map().get(key)
    if rel:
        p = Path(rel)
        if not p.is_absolute():
            p = AI_DIR / rel
        ok = _orig_safe(p)
        if ok:
            return ok
    slug = url_slug(url)
    for folder in (RAW_DIR, CORPUS_RAW):
        for ext in _ORIG_EXTS:
            ok = _orig_safe(folder / (slug + ext))
            if ok:
                return ok
    # slug.* not slug* — comun must not match comun-bank
    rank = {".html": 0, ".htm": 1, ".json": 2, ".pdf": 3, ".txt": 4}
    for folder in (RAW_DIR, CORPUS_RAW):
        if not folder.is_dir():
            continue
        try:
            hits = [p for p in folder.glob(slug + ".*") if p.is_file()]
        except OSError:
            hits = []
        hits.sort(key=lambda p: (rank.get(p.suffix.lower(), 9), p.name))
        for hit in hits:
            ok = _orig_safe(hit)
            if ok:
                return ok
    if host_of(url) == "fdeinterviews.com":
        rel_path = (urlparse(url).path or "").strip("/")
        cands = []
        if rel_path:
            cands.append(FDEI_DIR / rel_path / "index.html")
            cands.append(FDEI_DIR / rel_path)
        else:
            cands.append(FDEI_DIR / "index.html")
        for cand in cands:
            ok = _orig_safe(cand)
            if ok:
                return ok
    return None


def strip_html(markup: str) -> str:
    text = markup or ""
    text = html.unescape(html.unescape(text))
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n", text)
    text = re.sub(r"(?is)</h[1-6]>", "\n", text)
    text = re.sub(r"(?is)<li[^>]*>", "\n• ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def extract_article_html(raw: str) -> str:
    """Prefer article body over nav / cookie / related-story chrome."""
    raw = raw or ""
    for cls in (
        "content-body",
        "article-body",
        "entry-content",
        "post-content",
        "article__body",
        "js-article",
    ):
        m = re.search(
            rf'(?is)<([a-z0-9]+)[^>]*class="[^"]*\b{re.escape(cls)}\b[^"]*"[^>]*>',
            raw,
        )
        if m:
            return raw[m.end() : m.end() + 40000]
    m = re.search(r"(?is)<article\b[^>]*>(.*)</article>", raw)
    if m and len(m.group(1)) > 400:
        return m.group(1)
    m = re.search(r"(?is)<main\b[^>]*>(.*)</main>", raw)
    if m and len(m.group(1)) > 400:
        return m.group(1)
    return raw


def orig_excerpt(url: str, n: int = 900) -> dict:
    """Plain-text excerpt from the local original backup. Empty if none."""
    path = find_orig_file(url)
    if not path:
        return {}
    raw = path.read_text(encoding="utf-8", errors="replace")
    title = ""
    text = ""
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
        if isinstance(data, dict):
            title = (data.get("title") or data.get("text") or "").strip()
            blob = data.get("content") or data.get("descriptionPlain") or data.get("descriptionHtml") or ""
            if isinstance(blob, dict):
                blob = blob.get("html") or blob.get("plain") or ""
            text = strip_html(str(blob))
        if not text:
            text = trunc(raw, n)
    else:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", raw, flags=re.I | re.S)
        if m:
            title = strip_html(m.group(1))
        text = strip_html(extract_article_html(raw))
        text = re.sub(r"^Local backup of \S+\s*", "", text)
        if title and text.startswith(title):
            text = text[len(title) :].lstrip(" \n")
        # Drop leftover chrome that still sneaks in.
        for noise in (
            "Continue to the site",
            "Skip to Content",
            "Notice at Collection",
            "Your Privacy Choices",
            "Exercise Your Privacy Rights",
        ):
            if text.startswith(noise) or text.find(noise) == 0:
                text = text.replace(noise, " ", 1)
        text = re.sub(r"^(?:•\s*)+", "", text).strip()
    if not text:
        return {"path": str(path)}
    return {"title": title, "text": trunc(text, n)}


def orig_href(kind, ident, url) -> str:
    if find_orig_file(url) is None:
        return ""
    if kind == "动态":
        return "/原文/动态/%s" % ident
    if kind == "案例":
        return "/原文/案例/%s" % ident
    return ""


_ORIG_BAR_STYLE = (
    "position:sticky;top:0;z-index:2147483647;background:#111;color:#f5f5f5;"
    "font:14px/1.4 system-ui,sans-serif;padding:8px 12px;border-bottom:1px solid #333;"
)


def _orig_chrome(back_href: str) -> str:
    return (
        f'<div id="imfde-orig-bar" style="{_ORIG_BAR_STYLE}">'
        f'本地备份 · 核对用 · 不是源站 · '
        f'<a href="{esc(back_href)}" style="color:#8ec8ff">返回观察</a>'
        "</div>"
        "<script>(function(){"
        'document.addEventListener("click",function(ev){'
        "var t=ev.target;if(!t||!t.closest)return;"
        'var a=t.closest("a");if(!a)return;'
        'var href=a.getAttribute("href")||"";'
        "if(/^https?:/i.test(href)){ev.preventDefault();ev.stopPropagation();}"
        "},true);"
        "})();</script>"
    )


def _inject_orig_bar(html_text: str, back_href: str) -> str:
    chrome = _orig_chrome(back_href)
    m = re.search(r"<body[^>]*>", html_text, flags=re.I)
    if m:
        return html_text[: m.end()] + chrome + html_text[m.end() :]
    return chrome + html_text


def _wrap_orig_pre(text: str, back_href: str) -> str:
    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/>'
        "<title>本地备份</title></head><body>"
        + _orig_chrome(back_href)
        + "<pre>"
        + esc(text)
        + "</pre></body></html>"
    )


def _orig_missing_html(kind: str, ident: int) -> bytes:
    back = "/%s/%s" % (kind, ident)
    page = (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/>'
        "<title>没有本地原文</title></head><body>"
        "<p>没有本地原文</p>"
        f'<p><a href="{esc(back)}">返回观察</a></p>'
        "</body></html>"
    )
    return page.encode("utf-8")


def _orig_source_url(kind: str, ident: int) -> str:
    try:
        with connect() as con:
            if kind == "动态":
                row = con.execute(
                    "SELECT url FROM world_events WHERE id=?", (ident,)
                ).fetchone()
                return (row["url"] if row else "") or ""
            row = con.execute(
                "SELECT source_url FROM cases WHERE id=?", (ident,)
            ).fetchone()
            return (row["source_url"] if row else "") or ""
    except sqlite3.Error:
        return ""


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
    return KPI_LABELS.get(scope) or "没写数字怎么来的"


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
        "SELECT %s FROM cases x "
        "LEFT JOIN customers cu ON cu.id=x.customer_id "
        "LEFT JOIN customer_zh cz ON cz.customer_id=cu.id "
        "WHERE %s ORDER BY %s" % (CASE_FIELDS, where, order)
    )
    return attach_case_zh(cur, annotate([dict(r) for r in cur.execute(sql, args)]))


def evidence_label(value: str | None) -> str:
    key = (value or "").strip()
    return EVIDENCE_ZH.get(key, key)


def doc_type_label(value: str | None) -> str:
    key = (value or "").strip()
    return DOC_TYPE_ZH.get(key, key)


def attach_case_zh(cur, rows: list) -> list:
    """Overlay Chinese display fields. English stays on the row as _en."""
    ids = [r.get("id") for r in rows if r.get("id") is not None]
    if not ids:
        return rows
    by_id = {}
    try:
        q = ",".join("?" * len(ids))
        for rec in cur.execute("SELECT * FROM case_zh WHERE case_id IN (%s)" % q, ids):
            by_id[rec["case_id"]] = dict(rec)
    except sqlite3.OperationalError:
        return rows
    for row in rows:
        z = by_id.get(row.get("id"))
        if not z:
            continue
        en = dict(row.get("_en") or {})
        if row.get("customer_en") and row.get("customer") != row.get("customer_en"):
            en["customer"] = row.get("customer_en")
        for field in CASE_ZH_FIELDS:
            zh = (z.get(field) or "").strip()
            if not zh:
                continue
            src = row.get(field)
            if nonempty(src) and src != zh:
                en[field] = src
            row[field] = zh
        if en:
            row["_en"] = en
    return rows


def en_archive_html(row: dict, case_id: int) -> str:
    src = row.get("source_url") or ""
    oh = orig_href("案例", case_id, src)
    if oh:
        return (
            f'<p class="hint"><a class="orig" href="{esc(oh)}">对照原文（英文存档）</a></p>'
        )
    return ""


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
        SELECT cc.company_slug AS slug, COALESCE(NULLIF(c.name_zh,''), c.name) AS name, COUNT(*) AS n
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
            SELECT cc.role, cc.company_slug, COALESCE(NULLIF(c.name_zh,''), c.name) AS name
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
                SELECT q.id, q.title, q.kind, q.difficulty,
                       COALESCE(l.stem, q.title) AS title_zh
                FROM questions q
                JOIN question_companies qc ON qc.question_id=q.id
                LEFT JOIN question_locales l ON l.question_id=q.id AND l.locale='zh'
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
        return '<span class="tg">写了驻场团队</span>'
    return ""


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
        + (f'<span class="tg">{esc(evidence_label(evid))}</span>' if evid else "")
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
    cid = row.get("id")
    src = row.get("source_url") or ""
    url = href("/案例/%s" % cid) if cid else src
    title = row.get("source_title") or row.get("customer") or "条目"
    try:
        from worldview import title_from_url

        mapped = title_from_url(src or url)
        if mapped:
            has_han = any("\u4e00" <= ch <= "\u9fff" for ch in title)
            if not has_han:
                title = mapped
    except Exception:
        pass
    host = row.get("host") or extra or host_of(src)
    dtype = doc_type_label(row.get("doc_type"))
    sub = " · ".join(x for x in (dtype, host) if x)
    ext = "" if url.startswith("/") else (' target="_blank" rel="noopener noreferrer"' if url else "")
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
    """Official mark: cap-logo image only (imfde 定制：不放文字字样)."""
    return '<img class="brand-logo" src="/static/icons/logo-mark.png" alt="imfde.ai"/>'


_CURRENT_COOKIES: dict = {}


def set_request_cookies(cookies: dict | None) -> None:
    """每个请求渲染前调用：把当次请求的 cookie 交给渲染层（登录头像用）。"""
    global _CURRENT_COOKIES
    _CURRENT_COOKIES = cookies or {}


def auth_link(next_path: str = "/") -> str:
    """导航栏右侧的登录入口 / 已登录头像。不做限权，仅身份展示。"""
    import auth as A

    user = A.current_user_cookie(_CURRENT_COOKIES)
    if user:
        name = esc((user.get("name") or "用户")[:18])
        avatar = esc(user.get("avatar") or "")
        avatar_html = (
            f'<img class="auth-avatar" src="{avatar}" alt="" referrerpolicy="no-referrer"/>' if avatar else ""
        )
        return (
            f'<a class="auth-entry on" href="/退出登录?next={esc(next_path)}" title="退出登录">'
            f'{avatar_html}<span class="auth-name">{name}</span></a>'
        )
    return f'<a class="auth-entry" href="/登录?next={esc(next_path)}">登录</a>'


def brand_wordmark() -> str:
    """imfde.ai 文字字标：im 主体色、fde 强调色、.ai 灰。"""
    return (
        '<span class="brand-mark">'
        '<span class="brand-im">im</span>'
        '<span class="brand-fde">fde</span>'
        '<span class="brand-tld">.ai</span>'
        "</span>"
    )


def brand_lockup() -> str:
    """帽子 logo + imfde.ai 字样。"""
    return f"{brand_mark()}{brand_wordmark()}"


def abs_url(path: str = "/") -> str:
    text = (path or "/").strip() or "/"
    if not text.startswith("/"):
        text = "/" + text
    return SITE_ORIGIN + text


def mast(active: str, gh_url: str = "", tagline: str | None = None) -> str:
    links = []
    for label, path in NAV:
        cls = "on" if active == label else ""
        aria = ' aria-current="page"' if cls else ""
        links.append(f'<a class="{cls}" href="{esc(path)}"{aria}>{esc(label)}</a>')
    if IM_FDE_PORTAL_URL:
        links.append(f'<a class="back-to-portal" href="{esc(IM_FDE_PORTAL_URL)}">imfde 门户 →</a>')
    links.append(auth_link("/"))
    return f"""<div class="mast"><div class="mast-in">
  <a class="brand" href="/world3d" aria-label="{esc(SITE_NAME)} {esc(SITE_CLUB)}">
    {brand_lockup()}
  </a>
  <nav>{''.join(links)}</nav>
</div></div>"""


def footer(gh_url: str, extra="", tagline: str | None = None, learn: bool = False) -> str:
    gh = ext_link(gh_url, "github.com/Qbuby/imfde") if gh_url else ""
    learn = learn or bool(tagline and "学习资料" in tagline)
    if learn:
        line2 = f"{esc(SITE_DOMAIN)} · 学习手册，不是行业动态。"
        extra_line = "<p>面试答案不在此站展示。</p>"
    else:
        line2 = (
            f"{esc(SITE_DOMAIN)} · 观察截止 {esc(day_zh(SNAPSHOT))}。"
            "窗口按 7 / 30 / 90 天切换。"
        )
        extra_line = ""
    gh_p = f"<p>{gh}</p>" if gh else ""
    return f"""<footer class="ft">
  <p><b>{esc(SITE_NAME)}</b> · {esc(SITE_CLUB)}</p>
  <p>{esc(SITE_SLOGAN)}</p>
  <p>{line2}</p>
  {extra_line}{gh_p}
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
    tagline: str | None = None,
    learn: bool = False,
) -> str:
    css = '<link rel="stylesheet" href="/static/tokens.css"/>'
    if home_css:
        css += '<link rel="stylesheet" href="/static/home.css"/>'
        css += '<link rel="stylesheet" href="/static/desk.css"/>'
        if not body_class:
            body_class = "desk-page"
    body_attr = f' class="{esc(body_class)}"' if body_class else ""
    foot = "" if skip_foot else footer(gh_url, extra_foot, tagline=tagline, learn=learn)
    mast_html = "" if skip_mast else mast(active, gh_url, tagline=tagline)
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
<meta name="description" content="{esc(tagline or SITE_TAGLINE)}"/>
<link rel="canonical" href="{esc(canon)}"/>
<meta property="og:site_name" content="{esc(SITE_NAME)}"/>
<meta property="og:title" content="{esc(title)}"/>
<meta property="og:description" content="{esc(tagline or SITE_TAGLINE)}"/>
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


def qs_window(qs) -> int:
    n = qs_int(qs, "窗", "range", default=30)
    return n if n in (7, 30, 90) else 30


def load_pace(cur) -> dict:
    from worldview import load_world

    return load_world(cur)


def win_events(events, days, lanes=None, skip_jobs=True):
    from worldview import _win

    rows = _win(events, days)
    if lanes:
        want = set(lanes)
        rows = [e for e in rows if e.get("lane") in want]
    if skip_jobs:
        rows = [e for e in rows if e.get("info_kind") != "job_posting"]
    rows.sort(key=lambda e: (e.get("day") or "", e.get("id") or 0), reverse=True)
    return rows


def lane_tally(events, days) -> dict:
    from worldview import _win

    rows = _win(events, days)
    jobs = sum(1 for e in rows if e.get("info_kind") == "job_posting")
    solid = [e for e in rows if e.get("info_kind") != "job_posting"]
    by = {"company": 0, "deploy": 0, "people": 0, "method": 0}
    for e in solid:
        key = e.get("lane")
        if key in by:
            by[key] += 1
    return {"total": len(solid), "jobs": jobs, "by_lane": by}


def pace_strip(base, days, events, lanes=None, extra=None) -> str:
    extra = {k: v for k, v in (extra or {}).items() if v}
    keys = tuple(lanes) if lanes else ("company", "deploy", "people", "method")
    cards = []
    for d in (7, 30, 90):
        tally = lane_tally(events, d)
        n = sum(tally["by_lane"].get(k, 0) for k in keys)
        bits = " · ".join(f"{LANE_SHORT[k]} {tally['by_lane'].get(k, 0)}" for k in keys)
        if tally["jobs"] and (not lanes or "method" in keys):
            bits += f" · 岗 {tally['jobs']}（弱）"
        cls = "on" if d == days else ""
        url = href(base, 窗=d, **extra)
        cards.append(
            f'<a class="{cls}" href="{esc(url)}"><b>{d} 天</b>'
            f"<strong>{n}</strong><span>{esc(bits)}</span></a>"
        )
    return f'<nav class="pace" aria-label="时间窗口">{"".join(cards)}</nav>'


def other_windows(base, days, extra=None) -> str:
    extra = {k: v for k, v in (extra or {}).items() if v}
    links = [
        f'<a href="{esc(href(base, 窗=d, **extra))}">{d} 天</a>'
        for d in (7, 30, 90)
        if d != days
    ]
    return " · ".join(links)


def event_card(event, lens="boss") -> str:
    lane = event.get("lane") or ""
    day = event.get("day") or ""
    md = "%d-%s" % (int(day[5:7]), day[8:10]) if len(day) >= 10 else day
    title = event.get("title") or ""
    kicker = event.get("kicker") or event.get("entity_name") or ""
    if lens == "field":
        body = event.get("practitioner") or event.get("happened") or event.get("sub") or ""
    else:
        body = event.get("enterprise") or event.get("why") or event.get("happened") or event.get("sub") or ""
    page = event.get("href") or (href("/动态/%s" % event["id"]) if event.get("id") else "")
    heading = f'<a href="{esc(page)}">{esc(title)}</a>' if page else esc(title)
    meta = f'<time datetime="{esc(day)}">{esc(md)}</time>'
    meta += f'<span class="lane-dot {esc(lane)}"></span>{esc(LANE_ZH.get(lane, lane))}'
    if kicker:
        meta += f" · {esc(kicker)}"
    body_html = f'<p class="ev-body">{esc(trunc(body, 220))}</p>' if body else ""
    return (
        f'<article class="ev" data-lane="{esc(lane)}">'
        f'<p class="ev-meta">{meta}</p><h3>{heading}</h3>{body_html}</article>'
    )


def event_list(events, lens="boss", empty="这一窗没有条目。") -> str:
    if not events:
        return f'<p class="empty">{empty}</p>'
    return '<div class="ev-list">' + "".join(event_card(e, lens) for e in events) + "</div>"


def change_cards(changes, lanes=None) -> str:
    want = set(lanes) if lanes else None
    picked = []
    for ch in changes or []:
        ch_lanes = set(ch.get("lanes") or [])
        if want and ch_lanes and not (ch_lanes & want):
            continue
        picked.append(ch)
    bits = []
    for i, ch in enumerate(picked, 1):
        bits.append(
            claim_block(
                str(i),
                ch.get("title") or "",
                f"<p>{esc(ch.get('body') or '')}</p>",
            )
        )
    return "".join(bits)


ROOM_HEAD = (
    '<link rel="stylesheet" href="/static/room.css"/>'
    '<script defer src="/static/room.js"></script>'
)


def day_md(day: str) -> str:
    text = day or ""
    if len(text) >= 10:
        return "%d-%s" % (int(text[5:7]), text[8:10])
    return text


def room_nav(active: str, gh: str, days: int | None = None) -> str:
    bits = []
    for label, path in NAV:
        url = path
        if days and path in ("/落地", "/现场", "/案例"):
            url = href(path, 窗=days)
        cls = "on" if active == label else ""
        aria = ' aria-current="page"' if cls else ""
        bits.append(f'<a class="{cls}" href="{esc(url)}"{aria}>{esc(label)}</a>')
    bits.append(auth_link("/"))
    return "".join(bits)


def room_range(base: str, days: int, extra: dict | None = None) -> str:
    extra = {k: v for k, v in (extra or {}).items() if v}
    btns = []
    for d in (7, 30, 90):
        cls = ' class="on"' if d == days else ""
        url = href(base, 窗=d, **extra)
        btns.append(f"<a{cls} href=\"{esc(url)}\">{d} 天</a>")
    return f'<div class="room-seg" role="navigation" aria-label="看多久">{"".join(btns)}</div>'


def room_hud(
    active: str,
    gh: str,
    title: str,
    hint: str,
    days: int | None = None,
    range_base: str | None = None,
    extra: dict | None = None,
) -> str:
    tools = ""
    if range_base and days:
        tools += room_range(range_base, days, extra)
    tools += f'<nav class="room-nav" aria-label="站内导航">{room_nav(active, gh, days)}</nav>'
    return f"""<header class="room-hud">
  <a class="room-brand" href="/world3d" aria-label="{esc(SITE_NAME)} {esc(SITE_CLUB)}">{brand_lockup()}</a>
  <div class="room-hud-mid">
    <h1 class="room-title">{esc(title)}</h1>
    <p class="room-sub">{esc(hint)}</p>
  </div>
  <div class="room-hud-tools">{tools}</div>
</header>"""


def event_payload(e: dict) -> dict:
    return {
        "id": e.get("id"),
        "lane": e.get("lane"),
        "day": e.get("day"),
        "title": e.get("title"),
        "kicker": e.get("kicker") or e.get("entity_name") or "",
        "host": e.get("host") or "",
        "doc_label": e.get("doc_label") or "",
        "happened": e.get("happened") or "",
        "why": e.get("why") or "",
        "enterprise": e.get("enterprise") or "",
        "practitioner": e.get("practitioner") or "",
        "orig_href": e.get("orig_href") or "",
        "url": e.get("url") or "",
        "case_href": e.get("case_href") or "",
        "info_kind": e.get("info_kind") or "",
    }


def room_data_tag(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    raw = raw.replace("<", "\\u003c")
    return f'<script type="application/json" id="room-data">{raw}</script>'


def room_event_card(event: dict, selected_id, lens: str) -> str:
    eid = event.get("id")
    on = " on" if eid == selected_id else ""
    pressed = "true" if eid == selected_id else "false"
    day = event.get("day") or ""
    if lens == "field":
        blurb = event.get("practitioner") or event.get("happened") or event.get("sub") or ""
    else:
        blurb = event.get("enterprise") or event.get("happened") or event.get("sub") or ""
    return (
        f'<button type="button" class="room-card{on}" data-pick="{esc(str(eid))}" '
        f'aria-pressed="{pressed}">'
        f'<time datetime="{esc(day)}">{esc(day_md(day))}</time>'
        f'<strong>{esc(event.get("title") or "")}</strong>'
        f"<span>{esc(trunc(blurb, 110))}</span></button>"
    )


def room_page(
    title: str,
    active: str,
    gh: str,
    page_path: str,
    hud: str,
    stage: str,
    panel: str,
    payload: dict,
    *,
    lens: str = "boss",
    doc: bool = False,
) -> str:
    cls = "room room-doc" if doc else "room"
    inner = f"""<div class="{cls}" id="room" data-lens="{esc(lens)}">
{hud}
<div class="room-stage">{stage}</div>
<aside class="room-panel" id="room-panel">{panel}</aside>
</div>
{room_data_tag(payload)}
"""
    return shell(
        title,
        active,
        inner,
        gh,
        extra_head=ROOM_HEAD,
        body_class="room-page",
        skip_wrap=True,
        skip_mast=True,
        skip_foot=True,
        home_css=False,
        page_path=page_path,
    )


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
  <p class="lead">AI 抽出的是整体结构：编制几乎不出现、岗位讨论有时间线、库内条数被产品故事拉开。不是实时资讯，也不是编制咨询。</p>
  <p class="meta-line">{counts['n_cases']} 条观察 · 发布日从已抓 HTML 回填</p>
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
    <p class="k">给负责人</p>
    <h2>要实施，先看结构再看样板</h2>
    <p>编制在原文里有多薄、什么样板算数、结果带什么口径。行业切面改的是这些句子里的数字，不是先铺一墙卡片。</p>
    <a class="go" href="/落地">给负责人看本期</a>
  </article>
  <article class="door">
    <p class="k">现场读法</p>
    <h2>近态是评论时间线 + 现场密度</h2>
    <p>a16z / Pragmatic Engineer / OpenAI Frontier 排成一条有发布日的线；客户故事按厂商密度读，不当新闻 feed。</p>
    <a class="go" href="/现场">用现场读法看本期 <span>给从业者</span></a>
  </article>
</div>
{catalog_door("/案例", "逐条看案例", "目录、筛选、分页。两种读法的证据都在这里。")}
"""
    return shell("%s · 本期观察" % SITE_NAME, "", inner, gh, page_path="/")


def render_deploy(cur, qs) -> str:
    days = qs_window(qs)
    world = load_pace(cur)
    events = world.get("events") or []
    company = win_events(events, days, lanes=("company",))
    deploy = win_events(events, days, lanes=("deploy",))
    gh = world.get("github") or github_url(cur)
    alt = other_windows("/落地", days)
    selected = (deploy[0] if deploy else company[0] if company else None)
    sid = selected.get("id") if selected else None
    co_html = (
        "".join(room_event_card(e, sid, "boss") for e in company)
        or f'<p class="room-empty">这 {days} 天没有新的公司公告。{alt}</p>'
    )
    dp_html = (
        "".join(room_event_card(e, sid, "boss") for e in deploy)
        or f'<p class="room-empty">这 {days} 天没有带发布日的客户故事。空着就空着。{alt}</p>'
    )
    empty = not company and not deploy
    hud = room_hud(
        "负责人",
        gh,
        "给负责人看",
        "这几天没有新的公司动作" if empty else "点左边一条，右边告诉你对企业意味着什么",
        days=days,
        range_base="/落地",
    )
    how = (
        f'<p class="room-how"><b>这 {days} 天公司没发新东西。</b> 要看客户故事，切 30 天或 90 天。</p>'
        if empty
        else '<p class="room-how"><b>你是要拍板的人。</b> 点左边一条，右边告诉你对企业意味着什么。</p>'
    )
    stage = f"""
{how}
<div class="room-cols">
  <div class="room-col" data-lane="company"><h2>公司在做什么</h2>{co_html}</div>
  <div class="room-col" data-lane="deploy"><h2>客户那边发生了什么</h2>{dp_html}</div>
</div>
"""
    payload = {
        "kind": "event",
        "lens": "boss",
        "items": [event_payload(e) for e in company + deploy],
    }
    panel = ""
    return room_page(
        "给负责人看 · %s" % SITE_NAME,
        "负责人",
        gh,
        "/落地",
        hud,
        stage,
        panel,
        payload,
        lens="boss",
    )


def render_field(cur, qs) -> str:
    days = qs_window(qs)
    world = load_pace(cur)
    events = world.get("events") or []
    people = win_events(events, days, lanes=("people",))
    tally = lane_tally(events, days)
    gh = world.get("github") or github_url(cur)
    alt = other_windows("/现场", days)
    selected = people[0] if people else None
    sid = selected.get("id") if selected else None
    ticks = "".join(
        (
            f'<button type="button" class="room-tick{" on" if e.get("id")==sid else ""}" '
            f'data-pick="{esc(str(e.get("id")))}" aria-pressed="{"true" if e.get("id")==sid else "false"}">'
            f'<time datetime="{esc(e.get("day") or "")}">{esc(day_md(e.get("day") or ""))}</time>'
            f'<strong>{esc(e.get("title") or "")}</strong>'
            f'<span>{esc(trunc(e.get("practitioner") or e.get("happened") or "", 110))}</span>'
            f"</button>"
        )
        for e in people
    ) or f'<p class="room-empty">这 {days} 天没有新的公开评论。{alt}</p>'
    hud = room_hud(
        "从业者",
        gh,
        "给干活的人看",
        "点一条评论，听一线怎么讲这份工",
        days=days,
        range_base="/现场",
    )
    jobs_n = tally.get("jobs") or 0
    jobs_note = (
        f'<p class="room-weak"><a href="{esc(href("/", 窗=days))}">动态上有 {jobs_n} 条招聘</a>。'
        "只能说明还在招人，不说明事情已经做成了。</p>"
        if jobs_n
        else ""
    )
    stage = f"""
<p class="room-how"><b>你在现场干活。</b> 点一条评论，右边听一线怎么讲这份工。</p>
{jobs_note}
<div class="room-spine">{ticks}</div>
"""
    payload = {"kind": "event", "lens": "field", "items": [event_payload(e) for e in people]}
    return room_page(
        "给干活的人看 · %s" % SITE_NAME,
        "从业者",
        gh,
        "/现场",
        hud,
        stage,
        "",
        payload,
        lens="field",
    )


def render_library(cur, qs) -> str:
    days = qs_window(qs)
    industry = qs_get(qs, "行业", "industry")
    vendor = qs_get(qs, "厂商", "vendor")
    evidence = qs_get(qs, "证据", "evidence")
    windowed = qs_get(qs, "本窗") not in ("0", "false", "否")
    page = qs_int(qs, "页", "page", default=1)
    valid_ind = {name for name, _ in INDUSTRY_BUCKETS} | {"其他"}
    if industry not in valid_ind:
        industry = ""
    if evidence not in ("high", "medium", "low"):
        evidence = ""
    world = load_pace(cur)
    events = world.get("events") or []
    deploy = win_events(events, days, lanes=("deploy",))
    win_ids = set()
    for e in deploy:
        h = e.get("case_href") or ""
        m = re.fullmatch(r"/案例/(\d+)", h)
        if m:
            win_ids.add(int(m.group(1)))
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
    if windowed:
        rows = [r for r in rows if r.get("id") in win_ids]
    per = 18
    total = len(rows)
    pages = max(1, (total + per - 1) // per)
    if page > pages:
        page = pages
    shown = rows[(page - 1) * per : page * per]
    flags = load_flags(cur, [r["id"] for r in shown])
    gh = world.get("github") or github_url(cur)
    extra = {"行业": industry, "证据": evidence, "厂商": vendor, "本窗": "1" if windowed else "0"}
    q = {"窗": days, "行业": industry, "证据": evidence, "本窗": "1" if windowed else "0"}
    vchips = [
        chip(href("/案例", **q), "全部公司", on=not vendor),
        chip(href("/案例", 厂商="核心", **q), "主要这几家", on=vendor == "核心"),
    ]
    for v in vendors[:8]:
        vchips.append(
            chip(href("/案例", 厂商=v["slug"], **q), v["name"], on=vendor == v["slug"], n=v["n"])
        )
    evid_q = {"窗": days, "厂商": vendor, "行业": industry, "本窗": "1" if windowed else "0"}
    evid_chips = [
        chip(href("/案例", **evid_q), "可靠程度", on=not evidence),
        chip(href("/案例", 证据="high", **evid_q), "比较可靠", on=evidence == "high"),
        chip(href("/案例", 证据="medium", **evid_q), "一般", on=evidence == "medium"),
        chip(href("/案例", 证据="low", **evid_q), "不太够", on=evidence == "low"),
    ]
    base = {"窗": days, "厂商": vendor, "证据": evidence, "本窗": "1" if windowed else "0"}
    ind_chips = [chip(href("/案例", **base), "全部行业", on=not industry)]
    for name, _kws in INDUSTRY_BUCKETS:
        ind_chips.append(chip(href("/案例", 行业=name, **base), name, on=industry == name))
    win_q = {"窗": days, "厂商": vendor, "行业": industry, "证据": evidence}
    win_chip = chip(href("/案例", 本窗="1", **win_q), "这段时间的", on=windowed, n=len(win_ids))
    all_win = chip(href("/案例", 本窗="0", **win_q), "全部", on=not windowed)

    cards = []
    items = []
    for r in shown:
        cid = r.get("id")
        title = r.get("customer") or r.get("source_title") or "未具名客户"
        k = " · ".join(x for x in (vendor_name(r), r.get("bucket")) if x)
        evid = r.get("evidence_quality") or ""
        blurb = trunc(r.get("business_problem") or r.get("measured_outcome"), 110)
        on = " on" if cards == [] else ""
        tags = []
        if evid:
            tags.append(f"<i>{esc(evidence_label(evid))}</i>")
        if r.get("kpi_scope"):
            tags.append(f"<i>{esc(kpi_label(r.get('kpi_scope')))}</i>")
        if has_fde_role(r):
            tags.append("<i>写了驻场团队</i>")
        cards.append(
            f'<button type="button" class="room-gcard{on}" data-pick="{esc(str(cid))}">'
            f'<span class="k">{esc(k)}</span><strong>{esc(title)}</strong>'
            f'<p>{esc(blurb)}</p><div class="room-tags">{"".join(tags)}</div></button>'
        )
        items.append(
            {
                "id": cid,
                "title": title,
                "vendor": vendor_name(r),
                "evidence": evidence_label(evid) if evid else "",
                "kpi": kpi_label(r.get("kpi_scope")),
                "blurb": blurb,
                "fde": has_fde_role(r),
                "href": href("/案例/%s" % cid, 窗=days),
            }
        )
    grid = "".join(cards) or (
        f'<p class="room-empty">这 {days} 天没有带发布日的客户故事。空着就空着。</p>'
        if windowed
        else '<p class="room-empty">没有匹配的案例。</p>'
    )
    page_q = {"窗": days, "厂商": vendor, "行业": industry, "证据": evidence, "本窗": "1" if windowed else "0"}
    prev_h = href("/案例", 页=page - 1, **page_q) if page > 1 else ""
    next_h = href("/案例", 页=page + 1, **page_q) if page < pages else ""
    pager = f'<p class="room-pager">{page} / {pages} 页 · 共 {total} 条'
    if prev_h:
        pager += f' · <a href="{esc(prev_h)}">上一页</a>'
    if next_h:
        pager += f' · <a href="{esc(next_h)}">下一页</a>'
    pager += "</p>"
    hud = room_hud(
        "案例",
        gh,
        "案例",
        "点一张卡片看看，再打开全文",
        days=days,
        range_base="/案例",
        extra=extra,
    )
    stage = f"""
<p class="room-how"><b>找客户案例。</b> 默认只看这窗里带发布日的。点一张卡片看摘要，再打开全文对照原文。</p>
<div class="room-filt">{all_win}{win_chip}{''.join(vchips[:6])}</div>
<div class="room-filt">{''.join(ind_chips)}</div>
<div class="room-filt">{''.join(evid_chips)}</div>
<div class="room-grid">{grid}</div>
{pager}
"""
    payload = {"kind": "case", "lens": "boss", "items": items}
    return room_page(
        "案例 · %s" % SITE_NAME,
        "案例",
        gh,
        "/案例",
        hud,
        stage,
        "",
        payload,
        lens="boss",
    )


_FDE_NOTE = re.compile(
    r"[^。；;\n]*?(?:FDE/FDSE|forward-deployed|未描述 FDE|无 FDE|未明确 FDE|未自称 FDE|FDE 审阅|FDE 头衔)[^。；;\n]*[。；;]?",
    re.I,
)


def human_anatomy(value) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = _FDE_NOTE.sub("", text)
    return re.sub(r"[；;]\s*$", "", text).strip()


def dl_row(label, value) -> str:
    text = human_anatomy(value) if nonempty(value) else ""
    if text:
        return f"<dt>{esc(label)}</dt><dd>{esc(text).replace(chr(10), '<br/>')}</dd>"
    return f'<dt>{esc(label)}</dt><dd class="empty">原文未写</dd>'


def render_case(cur, case_id: int, qs) -> str:
    row = load_case(cur, case_id)
    gh = github_url(cur)
    if not row:
        inner = '<section class="desk-lede"><h1>没有这条案例</h1><p><a href="/案例">回到案例</a></p></section>'
        return shell("未找到 · %s" % SITE_NAME, "案例", inner, gh, page_path="/案例")
    view = qs_get(qs, "读法", "view")
    if view not in ("落地", "现场"):
        view = ""
    title = row.get("customer") or row.get("source_title") or "案例"
    k = " · ".join(x for x in (vendor_name(row), row.get("bucket"), row.get("product")) if x)
    src = row.get("source_url") or ""
    oh = orig_href("案例", case_id, src)
    if oh:
        src_html = (
            f'<a class="orig" href="{esc(oh)}">'
            f"对照原文 · {esc(host_of(src) or src)}</a>"
        )
    elif src:
        src_html = (
            f'<a class="orig" href="{esc(src)}" target="_blank" rel="noopener noreferrer">'
            f"打开原文 · {esc(host_of(src) or src)}</a>"
        )
    else:
        src_html = "没有原文链接"
    on_d = " on" if view == "落地" else ""
    on_f = " on" if view == "现场" else ""
    flags_html = ""
    if row.get("flags"):
        kept = [
            f
            for f in row["flags"]
            if not re.search(r"FDE|forward-deployed", (f.get("flag") or "") + (f.get("reason") or ""), re.I)
        ]
        if kept:
            flags_html = "<div class='list' style='margin-top:12px'>" + "".join(
                f'<div class="row">{esc(f["flag"])}<span class="s">{esc(f["reason"])}</span></div>'
                for f in kept
            ) + "</div>"
    related = ""
    if row.get("related_questions"):
        items = []
        for q in row["related_questions"]:
            label = q.get("title_zh") or q.get("stem_zh") or q.get("title") or q.get("id")
            items.append(
                f'<div class="row">{esc(label)}'
                f'<span class="s">开放题 · 答案不在此站展示</span></div>'
            )
        related = (
            '<section class="section"><h2>相关开放题</h2>'
            '<p class="note">附录。面试准备用，不是落地依据。</p>'
            f'<div class="list">{"".join(items)}</div></section>'
        )
    quote = ""
    if nonempty(row.get("quote")):
        quote = f'<blockquote class="quote">{esc(row["quote"])}</blockquote>'
    days = qs_window(qs)
    hud = room_hud("案例", gh, title, "对照原文看完整内容", days=days, range_base=None)
    inner = f"""
<div class="room room-doc" id="room">
{hud}
<div class="room-stage">
<div class="room-docmain">
  <a class="room-back" href="{esc(href("/案例", 窗=days))}">← 回案例</a>
  <p class="room-kicker">{esc(k)}</p>
  <h1>{esc(title)}</h1>
  <div class="room-meta">
    {src_html}
    {kpi_span(row.get("kpi_scope"))}
    <span class="tg">{esc(evidence_label(row.get("evidence_quality")))}</span>
    {fde_flag(row)}
    <a class="{ 'on' if view=='落地' else '' }" href="{esc(href("/案例/"+str(case_id), 读法="落地", 窗=days))}">给负责人</a>
    <a class="{ 'on' if view=='现场' else '' }" href="{esc(href("/案例/"+str(case_id), 读法="现场", 窗=days))}">给现场的人</a>
  </div>
  <div class="room-pair">
    <section class="room-box{on_d}" id="落地读法">
      <h2>给负责人</h2>
      <dl class="anatomy">
        {dl_row("要解决什么", row.get("business_problem"))}
        {dl_row("结果", row.get("measured_outcome"))}
        {dl_row("这个数字怎么来的", kpi_label(row.get("kpi_scope")))}
        {dl_row("接了哪些系统", row.get("integration"))}
        {dl_row("用了什么数据", row.get("data_sources"))}
        {dl_row("人还管哪一步", row.get("human_in_the_loop"))}
        {dl_row("多久上线", row.get("time_to_production"))}
        {dl_row("怎么交给客户", row.get("customer_handoff"))}
        {dl_row("有没有驻场团队", row.get("fde_role"))}
      </dl>
    </section>
    <section class="room-box{on_f}" id="现场读法">
      <h2>给现场的人</h2>
      <dl class="anatomy">
        {dl_row("主要用在哪", row.get("hero_use_case"))}
        {dl_row("以前怎么干", row.get("existing_workflow"))}
        {dl_row("卡在哪", row.get("pain_point"))}
        {dl_row("用了什么模型", row.get("ai_model"))}
        {dl_row("事情怎么流转", row.get("agent_workflow"))}
        {dl_row("怎么验收", row.get("evaluation"))}
        {dl_row("怎么上线", row.get("deployment"))}
        {dl_row("失败了怎么改", row.get("failure_iteration"))}
        {dl_row("能不能复用到下一家", row.get("productization"))}
      </dl>
    </section>
  </div>
  {quote}
  <section class="section">
    <h2>备注</h2>
    <p class="note">{esc(human_anatomy(row.get("evidence_note") or "") or "没有补充说明。")}</p>
    {flags_html}
  </section>
  {en_archive_html(row, case_id)}
  {related}
</div>
</div>
</div>
"""
    return shell(
        "%s · %s" % (title, SITE_NAME),
        "案例",
        inner,
        gh,
        extra_head='<link rel="stylesheet" href="/static/room.css"/>',
        body_class="room-page",
        skip_wrap=True,
        skip_mast=True,
        skip_foot=True,
        home_css=False,
        page_path="/案例/%s" % case_id,
    )


def load_world_event(cur, event_id: int):
    from worldview import event_from_world

    row = cur.execute(
        """SELECT e.*, COALESCE(NULLIF(ent.name_zh, ''), ent.name) AS entity_name
           FROM world_events e
           LEFT JOIN world_entities ent ON ent.slug=e.entity_slug
           WHERE e.id=?""",
        (event_id,),
    ).fetchone()
    if not row:
        return None
    case = None
    cid = row["source_case_id"]
    if cid:
        found = fetch_cases(cur, "x.id=?", (int(cid),), "x.id")
        case = found[0] if found else None
    event = event_from_world(row, case, row["entity_name"] or "")
    if event:
        event["orig_href"] = orig_href("动态", event["id"], event.get("url") or "")
    return event


def render_event(cur, event_id: int) -> str:
    event = load_world_event(cur, event_id)
    gh = github_url(cur)
    if not event:
        inner = '<section class="desk-lede"><h1>没有这条动态</h1><p><a href="/world3d">回世界动态</a></p></section>'
        return shell("未找到 · %s" % SITE_NAME, "动态", inner, gh, page_path="/动态")
    lane = event.get("lane") or ""
    day = event.get("day") or ""
    src = event.get("url") or ""
    case_href = event.get("case_href") or ""
    job = event.get("info_kind") == "job_posting"
    bits = []
    if src:
        oh = event.get("orig_href") or orig_href("动态", event_id, src)
        host = event.get("host") or host_of(src)
        if oh:
            bits.append(
                f'<a class="orig" href="{esc(oh)}">'
                f"对照原文 · {esc(host)}</a>"
            )
        else:
            bits.append(
                f'<a class="orig" href="{esc(src)}" target="_blank" rel="noopener noreferrer">'
                f"打开原文 · {esc(host)}</a>"
            )
    if case_href:
        bits.append(f'<a href="{esc(case_href)}">看完整案例</a>')
    extra = (" · ".join(bits)) if bits else ""
    job_note = (
        '<p class="note">岗位是弱信号：说明还在招现场的人，不是组织已经落地。</p>'
        if job
        else ""
    )
    orig_block = ""

    def fluff_why(text):
        t = (text or "").strip()
        return (not t) or any(
            m in t
            for m in (
                "有名字、有日期",
                "有日期、有名字",
                "具名客户且",
                "可作为交付现场",
                "这是公开材料",
                "有名字的人写的评论",
                "有日期的演讲",
                "讲怎么干活的材料",
                "这是公司自己宣布的组织变化",
            )
        )

    def fluff_prac(text):
        t = (text or "").strip()
        return (not t) or any(
            m in t
            for m in (
                "Forward Deployed 头衔",
                "驻场工程师这个岗位名",
                "不是编制样板",
                "不是怎么组团队",
                "可核的是客户",
            )
        )

    def block(title, text, empty=None):
        body = (text or "").strip()
        if not body:
            if empty is None:
                return ""
            body = empty
        cls = " empty" if not (text or "").strip() else ""
        return f'<section class="section"><h2>{esc(title)}</h2><p class="ev-read{cls}">{esc(body)}</p></section>'

    why_html = "" if fluff_why(event.get("why")) else block("为什么要看", event.get("why"))
    ent_html = block("对企业意味着什么", event.get("enterprise"))
    prac_html = (
        ""
        if fluff_prac(event.get("practitioner"))
        else block("对干活的人意味着什么", event.get("practitioner"))
    )

    inner = f"""
<section class="desk-lede">
  <p class="k">{esc(LANE_ZH.get(lane, lane))} · {esc(day_zh(day) or day)}</p>
  <h1>{esc(event.get("title") or "")}</h1>
  <p>{esc(event.get("kicker") or event.get("entity_name") or "")} · {esc(event.get("doc_label") or "")}</p>
  {job_note}
</section>
{orig_block}
{block("发生了什么", event.get("happened"), "还没写出摘要。")}
{why_html}
{ent_html}
{prac_html}
<p class="hint">{extra}</p>
<p class="hint"><a href="/world3d">回世界动态</a> · <a href="/落地">负责人</a> · <a href="/现场">从业者</a> · <a href="/方法">学习</a></p>
"""
    return shell(
        "%s · %s" % (event.get("title") or "动态", SITE_NAME),
        "动态",
        inner,
        gh,
        page_path="/动态/%s" % event_id,
    )


def render_methods(cur, qs) -> str:
    from methods import render_home

    return render_home(cur)


def render_path(path: str, qs) -> str:
    with connect() as con:
        cur = con.cursor()
        if path in ("/", "/index.html", "/世界动态", "/world3d", "/沙盘", "/立体世界"):
            from world3d import render_world3d

            return render_world3d(cur)
        if path in ("/平面", "/时间轴"):
            from worldview import render_world

            return render_world(cur)
        if path == "/落地":
            return render_deploy(cur, qs)
        if path == "/现场":
            return render_field(cur, qs)
        if path == "/案例":
            return render_library(cur, qs)
        if path == "/方法":
            return render_methods(cur, qs)
        m = re.fullmatch(r"/方法/([a-z0-9-]+)", path)
        if m:
            from methods import render_node

            return render_node(cur, m.group(1))
        m = re.fullmatch(r"/案例/(\d+)", path)
        if m:
            return render_case(cur, int(m.group(1)), qs)
        m = re.fullmatch(r"/动态/(\d+)", path)
        if m:
            return render_event(cur, int(m.group(1)))
    return ""


def normalize_path(path: str) -> str:
    aliases = {
        "/deploy": "/落地",
        "/field": "/现场",
        "/cases": "/案例",
        "/method": "/方法",
        "/methods": "/方法",
        "/world": "/世界动态",
        "/立体世界": "/",
        "/沙盘": "/",
        "/时间轴": "/平面",
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
    w3_css = STATIC_DIR / "world3d.css"
    if w3_css.is_file():
        page = page.replace(
            '<link rel="stylesheet" href="/static/world3d.css"/>',
            f"<style>\n{w3_css.read_text(encoding='utf-8')}\n</style>",
            1,
        )
    path = dest or SNAPSHOT_PATH
    path.write_text(page, encoding="utf-8")
    return path


class Handler(BaseHTTPRequestHandler):
    server_version = "imfde.ai/1.0"

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

    def _send_orig(self, kind: str, ident: int):
        extra = {"Cache-Control": "no-store"}
        url = _orig_source_url(kind, ident)
        path = find_orig_file(url) if url else None
        if path is None:
            self._send(404, _orig_missing_html(kind, ident), "text/html; charset=utf-8", extra)
            return
        back = "/%s/%s" % (kind, ident)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            self._send(200, path.read_bytes(), "application/pdf", extra)
            return
        text = path.read_bytes().decode("utf-8", errors="replace")
        if suffix in {".html", ".htm"}:
            page = _inject_orig_bar(text, back)
        else:
            page = _wrap_orig_pre(text, back)
        self._send(200, page.encode("utf-8"), "text/html; charset=utf-8", extra)

    def _handle_auth(self, path: str, query: str):
        """OAuth 登录路由（身份识别，不做内容限权）。"""
        import auth as A

        host = self.headers.get("Host", "")
        scheme = "https" if self.headers.get("X-Forwarded-Proto", "") == "https" else "http"
        base = A.base_url(host, scheme)
        qs = dict(parse_qs(query, keep_blank_values=True))
        cookies = A.parse_cookies(self.headers.get("Cookie", ""))

        # 退出登录
        if path == "/退出登录":
            nxt = (qs.get("next") or ["/"])[0]
            self.send_response(302)
            self.send_header("Location", nxt)
            self.send_header("Set-Cookie", f"{A.SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")
            self.end_headers()
            return

        # /登录 或 /登录/<provider> 或 /oauth/<provider>/callback
        # 归一化：/oauth/<p>[/callback] → 当作 provider 路由处理，callback 段与中文"回调"均可
        m = re.fullmatch(r"/oauth/([A-Za-z0-9]+)(/callback)?", path)
        if m:
            provider_hit = m.group(1).lower()
            is_callback = bool(m.group(2))
            # 复用统一逻辑：把 path 规范成 /登录/<provider>/回调 或 /登录/<provider>
            parts = ["", "登录", provider_hit] + (["回调"] if is_callback else [])
        else:
            parts = path.split("/")  # ['', '登录', 'github' ...]
        if len(parts) < 3 or not parts[2]:
            page = A.login_page_html((qs.get("next") or ["/"])[0], A.providers_enabled(), base)
            self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            return

        provider = parts[2].lower()
        enabled = A.providers_enabled()
        nxt = (qs.get("next") or ["/"])[0]
        if not nxt.startswith("/"):
            nxt = "/"

        if len(parts) < 4 or parts[3] != "回调":
            # 第一步：发 state 并 302 到授权页（state 自包含，无需写库）
            if not enabled.get(provider):
                self._send(200, A.login_page_html(nxt, enabled, base).encode("utf-8"), "text/html; charset=utf-8")
                return
            state = A.make_state(nxt)
            redirect_uri = A.callback_uri(base, provider)
            self.send_response(302)
            self.send_header("Location", A.authorize_url(provider, redirect_uri, state))
            self.end_headers()
            return
        # 第二步：回调换用户信息
        code = (qs.get("code") or [""])[0]
        state = (qs.get("state") or [""])[0]
        stored_next = A.verify_state(state)
        if not code or not stored_next:
            self._send(400, "登录状态失效，请重试".encode("utf-8"), "text/plain; charset=utf-8")
            return
        try:
            info = A.fetch_user(provider, code, A.callback_uri(base, provider))
        except Exception:
            import traceback

            self._send(500, ("登录失败\n" + traceback.format_exc()).encode("utf-8"), "text/plain; charset=utf-8")
            return
        uid = info.get("uid") or ""
        token = A.sign_session({"uid": str(uid), "provider": provider, "name": info.get("name") or "",
                                "avatar": info.get("avatar") or "", "exp": time.time() + A.SESSION_TTL})
        self.send_response(302)
        self.send_header("Location", stored_next or "/")
        self.send_header("Set-Cookie",
                         f"{A.SESSION_COOKIE}={urllib.parse.quote(token)}; Path=/; Max-Age={A.SESSION_TTL}; HttpOnly; SameSite=Lax")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path != "/":
            path = path.rstrip("/") or "/"
        path = normalize_path(path)
        qs = parse_qs(parsed.query, keep_blank_values=False)

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path.startswith("/登录") or path == "/退出登录" or path.startswith("/oauth/") or path == "/oauth":
            self._handle_auth(path, parsed.query)
            return
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
        m = re.fullmatch(r"/原文/(动态|案例)/(\d+)", path)
        if m:
            try:
                self._send_orig(m.group(1), int(m.group(2)))
            except Exception:
                self._send(
                    500,
                    ("查询失败\n" + traceback.format_exc()).encode("utf-8"),
                    "text/plain; charset=utf-8",
                )
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
