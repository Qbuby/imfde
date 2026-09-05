# -*- coding: utf-8 -*-
"""Learning graph: L1/L2 topics × questions × method pages.

Interview answers are never rendered. FDEInterviews license is citation + link.
Needle matching is only further-reading, not the graph. Edges belong in DB later.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import server as S

_SITE_DIR = Path(__file__).resolve().parent
if str(_SITE_DIR) not in sys.path:
    sys.path.insert(0, str(_SITE_DIR))

LEARN_TAGLINE = "AI 实战进化社 · 在现场里进化"
CYCLE_MAX_SORT = 8
SHOW_CASE_ID = 35

FDEI_ZH = {
    "ai-security-governance": "AI 安全与治理",
    "behavioral-customer": "客户与现场行为",
    "coding-dsa": "编码与数据结构",
    "llm-genai": "LLM / 生成式 AI",
    "ml-data-science": "机器学习与数据科学",
    "ml-infrastructure": "机器学习基础设施",
    "ml-system-design": "机器学习系统设计",
    "mlops": "MLOps",
    "rag-agents": "检索与 Agent",
    "sql-data-engineering": "SQL 与数据工程",
    "system-design": "系统设计",
}

# Usable field method, not slogans. No invented KPIs.
NODE_BRIEF = {
    "discovery": (
        "先跟一线把现有流程走一遍：谁在做、卡在哪、什么算做成。"
        "没有可检查的成果定义，就不要谈模型和编制。"
    ),
    "scoping": (
        "把约束、数据权限、验收标准和第一刀范围写死。"
        "驻场交付的失败，多半是范围没切开，不是模型不够强。"
    ),
    "evaluation": (
        "上线前先有评测集、风险阈值和人在环内的闸门。"
        "数字必须带口径：实测、目标、预测、系统规模要分开。"
    ),
    "adoption": (
        "嵌进旧流程，而不是另开一个没人打开的窗口。"
        "一线怕质量下降时，先并行、再替换，并留下可回退的路径。"
    ),
    "data-integration": (
        "先搞清数据在哪、谁能碰、刷新周期和权限边界。"
        "企业现场的硬活往往是接入和权限，不是提示词。"
    ),
    "prototype-iteration": (
        "用真实工单做短循环原型，用一线反馈改，而不是先做完演示再找用户。"
        "每一次迭代都要能指出改了流程里的哪一步。"
    ),
    "production-engineering": (
        "能值班、能回滚、能看日志，才叫生产。"
        "驻场把系统交给客户之后，这些比 demo 更能决定是否留下。"
    ),
    "field-productization": (
        "第三个客户开始重复第一个客户的做法时，就该收成产品面，而不是再雇一队人重做。"
        "现场赢了却收不回去，编制会把公司拖成咨询所。"
    ),
    "loop-engineering": (
        "Agent 要有工具边界、失败恢复和停止条件。"
        "模糊成功（解决了、没生气、没再开单）不能只用一次点击率来评。"
    ),
    "token-cost-control": (
        "预算、缓存、路由和「这场对话还值不值得继续烧」要写进方案。"
        "否则现场一放大，成本先把项目打死。"
    ),
    "enterprise-knowledge-base": (
        "企业知识库是权限、新鲜度和引用，不只是把文档切片丢进向量库。"
        "谁能看哪一份、过期了怎么办，要在发现阶段就问。"
    ),
    "strategic-framing": (
        "先问这是不是一个该用驻场的问题，而不是有模型就上。"
        "买产品、买驻场、自建编制，在公开材料里不是同一件事。"
    ),
    "portfolio-prioritization": (
        "同时有三条线时，用可验证成果和交接成本排序，而不是按演示好看程度排序。"
    ),
    "enterprise-architecture": (
        "驻场系统要落在客户已有的身份、数据和值班体系上。"
        "另起炉灶的平台，现场几乎交不出去。"
    ),
    "governance-risk": (
        "安全、合规、审计和「模型不能做什么」是范围的一部分，不是上线附录。"
    ),
    "economics-commercial": (
        "驻场能换来成交和留存，也会吃掉毛利。"
        "公开材料里的编制扩张，要分清是卖方扩编还是买方自己的 FDE 组织。"
    ),
    "fde-operating-model": (
        "编制放在销售、产品还是独立前线，决定人听谁的、赢了归谁。"
        "库里几乎没有「如何组建 FDE 团队」的完整样本，只能从公开口径里读结构。"
    ),
    "change-scale-adoption": (
        "一个现场赢了，不等于能铺到所有事业部。"
        "规模化靠的是交接、培训和产品化，不是把驻场人数线性加下去。"
    ),
    "field-product-strategy": (
        "前线看到的重复痛点，要能改核心产品路线。"
        "否则 FDE 永远在客户那里补洞，产品没有记忆。"
    ),
}

# Further reading only. Not a graph query engine.
METHOD_NEEDLES = (
    ("how-forward-deployed-engineers-work", ("discovery", "scoping", "adoption")),
    ("day-in-the-life", ("discovery", "adoption")),
    ("what-is-a-forward-deployed-engineer", ("strategic-framing", "fde-operating-model")),
    ("what-does-a-forward-deployed-engineer-do", ("scoping", "production-engineering")),
    ("fde-war-stories", ("field-productization", "discovery")),
    ("fde-exit-options", ("fde-operating-model",)),
    ("negotiating-forward-deployed", ("economics-commercial", "fde-operating-model")),
    ("fde-101", ("fde-operating-model", "strategic-framing")),
    ("what-it-means-to-be-a-forward-deployed", ("fde-operating-model", "economics-commercial")),
    ("hire-forward-deployed", ("fde-operating-model",)),
    ("services-led-growth", ("economics-commercial", "fde-operating-model")),
    ("insights-for-enterprise-ai", ("scoping", "adoption")),
    ("capability-building", ("adoption", "change-scale-adoption")),
)

LESSONS_CORE = {
    "discovery": {
        "title": "客户发现",
        "goal": "90 分钟内交「一页发现简报」。先跟一线把现有流程走一遍：谁在做、卡在哪、什么算做成。",
        "deliverable": "一页发现简报",
        "minutes": 90,
        "show_case_id": SHOW_CASE_ID,
        "show_fields": (
            ("经营问题", "business_problem"),
            ("旧流程", "existing_workflow"),
            ("卡点", "pain_point"),
            ("发现方法", "discovery_method"),
        ),
        "show_note": (
            "公开客户页能读到的发现材料。页面没有自称前线部署（FDE），"
            "也没有给出上线后的任务可用度百分比——简报里不要编这两个数。"
        ),
        "steps": (
            (
                "跟一线走现有流程",
                "谁在做每一步、用哪套系统、卡在哪。先问现场怎么干活，不要先问「你们想要什么 AI」。",
            ),
            (
                "写下可检查的成果",
                "什么叫做成：时长、返工、错误，还是一线负担。说不清当前成本就先量，不要承诺一个节省比例。",
            ),
            (
                "把冲突写进成功标准",
                "高管要降本、一线怕质量掉——两边都写进去。只听一边，上线会翻。",
            ),
            (
                "检查样本是不是只有顺利案例",
                "只给最顺的历史单，评测会偏。要补常见失败、边界情况和不同用户群。",
            ),
            (
                "交一页发现简报",
                "角色、旧流程、卡点、成果定义、数据/权限、明确不做。这一页过了，才进入方案范围。",
            ),
        ),
        "rubric": (
            ("及格", "五项都有可观察的内容，不是口号。成果能检查，数据说得清谁能碰。"),
            ("不及格", "只有模型选型、只有演示、用行业平均值代替现场基线，或成果不可检查。"),
            ("不要编的数", "原文没写的 KPI、头衔、上线后百分比，简报里不要补。"),
        ),
        "brief_tpl": (
            "客户 / 现场：\n"
            "一线角色（谁在做）：\n"
            "现有流程（步骤 / 系统）：\n"
            "卡点（可观察，不是口号）：\n"
            "现在怎么衡量（时长 / 返工 / 错误 / 负担）：\n"
            "做成的定义（可检查）：\n"
            "数据在哪、谁能碰：\n"
            "这一刀明确不做：\n"
            "冲突（谁要什么、谁怕什么）："
        ),
        "why": {
            "aifde:discovery:01": (
                "对。先还原工单流程和可衡量成果，模型往后排。",
                "不对。发现阶段不是挑模型或做演示。",
            ),
            "aifde:discovery:02": (
                "对。说不清当前成本就先量现场，不要先承诺比例。",
                "不对。没有基线就承诺节省，验收会空。",
            ),
            "aifde:discovery:03": (
                "对。降本和质量、一线负担都要写进成功标准。",
                "不对。只听高管或拖到上线再谈冲突，现场会翻。",
            ),
            "aifde:discovery:04": (
                "对。只有顺利样本，评测会偏；要补失败和边界。",
                "不对。干净样本不等于能上生产。",
            ),
        },
    }
}

MCQ_JS = """
<script>
document.addEventListener("click", function (e) {
  var btn = e.target.closest("[data-mcq-check]");
  if (!btn) return;
  var form = btn.closest(".mcq");
  if (!form) return;
  var out = form.querySelector(".mcq-result");
  var picked = form.querySelector("input[type=radio]:checked");
  if (!picked) {
    out.hidden = false;
    out.className = "mcq-result wait";
    out.textContent = "先选一项。";
    return;
  }
  var ok = picked.value === form.getAttribute("data-ok");
  out.hidden = false;
  out.className = "mcq-result " + (ok ? "ok" : "no");
  out.textContent = ok
    ? (form.getAttribute("data-yes") || "对。")
    : (form.getAttribute("data-no") || "不对。先看上面的步骤。");
});
</script>
"""

LEARN_HEAD = (
    '<link rel="stylesheet" href="/static/learn.css"/>'
    '<script defer src="/static/learn.js"></script>'
)


def load_lessons() -> dict:
    out = dict(LESSONS_CORE)
    for name in (
        "lesson_pack_early",
        "lesson_pack_late",
        "lesson_pack_eng",
        "lesson_pack_l2a",
        "lesson_pack_l2b",
    ):
        try:
            mod = importlib.import_module(name)
        except ImportError:
            continue
        pack = getattr(mod, "PACK", None) or {}
        if isinstance(pack, dict):
            out.update(pack)
    return out


NODE_NAME_ZH = {
    "discovery": "客户发现",
    "scoping": "方案范围",
    "evaluation": "评测与安全",
    "adoption": "上线与采用",
    "data-integration": "数据与集成",
    "prototype-iteration": "原型与迭代",
    "production-engineering": "生产工程",
    "field-productization": "反馈与产品化",
    "loop-engineering": "闭环工程",
    "token-cost-control": "控制 Token 成本",
    "enterprise-knowledge-base": "企业知识库搭建",
    "strategic-framing": "战略问题定义",
    "portfolio-prioritization": "组合与优先级",
    "enterprise-architecture": "企业架构与平台",
    "governance-risk": "治理、安全与合规",
    "economics-commercial": "商业模型与经济性",
    "fde-operating-model": "FDE 组织与授权",
    "change-scale-adoption": "变革与规模采用",
    "field-product-strategy": "现场洞察与产品战略",
}


def _zh_name(topic: dict) -> str:
    slug = topic.get("slug") or ""
    zh = (topic.get("name_zh") or "").strip()
    for prefix in ("L1 ", "L2 "):
        if zh.startswith(prefix):
            zh = zh[len(prefix) :]
    if zh and any("\u4e00" <= ch <= "\u9fff" for ch in zh):
        return zh
    return NODE_NAME_ZH.get(slug) or zh or slug


def _needles_for(slug: str) -> list[str]:
    return [n for n, slugs in METHOD_NEEDLES if slug in slugs]


def _is_complete(slug: str, lessons: dict | None = None) -> bool:
    return slug in (lessons if lessons is not None else load_lessons())


def _shell(title: str, inner: str, gh: str, page_path: str, extra_head: str = "") -> str:
    return S.shell(
        title,
        "方法",
        inner,
        gh,
        extra_head=extra_head,
        page_path=page_path,
        tagline=LEARN_TAGLINE,
        learn=True,
    )


def load_graph(cur) -> dict:
    topics = [
        dict(r)
        for r in cur.execute(
            "SELECT id, slug, name_zh, name_en, level, sort FROM topics "
            "WHERE taxonomy='aifde' ORDER BY sort, slug"
        )
    ]
    xwalk = {}
    for r in cur.execute("SELECT aifde_id, fdei_id, note FROM topic_crosswalk"):
        xwalk.setdefault(r["aifde_id"], []).append(dict(r))
    qn = {
        r["topic_id"]: r["n"]
        for r in cur.execute(
            "SELECT topic_id, count(*) n FROM question_topics GROUP BY 1"
        )
    }
    for t in topics:
        t["name"] = _zh_name(t)
        t["n_q"] = int(qn.get(t["id"], 0))
        t["fdei"] = xwalk.get(t["id"]) or []
    return {"topics": topics, "by_slug": {t["slug"]: t for t in topics}}


def _match_methods(cur, slug: str) -> list[dict]:
    needles = _needles_for(slug)
    if not needles:
        return []
    rows = S.dedupe_by_url(
        S.fetch_cases(cur, "x.doc_type IN ('methodology','opinion')", (), "x.id")
    )
    hit = []
    for row in rows:
        blob = ((row.get("source_url") or "") + " " + (row.get("source_title") or "")).lower()
        if any(n in blob for n in needles):
            hit.append(row)
    return hit[:8]


def _aifde_items(cur, topic_id: str) -> list[dict]:
    rows = [
        dict(r)
        for r in cur.execute(
            """
            SELECT q.id, q.title, q.kind, q.difficulty,
                   COALESCE(l.stem, q.title) AS stem_zh,
                   l.options_json, l.answer
            FROM questions q
            JOIN question_topics qt ON qt.question_id=q.id
            LEFT JOIN question_locales l ON l.question_id=q.id AND l.locale='zh'
            WHERE qt.topic_id=? AND q.source='aifde'
            ORDER BY q.id
            """,
            (topic_id,),
        )
    ]
    for row in rows:
        opts = []
        raw = row.get("options_json") or ""
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    opts = [str(x) for x in parsed]
            except ValueError:
                opts = []
        row["options"] = opts
        ans = (row.get("answer") or "").strip()
        row["ok_idx"] = opts.index(ans) if ans in opts else -1
    return rows


def _fdei_prompts(cur, fdei_ids: list[str], limit=6) -> list[dict]:
    if not fdei_ids:
        return []
    ph = ",".join("?" * len(fdei_ids))
    return [
        dict(r)
        for r in cur.execute(
            f"""
            SELECT q.id, COALESCE(l.stem, q.title) AS title, q.difficulty
            FROM questions q
            JOIN question_topics qt ON qt.question_id=q.id
            LEFT JOIN question_locales l ON l.question_id=q.id AND l.locale='zh'
            WHERE qt.topic_id IN ({ph}) AND q.source='fdei'
            ORDER BY q.id
            LIMIT {int(limit)}
            """,
            tuple(fdei_ids),
        )
    ]


def _split_topics(topics: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    l1 = [
        t
        for t in topics
        if t.get("level") == "L1" and (t.get("sort") or 0) <= CYCLE_MAX_SORT
    ]
    extra = [
        t
        for t in topics
        if t.get("level") == "L1" and (t.get("sort") or 0) > CYCLE_MAX_SORT
    ]
    l2 = [t for t in topics if t.get("level") == "L2"]
    return l1, extra, l2


def _peer_group(topics: list[dict], slug: str) -> list[dict]:
    l1, extra, l2 = _split_topics(topics)
    for group in (l1, extra, l2):
        if any(t["slug"] == slug for t in group):
            return group
    return []


def _cycle_nav(topics: list[dict], slug: str) -> tuple[dict | None, dict | None]:
    peers = _peer_group(topics, slug)
    slugs = [t["slug"] for t in peers]
    if slug not in slugs:
        return None, None
    i = slugs.index(slug)
    prev_t = peers[i - 1] if i > 0 else None
    next_t = peers[i + 1] if i + 1 < len(peers) else None
    return prev_t, next_t


def _payload_node(t: dict, lessons: dict) -> dict:
    lesson = lessons.get(t["slug"]) or {}
    cycle = t.get("level") == "L1" and (t.get("sort") or 0) <= CYCLE_MAX_SORT
    if cycle:
        group = "cycle"
    elif t.get("level") == "L1":
        group = "eng"
    else:
        group = "l2"
    return {
        "slug": t["slug"],
        "name": t["name"],
        "brief": NODE_BRIEF.get(t["slug"]) or "",
        "ready": t["slug"] in lessons,
        "href": "/方法/" + t["slug"],
        "goal": lesson.get("goal") or "",
        "deliverable": lesson.get("deliverable") or "",
        "steps": [title for title, _body in lesson.get("steps") or ()],
        "kind": "cycle" if cycle else "dir",
        "group": group,
    }


def _learn_data_tag(topics: list[dict], lessons: dict) -> str:
    payload = [_payload_node(t, lessons) for t in topics]
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/json" id="learn-data">{blob}</script>'


def _cycle_buttons(nodes: list[dict], current: str | None = None) -> str:
    parts = []
    for i, t in enumerate(nodes):
        ready = t.get("ready") if "ready" in t else _is_complete(t["slug"])
        on = t["slug"] == current
        status = "完整课" if ready else "目录"
        cls = "learn-node" + (" on" if on else "") + ("" if ready else " is-stub")
        parts.append(
            f'<button type="button" class="{cls}" data-node="{S.esc(t["slug"])}" '
            f'style="--i:{i}" aria-pressed="{"true" if on else "false"}">'
            f'<b>{S.esc(t["name"])}</b><span>{status}</span></button>'
        )
    return "".join(parts)


def _exit_buttons(nodes: list[dict]) -> str:
    return "".join(
        f'<button type="button" class="learn-exit" data-node="{S.esc(t["slug"])}">'
        f'{S.esc(t["name"])}</button>'
        for t in nodes
    )


def _hud_nav(gh: str) -> str:
    links = []
    for label, path in S.NAV:
        cls = "on" if label == "方法" else ""
        aria = ' aria-current="page"' if cls else ""
        links.append(f'<a class="{cls}" href="{S.esc(path)}"{aria}>{S.esc(label)}</a>')
    if gh:
        links.append(
            f'<a class="learn-gh" href="{S.esc(gh)}" target="_blank" rel="noopener noreferrer">GitHub</a>'
        )
    return "".join(links)


def _fdei_appendix(prompts: list[dict], fdei_note: str) -> str:
    if not prompts:
        return ""
    items = "".join(
        f'<div class="row">{S.esc(p.get("title") or "")}'
        f'<span class="s">现场题 · 答案不在此站展示</span></div>'
        for p in prompts
    )
    note = fdei_note or "对应题库类目"
    return f"""
<details class="fold fdei-app">
  <summary>附录 · 还会碰到的现场题</summary>
  <p class="note">只列题干。许可是引用，答案不在此站展示。对应：{S.esc(note)}</p>
  <div class="list">{items}</div>
</details>
"""


def _method_list(methods: list[dict]) -> str:
    html = "".join(S.row_link(r) for r in methods)
    if html:
        return f'<div class="list">{html}</div>'
    return '<p class="empty">这一节点还没有挂上方法文。</p>'


DIFF_ZH = {"beginner": "入门", "intermediate": "进阶", "advanced": "高阶"}


def _diff_zh(value: str | None) -> str:
    key = (value or "").strip().lower()
    return DIFF_ZH.get(key, value or "")


def _stem_list(stems: list[dict]) -> str:
    html = "".join(
        f'<article class="q-stem"><p class="k">练习情景 · {S.esc(_diff_zh(s.get("difficulty")))}</p>'
        f'<p>{S.esc(s.get("stem_zh") or s.get("title") or "")}</p></article>'
        for s in stems
    )
    return html or '<p class="empty">这一节点还没有中文练习情景。</p>'


def _mcq_block(items: list[dict], why: dict) -> str:
    parts = []
    for i, q in enumerate(items, 1):
        opts = q.get("options") or []
        if not opts or q.get("ok_idx", -1) < 0:
            continue
        yes, no = why.get(q["id"], ("对。", "不对。先看上面的步骤。"))
        labels = "".join(
            f'<label class="mcq-opt"><input type="radio" name="q{i}" value="{j}"/>'
            f'<span>{S.esc(opt)}</span></label>'
            for j, opt in enumerate(opts)
        )
        parts.append(
            f'<form class="mcq" data-ok="{int(q["ok_idx"])}" '
            f'data-yes="{S.esc(yes)}" data-no="{S.esc(no)}">'
            f'<p class="k">练习 {i} · {S.esc(_diff_zh(q.get("difficulty")))}</p>'
            f'<p class="mcq-stem">{S.esc(q.get("stem_zh") or q.get("title") or "")}</p>'
            f"{labels}"
            f'<button type="button" class="mcq-btn" data-mcq-check>核对</button>'
            f'<p class="mcq-result" hidden></p>'
            f"</form>"
        )
    return "".join(parts) or '<p class="empty">这一课还没有可核的练习。</p>'


def _show_case(cur, lesson: dict) -> str:
    cid = int(lesson.get("show_case_id") or 0)
    row = S.load_case(cur, cid) if cid else None
    if not row:
        return '<p class="empty">范例还没挂上。</p>'
    customer = row.get("customer") or "未具名客户"
    vendor = row.get("vendor_names") or row.get("raw_company_text") or ""
    title = " / ".join(x for x in (customer, vendor) if x)
    fields = lesson.get("show_fields") or (
        ("经营问题", "business_problem"),
        ("旧流程", "existing_workflow"),
        ("卡点", "pain_point"),
        ("发现方法", "discovery_method"),
    )
    body = "".join(S.dl_row(lab, S.trunc(row.get(key), 280)) for lab, key in fields)
    href = S.href("/案例/%s" % cid)
    note = lesson.get("show_note") or "用库里的字段，不另造 KPI。"
    return f"""
<article class="learn-show">
  <p class="k">范例</p>
  <h3><a href="{S.esc(href)}">{S.esc(title)}</a></h3>
  <p class="note">{S.esc(note)}</p>
  <dl class="anatomy">{body}</dl>
  <p class="hint"><a href="{S.esc(href)}">打开案例全文</a> · <a class="orig" href="/原文/案例/{cid}">核对原文</a></p>
</article>
"""


def _learn_strip(l1: list[dict], slug: str, lessons: dict) -> str:
    items = []
    for t in l1:
        ready = t["slug"] in lessons
        on = t["slug"] == slug
        cls = "learn-node" + (" on" if on else "") + ("" if ready else " is-stub")
        cur = ' aria-current="page"' if on else ""
        items.append(
            f'<button type="button" class="{cls}" data-node="{S.esc(t["slug"])}" '
            f'aria-pressed="{"true" if on else "false"}"{cur}>'
            f'{S.esc(t["name"])}</button>'
        )
    return f'<nav class="learn-strip" aria-label="交付循环">{"".join(items)}</nav>'


def render_home(cur) -> str:
    graph = load_graph(cur)
    lessons = load_lessons()
    topics = graph["topics"]
    l1, extra, l2 = _split_topics(topics)
    gh = S.github_url(cur)
    n_ready = sum(1 for t in l1 if t["slug"] in lessons)
    n_eng = sum(1 for t in extra if t["slug"] in lessons)
    n_l2 = sum(1 for t in l2 if t["slug"] in lessons)
    inner = f"""
<div class="learn" id="learn">
  <header class="learn-hud" role="banner">
    <a class="learn-brand" href="/" aria-label="{S.esc(S.SITE_NAME)} {S.esc(S.SITE_CLUB)}">
      {S.brand_mark()}
    </a>
    <div class="learn-hud-mid">
      <h1 class="learn-title">现场交付循环</h1>
      <p class="learn-sub">点选看这一步 · {n_ready}/{len(l1)} 课已写成教程</p>
    </div>
    <div class="learn-hud-tools">
      <nav class="learn-nav" aria-label="站内导航">{_hud_nav(gh)}</nav>
    </div>
  </header>
  <div class="learn-stage" id="learn-stage">
    <div class="learn-cycle" role="list">
      <p class="learn-cycle-core">现场交付循环</p>
      {_cycle_buttons(l1)}
    </div>
    <p class="learn-hint">点击任一节点看这一步 · 再进完整课。这不是行业动态。</p>
  </div>
  <aside class="learn-panel" id="learn-panel" hidden aria-label="这一课" aria-live="polite"></aside>
  <nav class="learn-exits" aria-label="离开循环">
    <span class="learn-lg-k">循环外</span>
    <button type="button" class="learn-exit" data-group="eng">现场工程 · {n_eng}/{len(extra)}</button>
    <button type="button" class="learn-exit" data-group="l2">组织与战略 · {n_l2}/{len(l2)}</button>
    <a href="/">回世界动态</a>
  </nav>
</div>
{_learn_data_tag(topics, lessons)}
"""
    return S.shell(
        "方法 · %s" % S.SITE_NAME,
        "方法",
        inner,
        gh,
        extra_head=LEARN_HEAD,
        body_class="learn-page",
        skip_wrap=True,
        skip_mast=True,
        skip_foot=True,
        home_css=False,
        page_path="/方法",
        tagline=LEARN_TAGLINE,
    )


def _render_lesson(cur, topic: dict, graph: dict, gh: str, lesson: dict) -> str:
    lessons = load_lessons()
    l1, _, _ = _split_topics(graph["topics"])
    stems = _aifde_items(cur, topic["id"])
    methods = _match_methods(cur, topic["slug"])
    fdei_ids = [x["fdei_id"] for x in topic.get("fdei") or []]
    prompts = _fdei_prompts(cur, fdei_ids)
    fdei_note = "、".join(
        FDEI_ZH.get((x["fdei_id"] or "").split(":")[-1], x["fdei_id"])
        for x in topic.get("fdei") or []
    )
    prev_t, next_t = _cycle_nav(graph["topics"], topic["slug"])
    steps = "".join(
        f"<li><h3>{S.esc(title)}</h3><p>{S.esc(body)}</p></li>"
        for title, body in lesson.get("steps") or ()
    )
    rubric = "".join(
        f"<li><h3>{S.esc(title)}</h3><p>{S.esc(body)}</p></li>"
        for title, body in lesson.get("rubric") or ()
    )
    nav = ['<a href="/方法">图谱总览</a>']
    if prev_t:
        nav.append(f'<a href="/方法/{S.esc(prev_t["slug"])}">上一步 · {S.esc(prev_t["name"])}</a>')
    if next_t:
        nav.append(f'<a href="/方法/{S.esc(next_t["slug"])}">下一步 · {S.esc(next_t["name"])}</a>')
    title = lesson.get("title") or topic["name"]
    goal = lesson.get("goal") or NODE_BRIEF.get(topic["slug"]) or ""
    deliverable = lesson.get("deliverable") or "一页简报"
    minutes = int(lesson.get("minutes") or 90)
    tpl = lesson.get("brief_tpl") or ""
    inner = f"""
{_learn_strip(l1, topic["slug"], lessons)}
<aside class="learn-panel" id="learn-panel" hidden aria-label="其他节点" aria-live="polite"></aside>
{_learn_data_tag(graph["topics"], lessons)}
<section class="desk-lede">
  <p class="k">方法 · 完整课</p>
  <h1>{S.esc(title)}</h1>
  <p class="learn-goal"><b>学习目标</b>：{S.esc(goal)}</p>
</section>
<section class="section" id="怎么做">
  <h2>这一步怎么做</h2>
  <ol class="learn-steps">{steps}</ol>
</section>
<section class="section" id="范例">
  <h2>看一个例子</h2>
  <p class="note">用库里的字段，不另造数字。</p>
  {_show_case(cur, lesson)}
</section>
<section class="section" id="练习">
  <h2>练习</h2>
  <p class="note">四道本地选择题。选完再核对。这不是面试题库。</p>
  {_mcq_block(stems, lesson.get("why") or {})}
</section>
<section class="section" id="作业">
  <h2>作业 · {S.esc(deliverable)}</h2>
  <p class="note">抄到自己的笔记里填。本站不收作业。</p>
  <pre class="brief-tpl">{S.esc(tpl)}</pre>
  <ul class="learn-steps rubric">{rubric}</ul>
</section>
<section class="section">
  <h2>延伸阅读</h2>
  <p class="note">方法文，不是这一窗的行业动态。</p>
  {_method_list(methods)}
</section>
{_fdei_appendix(prompts, fdei_note)}
<p class="hint">{" · ".join(nav)}</p>
"""
    return _shell(
        "%s · 方法 · %s" % (title, S.SITE_NAME),
        inner,
        gh,
        "/方法/%s" % topic["slug"],
        extra_head=LEARN_HEAD + MCQ_JS,
    )


def render_node(cur, slug: str) -> str:
    graph = load_graph(cur)
    topic = graph["by_slug"].get(slug)
    gh = S.github_url(cur)
    lessons = load_lessons()
    if not topic:
        inner = '<section class="desk-lede"><h1>没有这个节点</h1><p><a href="/方法">回方法图谱</a></p></section>'
        return _shell("未找到 · %s" % S.SITE_NAME, inner, gh, "/方法")
    lesson = lessons.get(slug)
    if lesson:
        return _render_lesson(cur, topic, graph, gh, lesson)

    l1, _, _ = _split_topics(graph["topics"])
    brief = NODE_BRIEF.get(slug) or "这一步要能检查、能交接，而不是只做演示。"
    methods = _match_methods(cur, slug)
    stems = _aifde_items(cur, topic["id"])
    fdei_ids = [x["fdei_id"] for x in topic.get("fdei") or []]
    prompts = _fdei_prompts(cur, fdei_ids)
    prev_t, next_t = _cycle_nav(graph["topics"], slug)
    fdei_note = "、".join(
        FDEI_ZH.get((x["fdei_id"] or "").split(":")[-1], x["fdei_id"])
        for x in topic.get("fdei") or []
    )
    nav = ['<a href="/方法">图谱总览</a>']
    if "discovery" in lessons:
        nav.append('<a href="/方法/discovery">先去完整课 · 客户发现</a>')
    if prev_t:
        nav.append(f'<a href="/方法/{S.esc(prev_t["slug"])}">上一步 · {S.esc(prev_t["name"])}</a>')
    if next_t:
        nav.append(f'<a href="/方法/{S.esc(next_t["slug"])}">下一步 · {S.esc(next_t["name"])}</a>')
    inner = f"""
{_learn_strip(l1, slug, lessons)}
<aside class="learn-panel" id="learn-panel" hidden aria-label="其他节点" aria-live="polite"></aside>
{_learn_data_tag(graph["topics"], lessons)}
<section class="desk-lede">
  <p class="k">方法 · 目录</p>
  <h1>{S.esc(topic["name"])}</h1>
  <p>{S.esc(brief)}</p>
  <p class="note">本页是目录：练习情景和方法文。完整课从图谱点选进入。</p>
</section>
<section class="section">
  <h2>练习情景</h2>
  <p class="note">中文情景用来预览这一步会碰到什么。完整练习还没写成课。</p>
  {_stem_list(stems)}
</section>
<section class="section">
  <h2>相关方法文</h2>
  {_method_list(methods)}
</section>
{_fdei_appendix(prompts, fdei_note)}
<p class="hint">{" · ".join(nav)}</p>
"""
    return _shell(
        "%s · 方法 · %s" % (topic["name"], S.SITE_NAME),
        inner,
        gh,
        "/方法/%s" % slug,
        extra_head=LEARN_HEAD,
    )
