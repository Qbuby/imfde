# -*- coding: utf-8 -*-
"""OpenFDE world dynamics, 3D sand-table homepage (/).

Same data as the 2D timeline at ``/平面`` (``worldview.load_world``); nothing
here invents coordinates. x = date, z = lane, y = signal. Organisations sit
on a rear "base" row and project lines forward to their dated events, which
is the forward-deployed metaphor. No WebGL or a narrow viewport falls back
to a plain list that links to ``/平面``.
"""
from __future__ import annotations

import server as S
from worldview import WORLD_BRAND, json_tag, load_world

THREE_VERSION = "0.185.1"

IMPORT_MAP = """<script type="importmap">
{"imports":{"three":"/static/vendor/three/three.module.min.js","three/addons/":"/static/vendor/three/addons/"}}
</script>"""


def _ov_stats(data: dict) -> str:
    """概览层数据摘要：近 30 天各泳道条数 + 总数（prerender 兜底，JS 按 currentRange 重绘）。"""
    counts = (data.get("window_counts") or {}).get("30") or {}
    by_lane = counts.get("by_lane") or {}
    items = "".join(
        f'<div class="w3-ov-stat" data-lane="{S.esc(l.get("id") or "")}">'
        f'<b>{int(by_lane.get(l.get("id")) or 0)}</b><span>{S.esc(l.get("zh") or "")}</span></div>'
        for l in (data.get("lanes") or [])
    )
    items += (
        f'<div class="w3-ov-stat w3-ov-total"><b>{int(counts.get("total") or 0)}</b>'
        f"<span>近 30 天全部</span></div>"
    )
    return items


def _ov_changes(data: dict) -> str:
    """概览层 3 张关键变化卡；chain 为空的卡片去 data-chain 并置 aria-disabled。"""
    out = []
    for i, c in enumerate((data.get("changes_by_range") or {}).get("30") or []):
        chain = c.get("chain") or []
        n = int(c.get("n") or 0)
        if chain:
            attrs = f' data-chain="{i}"'
            meta = f"{n} 条信号 · 证据链 {len(chain)} 步"
        else:
            attrs = ' aria-disabled="true"'
            meta = "本窗暂无对应信号"
        out.append(
            f'<button type="button" class="w3-ov-card-item"{attrs}>'
            f'<b class="w3-ov-c-num">{S.esc(c.get("num") or str(i + 1))}</b>'
            f'<span class="w3-ov-c-body"><strong>{S.esc(c.get("title") or "")}</strong>'
            f"<small>{S.esc(c.get('body') or '')}</small>"
            f'<span class="w3-ov-c-meta">{S.esc(meta)}</span></span>'
            f'<span class="w3-ov-c-go">看证据链 →</span></button>'
        )
    return "".join(out)


def render_world3d(cur) -> str:
    data = load_world(cur)
    github = data.get("github") or ""
    snapshot = S.esc(S.day_zh(S.SNAPSHOT))
    n30 = int(((data.get("window_counts") or {}).get("30") or {}).get("total") or 0)
    nav_links = "".join(
        (
            f'<a href="{S.esc(path)}" class="on" aria-current="page">{S.esc(label)}</a>'
            if label == "动态"
            else f'<a href="{S.esc(path)}">{S.esc(label)}</a>'
        )
        for label, path in S.NAV
    )
    auth_link = S.auth_link("/")
    # SEO：无 JS 的爬虫（百度/搜狗等）抓不到 3D 画布内容，服务端铺一份真实列表
    events = data.get("events") or []
    events_sorted = sorted(
        (e for e in events if e.get("day")),
        key=lambda e: e.get("day") or "",
        reverse=True,
    )
    seo_items = "".join(
        f'<li><time datetime="{S.esc(e.get("day") or "")}">{S.esc(S.day_zh(e.get("day") or ""))}</time> '
        f'[{S.esc(e.get("doc_label") or e.get("lane") or "")}] '
        f'<a href="{S.esc(e.get("href") or S.href("/动态/%s" % e["id"]))}">{S.esc(e.get("title") or "")}</a>'
        f'{(" — " + S.esc(S.trunc(e.get("happened") or e.get("why") or "", 90))) if (e.get("happened") or e.get("why")) else ""}</li>'
        for e in events_sorted[:30]
    )
    seo_counts = data.get("window_counts") or {}
    n_all = int(((seo_counts.get("90")) or {}).get("total") or len(events))
    inner = f"""
<div class="w3" id="w3" data-three="{THREE_VERSION}">
  <header class="w3-hud" role="banner">
    <a class="w3-brand" href="/world3d" aria-label="{S.esc(WORLD_BRAND)} {S.esc(S.SITE_CLUB)}">
      {S.brand_lockup()}
      <span class="brand-lock"><span class="brand-club">全球首个 FDE 实时情报动态沙盘</span></span>
    </a>
    <div class="w3-hud-tools">
      <div class="w3-range" role="radiogroup" aria-label="时间窗口">
        <button type="button" data-range="7" aria-pressed="false">7 天</button>
        <button type="button" data-range="30" class="on" aria-pressed="true">30 天</button>
        <button type="button" data-range="90" aria-pressed="false">90 天</button>
      </div>
      <div class="w3-lens" role="radiogroup" aria-label="你想站在谁那边看">
        <button type="button" data-lens="boss" class="on" aria-pressed="true">负责人</button>
        <button type="button" data-lens="field" aria-pressed="false">干活的人</button>
      </div>
      <nav class="w3-nav" aria-label="站内导航">{nav_links}{auth_link}</nav>
    </div>
  </header>

  <div class="w3-stage" id="w3-stage" aria-label="立体图">
    <canvas id="w3-canvas" tabindex="0" aria-describedby="w3-legend"></canvas>
    <div class="w3-labels w3-labels-3d" id="w3-labels-3d" aria-hidden="true"></div>
    <div class="w3-labels" id="w3-labels" aria-hidden="true"></div>
    <section class="w3-ov" id="w3-overview" aria-label="本期概览">
      <div class="w3-ov-card">
        <p class="w3-ov-k">imfde.ai · FDE 实时情报沙盘</p>
        <h1 class="w3-title">FDE 行业，正在发生什么</h1>
        <p class="w3-ov-desc">按 7 / 30 / 90 天三个窗口持续追踪 FDE 行业的<b>公司动作</b>、<b>客户部署</b>、<b>人物观点</b>与<b>招聘动向</b>；沙盘上每个形体都对应一份可核对的原文。</p>
        <p class="w3-sub" data-w3-lede>点开观察，读事实与影响，再进入落地或方法 · 过去 30 天</p>
        <div class="w3-ov-stats" id="w3-ov-stats">{_ov_stats(data)}</div>
        <div class="w3-ov-changes" id="w3-ov-changes">{_ov_changes(data)}</div>
        <div class="w3-ov-foot">
          <button type="button" class="w3-ov-cta" id="w3-ov-enter" data-ov-enter>进入情报沙盘</button>
          <p class="w3-ov-note" id="w3-ov-note">资料截止 {snapshot} · 全部 {n30} 条</p>
        </div>
      </div>
    </section>
    <div class="w3-scope" role="group" aria-label="沙盘范围">
      <button type="button" data-scope="featured" class="on" aria-pressed="true">精选</button>
      <button type="button" data-scope="all" aria-pressed="false">全部</button>
    </div>
    <p class="w3-hint" id="w3-hint">拖一拖、滚一滚。点一个点看说明。</p>
  </div>

  <aside class="w3-panel" id="w3-panel" aria-label="这条的说明" aria-live="polite"></aside>

  <footer class="w3-legend" id="w3-legend" aria-label="图例">
    <span class="w3-lg-k">图例</span>
    <span title="公司自己发布的动作"><i class="w3-gl w3-gl-tower"></i>公司</span>
    <span title="有日期的客户故事"><i class="w3-gl w3-gl-landing"></i>客户故事</span>
    <span title="人物公开讲的话"><i class="w3-gl w3-gl-beacon"></i>人物</span>
    <span title="招聘和学习材料"><i class="w3-gl w3-gl-rail"></i>招聘 / 学习</span>
    <span class="w3-lg-note">亮的是材料比较扎实</span>
    <span class="w3-lg-sep"></span>
    <span><i class="w3-dot w3-dot-pub"></i>发布日</span>
    <span><i class="w3-dot w3-dot-mod"></i>页面上写的日期</span>
    <span class="w3-lg-sep"></span>
    <span><i class="w3-ln w3-ln-direct"></i>直接有关</span>
    <span><i class="w3-ln w3-ln-indirect"></i>间接有关</span>
    <span><i class="w3-ln w3-ln-base"></i>从公司到客户</span>
    <span class="w3-lg-snap">资料截止 {snapshot}</span>
  </footer>

  <nav class="w3-exits" id="w3-exits" aria-label="接下来">
    <span class="w3-lg-k">接下来</span>
    <a href="/落地?窗=30" data-room="落地">负责人</a>
    <a href="/现场?窗=30" data-room="现场">从业者</a>
    <a href="/案例?窗=30" data-room="案例">案例</a>
    <a href="/方法" data-room="方法">学习</a>
  </nav>

  <aside class="w3-book" id="w3-book" tabindex="0" aria-label="翻开查看企业微信小助手二维码">
    <button type="button" class="w3-book-fold" aria-label="收起手册" title="收起">—</button>
    <div class="w3-book-mini" aria-hidden="true"><span>手册</span></div>
    <div class="w3-book-page">
      <p class="w3-book-line">助力未来<b>999 万</b>FDE 的成长</p>
      <img class="w3-book-qr" src="/static/icons/wecom-qrcode.png" alt="企业微信小助手二维码"/>
      <p class="w3-book-cap">企业微信 · 小助手</p>
    </div>
    <div class="w3-book-cover">
      <img class="w3-book-cover-face" src="/static/icons/book-cover.png" alt="imfde.ai 成长手册封面"/>
      <div class="w3-book-cover-back"></div>
    </div>
  </aside>

  <section class="w3-fallback" id="w3-fallback" hidden>
    <h1 class="sr-only">FDE 行业，正在发生什么 — 平面列表</h1>
    <h2>改成列表了</h2>
    <p id="w3-fallback-why">这个屏幕用不了立体图。内容和首页是同一批。</p>
    <p><a class="w3-fallback-link" href="/平面">打开列表 →</a></p>
    <ol class="w3-fallback-list" id="w3-fallback-list"></ol>
  </section>

  <noscript>
    <section class="w3-seo">
      <h2>世界动态 · 最近更新</h2>
      <p>imfde.ai 持续追踪 FDE（Forward Deployed Engineer）相关的公司动作、真实客户部署、人物观点与方法岗位。本页是 3D 沙盘，你的浏览器未启用脚本，以下是同一批数据的文字版（最近 {len(seo_items)} 条，全库近 90 天 {n_all} 条）。</p>
      <ol>
        {seo_items}
      </ol>
      <p>
        <a href="/落地">负责人视图</a> ·
        <a href="/现场">从业者视图</a> ·
        <a href="/案例">客户案例目录</a> ·
        <a href="/方法">FDE 学习手册</a> ·
        <a href="/平面">平面时间轴</a>
      </p>
    </section>
  </noscript>
</div>
{json_tag(data)}
<script type="module" src="/static/world3d.js"></script>
"""
    return S.shell(
        "imfde.ai — 全球首个 FDE 实时情报动态沙盘",
        "动态",
        inner,
        github,
        extra_head=IMPORT_MAP
        + '\n<link rel="preload" as="image" href="/static/icons/book-cover.png"/>'
        + '\n<link rel="stylesheet" href="/static/world3d.css"/>',
        body_class="world3d-page",
        skip_wrap=True,
        skip_mast=True,
        skip_foot=True,
        home_css=False,
        page_path="/",
        meta_description=(
            "imfde.ai 持续追踪 FDE（Forward Deployed Engineer）行业的公司动作、真实客户部署、"
            "人物观点与方法岗位，以 3D 实时情报沙盘呈现，可按 7/30/90 天窗口查看，"
            "每条动态可对照原文核读。首页先给出当期概览与三条关键变化，再进入沙盘探索。"
        ),
        json_ld={
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": S.SITE_NAME,
            "url": S.SITE_ORIGIN + "/",
            "logo": S.abs_url("/static/icons/logo-mark.png"),
            "description": "全球首个 FDE 实时情报动态沙盘",
        },
    )
