# -*- coding: utf-8 -*-
"""OpenFDE world dynamics, 3D sand-table view (/world3d).

Same data as the 2D homepage (``worldview.load_world``); nothing here invents
coordinates. x = date, z = lane, y = signal. Organisations sit on a rear
"base" row and project lines forward to their dated events, which is the
forward-deployed metaphor. Rendering is a progressive enhancement over the
2D timeline: no WebGL or a narrow viewport falls back to a plain list that
links back to ``/``.
"""
from __future__ import annotations

import os

import server as S
from worldview import WORLD_BRAND, json_tag, load_world

THREE_VERSION = "0.185.1"

# 站外门户（交易/撮合平台）地址：由环境变量注入，留空则不显示入口。
PLATFORM_URL = (os.environ.get("IMFDE_PLATFORM_URL") or "").strip()
# AI 解读：由环境变量注入（Vercel 项目设置里配置），未配置则隐藏 AI 入口。
AI_ENABLED = bool((os.environ.get("AI_API_KEY") or "").strip())

IMPORT_MAP = """<script type="importmap">
{"imports":{"three":"/static/vendor/three/three.module.min.js","three/addons/":"/static/vendor/three/addons/"}}
</script>"""


def render_world3d(cur) -> str:
    data = load_world(cur)
    github = data.get("github") or ""
    snapshot = S.esc(S.SNAPSHOT)
    # 世界动态（平面时间轴）暂时废弃，导航与图例里不再放它的入口。
    nav_links = "".join(
        f'<a href="{S.esc(path)}">{S.esc(label)}</a>'
        for label, path in S.NAV
        if path not in ("/世界动态", "/world", "/")
    )
    platform_link = (
        f'<a class="w3-plat" href="{S.esc(PLATFORM_URL)}">imfde 平台 →</a>'
        if PLATFORM_URL
        else ""
    )
    gh_link = (
        f'<a class="w3-gh" href="{S.esc(github)}" target="_blank" rel="noopener noreferrer">GitHub</a>'
        if github
        else ""
    )
    inner = f"""
<div class="w3" id="w3" data-three="{THREE_VERSION}" data-ai="{1 if AI_ENABLED else 0}">
  <header class="w3-hud" role="banner">
    <a class="w3-brand" href="/" aria-label="{S.esc(WORLD_BRAND)} 立体沙盘">
      {S.brand_mark()}
      <span class="w3-brand-sub">立体世界 · 沙盘</span>
    </a>
    <div class="w3-hud-mid">
      <h1 class="w3-title">FDE 世界正在发生什么</h1>
      <p class="w3-sub" data-w3-lede>过去 30 天 · 沙盘上每一个形体都是一份可核对的官方原文</p>
    </div>
    <div class="w3-hud-tools">
      <div class="w3-range" role="radiogroup" aria-label="时间窗口">
        <button type="button" data-range="7" aria-pressed="false">7 天</button>
        <button type="button" data-range="30" class="on" aria-pressed="true">30 天</button>
        <button type="button" data-range="90" aria-pressed="false">90 天</button>
      </div>
      <div class="w3-lens" role="radiogroup" aria-label="AI 解释视角">
        <button type="button" data-lens="boss" class="on" aria-pressed="true">决策者</button>
        <button type="button" data-lens="field" aria-pressed="false">从业者</button>
      </div>
      <nav class="w3-nav" aria-label="站内导航">{nav_links}{platform_link}{gh_link}</nav>
    </div>
  </header>

  <div class="w3-stage" id="w3-stage" aria-label="FDE 世界 3D 沙盘">
    <canvas id="w3-canvas" tabindex="0" aria-describedby="w3-legend"></canvas>
    <div class="w3-labels w3-labels-3d" id="w3-labels-3d" aria-hidden="true"></div>
    <div class="w3-labels" id="w3-labels" aria-hidden="true"></div>
    <p class="w3-hint" id="w3-hint">拖动旋转 · 滚轮缩放 · 点击任一形体看证据</p>
  </div>

  <aside class="w3-panel" id="w3-panel" aria-label="动态证据详情" aria-live="polite"></aside>

  <footer class="w3-legend" id="w3-legend" aria-label="沙盘图例">
    <span class="w3-lg-k">形体</span>
    <span title="公司动作：组织自己发布的官方动作"><i class="w3-gl w3-gl-tower"></i>塔 · 机构</span>
    <span title="真实部署：公司射向客户前线的落点"><i class="w3-gl w3-gl-landing"></i>落点 · 部署</span>
    <span title="人物与观点：悬在轨道上空的信号灯"><i class="w3-gl w3-gl-beacon"></i>信号灯 · 人物</span>
    <span title="方法与岗位：铺在地面上的轨道"><i class="w3-gl w3-gl-rail"></i>轨道 · 方法</span>
    <span class="w3-lg-note">高度 / 亮度 = 信号</span>
    <span class="w3-lg-sep"></span>
    <span><i class="w3-dot w3-dot-pub"></i>已发布日期</span>
    <span><i class="w3-dot w3-dot-mod"></i>页上修改日</span>
    <span class="w3-lg-sep"></span>
    <span><i class="w3-ln w3-ln-direct"></i>直接</span>
    <span><i class="w3-ln w3-ln-indirect"></i>间接</span>
    <span><i class="w3-ln w3-ln-base"></i>机构 → 前线</span>
    <span class="w3-lg-snap">快照 {snapshot} · 仅 published / modified 上轴 · <a href="/落地">落地</a> · <a href="/现场">现场</a> · <a href="/案例">部署证据</a> · <a href="/方法">方法</a></span>
  </footer>

  <section class="w3-fallback" id="w3-fallback" hidden>
    <h2>已切换到平面列表</h2>
    <p id="w3-fallback-why">此设备不支持 WebGL，或屏幕较窄。数据与 3D 沙盘完全一致。</p>
    <p><a class="w3-fallback-link" href="/案例">打开部署证据目录 →</a></p>
    <ol class="w3-fallback-list" id="w3-fallback-list"></ol>
  </section>
</div>
{json_tag(data)}
<script type="module" src="/static/world3d.js"></script>
"""
    return S.shell(
        "立体世界 · %s" % WORLD_BRAND,
        "世界动态",
        inner,
        github,
        extra_head=IMPORT_MAP + '\n<link rel="stylesheet" href="/static/world3d.css"/>',
        body_class="world3d-page",
        skip_wrap=True,
        skip_mast=True,
        skip_foot=True,
        home_css=False,
        page_path="/world3d",
    )
