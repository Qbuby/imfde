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

  <section class="w3-fallback" id="w3-fallback" hidden>
    <h2>改成列表了</h2>
    <p id="w3-fallback-why">这个屏幕用不了立体图。内容和首页是同一批。</p>
    <p><a class="w3-fallback-link" href="/平面">打开列表 →</a></p>
    <ol class="w3-fallback-list" id="w3-fallback-list"></ol>
  </section>
</div>
{json_tag(data)}
<script type="module" src="/static/world3d.js"></script>
"""
    return S.shell(
        "%s · %s" % (S.SITE_CLUB, WORLD_BRAND),
        "动态",
        inner,
        github,
        extra_head=IMPORT_MAP + '\n<link rel="stylesheet" href="/static/world3d.css"/>',
        body_class="world3d-page",
        skip_wrap=True,
        skip_mast=True,
        skip_foot=True,
        home_css=False,
        page_path="/",
    )
