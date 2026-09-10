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
        "没有可检查的成果定义，就不要谈模型和人手。"
    ),
    "scoping": (
        "先写死这一刀做什么、不做什么：谁的数据能碰、什么叫验收通过。"
        "驻场交付的失败，多半是范围没切开，不是模型不够强。"
    ),
    "evaluation": (
        "上线前先有一套真单子能测、错了谁拍板、什么情况必须人看一眼。"
        "数字要分开看：测过的、目标、预测、系统规模，不是同一回事。"
    ),
    "adoption": (
        "嵌进旧流程，而不是另开一个没人打开的窗口。"
        "一线怕质量掉时，新旧一起跑一阵再换，并留一条能退回去的路。"
    ),
    "data-integration": (
        "先问清数据在哪、谁有钥匙、多久更新一次。"
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
        "现场赢了却收不回去，一直派人会把公司拖成咨询所。"
    ),
    "loop-engineering": (
        "Agent 能调哪些工具、挂了怎么接着干、什么时候必须停，都要写死。"
        "模糊成功（解决了、没生气、没再开单）不能只用一次点击率来评。"
    ),
    "token-cost-control": (
        "这轮对话还值不值得继续烧，预算、缓存和走哪套模型，要写进方案。"
        "否则现场一放大，成本先把项目打死。"
    ),
    "enterprise-knowledge-base": (
        "企业知识库要能说清谁能看、新不新、这句话从哪篇来，不是把文档切了丢进向量库。"
        "谁能看哪一份、过期了怎么办，要在发现阶段就问。"
    ),
    "strategic-framing": (
        "先问这是不是一个该用驻场的问题，而不是有模型就上。"
        "买现成产品、买驻场、自己组队，在公开材料里不是同一件事。"
    ),
    "portfolio-prioritization": (
        "同时有三条线时，先看哪条能交出可检查的结果、走的时候人能接手，别按演示好不好看排。"
    ),
    "enterprise-architecture": (
        "驻场系统要接到客户已经在用的登录、数据和值班，不要另起一套。"
        "另起炉灶的平台，现场几乎交不出去。"
    ),
    "governance-risk": (
        "模型不能做什么、出事谁负责、审计怎么查，开工时就要写进范围，别等到上线再补。"
    ),
    "economics-commercial": (
        "驻场能换来成交和留存，也会吃掉毛利。"
        "公开材料里人变多了，要分清是卖方加人还是买方自己养队伍。"
    ),
    "fde-operating-model": (
        "人放在销售、产品还是独立前线，决定听谁的、赢了归谁。"
        "库里几乎没有完整组队样本，只能从页上已经写明的结构来读。"
    ),
    "change-scale-adoption": (
        "一个现场赢了，不等于能铺到所有事业部。"
        "铺开靠能交接、能教会下一家、能收成产品，不是把驻场人数一直加下去。"
    ),
    "field-product-strategy": (
        "前线看到的重复痛点，要能改核心产品路线。"
        "否则驻场的人永远在客户那里补洞，产品没有记忆。"
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
        "goal": "把客户来的那一刻写清楚：谁在打电话、门禁锁没锁、什么算帮到忙。不要先谈模型。",
        "deliverable": "一页发现简报",
        "minutes": 90,
        "show_case_id": 315,
        "show_fields": (
            ("经营问题", "business_problem"),
            ("旧流程", "existing_workflow"),
            ("卡点", "pain_point"),
            ("发现方法", "discovery_method"),
        ),
        "show_note": (
            "StoreEase 页上写的是搬家、离婚、身故那种时刻。没有驻场头衔，也没有编上线可用度。"
            "简报只写页上有的场面，不要补数字。"
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
        "mcq": {
            "aifde:discovery:01": {
                "stem": "客户希望用 AI 缩短工单处理时间。现场的人 / 你最应该先做什么？",
                "options": (
                    "跟随一线人员还原当前工单流程，找出瓶颈、约束和可衡量成果。",
                    "马上挑一个最强模型做聊天机器人，发现阶段先把选型定下来。",
                    "先做一个视觉效果完整的演示，用画面说服客户再回头看流程。",
                    "让客户提供一份功能清单后直接估期，发现阶段不跟一线走现有流程。",
                ),
                "ok": 0,
            },
            "aifde:discovery:02": {
                "stem": "业务负责人要求“把审核流程自动化”，但说不清当前成本。最佳下一步是什么？",
                "options": (
                    "先承诺一个节省比例，当前成本说不清也写进方案。",
                    "观察实际审核，建立时长、返工和错误基线。",
                    "根据行业平均值估算审核成本，不观察本现场的时长和返工。",
                    "直接生成完整 PRD，把「说不清当前成本」留给后面的人。",
                ),
                "ok": 1,
            },
            "aifde:discovery:03": {
                "stem": "高管关注降本，一线用户担心 AI 降低质量。发现阶段应该如何处理？",
                "options": (
                    "只采用高管的降本指标，一线的质量担心先不写进成功标准。",
                    "避免讨论冲突直到上线，发现阶段只记一边的口径。",
                    "把成本、质量和用户负担共同写入成功标准。",
                    "先扩大模型上下文，指望质量担心会随模型变大消失。",
                ),
                "ok": 2,
            },
            "aifde:discovery:04": {
                "stem": "客户只提供了最顺利的历史案例作为训练和评测样本。现场的人 / 你应该指出什么？",
                "options": (
                    "样本越干净越适合生产，顺利案例可以直接当评测集。",
                    "让模型自己生成全部边界案例，不再向现场要失败样本。",
                    "只要样本数量多就足够，不区分顺利单和失败单。",
                    "需要补充常见失败、边界案例和不同用户群的代表性样本。",
                ),
                "ok": 3,
            },
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

LEARN_HEAD = ""


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
            if name in sys.modules:
                mod = importlib.reload(sys.modules[name])
            else:
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
    "fde-operating-model": "驻场团队怎么挂、听谁的",
    "change-scale-adoption": "变革与规模采用",
    "field-product-strategy": "现场洞察与产品战略",
}


def _zh_name(topic: dict) -> str:
    slug = topic.get("slug") or ""
    mapped = NODE_NAME_ZH.get(slug)
    if mapped:
        return mapped
    zh = (topic.get("name_zh") or "").strip()
    for prefix in ("L1 ", "L2 "):
        if zh.startswith(prefix):
            zh = zh[len(prefix) :]
    if zh and any("\u4e00" <= ch <= "\u9fff" for ch in zh):
        return zh
    return zh or slug


def _needles_for(slug: str) -> list[str]:
    return [n for n, slugs in METHOD_NEEDLES if slug in slugs]


def _is_complete(slug: str, lessons: dict | None = None) -> bool:
    return slug in (lessons if lessons is not None else load_lessons())


def _shell(title: str, inner: str, gh: str, page_path: str, extra_head: str = "", meta_description: str | None = None) -> str:
    short = title.split(" · ")[0]
    hud = S.room_hud("学习", gh, short, "按步骤做完这一课")
    wrapped = (
        f'<div class="room room-doc" id="room">{hud}'
        f'<div class="room-stage"><div class="room-docmain">'
        f'<a class="room-back" href="/方法">← 回学习</a>'
        f"{inner}</div></div></div>"
    )
    return S.shell(
        title,
        "学习",
        wrapped,
        gh,
        extra_head='<link rel="stylesheet" href="/static/room.css"/>' + extra_head,
        body_class="room-page desk-page",
        skip_wrap=True,
        skip_mast=True,
        skip_foot=True,
        home_css=True,
        page_path=page_path,
        tagline=LEARN_TAGLINE,
        learn=True,
        meta_description=meta_description,
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


def _lesson_rows(nodes: list[dict], lessons: dict) -> str:
    parts = []
    for t in nodes:
        ready = t["slug"] in lessons
        goal = (lessons.get(t["slug"]) or {}).get("goal") or NODE_BRIEF.get(t["slug"]) or ""
        go = "读这一课" if ready else "先看目录"
        parts.append(
            f'<article class="room-article">'
            f'<p class="room-article-k">{go}</p>'
            f'<h2><a href="/方法/{S.esc(t["slug"])}">{S.esc(t["name"])}</a></h2>'
            f"<p>{S.esc(goal)}</p></article>"
        )
    return "".join(parts)


def _fdei_appendix(prompts: list[dict], fdei_note: str) -> str:
    return ""


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


def _apply_lesson_mcq(items: list[dict], lesson: dict) -> list[dict]:
    overlay = lesson.get("mcq") or {}
    if not overlay:
        return items
    for row in items:
        patch = overlay.get(row.get("id"))
        if not isinstance(patch, dict):
            continue
        stem = (patch.get("stem") or "").strip()
        if stem:
            row["stem_zh"] = stem
        raw_opts = patch.get("options")
        if raw_opts:
            opts = [str(x) for x in raw_opts]
            row["options"] = opts
            if "ok" in patch:
                try:
                    row["ok_idx"] = int(patch["ok"])
                except (TypeError, ValueError):
                    row["ok_idx"] = -1
            else:
                ans = (patch.get("answer") or "").strip()
                row["ok_idx"] = opts.index(ans) if ans in opts else -1
    return items


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
    body = "".join(S.dl_row(lab, row.get(key)) for lab, key in fields)
    href = S.href("/案例/%s" % cid)
    note = lesson.get("show_note") or ""
    note_html = f'<p class="note">{S.esc(note)}</p>' if note else ""
    return f"""
<article class="learn-show">
  <h3><a href="{S.esc(href)}">{S.esc(title)}</a></h3>
  {note_html}
  <dl class="anatomy">{body}</dl>
  <p class="hint"><a href="{S.esc(href)}">看完整案例</a></p>
</article>
"""


def _learn_strip(l1: list[dict], slug: str, lessons: dict) -> str:
    items = []
    for t in l1:
        on = " on" if t["slug"] == slug else ""
        cur = ' aria-current="page"' if on else ""
        items.append(
            f'<a class="chip{on}" href="/方法/{S.esc(t["slug"])}"{cur}>'
            f"{S.esc(t['name'])}</a>"
        )
    return f'<nav class="room-filt" aria-label="交付循环">{"".join(items)}</nav>'


def render_home(cur) -> str:
    graph = load_graph(cur)
    lessons = load_lessons()
    topics = graph["topics"]
    l1, extra, l2 = _split_topics(topics)
    gh = S.github_url(cur)
    n_ready = sum(1 for t in l1 if t["slug"] in lessons)
    n_eng = sum(1 for t in extra if t["slug"] in lessons)
    n_l2 = sum(1 for t in l2 if t["slug"] in lessons)
    hud = S.room_hud("学习", gh, "现场怎么干活", "往下读，点进课")
    stage = f"""
<p class="room-how"><b>往下读就行。</b> 点课名进这一课。</p>
<div class="room-feedlist">
  <h2>做事的步骤 · {n_ready}/{len(l1)}</h2>
  {_lesson_rows(l1, lessons)}
  <h2>现场会碰到的工程题 · {n_eng}/{len(extra)}</h2>
  {_lesson_rows(extra, lessons)}
  <h2>组织和生意 · {n_l2}/{len(l2)}</h2>
  {_lesson_rows(l2, lessons)}
</div>
"""
    return S.room_page(
        "学习 · %s" % S.SITE_NAME,
        "学习",
        gh,
        "/方法",
        hud,
        stage,
        "",
        {"kind": "learn", "items": []},
        lens="learn",
        feed=True,
        meta_description="学习 · 现场怎么干活：FDE 交付循环分步教程、现场工程题、组织与生意，每课给目标、步骤和判断标准。",
    )


def _render_lesson(cur, topic: dict, graph: dict, gh: str, lesson: dict) -> str:
    lessons = load_lessons()
    l1, _, _ = _split_topics(graph["topics"])
    stems = _apply_lesson_mcq(_aifde_items(cur, topic["id"]), lesson)
    methods = _match_methods(cur, topic["slug"])
    prev_t, next_t = _cycle_nav(graph["topics"], topic["slug"])
    steps = "".join(
        f"<li><h3>{S.esc(title)}</h3><p>{S.esc(body)}</p></li>"
        for title, body in lesson.get("steps") or ()
    )
    rubric = "".join(
        f"<li><h3>{S.esc(title)}</h3><p>{S.esc(body)}</p></li>"
        for title, body in lesson.get("rubric") or ()
    )
    nav = ['<a href="/方法">回学习</a>']
    if prev_t:
        nav.append(f'<a href="/方法/{S.esc(prev_t["slug"])}">上一步 · {S.esc(prev_t["name"])}</a>')
    if next_t:
        nav.append(f'<a href="/方法/{S.esc(next_t["slug"])}">下一步 · {S.esc(next_t["name"])}</a>')
    title = lesson.get("title") or topic["name"]
    goal = lesson.get("goal") or NODE_BRIEF.get(topic["slug"]) or ""
    deliverable = lesson.get("deliverable") or "一页简报"
    tpl = lesson.get("brief_tpl") or ""
    inner = f"""
{_learn_strip(l1, topic["slug"], lessons)}
<section class="desk-lede">
  <p class="k">学习 · 这一课</p>
  <h1>{S.esc(title)}</h1>
  <p class="learn-goal"><b>学习目标</b>：{S.esc(goal)}</p>
</section>
<section class="section" id="怎么做">
  <h2>这一步怎么做</h2>
  <ol class="learn-steps">{steps}</ol>
</section>
<section class="section" id="范例">
  <h2>看一个例子</h2>
  {_show_case(cur, lesson)}
</section>
<section class="section" id="练习">
  <h2>练习</h2>
  <p class="note">选完再核对。</p>
  {_mcq_block(stems, lesson.get("why") or {})}
</section>
<section class="section" id="作业">
  <h2>作业 · {S.esc(deliverable)}</h2>
  <p class="note">抄到自己的笔记里填。</p>
  <pre class="brief-tpl">{S.esc(tpl)}</pre>
  <ul class="learn-steps rubric">{rubric}</ul>
</section>
<section class="section">
  <h2>延伸阅读</h2>
  {_method_list(methods)}
</section>
<p class="hint">{" · ".join(nav)}</p>
"""
    return _shell(
        "%s · 方法 · %s" % (title, S.SITE_NAME),
        inner,
        gh,
        "/方法/%s" % topic["slug"],
        extra_head=LEARN_HEAD + MCQ_JS,
        meta_description=S.trunc("".join(filter(None, (topic.get("name"), "：", goal))), 158) or None,
    )


def render_node(cur, slug: str) -> str:
    graph = load_graph(cur)
    topic = graph["by_slug"].get(slug)
    gh = S.github_url(cur)
    lessons = load_lessons()
    if not topic:
        inner = '<section class="desk-lede"><h1>没有这一课</h1><p><a href="/方法">回学习</a></p></section>'
        return _shell("未找到 · %s" % S.SITE_NAME, inner, gh, "/方法")
    lesson = lessons.get(slug)
    if lesson:
        return _render_lesson(cur, topic, graph, gh, lesson)

    l1, _, _ = _split_topics(graph["topics"])
    brief = NODE_BRIEF.get(slug) or "这一步要能检查、能交给下一个人，别只做演示。"
    methods = _match_methods(cur, slug)
    stems = _aifde_items(cur, topic["id"])
    prev_t, next_t = _cycle_nav(graph["topics"], slug)
    nav = ['<a href="/方法">回学习</a>']
    if "discovery" in lessons:
        nav.append('<a href="/方法/discovery">先去客户发现这一课</a>')
    if prev_t:
        nav.append(f'<a href="/方法/{S.esc(prev_t["slug"])}">上一步 · {S.esc(prev_t["name"])}</a>')
    if next_t:
        nav.append(f'<a href="/方法/{S.esc(next_t["slug"])}">下一步 · {S.esc(next_t["name"])}</a>')
    inner = f"""
{_learn_strip(l1, slug, lessons)}
<section class="desk-lede">
  <p class="k">学习 · 还没写成课</p>
  <h1>{S.esc(topic["name"])}</h1>
  <p>{S.esc(brief)}</p>
  <p class="note">这一页先列练习和阅读。写成课以后从「学习」点进来。</p>
</section>
<section class="section">
  <h2>练习情景</h2>
  {_stem_list(stems)}
</section>
<section class="section">
  <h2>相关阅读</h2>
  {_method_list(methods)}
</section>
<p class="hint">{" · ".join(nav)}</p>
"""
    return _shell(
        "%s · 方法 · %s" % (topic["name"], S.SITE_NAME),
        inner,
        gh,
        "/方法/%s" % slug,
        extra_head=LEARN_HEAD,
        meta_description=S.trunc(f"{topic['name']}：{NODE_BRIEF.get(slug, '')}", 158) or None,
    )
