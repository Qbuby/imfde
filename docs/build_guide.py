# -*- coding: utf-8 -*-
"""构建《FDE 从知道到入门》阅读页（docs/index.html）。

数据源：docs/fde-guide.md（v2 结构重排稿）
用法：python build_guide.py   （在本目录执行）

生成物：docs/index.html —— 零运行时依赖的静态阅读页：
- 预渲染 HTML 正文（markdown 库 + tables）
- 侧栏分层目录（部 / 章 / 节）+ 筛选 + 滚动定位
- 上一章/下一章、阅读进度、移动端抽屉目录
"""
import json
import re
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
SRC = HERE / "fde-guide.md"
OUT = HERE / "index.html"

# ---------- 1. 读 MD，去掉内置"目录"章节（阅读页有自己的侧栏目录） ----------
text = SRC.read_text(encoding="utf-8")
m = re.search(r"^## 目录\s*$", text, flags=re.M)
if m:
    nxt = re.search(r"^---\s*$", text[m.end():], flags=re.M)
    if nxt:
        text = text[: m.start()] + text[m.end() + nxt.end():]
    else:
        text = text[: m.start()]

# ---------- 2. Markdown → HTML ----------
body = markdown.markdown(text, extensions=["tables"])

# ---------- 3. 注入标题 id，收集目录 ----------
counter = 0
toc = []          # {t: 标题, id, l: 0部/1章/2节}
cur_part = "开场"  # 首个部标题前的章归入"开场"
seen_doc_title = False

head_re = re.compile(r"<h([123])>(.*?)</h\1>", flags=re.S)

def _tag(mm: "re.Match") -> str:
    global counter, cur_part, seen_doc_title
    lvl, inner = int(mm.group(1)), mm.group(2)
    plain = re.sub(r"<[^>]+>", "", inner).strip()

    if lvl == 1:
        if not seen_doc_title:          # 文档主标题，页面顶栏已有，跳过
            seen_doc_title = True
            return ""
        cur_part = plain
        counter += 1
        hid = f"s-{counter}"
        toc.append({"t": plain, "id": hid, "l": 0})
        return f'<h1 id="{hid}" class="part">{inner}</h1>'

    if lvl == 2:
        part = cur_part
        if plain.startswith("附录"):      # 附录归入独立分组
            part = "附录"
        counter += 1
        hid = f"s-{counter}"
        toc.append({"t": plain, "id": hid, "l": 1})
        toc_meta[hid] = part
        return f'<h2 id="{hid}" data-part="{part}">{inner}</h2>'

    counter += 1
    hid = f"s-{counter}"
    toc.append({"t": plain, "id": hid, "l": 2})
    return f'<h3 id="{hid}">{inner}</h3>'

toc_meta: dict = {}
body = head_re.sub(_tag, body)

# 目录分组：把 h2 的所属部写进目录项（供侧栏分组渲染）
for item in toc:
    if item["l"] == 1:
        item["g"] = toc_meta.get(item["id"], "")

# 补组头：开场（首部之前的章）与附录各插一个 lvl0 分组头（无锚点，纯展示）
final: list = []
part_heads = {i for i, t in enumerate(toc) if t["l"] == 0}
first_part = min(part_heads) if part_heads else len(toc)
if first_part > 0:
    final.append({"t": "开场", "id": "", "l": 0})
    final.extend(toc[:first_part])
final.extend(toc[first_part:])
if any(t["t"].startswith("附录") for t in toc):
    for i, t in enumerate(final):
        if t["l"] == 1 and t["t"].startswith("附录"):
            final.insert(i, {"t": "附录", "id": "", "l": 0})
            break
    toc = final
else:
    toc = final

# ---------- 4. 页面模板 ----------
TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FDE 从知道到入门 · 学习成长 | imfde.ai</title>
<meta name="description" content="《FDE 从知道到入门》v2 在线阅读 — 五部二十一章 + 五附录，左侧目录导航、筛选与滚动定位。">
<style>
  :root{
    --bg:#fafaf9; --surface:#ffffff; --text:#18181b; --muted:#71717a;
    --border:#e4e4e7; --accent:#4f46e5; --accent-dark:#4338ca; --accent-soft:#eef2ff;
    --topbar-h:56px; --sidebar-w:300px;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  html{scroll-behavior:smooth;scroll-padding-top:72px}
  body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);line-height:1.85;font-size:15.5px}
  a{text-decoration:none;color:var(--accent-dark)}
  a:hover{text-decoration:underline}
  button{font-family:inherit}

  /* 顶栏 */
  .topbar{position:fixed;top:0;left:0;right:0;height:var(--topbar-h);z-index:100;background:rgba(255,255,255,.94);backdrop-filter:blur(8px);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:14px;padding:0 16px}
  .tb-back{display:flex;align-items:center;gap:8px;font-weight:600;font-size:14px;color:var(--text);white-space:nowrap}
  .tb-back:hover{color:var(--accent);text-decoration:none}
  .tb-back .logo-badge{background:var(--accent);color:#fff;font-weight:700;font-size:13px;padding:5px 10px;border-radius:8px}
  .tb-title{font-size:13px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .tb-title b{color:var(--text);font-weight:600}
  .tb-spacer{flex:1}
  .tb-btn{border:1px solid var(--border);background:var(--surface);color:var(--text);border-radius:8px;padding:5px 10px;font-size:13px;cursor:pointer;transition:border-color .15s,color .15s;white-space:nowrap}
  .tb-btn:hover{border-color:var(--accent);color:var(--accent)}
  .tb-btn.icon{padding:5px 9px}
  .progress{position:fixed;top:var(--topbar-h);left:0;right:0;height:2px;z-index:99;background:transparent}
  .progress i{display:block;height:100%;width:0;background:var(--accent)}
  .tb-menu{display:none}

  /* 侧栏目录 */
  .sidebar{position:fixed;top:var(--topbar-h);left:0;bottom:0;width:var(--sidebar-w);background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:90}
  .side-filter{padding:12px 14px;border-bottom:1px solid var(--border)}
  .side-filter input{width:100%;border:1px solid var(--border);border-radius:8px;padding:7px 12px;font-size:13px;outline:none;background:var(--bg);color:var(--text)}
  .side-filter input:focus{border-color:var(--accent);background:#fff}
  .toc{flex:1;overflow-y:auto;padding:10px 8px 24px;overscroll-behavior:contain}
  .toc a{display:block;border-radius:7px;padding:5px 10px;font-size:13px;color:var(--text);cursor:pointer;line-height:1.45;margin-bottom:1px}
  .toc a:hover{background:var(--accent-soft);color:var(--accent-dark);text-decoration:none}
  .toc a.active{background:var(--accent);color:#fff;font-weight:600}
  .toc a.lvl0{font-weight:650;margin-top:12px;color:var(--text)}
  .toc a.lvl0.active{color:#fff}
  .toc a.lvl1{padding-left:22px}
  .toc a.lvl2{padding-left:36px;font-size:12.5px;color:var(--muted)}
  .toc a.lvl2:hover{color:var(--accent-dark)}
  .toc-empty{padding:16px 12px;font-size:13px;color:var(--muted);display:none}
  .side-foot{border-top:1px solid var(--border);padding:10px 14px;font-size:12px;color:var(--muted);display:flex;justify-content:space-between;align-items:center;gap:8px}
  .side-foot a{color:var(--accent)}
  .side-foot a:hover{text-decoration:underline}
  .backdrop{display:none;position:fixed;inset:0;top:var(--topbar-h);background:rgba(24,24,27,.4);z-index:85}

  /* 正文 */
  .viewer{margin-left:var(--sidebar-w);margin-top:var(--topbar-h);padding:34px 24px 90px}
  .article{max-width:740px;margin:0 auto}
  .article p{margin:0 0 14px}
  .article strong{color:var(--text)}
  .article h1.part{margin:56px 0 6px;padding-top:26px;border-top:1px solid var(--border);font-size:23px;line-height:1.45;letter-spacing:-.2px}
  .article h1.part:first-child{margin-top:0;padding-top:0;border-top:none}
  .article h2{margin:44px 0 12px;font-size:19.5px;letter-spacing:-.2px}
  .article h3{margin:26px 0 8px;font-size:16px;color:var(--text)}
  .article blockquote{margin:18px 0;padding:12px 18px;border-left:3px solid var(--accent);background:var(--accent-soft);border-radius:0 10px 10px 0;color:#3730a3;font-size:14.5px}
  .article blockquote p{margin:0 0 6px}
  .article blockquote p:last-child{margin:0}
  .article table{border-collapse:collapse;width:100%;margin:18px 0;font-size:13.5px;line-height:1.6;display:block;overflow-x:auto}
  .article th{text-align:left;font-size:12.5px;color:var(--muted);font-weight:600;padding:8px 12px;border-bottom:1.5px solid var(--border);background:var(--bg);white-space:nowrap}
  .article td{padding:9px 12px;border-bottom:1px solid var(--border);vertical-align:top}
  .article tr:last-child td{border-bottom:none}
  .article hr{border:none;border-top:1px solid var(--border);margin:34px 0}
  .doc-title-block{margin-bottom:8px}
  .doc-title-block .sub{color:var(--muted);font-size:14px}

  /* 章末导航 */
  .chapter-nav{display:flex;justify-content:space-between;gap:12px;max-width:740px;margin:56px auto 0;padding-top:22px;border-top:1px solid var(--border)}
  .chapter-nav a{display:flex;flex-direction:column;gap:2px;padding:10px 14px;border:1px solid var(--border);border-radius:10px;background:var(--surface);max-width:48%;transition:border-color .15s}
  .chapter-nav a:hover{border-color:var(--accent);text-decoration:none}
  .chapter-nav .dir{font-size:11.5px;color:var(--muted)}
  .chapter-nav .name{font-size:13.5px;color:var(--accent-dark);font-weight:500}

  .to-top{position:fixed;right:22px;bottom:26px;width:38px;height:38px;border-radius:10px;border:1px solid var(--border);background:var(--surface);color:var(--muted);font-size:15px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.06);opacity:0;pointer-events:none;transition:opacity .2s}
  .to-top.show{opacity:1;pointer-events:auto}
  .to-top:hover{color:var(--accent);border-color:var(--accent)}

  @media (max-width:860px){
    .sidebar{transform:translateX(-100%);transition:transform .22s ease;box-shadow:4px 0 20px rgba(0,0,0,.08)}
    body.side-open .sidebar{transform:none}
    body.side-open .backdrop{display:block}
    .viewer{margin-left:0;padding:24px 18px 80px}
    .tb-title{display:none}
    .tb-menu{display:inline-flex}
  }
</style>
</head>
<body>

<header class="topbar">
  <a class="tb-back" href="../index.html"><span class="logo-badge">ImFDE</span><span>← 返回门户</span></a>
  <div class="tb-title"><b>FDE 从知道到入门</b> · 学习成长</div>
  <div class="tb-spacer"></div>
  <div style="display:flex;gap:4px">
    <span id="chNow" style="font-size:12.5px;color:var(--muted);align-self:center;white-space:nowrap;font-variant-numeric:tabular-nums"></span>
    <button class="tb-btn icon" id="prevBtn" title="上一章">↑</button>
    <button class="tb-btn icon" id="nextBtn" title="下一章">↓</button>
  </div>
  <button class="tb-menu tb-btn icon" id="menuBtn" title="目录">☰ 目录</button>
</header>
<div class="progress"><i id="progBar"></i></div>

<aside class="sidebar">
  <div class="side-filter"><input id="tocFilter" type="text" placeholder="筛选章节标题…" autocomplete="off"></div>
  <nav class="toc" id="toc"></nav>
  <div class="toc-empty" id="tocEmpty">没有匹配的章节</div>
  <div class="side-foot"><span>v2 · 五部二十一章</span><a href="fde-guide.md" download="FDE从知道到入门.md">下载 MD</a></div>
</aside>
<div class="backdrop" id="backdrop"></div>

<main class="viewer">
  <div class="article">
    <div class="doc-title-block">
      <h1 style="font-size:27px;letter-spacing:-.3px;margin-bottom:6px">FDE 从知道到入门</h1>
      <p class="sub">Forward Deployed Engineer 的认知、方法与实践手册 · v2 结构重排稿</p>
    </div>
    <!--ARTICLE-->
  </div>
  <div class="chapter-nav" id="chapterNav">
    <a id="navPrev" href="javascript:void(0)"><span class="dir">← 上一章</span><span class="name"></span></a>
    <a id="navNext" href="javascript:void(0)"><span class="dir">下一章 →</span><span class="name"></span></a>
  </div>
</main>

<button class="to-top" id="toTop" title="回到顶部">↑</button>

<script>
/* ====== 目录数据（构建时生成）====== */
const TOC=__TOC__;

const $=id=>document.getElementById(id);
const tocEl=$('toc'), chNow=$('chNow'), progBar=$('progBar');
let spyLock=false, curIdx=-1;

/* ====== 构建侧栏目录 ====== */
function buildTOC(){
  const frag=document.createDocumentFragment();
  TOC.forEach((item,i)=>{
    const a=document.createElement('a');
    a.className='lvl'+item.l; a.dataset.i=i; a.dataset.id=item.id;
    a.textContent=item.t;
    a.addEventListener('click',()=>{ if(!item.id)return; jump(item.id); spyLock=true; setActive(i); if(innerWidth<=860) closeSide(); });
    frag.appendChild(a);
  });
  tocEl.appendChild(frag);
}
function setActive(i){
  tocEl.querySelectorAll('a.active').forEach(x=>x.classList.remove('active'));
  const el=tocEl.querySelector(`a[data-i="${i}"]`);
  if(el){ el.classList.add('active');
    const r=el.getBoundingClientRect(), cr=tocEl.getBoundingClientRect();
    if(r.top<cr.top+8||r.bottom>cr.bottom-8) el.scrollIntoView({block:'nearest'});
  }
}

/* 目录筛选 */
$('tocFilter').addEventListener('input',e=>{
  const q=e.target.value.trim().toLowerCase();
  let n=0;
  tocEl.querySelectorAll('a').forEach(a=>{
    const hit=!q||a.textContent.toLowerCase().includes(q);
    a.style.display=hit?'':'none'; if(hit)n++;
  });
  $('tocEmpty').style.display=n?'none':'block';
});

/* ====== 跳转与滚动定位 ====== */
function jump(id){ const el=document.getElementById(id); if(el) el.scrollIntoView({block:'start'}); }
function topOf(el){ return el.getBoundingClientRect().top+scrollY-76; }

let raf=0;
addEventListener('scroll',()=>{ if(raf)return; raf=requestAnimationFrame(()=>{ raf=0; onScroll(); }); },{passive:true});
function onScroll(){
  renderProgress();
  const line=scrollY+96;
  let best=-1;
  for(let i=0;i<TOC.length;i++){
    const el=TOC[i].id?document.getElementById(TOC[i].id):null;
    if(!el) continue;
    if(topOf(el)<=line) best=i; else break;
  }
  if(best!==curIdx){ curIdx=best; updateCur(); }
  if(spyLock&&curIdx>=0){
    const el=document.getElementById(TOC[curIdx].id||'');
    if(!el||Math.abs(scrollY-topOf(el))<60) spyLock=false;
  }
  $('toTop').classList.toggle('show',scrollY>600);
}
function updateCur(){
  if(curIdx<0){ chNow.textContent=''; return; }
  chNow.textContent=TOC[curIdx].t.length>18?TOC[curIdx].t.slice(0,18)+'…':TOC[curIdx].t;
  if(!spyLock) setActive(curIdx);
  updateNav();
}
function updateNav(){
  const chapters=TOC.map((x,i)=>({...x,i})).filter(x=>x.l===1);
  let cur=chapters.findIndex(c=>c.i===curIdx);
  if(cur<0) cur=chapters.findIndex(c=>c.i>curIdx);
  const prev=cur>0?chapters[cur-1]:null;
  const next=cur>=0&&cur<chapters.length-1?chapters[cur+1]:(cur<0?chapters[0]:null);
  const set=(el,item)=>{ if(item){ el.style.visibility=''; el.querySelector('.name').textContent=item.t; el.onclick=()=>{ jump(item.id); spyLock=true; }; } else el.style.visibility='hidden'; };
  set($('navPrev'),prev); set($('navNext'),next);
}
$('prevBtn').addEventListener('click',()=>{ if(curIdx>0){ jump(TOC[curIdx-1].id); spyLock=true; } });
$('nextBtn').addEventListener('click',()=>{ if(curIdx<TOC.length-1){ jump(TOC[curIdx+1].id); spyLock=true; } });

function renderProgress(){
  const h=document.documentElement.scrollHeight-innerHeight;
  progBar.style.width=(h>0?Math.min(100,scrollY/h*100):0)+'%';
}

/* ====== 侧栏开合（窄屏） ====== */
$('menuBtn').addEventListener('click',()=>document.body.classList.toggle('side-open'));
$('backdrop').addEventListener('click',closeSide);
function closeSide(){ document.body.classList.remove('side-open'); }
$('toTop').addEventListener('click',()=>scrollTo({top:0,behavior:'smooth'}));

/* ====== 启动 ====== */
buildTOC();
renderProgress();
if(location.hash){ const t=document.getElementById(location.hash.slice(1)); if(t) setTimeout(()=>scrollTo({top:topOf(t),behavior:'auto'}),60); }
</script>
</body>
</html>
"""

html = TEMPLATE.replace("<!--ARTICLE-->", body).replace(
    "__TOC__", json.dumps(toc, ensure_ascii=False)
)
OUT.write_text(html, encoding="utf-8")
print(f"OK  {OUT.name}  {OUT.stat().st_size//1024} KB  目录项 {len(toc)}")
