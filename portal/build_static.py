# -*- coding: utf-8 -*-
"""全站预渲染：Cloudflare Workers 静态资产的构建脚本。

产出（portal/ 下，全部 ASCII 文件名，根绝对资源路径 /site/static/...）：
  world3d.html            首页（内联 world-data JSON）
  world.html              平面 / 时间轴
  deploy.html / field.html / methods.html / cases.html（含 cases-data JSON + ?id= 渲染）
  methods/<slug>.html     方法课详情（增量：写缺失的）
  events/<id>.html        动态详情（增量：事件内容不变，只写缺失的）
  world.json              /api/world.json 的静态等价
  robots.txt / sitemap.xml
  _redirects              Cloudflare 静态资产的重写表（中文路由 → ASCII 文件）

认证等动态端点由 Worker（worker/index.js）接管；页面里的登录入口是「未登录」
占位，浏览器端由 /site/static/auth-me.js 调 /api/me 升级成头像。

用法：python portal/build_static.py（仓库根或任意目录均可，路径按 HERE 解析）
"""
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "site"))

import server as S  # noqa: E402
import worldview  # noqa: E402
import world3d  # noqa: E402

DB = HERE / "fde.db"
OUT = HERE

AUTH_ME_SNIPPET = '\n<script src="/site/static/auth-me.js" defer></script>\n'


def _to_site_paths(html: str) -> str:
    """静态资产路径 /static/ → /site/static/（导入映射一并处理）；站内导航保持干净的
    中文根路径，由 _redirects 在 Cloudflare 上做 200 重写。"""
    html = html.replace('href="/static/', 'href="/site/static/')
    html = html.replace('src="/static/', 'src="/site/static/')
    html = html.replace('"/static/vendor/', '"/site/static/vendor/')
    return html


def _finish(html: str) -> str:
    """资源路径改写 + 注入 /api/me 登录态升级脚本。"""
    html = _to_site_paths(html)
    if "auth-me.js" not in html:
        html = html.replace("</body>", AUTH_ME_SNIPPET + "</body>", 1)
    return html


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"OK {path.relative_to(OUT).as_posix()}  {path.stat().st_size // 1024} KB")


def _write_if_missing(path: Path, text: str) -> bool:
    """事件/方法页内容不变，只补缺失的；已有文件不重写（避免 git 每日全量抖动）。"""
    if path.is_file():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def _page(fn, *args, **kwargs) -> str:
    return _finish(fn(*args, **kwargs))


REDIRECTS = """# Cloudflare 静态资产重写表（200 = 内部改写，URL 保持干净）
# 同时提供解码与百分编码两种写法，兼容 _redirects 的路径匹配口径。
/ /world3d.html 200
/index.html /world3d.html 200
/world3d /world3d.html 200
/世界动态 /world3d.html 200
/%E4%B8%96%E7%95%8C%E5%8A%A8%E6%80%81 /world3d.html 200
/world /world3d.html 200
/沙盘 /world3d.html 200
/立体世界 /world3d.html 200
/平面 /world.html 200
/%E5%B9%B3%E9%9D%A2 /world.html 200
/时间轴 /world.html 200
/落地 /deploy.html 200
/%E8%90%BD%E5%9C%B0 /deploy.html 200
/现场 /field.html 200
/%E7%8E%B0%E5%9C%BA /field.html 200
/案例 /cases.html 200
/%E6%A1%88%E4%BE%8B /cases.html 200
/方法 /methods.html 200
/%E6%96%B9%E6%B3%95 /methods.html 200
/方法/:slug /methods/:slug.html 200
/%E6%96%B9%E6%B3%95/:slug /methods/:slug.html 200
/动态/:id /events/:id.html 200
/%E5%8A%A8%E6%80%81/:id /events/:id.html 200
/动态/:id/* /events/:id.html 200
/%E5%8A%A8%E6%80%81/:id/* /events/:id.html 200
/api/world.json /world.json 200
/static/* /site/static/* 200
/favicon.ico /site/static/icons/logo-mark.png 200
# 旧认证入口 → ASCII 路由（Worker 接管 /login 与 /logout）
/登录 /login 200
/%E7%99%BB%E5%BD%95 /login 200
/退出登录 /logout 200
/%E9%80%80%E5%87%BA%E7%99%BB%E5%BD%95 /logout 200
"""


def _cases_viewer_js() -> str:
    """客户端：从 URL ?id=N 读 cases-data 渲染详情，否则保持默认目录。"""
    return """
<script>
(function(){
  var pathId=null; try{ var m=decodeURIComponent(location.pathname).match(/\/案例\/(\d+)/); if(m) pathId=m[1]; }catch(e){}
  var p=new URLSearchParams(location.search).get('id')||pathId;
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
    h+='<p style="margin-top:30px;"><a href="/案例">← 回到案例目录</a></p>';
    h+='</article>';
    return h;
  }
  function labelOf(k){return {'business_problem':'业务问题','existing_workflow':'现有工作流','pain_point':'卡点','discovery_method':'怎么发现的','why_ai':'为什么用 AI','hero_use_case':'核心场景','data_sources':'数据来源','integration':'集成','ai_model':'AI 模型','agent_workflow':'智能体工作流','human_in_the_loop':'人在回路','evaluation':'评测','deployment':'部署形态','time_to_production':'上线周期','business_kpi':'业务指标','measured_outcome':'实测结果','failure_iteration':'失败迭代','productization':'产品化'}[k]||k;}
})();
</script>
"""


def _cases_full(db) -> list:
    cols = ["id","source_url","source_title","tier","doc_type","customer_id",
            "industry","business_problem","existing_workflow","pain_point",
            "discovery_method","why_ai","hero_use_case","data_sources",
            "integration","ai_model","agent_workflow","human_in_the_loop",
            "evaluation","deployment","time_to_production","business_kpi",
            "measured_outcome","failure_iteration","productization"]
    cur = db.execute(f"SELECT {','.join(cols)} FROM cases")
    return [dict(r) for r in cur.fetchall()]


def main():
    if not DB.exists():
        print(f"DB 缺失: {DB}", file=sys.stderr)
        sys.exit(1)
    db = sqlite3.connect(str(DB))
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    # 1. 主页面（ASCII 文件名）
    pages = [
        ("world3d.html", lambda: world3d.render_world3d(cur)),
        ("world.html", lambda: worldview.render_world(cur)),
        ("deploy.html", lambda: S.render_deploy(cur, {})),
        ("field.html", lambda: S.render_field(cur, {})),
        ("methods.html", lambda: S.render_methods(cur, {})),
        ("cases.html", None),  # 案例目录单独注入 cases-data
    ]
    for name, fn in pages:
        if fn is None:
            continue
        _write(OUT / name, _page(fn))

    # 2. 案例目录 + 每条案例详情（增量：案例正文稳定，只补缺失文件）
    _write(OUT / "cases.html", _page(S.render_library, cur, {}))
    cases = _cases_full(db)
    new_cases = 0
    case_rows = list(cur.execute("SELECT id FROM cases ORDER BY id"))
    for row in case_rows:
        cid = int(row["id"])
        try:
            html = _page(S.render_case, cur, cid, {})
        except Exception as exc:  # 单条缺数据时跳过，不阻塞构建
            print(f"SKIP 案例/{cid}: {exc}")
            continue
        if _write_if_missing(OUT / "cases" / f"{cid}.html", html):
            new_cases += 1
    total_cases = len(list((OUT / "cases").glob("*.html"))) if (OUT / "cases").is_dir() else 0
    print(f"OK cases/   新增 {new_cases}，共 {total_cases}")
    (OUT / "cases.json").write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    print(f"OK cases.json  {len(cases)} 条")

    # 3. 动态详情（增量：事件内容不变，只补缺失的文件）
    new_events = 0
    rows = list(cur.execute("SELECT id FROM world_events WHERE day IS NOT NULL ORDER BY id"))
    ids = [r["id"] for r in rows]
    for eid in ids:
        html = _page(S.render_event, cur, int(eid))
        if _write_if_missing(OUT / "events" / f"{eid}.html", html):
            new_events += 1
    total_files = len(list((OUT / "events").glob("*.html"))) if (OUT / "events").is_dir() else 0
    print(f"OK events/  新增 {new_events}，共 {total_files}")

    # 4. 方法课详情（增量）
    slugs = [r[0] for r in cur.execute("SELECT slug FROM topics WHERE slug IS NOT NULL AND slug != ''")]
    from methods import render_node  # noqa: E402

    for slug in slugs:
        try:
            html = _page(render_node, cur, slug)
        except Exception as exc:  # 某节课缺数据时跳过，不阻塞构建
            print(f"SKIP 方法/{slug}: {exc}")
            continue
        _write_if_missing(OUT / "methods" / f"{slug}.html", html)
    print(f"OK methods/  {len(slugs)} 课")

    # 5. world.json / robots.txt / sitemap.xml / _redirects
    from worldview import load_world  # noqa: E402

    payload = load_world(cur)
    _write(OUT / "world.json", json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    _write(OUT / "robots.txt", S.robots_txt())
    _write(OUT / "sitemap.xml", S.sitemap_xml(cur))
    (OUT / "_redirects").write_text(REDIRECTS, encoding="utf-8")
    print("OK _redirects")

    print("\n完成。git 提交 portal/ 后，Cloudflare Workers 静态资产直接服务。")


if __name__ == "__main__":
    main()
