# -*- coding: utf-8 -*-
"""将 portal 内容服务静态化落盘，让 Vercel 等静态站可直接服务。

输出：portal/<路由>.html + portal/cases.json（案例数据，供 portal/案例.html 前端 JS 渲染详情）
用法：python build_static.py   （在 portal/site 目录外，portal/ 同级执行，或本脚本按 HERE 解析）
"""
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "site"))

import server as S  # noqa: E402  import 必须在 sys.path 之后
import worldview   # noqa: E402
import world3d      # noqa: E402

DB = HERE / "fde.db"
OUT = HERE          # 直接输出到 portal/ 下

ROUTES = [
    ("世界动态", "world", worldview.render_world, {}),
    ("落地",     "deploy", S.render_deploy, {}),
    ("现场",     "field",  S.render_field,  {}),
    ("方法",     "methods",S.render_methods,{}),
    # 案例目录单独处理（要带数据）
]

# 世界动态路径里有完整 JSON 落盘 + 静态资源相对化。 world3d 单独处理（要内联 data 并相对化 /static/）。
ROUTES_WORLD3D = ("world3d", world3d.render_world3d)


def _to_relative_paths(html: str) -> str:
    """把 /static/...、/portal/...、绝对路径改写为相对路径，让 HTML 可在任意子目录直接打开。
    静态 HTML 输出到 portal/ 根，CSS/JS 在 portal/site/static/ 下，所以 /static/ -> site/static/。"""
    html = html.replace('href="/static/', 'href="site/static/')
    html = html.replace('src="/static/',  'src="site/static/')
    html = html.replace('href="/portal/', 'href="')
    # importmap 内的 three 模块与 addons 路径
    html = html.replace('"three":"/static/vendor/', '"three":"site/static/vendor/')
    html = html.replace('"three/addons/":"/static/vendor/', '"three/addons/":"site/static/vendor/')
    # 路径互引（侧栏导航等）
    html = html.replace('href="/世界动态"',  'href="世界动态.html"')
    html = html.replace('href="/world"',     'href="世界动态.html"')
    html = html.replace('href="/落地"',      'href="落地.html"')
    html = html.replace('href="/现场"',      'href="现场.html"')
    html = html.replace('href="/案例"',      'href="案例.html"')
    html = html.replace('href="/方法"',      'href="方法.html"')
    html = html.replace('href="/world3d"',   'href="world3d.html"')
    # 品牌返回门户首页（/ 在原服务是世界动态；静态导出后门户首页在上级）
    html = html.replace('href="index.html"', 'href="../index.html"')
    html = html.replace('href="/"',          'href="../index.html"')
    # 案例详情：/案例/<id> → 案例.html?id=<id>（同页 hash 渲染，由 portal/案例.html 的内嵌 JS 处理）
    import re
    html = re.sub(r'href="/案例/(\d+)"', lambda m: f'href="案例.html?id={m.group(1)}"', html)
    # canonical / OG url 不动（保留绝对域名，便于 SEO）
    return html


def _add_cases_json_to_library(html: str, cases: list) -> str:
    """在 portal/案例.html 末尾注入 cases.json 数据 + 详情渲染脚本占位（替换用）。"""
    js = (
        "\n<script id=\"cases-data\" type=\"application/json\">"
        + json.dumps(cases, ensure_ascii=False)
        + "</script>\n"
        + _cases_viewer_js()
    )
    return html.replace("</body>", js + "\n</body>", 1)


def _cases_viewer_js() -> str:
    """客户端：从 URL ?id=N 读 cases-data 渲染详情，否则保持默认目录。"""
    return """
<script>
(function(){
  var p=new URLSearchParams(location.search).get('id');
  if(!p) return;
  var data=document.getElementById('cases-data');
  if(!data) return;
  try{ var list=JSON.parse(data.textContent); }catch(e){ return; }
  var row=list.find(function(x){return String(x.id)===String(p);});
  if(!row) return;
  document.getElementById('main').innerHTML=renderDetail(row);
  document.title=row.source_title+' · 部署证据 · imfde.ai';
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c];});}
  function renderDetail(r){
    var h='<article style="max-width:780px;margin:30px auto;padding:0 20px;">';
    h+='<p style="font-size:12.5px;color:var(--mut);margin-bottom:6px;">部署证据 · 案例 #'+r.id+'</p>';
    h+='<h1 style="font-size:26px;line-height:1.3;margin-bottom:14px;">'+esc(r.source_title||'(无标题)')+'</h1>';
    var meta=[['tier',r.tier],['行业',r.industry],['客户具名',r.customer_named?'是':'否'],['原文',r.source_url]];
    h+='<p style="font-size:13px;color:var(--mut);margin-bottom:20px;">';
    meta.forEach(function(m){if(m[1])h+='<span style="margin-right:14px;">'+esc(m[0])+': '+esc(m[1])+'</span>';});
    h+='</p>';
    ['business_problem','existing_workflow','pain_point','discovery_method','why_ai','hero_use_case','data_sources','integration','ai_model','agent_workflow','human_in_the_loop','evaluation','deployment','time_to_production','business_kpi','measured_outcome','failure_iteration','productization']
      .forEach(function(k){var v=r[k]; if(v){h+='<h3 style="margin:18px 0 6px;font-size:15px;">'+esc(labelOf(k))+'</h3><p style="margin-bottom:6px;">'+esc(v)+'</p>';}});
    h+='<p style="margin-top:30px;"><a href="案例.html">← 回到案例目录</a></p>';
    h+='</article>';
    return h;
  }
  function labelOf(k){return {'business_problem':'业务问题','existing_workflow':'现有工作流','pain_point':'卡点','discovery_method':'怎么发现的','why_ai':'为什么用 AI','hero_use_case':'核心场景','data_sources':'数据来源','integration':'集成','ai_model':'AI 模型','agent_workflow':'智能体工作流','human_in_the_loop':'人在回路','evaluation':'评测','deployment':'部署形态','time_to_production':'上线周期','business_kpi':'业务指标','measured_outcome':'实测结果','failure_iteration':'失败迭代','productization':'产品化'}[k]||k;}
})();
</script>
"""


def _cases_full(db) -> list:
    """把 cases 表关键字段导出为 JSON，供 portal/案例.html 客户端渲染详情。
    customer_named 字段由 customers 表 LEFT JOIN 推导，这里不导（避免复杂 JOIN）。"""
    cols = ["id","source_url","source_title","tier","doc_type","customer_id",
            "industry","business_problem","existing_workflow","pain_point",
            "discovery_method","why_ai","hero_use_case","data_sources",
            "integration","ai_model","agent_workflow","human_in_the_loop",
            "evaluation","deployment","time_to_production","business_kpi",
            "measured_outcome","failure_iteration","productization"]
    cur = db.execute(f"SELECT {','.join(cols)} FROM cases")
    out = []
    for r in cur.fetchall():
        out.append(dict(r))
    return out


def main():
    if not DB.exists():
        print(f"DB 缺失: {DB}", file=sys.stderr); sys.exit(1)
    db = sqlite3.connect(str(DB))
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    # 1. 6 类核心路由（不含案例目录：单独处理）
    for name, _, fn, qs in ROUTES:
        html = fn(cur, qs) if name in ("落地", "现场", "方法") else fn(cur)
        html = _to_relative_paths(html)
        out = OUT / f"{name}.html"
        out.write_text(html, encoding="utf-8")
        print(f"OK {out.name}  {out.stat().st_size//1024} KB")

    # 2. world3d 单独（重要：要把 data JSON 内联）
    html = ROUTES_WORLD3D[1](cur)
    html = _to_relative_paths(html)
    out = OUT / "world3d.html"
    out.write_text(html, encoding="utf-8")
    print(f"OK {out.name}  {out.stat().st_size//1024} KB")

    # 3. 案例目录页（增强：注入 cases 数据用于 ?id=N 详情渲染）
    lib_html = S.render_library(cur, {})
    cases = _cases_full(db)
    lib_html = _to_relative_paths(lib_html)
    lib_html = _add_cases_json_to_library(lib_html, cases)
    out = OUT / "案例.html"
    out.write_text(lib_html, encoding="utf-8")
    print(f"OK {out.name}  {out.stat().st_size//1024} KB  (cases data {len(cases)})")

    # 4. 顺手把 cases.json 单独导出（方便其它用途）
    (OUT / "cases.json").write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    print(f"OK cases.json  {len(cases)} 条")

    print("\n完成。提交 portal/*.html + cases.json 到 git，Vercel 即可直接服务。")


if __name__ == "__main__":
    main()