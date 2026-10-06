/* OpenFDE world dynamics — 3D sand table (/world3d).
   Same #world-data payload as the 2D timeline. No network, no randomness:
   x = date, z = lane, y = signal. Organisations sit on a rear "base" row and
   project lines forward to their dated events. */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import { CSS3DObject, CSS3DRenderer } from "three/addons/renderers/CSS3DRenderer.js";

const raw = document.getElementById("world-data");
const root = document.getElementById("w3");
if (!raw || !root) throw new Error("world3d: missing data");
const DATA = JSON.parse(raw.textContent || "{}");

const stage = document.getElementById("w3-stage");
const canvas = document.getElementById("w3-canvas");
const labelsHost = document.getElementById("w3-labels");
const labels3dHost = document.getElementById("w3-labels-3d");
const panel = document.getElementById("w3-panel");
const ledeEl = document.querySelector("[data-w3-lede]");
const hintEl = document.getElementById("w3-hint");
const fallback = document.getElementById("w3-fallback");
const ovStatsEl = document.getElementById("w3-ov-stats");
const ovChangesEl = document.getElementById("w3-ov-changes");
const ovNoteEl = document.getElementById("w3-ov-note");

const params = new URLSearchParams(location.search);
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const NARROW = matchMedia("(max-width: 767px)").matches;
const DAY = 86400000;
const rangeFromUrl = Number(params.get("窗") || params.get("range"));

/* 右侧悬浮手册：可拖动（位置记忆）、可折叠成书签；悬停翻页只认鼠标
   （pointerenter+pointerType 守卫，触屏合成 enter 不干扰 tap）；触屏/笔 tap
   切换翻页，键盘回车兜底（拖拽超阈值则不算 tap）。封面就绪前整本隐藏。 */
const book = document.getElementById("w3-book");
if (book) {
  const foldBtn = book.querySelector(".w3-book-fold");
  const MOBILE = matchMedia("(max-width: 1180px)");
  const setFolded = (v) => {
    book.classList.toggle("is-folded", v);
    try { localStorage.setItem("w3-book-folded", v ? "1" : "0"); } catch (_) {}
  };
  try {
    if (MOBILE.matches) book.classList.add("is-folded"); // 手机默认书签态，不占屏
    else if (localStorage.getItem("w3-book-folded") === "1") book.classList.add("is-folded");
  } catch (_) {
    if (MOBILE.matches) book.classList.add("is-folded");
  }

  const clampPos = (x, y) => {
    const w = book.offsetWidth || 188, h = book.offsetHeight || 250;
    return [
      Math.min(Math.max(x, 8), window.innerWidth - w - 8),
      Math.min(Math.max(y, 60), window.innerHeight - h - 8),
    ];
  };
  try {
    const saved = JSON.parse(localStorage.getItem("w3-book-pos") || "null");
    if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) {
      const [x, y] = clampPos(saved.x, saved.y);
      book.style.left = x + "px";
      book.style.top = y + "px";
      book.style.right = "auto";
    }
  } catch (_) {}

  book.addEventListener("pointerenter", (e) => {
    if (e.pointerType !== "mouse") return;
    if (book.dataset.noHover) delete book.dataset.noHover; // 拖完的第一次进入只吞掉；.no-hover 类保留压制 CSS hover，离开时再摘
    else book.classList.add("is-open");
  });
  book.addEventListener("pointerleave", (e) => {
    if (e.pointerType === "mouse" && !drag) { book.classList.remove("is-open", "no-hover"); }
  });

  /* 拖拽：move/up 挂在 window 上——书本布局移动会让元素级 pointer 捕获
     隐式丢失（实测 lostpointercapture），window 级监听不受命中测试影响 */
  let drag = null;
  const onDragMove = (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
    if (!drag.moved && Math.hypot(dx, dy) < 6) return;
    if (!drag.moved) { drag.moved = true; book.classList.add("is-dragging"); book.classList.remove("is-open"); }
    const [x, y] = clampPos(drag.ox + dx, drag.oy + dy);
    book.style.left = x + "px";
    book.style.top = y + "px";
    book.style.right = "auto";
  };
  const onDragEnd = (e) => {
    if (!drag) return;
    const moved = drag.moved;
    drag = null;
    window.removeEventListener("pointermove", onDragMove);
    window.removeEventListener("pointerup", onDragEnd);
    window.removeEventListener("pointercancel", onDragEnd);
    book.classList.remove("is-dragging");
    if (moved) {
      book.classList.remove("is-open"); // 松手即合上
      book.classList.add("no-hover");   // 压制 CSS :hover 翻页，直到指针真正离开一次
      book.dataset.noHover = "1";
      const r = book.getBoundingClientRect();
      try { localStorage.setItem("w3-book-pos", JSON.stringify({ x: Math.round(r.left), y: Math.round(r.top) })); } catch (_) {}
    } else if (e.type === "pointerup" && (e.pointerType !== "mouse" || book.classList.contains("is-folded"))) {
      /* 鼠标展开态由悬停翻页接管（书签态与触屏/笔 tap 切换）；
         手机窄屏：书签⇄内页卡双态切换 */
      if (MOBILE.matches) {
        if (book.classList.contains("is-folded")) { setFolded(false); book.classList.add("is-open"); }
        else { setFolded(true); book.classList.remove("is-open"); }
        return;
      }
      if (book.classList.contains("is-folded")) setFolded(false);
      else book.classList.toggle("is-open");
    }
  };
  book.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || drag) return;
    if (foldBtn && foldBtn.contains(e.target)) return;
    e.preventDefault(); // 拖拽不选中页面文字
    const r = book.getBoundingClientRect();
    drag = { sx: e.clientX, sy: e.clientY, ox: r.left, oy: r.top, moved: false };
    window.addEventListener("pointermove", onDragMove);
    window.addEventListener("pointerup", onDragEnd);
    window.addEventListener("pointercancel", onDragEnd);
  });
  book.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    if (book.classList.contains("is-folded")) setFolded(false);
    else book.classList.toggle("is-open");
  });
  foldBtn && foldBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    setFolded(!book.classList.contains("is-folded"));
  });

  const coverImg = book.querySelector(".w3-book-cover-face");
  const ready = () => book.classList.add("is-ready");
  if (coverImg && coverImg.complete && coverImg.naturalWidth) ready();
  else if (coverImg) {
    coverImg.addEventListener("load", ready);
    coverImg.addEventListener("error", ready);
  } else ready();
}

/* ---------- palette (dark variants of tokens.css lane hues) ---------- */
const LANE_COLOR = {
  company: { hi: "#3fc0c0", lo: "#017272" },
  deploy: { hi: "#6db0f4", lo: "#32618e" },
  people: { hi: "#fba952", lo: "#9b6325" },
  method: { hi: "#b7a1f5", lo: "#685698" },
};
const BG = "#020a12";
const GRID = "#1b2a35";
const BASE_FACE = "#0d1c29";
const ACCENT = "#3fc0c0";

/* ---------- layout ---------- */
const LANES = (DATA.lanes || []).map((l) => l.id);
const LANE_D = 14;
const LANE_HALF = (LANE_D - 3) / 2;
const laneZ = (lane) => (LANES.indexOf(lane) - (LANES.length - 1) / 2) * LANE_D;
const FRONT_Z = ((LANES.length - 1) / 2) * LANE_D + LANE_D / 2;
const BACK_Z = -FRONT_Z;
const BASE_Z = BACK_Z - 17;
const BOARD_W = { 7: 72, 30: 112, 90: 138 };
const LABEL_MAX_LIFT = 150; // px a label may be pushed up before it is hidden
const GT = 0.07; // CSS3D ground-text scale: 1 CSS px = 0.07 world units
const LANE_TEXT_W = 24; // world units reserved left of the board for lane names
const SIGNAL_H = { low: 2.4, mid: 4.8, high: 8 };
const SIGNAL_GLOW = { low: 0.22, mid: 0.42, high: 0.7 };

const byId = {};
(DATA.events || []).forEach((e) => (byId[e.id] = e));
const laneLabel = (id) => ((DATA.lanes || []).find((l) => l.id === id) || {}).zh || id;
const laneEn = (id) => ((DATA.lanes || []).find((l) => l.id === id) || {}).en || "";

const state = {
  range: [7, 30, 90].includes(rangeFromUrl) ? rangeFromUrl : 30,
  lens: params.get("lens") === "field" ? "field" : "boss",
  scope: "featured", // 精选沙盘；查看全部 / 深链 / 平面回退切 "all"
  selected: null,
  hovered: null,
  chain: null,
  chainLit: null,
};

/* ---------- helpers ---------- */
const esc = (v) =>
  String(v == null ? "" : v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

function parseDay(day) {
  if (!day) return null;
  const p = String(day).split("-").map(Number);
  if (p.length < 3 || p.some((n) => !Number.isFinite(n))) return null;
  return Date.UTC(p[0], p[1] - 1, p[2]);
}
const monthDay = (day) => (day ? `${Number(day.slice(5, 7))}-${day.slice(8, 10)}` : "无日期");
const tickLabel = (t) => {
  const d = new Date(t);
  return `${d.getUTCMonth() + 1}-${String(d.getUTCDate()).padStart(2, "0")}`;
};

function axisRange() {
  const end = parseDay(DATA.snapshot);
  const endDate = new Date(end);
  const ticks = [];
  let start;
  if (state.range === 7) {
    start = end - 6 * DAY;
    for (let d = start; d <= end; d += DAY) ticks.push({ t: d, label: tickLabel(d) });
  } else if (state.range === 90) {
    start = Date.UTC(endDate.getUTCFullYear(), endDate.getUTCMonth() - 2, 1);
    let c = new Date(start);
    while (c.getTime() < end) {
      ticks.push({ t: c.getTime(), label: tickLabel(c.getTime()) });
      const y = c.getUTCFullYear();
      const m = c.getUTCMonth();
      c = c.getUTCDate() === 1 ? new Date(Date.UTC(y, m, 15)) : new Date(Date.UTC(y, m + 1, 1));
    }
    ticks.push({ t: end, label: tickLabel(end) });
  } else {
    start = end - 28 * DAY;
    for (let w = 0; w < 5; w += 1) {
      const t = start + w * 7 * DAY;
      ticks.push({ t, label: tickLabel(t) });
    }
    ticks.push({ t: end, label: tickLabel(end) });
  }
  const winStart = parseDay(DATA.windows[String(state.range)]);
  return { start: Math.min(start, winStart), end, ticks };
}

function inWindow(e, range = state.range) {
  const d = parseDay(e.day);
  return !!d && d >= parseDay(DATA.windows[String(range)]) && d <= parseDay(DATA.snapshot);
}
function windowBase(range = state.range) {
  const all = (DATA.events || [])
    .filter((e) => inWindow(e, range))
    .sort((a, b) => (a.day !== b.day ? (a.day < b.day ? -1 : 1) : a.id - b.id));
  const hasCore = all.some((e) => e.lane === "company" || e.lane === "deploy");
  if (hasCore) return all;
  return all.filter((e) => e.info_kind !== "job_posting");
}
function windowEvents() {
  if (state.scope !== "featured") return windowBase();
  const f = featuredIds(state.range);
  const picked = windowBase().filter((e) => f.has(e.id));
  return picked.length ? picked : windowBase();
}

/* ---------- 精选节点（scope="featured" 的可见集）----------
   价值优先单一算法：公司动作全保留；客户故事按信号/证据取前 10；人物前 5；
   方法类非招聘前 3；招聘类前 2。不足 8 按分回填，超过 24 裁最低分非保护项；
   本窗三卡证据链 id 与默认节点是保护项（不受桶上限与裁剪约束）。
   featuredIds 惰性构建（首次 rebuild 早于任何显式预热点），缓存只增不删。 */
const featuredCache = new Map(); // range -> { list, ids:Set }；DATA 单次加载内不变
function eventScore(e) {
  const published = e.date_kind === "published" ? 1 : 0;
  if (e.lane === "company") return 100 + 10 * published;
  if (e.lane === "deploy") {
    let s = 70;
    if (e.signal === "high") s += 30;
    else if (e.signal === "mid") s += 18;
    if (e.case_href) s += 12;
    if (e.outcome || e.kpi) s += 8;
    return s + 6 * published;
  }
  if (e.lane === "people") {
    let s = 50;
    if (e.signal === "high") s += 25;
    if (e.practitioner || e.why) s += 15;
    return s + 5 * published;
  }
  if (e.info_kind === "job_posting" || e.info_kind === "hiring_census") return 10 + 4 * published;
  let s = 28;
  if (e.signal === "high") s += 20;
  return s + 4 * published;
}
function featuredEvents(range) {
  const base = windowBase(range);
  const inBase = new Set(base.map((e) => e.id));
  // 保护集：本窗三卡证据链 + 本窗默认节点 + 全局默认（仅并 base 内存在者）
  const keep = new Set();
  const changes = (DATA.changes_by_range || {})[String(range)] || DATA.changes || [];
  changes.forEach((c) =>
    (c.chain || []).forEach((n) => {
      const id = Number(n.id);
      if (inBase.has(id)) keep.add(id);
    })
  );
  [(DATA.default_by_range || {})[String(range)], DATA.default_id].forEach((v) => {
    const id = Number(v);
    if (id && inBase.has(id)) keep.add(id);
  });

  const isHiring = (e) => e.info_kind === "job_posting" || e.info_kind === "hiring_census";
  const scored = base.map((e) => ({ e, s: eventScore(e) }));
  const cmp = (a, b) => b.s - a.s || (a.e.day < b.e.day ? 1 : a.e.day > b.e.day ? -1 : b.e.id - a.e.id);
  const buckets = { deploy: [], people: [], method: [], hire: [] };
  scored.forEach((it) => {
    if (it.e.lane === "company") return; // 公司动作全保留，不进桶
    const key = isHiring(it.e) ? "hire" : it.e.lane;
    (buckets[key] || buckets.method).push(it);
  });
  Object.values(buckets).forEach((arr) => arr.sort(cmp));
  const caps = { deploy: 10, people: 5, method: 3, hire: 2 };

  const picked = new Map();
  scored.forEach(({ e }) => {
    if (e.lane === "company") picked.set(e.id, e);
  });
  Object.keys(buckets).forEach((key) => buckets[key].slice(0, caps[key]).forEach(({ e }) => picked.set(e.id, e)));
  keep.forEach((id) => picked.set(id, byId[id]));

  // floor：不足 8 时按分回填 base 剩余（7 天窗几乎只有招聘，否则画布空）
  if (picked.size < 8) {
    scored.sort(cmp);
    for (const { e } of scored) {
      if (picked.size >= 8) break;
      picked.set(e.id, e);
    }
  }
  // cap：超过 24 时按分升序裁非 company 非保护项至 24
  if (picked.size > 24) {
    const removable = [...picked.values()]
      .filter((e) => e.lane !== "company" && !keep.has(e.id))
      .sort((a, b) => eventScore(a) - eventScore(b) || (a.day < b.day ? -1 : a.day > b.day ? 1 : a.id - b.id));
    let excess = picked.size - 24;
    for (const e of removable) {
      if (excess <= 0) break;
      picked.delete(e.id);
      excess -= 1;
    }
  }
  const list = [...picked.values()].sort((a, b) => (a.day !== b.day ? (a.day < b.day ? -1 : 1) : a.id - b.id));
  const entry = { list, ids: new Set(list.map((e) => e.id)) };
  featuredCache.set(range, entry);
  return entry;
}
function featuredIds(range = state.range) {
  let c = featuredCache.get(range);
  if (!c) c = featuredEvents(range);
  return c.ids;
}
function featuredCount(range = state.range) {
  let c = featuredCache.get(range);
  if (!c) c = featuredEvents(range);
  return c.list.length;
}
/* 证据链点击：把链上 id 并入该窗精选缓存（链节点必须可见），返回是否新增 */
function ensureFeatured(range, ids) {
  const c = featuredCache.get(range) || featuredEvents(range);
  let added = false;
  ids.forEach((id) => {
    if (!c.ids.has(id) && byId[id] && inWindow(byId[id], range)) {
      c.ids.add(id);
      c.list.push(byId[id]);
      added = true;
    }
  });
  if (added) c.list.sort((a, b) => (a.day !== b.day ? (a.day < b.day ? -1 : 1) : a.id - b.id));
  return added;
}
/* 变化卡按当前窗取数：优先 changes_by_range，缺则回退 30 天的 changes */
function currentChanges() {
  return (DATA.changes_by_range || {})[String(state.range)] || DATA.changes || [];
}
/* 链节点在某窗是否可见：inWindow 之外还要过 windowBase 的 job_posting 剔除规则 */
const coreAtCache = {};
function coreAt(r) {
  if (!(r in coreAtCache)) {
    const by = ((DATA.window_counts || {})[String(r)] || {}).by_lane || {};
    coreAtCache[r] = !!(by.company || by.deploy);
  }
  return coreAtCache[r];
}
function visibleAt(id, r) {
  const e = byId[id];
  return !!e && inWindow(e, r) && (coreAt(r) || e.info_kind !== "job_posting");
}

/* Organisations own company/deploy events; people & method group by host,
   mirroring worldview.build_entities so case-layer vendor quirks don't
   attach a method article to a company base. */
function baseKeyOf(e) {
  if (e.lane === "company" || e.lane === "deploy") return e.entity_key || e.host;
  return e.host || e.entity_key;
}
function baseNameOf(e) {
  if (e.lane === "company" || e.lane === "deploy") return e.entity_name || e.vendor || e.kicker || e.host;
  return e.entity_name || e.kicker || e.host;
}

/* ---------- WebGL / fallback ---------- */
function webglOK() {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch (_e) {
    return false;
  }
}

function showFallback(reason) {
  state.scope = "all"; // 平面列表恒全量，保持「数据与 3D 沙盘完全一致」
  root.classList.add("w3-flat");
  fallback.hidden = false;
  const why = document.getElementById("w3-fallback-why");
  if (why && reason) why.textContent = reason;
  const list = document.getElementById("w3-fallback-list");
  if (list) {
    list.innerHTML = windowEvents()
      .map(
        (e) =>
          `<li><span class="w3-fb-day">${esc(monthDay(e.day))}</span><span class="w3-fb-lane" data-lane="${esc(e.lane)}">${esc(laneLabel(e.lane))}</span><a href="${esc(e.href || "/动态/" + e.id)}">${esc(e.title)}</a><small>${esc(e.host)}</small></li>`
      )
      .join("");
  }
}

function syncRooms() {
  const q = "?窗=" + state.range;
  document.querySelectorAll("[data-room]").forEach((a) => {
    const key = a.getAttribute("data-room");
    if (key && key !== "平面" && key !== "方法") a.setAttribute("href", "/" + key + q);
  });
}
syncRooms();

/* ---------- 首屏概览层：按当前窗重绘统计 / 变化卡 / 注脚 ---------- */
function dayZh(day) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(day || "").trim());
  return m ? `${Number(m[1])}年${Number(m[2])}月${Number(m[3])}日` : String(day || "");
}
function ovStatsHtml(range) {
  const wc = (DATA.window_counts || {})[String(range)] || {};
  const by = wc.by_lane || {};
  const items = (DATA.lanes || []).map(
    (l) => `<div class="w3-ov-stat" data-lane="${esc(l.id)}"><b>${Number(by[l.id] || 0)}</b><span>${esc(l.zh)}</span></div>`
  );
  items.push(`<div class="w3-ov-stat w3-ov-total"><b>${Number(wc.total || 0)}</b><span>近 ${range} 天全部</span></div>`);
  return items.join("");
}
function ovChangesHtml() {
  return currentChanges()
    .map((c, i) => {
      const chain = (c.chain || []).filter((n) => byId[Number(n.id)]);
      const disabled = !chain.length;
      const meta = disabled ? "本窗暂无对应信号" : `${c.n} 条信号 · 证据链 ${chain.length} 步`;
      const attrs = disabled ? ' aria-disabled="true"' : ` data-chain="${i}"`;
      return `<button type="button" class="w3-ov-card-item"${attrs}><b class="w3-ov-c-num">${esc(c.num)}</b><span class="w3-ov-c-body"><strong>${esc(c.title)}</strong><small>${esc(c.body)}</small><span class="w3-ov-c-meta">${esc(meta)}</span></span><span class="w3-ov-c-go">看证据链 →</span></button>`;
    })
    .join("");
}
function renderOverview() {
  if (ovStatsEl) ovStatsEl.innerHTML = ovStatsHtml(state.range);
  if (ovChangesEl) ovChangesEl.innerHTML = ovChangesHtml();
  if (ovNoteEl) {
    const fCount = featuredCount(state.range);
    const aCount = windowBase().length;
    const allBtn = fCount < aCount ? ' <button type="button" data-ov-all>查看全部</button>' : "";
    ovNoteEl.innerHTML = `资料截止 ${esc(dayZh(DATA.snapshot))} · 精选 ${fCount} / 全部 ${aCount} 条${allBtn}`;
    const allChip = document.querySelector('.w3-scope [data-scope="all"]');
    if (allChip) allChip.hidden = fCount >= aCount;
  }
}
function enterSandbox() {
  root.classList.add("w3-play"); // 幂等：收概览、亮范围 chips
}

/* ---------- 解读报告（fallback 路径）：手机/WebGL 不可用时也要有，
   报告条目用真实链接跳转 /动态/<id>，不依赖 3D 场景 ---------- */
const fallbackReportCache = new Map();
function fbMdLite(t) {
  return esc(String(t || ""))
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, txt, href) => {
      const mId = String(href).match(/\/(?:动态|world_event)\/(\d+)/);
      const u = mId ? "/动态/" + mId[1] : href;
      return `<a href="${u}">${txt}</a>`;
    })
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .split(/\n{2,}/)
    .map((p) => `<p>${p.replace(/\n/g, "<br/>")}</p>`)
    .join("");
}
function fbOpenReport(range) {
  let overlay = document.getElementById("w3-report-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "w3-report-overlay";
    overlay.innerHTML = `
<div class="w3-rp" role="dialog" aria-label="解读报告">
  <header class="w3-rp-h">
    <h2>解读报告</h2>
    <div class="w3-range" role="radiogroup" aria-label="报告时间窗">
      <button type="button" data-rp-range="7">7 天</button>
      <button type="button" data-rp-range="30" class="on">30 天</button>
      <button type="button" data-rp-range="90">90 天</button>
    </div>
    <button type="button" class="w3-rp-x" data-rp-close aria-label="关闭">×</button>
  </header>
  <div class="w3-rp-body" id="w3-rp-body"></div>
</div>`;
    document.body.appendChild(overlay);
    overlay.addEventListener("click", (ev) => {
      const rbtn = ev.target.closest("[data-rp-range]");
      if (rbtn) { fbOpenReport(Number(rbtn.dataset.rpRange)); return; }
      if (ev.target.closest("[data-rp-close]") || ev.target === overlay) overlay.hidden = true;
    });
  }
  overlay.hidden = false;
  overlay.querySelectorAll("[data-rp-range]").forEach((b) => {
    const on = Number(b.dataset.rpRange) === Number(range);
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
  });
  const bodyEl = overlay.querySelector("#w3-rp-body");
  if (fallbackReportCache.has(range)) {
    bodyEl.innerHTML = `<div class="w3-ai-text">${fbMdLite(fallbackReportCache.get(range).text)}</div>`;
    return;
  }
  bodyEl.innerHTML = '<p class="w3-ai-loading">✦ 生成中…</p>';
  fetch(`/api/ai-report?range=${range}`)
    .then((r) => r.json())
    .then((rep) => {
      if (!rep || rep.enabled === false) throw new Error(rep.error || "报告不可用");
      fallbackReportCache.set(range, rep);
      bodyEl.innerHTML = `<div class="w3-ai-text">${fbMdLite(rep.text)}</div>`;
    })
    .catch((err) => {
      bodyEl.innerHTML = `<p class="w3-ai-err">报告不可用：${esc(String(err.message || err))}</p>`;
    });
}
function ensureReportBtnFallback() {
  if (document.getElementById("w3-report-fab")) return;
  const fab = document.createElement("button");
  fab.id = "w3-report-fab";
  fab.type = "button";
  fab.setAttribute("aria-label", "解读报告");
  fab.innerHTML = '<span class="w3-fab-ico">✦</span><span class="w3-fab-t">解读报告</span>';
  document.body.appendChild(fab);
  fab.addEventListener("click", () => fbOpenReport(rangeFromUrl || 30));
}

/* 手机也直接渲染 3D（fitDistance 按 aspect 自适应取景）；WebGL 不可用或
   初始化失败时自动切文字列表；?flat=1 可手动强制列表视图 */
if (!webglOK()) {
  showFallback("此设备不支持 WebGL，已切换到平面列表。数据与 3D 沙盘完全一致。");
  ensureReportBtnFallback();
} else if (params.get("flat") === "1" || params.get("视图") === "列表") {
  showFallback("已按你的选择切换到平面列表。");
  ensureReportBtnFallback();
} else {
  try {
    boot();
  } catch (err) {
    console.error(err);
    showFallback("3D 初始化失败，已切换到平面列表。数据与 3D 沙盘完全一致。");
    ensureReportBtnFallback();
  }
}

/* =====================================================================
   Scene
   ===================================================================== */
function boot() {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = false;

  const labelRenderer = new CSS2DRenderer({ element: labelsHost });
  const groundRenderer = new CSS3DRenderer({ element: labels3dHost });

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(BG);
  scene.fog = new THREE.Fog(BG, 150, 360);

  const camera = new THREE.PerspectiveCamera(36, 1, 0.5, 800);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.maxPolarAngle = Math.PI * 0.47;
  controls.minPolarAngle = Math.PI * 0.12;
  controls.minDistance = 48;
  /* 上限随取景走：桌面 fit≈155（320 上限够用），手机竖屏 fit≈754，320 会把相机钳回近景 */
  controls.maxDistance = 320;
  controls.enablePan = true;
  controls.screenSpacePanning = false;
  controls.target.set(0, 0, -4);

  scene.add(new THREE.HemisphereLight(0x7fa0b8, 0x04101a, 0.95));
  const sun = new THREE.DirectionalLight(0xffffff, 0.85);
  sun.position.set(60, 90, 70);
  scene.add(sun);
  const rim = new THREE.DirectionalLight(0x3fc0c0, 0.25);
  rim.position.set(-80, 30, -60);
  scene.add(rim);

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(900, 900),
    new THREE.MeshStandardMaterial({ color: 0x05111b, roughness: 1, metalness: 0 })
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.05;
  scene.add(ground);

  const board = new THREE.Group();
  const eventsG = new THREE.Group();
  const basesG = new THREE.Group();
  const linksG = new THREE.Group();
  scene.add(board, eventsG, basesG, linksG);

  const nodes = new Map(); // event id -> record
  const pickables = [];
  const animations = [];
  let disposables = [];

  const track = (obj) => {
    disposables.push(obj);
    return obj;
  };
  function clearGroup(group) {
    while (group.children.length) group.remove(group.children[0]);
  }
  function disposeAll() {
    disposables.forEach((o) => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose());
    });
    disposables = [];
  }

  /* wrapper is positioned by CSS2DRenderer; the inner node carries the look
     and can be lifted (translateY) by the screen-space de-conflict pass. */
  function label(html, cls) {
    const wrap = document.createElement("div");
    wrap.className = "w3-lblw";
    const inner = document.createElement("div");
    inner.className = "w3-lbl " + (cls || "");
    inner.innerHTML = html;
    const stem = document.createElement("i");
    stem.className = "w3-stem";
    wrap.appendChild(stem);
    wrap.appendChild(inner);
    const obj = new CSS2DObject(wrap);
    obj.userData.inner = inner;
    obj.userData.stem = stem;
    return obj;
  }
  const managed = []; // labels that take part in de-conflict: {obj, prio, w, h, dy}

  /* Text that belongs to the world (lane names, dates, the snapshot wall) is
     painted onto surfaces with CSS3D so it sits in perspective like the
     geometry does; only event/base tags stay as readable billboards. */
  function groundText(html, cls, opts = {}) {
    const el = document.createElement("div");
    el.className = "w3-g " + (cls || "");
    el.innerHTML = html;
    if (opts.width) el.style.width = opts.width + "px";
    const obj = new CSS3DObject(el);
    obj.scale.setScalar(GT);
    obj.rotation.x = -Math.PI / 2; // lie flat on the ground, top edge toward -z
    return obj;
  }

  /* ---------- board: lanes, ticks, snapshot wall, base row ---------- */
  function buildBoard(axis, W) {
    clearGroup(board);
    const half = W / 2;
    // inset so first/last-day glyphs don't sit on the board edge under the lane names
    const inset = W * 0.045;
    const xOf = (t) => -half + inset + ((t - axis.start) / Math.max(axis.end - axis.start, DAY)) * (W - 2 * inset);

    LANES.forEach((lane) => {
      const z = laneZ(lane);
      const c = LANE_COLOR[lane];
      const strip = track(
        new THREE.Mesh(
          new THREE.PlaneGeometry(W, LANE_HALF * 2),
          new THREE.MeshBasicMaterial({ color: c.lo, transparent: true, opacity: 0.2, depthWrite: false })
        )
      );
      strip.rotation.x = -Math.PI / 2;
      strip.position.set(0, 0.02, z);
      board.add(strip);

      const edge = new Float32Array([-half, 0.04, z - LANE_HALF, half, 0.04, z - LANE_HALF, -half, 0.04, z + LANE_HALF, half, 0.04, z + LANE_HALF]);
      const eg = new THREE.BufferGeometry();
      eg.setAttribute("position", new THREE.BufferAttribute(edge, 3));
      board.add(track(new THREE.LineSegments(eg, new THREE.LineBasicMaterial({ color: c.hi, transparent: true, opacity: 0.42 }))));

      const LW = LANE_TEXT_W / GT; // element px width so the text block is LANE_TEXT_W units wide
      const lbl = groundText(`<b>${esc(laneLabel(lane))}</b>`, "w3-g-lane", { width: LW });
      lbl.element.style.setProperty("--c", c.hi);
      lbl.position.set(-half - 2 - LANE_TEXT_W / 2, 0.06, z);
      board.add(lbl);
    });

    // tick lines across all lanes + base row
    const tickPts = [];
    const seenTick = new Set();
    axis.ticks.forEach((tk) => {
      if (seenTick.has(tk.t)) return;
      seenTick.add(tk.t);
      const x = xOf(tk.t);
      tickPts.push(x, 0.03, BASE_Z - 4, x, 0.03, FRONT_Z);
      const last = tk.t === axis.end;
      // the last tick doubles as the snapshot marker, like the 2D axis does
      const tl = groundText(esc(tk.label), last ? "w3-g-tick w3-g-tick-end" : "w3-g-tick");
      tl.position.set(x, 0.06, FRONT_Z + (last ? 4.2 : 3.2));
      board.add(tl);
    });
    const tg = new THREE.BufferGeometry();
    tg.setAttribute("position", new THREE.BufferAttribute(new Float32Array(tickPts), 3));
    board.add(track(new THREE.LineSegments(tg, new THREE.LineBasicMaterial({ color: GRID, transparent: true, opacity: 0.9 }))));

    // base row
    const bg = new THREE.BufferGeometry();
    bg.setAttribute("position", new THREE.BufferAttribute(new Float32Array([-half, 0.04, BASE_Z, half, 0.04, BASE_Z]), 3));
    board.add(track(new THREE.LineSegments(bg, new THREE.LineDashedMaterial({ color: ACCENT, dashSize: 1.6, gapSize: 1.1, transparent: true, opacity: 0.45 }))));
    board.children[board.children.length - 1].computeLineDistances();
    const bl = groundText(`<b>大本营</b><small>公司</small>`, "w3-g-lane", { width: LANE_TEXT_W / GT });
    bl.element.style.setProperty("--c", ACCENT);
    bl.position.set(-half - 2 - LANE_TEXT_W / 2, 0.06, BASE_Z);
    board.add(bl);

    // snapshot wall
    const depth = FRONT_Z - (BASE_Z - 6);
    const wall = track(
      new THREE.Mesh(
        new THREE.PlaneGeometry(depth, 11),
        new THREE.MeshBasicMaterial({ color: ACCENT, transparent: true, opacity: 0.07, side: THREE.DoubleSide, depthWrite: false })
      )
    );
    wall.rotation.y = -Math.PI / 2;
    wall.position.set(half + 0.6, 5.5, (FRONT_Z + BASE_Z - 6) / 2);
    board.add(wall);
    const wg = new THREE.BufferGeometry();
    wg.setAttribute("position", new THREE.BufferAttribute(new Float32Array([half + 0.6, 0.05, BASE_Z - 6, half + 0.6, 0.05, FRONT_Z, half + 0.6, 11, BASE_Z - 6, half + 0.6, 11, FRONT_Z]), 3));
    board.add(track(new THREE.LineSegments(wg, new THREE.LineBasicMaterial({ color: ACCENT, transparent: true, opacity: 0.55 }))));
    return xOf;
  }

  /* ---------- events ---------- */
  function buildEvents(list, xOf) {
    clearGroup(eventsG);
    nodes.clear();
    pickables.length = 0;
    managed.length = 0;

    // same day + lane → spread across the lane depth, deterministic
    const groups = new Map();
    list.forEach((e) => {
      const k = e.day + "|" + e.lane;
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(e);
    });

    /* One glyph per lane, following the forward-deployed metaphor:
       company  → tower (organisation moves are landmarks)
       deploy   → landing point: a ring on the ground where the line from the
                  base touches down, plus a thin beam whose height is signal
       people   → beacon: a lit sphere floating over the lane on a tether
       method   → rail: a flat plate laid on the ground */
    const towerGeo = track({ geometry: new THREE.BoxGeometry(1.3, 1, 1.3).translate(0, 0.5, 0) }).geometry;
    const towerEdge = track({ geometry: new THREE.EdgesGeometry(towerGeo) }).geometry;
    const capGeo = track({ geometry: new THREE.SphereGeometry(0.5, 18, 14) }).geometry;
    const beamGeo = track({ geometry: new THREE.CylinderGeometry(0.3, 0.3, 1, 12).translate(0, 0.5, 0) }).geometry;
    const tipGeo = track({ geometry: new THREE.SphereGeometry(0.46, 14, 10) }).geometry;
    const ringGeo = track({ geometry: new THREE.RingGeometry(0.95, 1.5, 40) }).geometry;
    const dotGeo = track({ geometry: new THREE.CircleGeometry(0.42, 20) }).geometry;
    const beaconGeo = track({ geometry: new THREE.SphereGeometry(0.8, 20, 16) }).geometry;
    const railGeos = {};
    const railEdges = {};
    const hitGeo = track({ geometry: new THREE.SphereGeometry(2.8, 10, 8) }).geometry;
    const hitMat = track({ material: new THREE.MeshBasicMaterial({ visible: false }) }).material;
    ["low", "mid", "high"].forEach((sig) => {
      const L = { low: 2.8, mid: 3.6, high: 4.4 }[sig];
      railGeos[sig] = track({ geometry: new THREE.BoxGeometry(L, 0.4, 2.0).translate(0, 0.2, 0) }).geometry;
      railEdges[sig] = track({ geometry: new THREE.EdgesGeometry(railGeos[sig]) }).geometry;
    });

    const glowMat = (c, glow, modified) =>
      track({
        material: new THREE.MeshStandardMaterial({
          color: c.lo,
          emissive: new THREE.Color(c.hi),
          emissiveIntensity: glow,
          roughness: 0.45,
          metalness: 0.1,
          transparent: modified,
          opacity: modified ? 0.3 : 1,
        }),
      }).material;
    const flatMat = (c, opacity) =>
      track({ material: new THREE.MeshBasicMaterial({ color: c.hi, transparent: true, opacity, side: THREE.DoubleSide, depthWrite: false }) }).material;
    const lineMat = (c, opacity, dashed) =>
      track({
        material: dashed
          ? new THREE.LineDashedMaterial({ color: c.hi, dashSize: 0.5, gapSize: 0.35, transparent: true, opacity })
          : new THREE.LineBasicMaterial({ color: c.hi, transparent: true, opacity }),
      }).material;

    list.forEach((e, index) => {
      const c = LANE_COLOR[e.lane] || LANE_COLOR.company;
      const grp = groups.get(e.day + "|" + e.lane);
      const gi = grp.indexOf(e);
      const spread = Math.min(3.6, (LANE_HALF * 2 - 1.8) / Math.max(grp.length, 1));
      const z = laneZ(e.lane) + (gi - (grp.length - 1) / 2) * spread;
      const x = xOf(parseDay(e.day));
      const h = SIGNAL_H[e.signal] || SIGNAL_H.mid;
      const glow = SIGNAL_GLOW[e.signal] || 0.4;
      const modified = e.date_kind === "modified";
      // beams and beacons are "lights": brighter than solid towers/rails
      const lit = e.lane === "deploy" || e.lane === "people";
      const mat = glowMat(c, lit ? Math.min(1, glow + 0.3) : glow, modified);
      const n = { e, x, z, h, mat, glow: mat.emissiveIntensity, modified, extras: [], lineEnd: null, linkY: 0, top: 0, main: null, hot: null, hotSel: 1.5, hotHov: 1.2, enter: null };

      if (e.lane === "company") {
        const tower = new THREE.Mesh(towerGeo, mat);
        tower.position.set(x, 0, z);
        const edges = new THREE.LineSegments(towerEdge, lineMat(c, modified ? 0.9 : 0.55));
        edges.position.copy(tower.position);
        const cap = new THREE.Mesh(capGeo, flatMat(c, 1));
        cap.position.set(x, h + 0.55, z);
        eventsG.add(tower, edges, cap);
        n.main = tower;
        n.hot = cap;
        n.extras.push({ obj: edges, base: modified ? 0.9 : 0.55 }, { obj: cap, base: 1 });
        n.lineEnd = new THREE.Vector3(x, h + 0.4, z);
        n.linkY = h + 0.8;
        n.top = h + 1.0;
        n.enter = (k) => {
          tower.scale.y = Math.max(0.001, k * h);
          edges.scale.y = tower.scale.y;
          cap.visible = k > 0.85;
        };
        n.enter(REDUCED ? 1 : 0);
      } else if (e.lane === "deploy") {
        const ring = new THREE.Mesh(ringGeo, flatMat(c, 0.85));
        ring.rotation.x = -Math.PI / 2;
        ring.position.set(x, 0.05, z);
        const beam = new THREE.Mesh(beamGeo, mat);
        beam.position.set(x, 0, z);
        const tip = new THREE.Mesh(tipGeo, flatMat(c, 1));
        tip.position.set(x, h, z);
        eventsG.add(ring, beam, tip);
        n.main = beam;
        n.hot = ring;
        n.hotSel = 1.45;
        n.hotHov = 1.15;
        n.extras.push({ obj: ring, base: 0.85 }, { obj: tip, base: 1 });
        pickables.push(ring, tip);
        n.lineEnd = new THREE.Vector3(x, 0.3, z); // the base line lands here
        n.linkY = h + 0.5;
        n.top = h + 0.7;
        n.enter = (k) => {
          beam.scale.y = Math.max(0.001, k * h);
          tip.position.y = beam.scale.y;
          ring.scale.setScalar(0.2 + 0.8 * k);
          ring.material.opacity = 0.85 * k;
        };
        n.enter(REDUCED ? 1 : 0);
      } else if (e.lane === "people") {
        const y = h + 1.6;
        const beacon = new THREE.Mesh(beaconGeo, mat);
        beacon.position.set(x, y, z);
        const halo = new THREE.Sprite(
          track({ material: new THREE.SpriteMaterial({ map: haloTexture(), color: c.hi, transparent: true, opacity: 0.75, blending: THREE.AdditiveBlending, depthWrite: false }) }).material
        );
        halo.scale.setScalar(7);
        halo.position.copy(beacon.position);
        const tetherGeo = track({ geometry: new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x, 0.05, z), new THREE.Vector3(x, y - 0.8, z)]) }).geometry;
        const tether = new THREE.Line(tetherGeo, lineMat(c, 0.55, true));
        tether.computeLineDistances();
        const dot = new THREE.Mesh(dotGeo, flatMat(c, 0.7));
        dot.rotation.x = -Math.PI / 2;
        dot.position.set(x, 0.05, z);
        eventsG.add(beacon, halo, tether, dot);
        n.main = beacon;
        n.hot = beacon;
        n.hotSel = 1.35;
        n.hotHov = 1.15;
        n.extras.push({ obj: halo, base: 0.75 }, { obj: tether, base: 0.55 }, { obj: dot, base: 0.7 });
        n.lineEnd = beacon.position.clone();
        n.linkY = y;
        n.top = y + 1.0;
        n.enter = (k) => {
          beacon.position.y = y + (1 - k) * 7;
          halo.position.y = beacon.position.y;
          halo.material.opacity = 0.75 * k;
          tether.visible = k > 0.9;
        };
        n.enter(REDUCED ? 1 : 0);
      } else {
        const rail = new THREE.Mesh(railGeos[e.signal] || railGeos.mid, mat);
        rail.position.set(x, 0, z);
        const edges = new THREE.LineSegments(railEdges[e.signal] || railEdges.mid, lineMat(c, 0.7));
        edges.position.copy(rail.position);
        eventsG.add(rail, edges);
        n.main = rail;
        n.hot = rail;
        n.hotSel = 1.18;
        n.hotHov = 1.08;
        n.extras.push({ obj: edges, base: 0.7 });
        n.lineEnd = new THREE.Vector3(x, 0.5, z);
        n.linkY = 0.7;
        n.top = 0.9;
        n.enter = (k) => {
          rail.scale.x = Math.max(0.001, k);
          edges.scale.x = rail.scale.x;
        };
        n.enter(REDUCED ? 1 : 0);
      }
      n.main.userData.id = e.id;
      n.hot.userData.id = e.id;
      pickables.push(n.main, n.hot);
      const hit = new THREE.Mesh(hitGeo, hitMat);
      hit.position.set(x, Math.max(1.4, Math.min(n.top * 0.45, 3.2)), z);
      hit.userData.id = e.id;
      eventsG.add(hit);
      pickables.push(hit);
      n.hotBase = new THREE.Vector3(1, 1, 1);

      const lbl = label(
        `<span class="w3-lbl-day">${esc(monthDay(e.day))}</span><b>${esc(e.title_short || e.title)}</b>`,
        "w3-lbl-ev"
      );
      lbl.element.style.setProperty("--c", c.hi);
      lbl.element.dataset.id = String(e.id);
      lbl.element.style.pointerEvents = "auto";
      lbl.center.set(0.5, 1);
      lbl.position.set(x, n.top, z);
      lbl.element.classList.toggle("w3-lbl-hidden", !REDUCED);
      eventsG.add(lbl);
      managed.push({ obj: lbl, id: e.id, prio: { high: 2, mid: 1, low: 0 }[e.signal] ?? 1, w: 0, h: 0, dy: 0 });
      n.lbl = lbl;
      nodes.set(e.id, n);

      if (!REDUCED) {
        animations.push({
          t0: performance.now() + 120 + index * 40,
          dur: 560,
          tick: (k) => {
            n.enter(easeOutCubic(k));
            if (k >= 0.85) lbl.element.classList.remove("w3-lbl-hidden");
          },
        });
      }
    });

    labelsDirty = true;
  }

  let _halo = null;
  function haloTexture() {
    if (_halo) return _halo;
    const cv = document.createElement("canvas");
    cv.width = cv.height = 64;
    const g = cv.getContext("2d");
    const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grad.addColorStop(0, "rgba(255,255,255,0.9)");
    grad.addColorStop(0.35, "rgba(255,255,255,0.35)");
    grad.addColorStop(1, "rgba(255,255,255,0)");
    g.fillStyle = grad;
    g.fillRect(0, 0, 64, 64);
    _halo = new THREE.CanvasTexture(cv);
    return _halo;
  }

  /* ---------- screen-space label de-conflict ----------
     Labels are projected each frame the camera moves; overlapping boxes are
     lifted (higher-priority labels stay put), and anything lifted beyond
     LABEL_MAX_LIFT is hidden. Deterministic, ~n² with n ≤ 60. */
  let labelsDirty = true;
  const _p = new THREE.Vector3();
  const _prevCam = new THREE.Matrix4();
  function deconflictLabels() {
    const W = stage.clientWidth;
    const H = stage.clientHeight;
    if (!W || !H) return;
    const items = [];
    const ref = controls.getDistance(); // tags at the orbit target render at scale 1
    managed.forEach((m) => {
      const el = m.obj.element;
      if (el.style.display === "none") return;
      const inner = m.obj.userData.inner;
      // 90-day view: only strong signals keep their title; the rest collapse
      // to a date chip until hovered/selected (measured size changes with it)
      const sel = m.id === state.selected;
      const hov = m.id === state.hovered;
      const min = m.id != null && state.range === 90 && m.prio < 2 && !sel && !hov;
      if (el.classList.contains("min") !== min) {
        el.classList.toggle("min", min);
        m.w = 0;
      }
      if (!m.w) {
        m.w = inner.offsetWidth;
        m.h = inner.offsetHeight;
        if (!m.w) return;
      }
      _p.setFromMatrixPosition(m.obj.matrixWorld);
      const dist = _p.distanceTo(camera.position);
      _p.project(camera);
      const sx = (_p.x + 1) * 0.5 * W;
      const sy = (1 - _p.y) * 0.5 * H;
      // mild perspective on the tags so far ones recede with the geometry
      const s = THREE.MathUtils.clamp(Math.pow(ref / Math.max(dist, 1), 0.55), 0.72, 1.12);
      items.push({ m, sx, sy, s, prio: sel ? 9 : hov ? 8 : m.prio, depth: _p.z });
    });
    // higher priority first; among equals the nearer (lower on screen) first
    items.sort((a, b) => b.prio - a.prio || b.sy - a.sy);
    const placed = [];
    const collide = (x0, x1, y0, y1) => placed.find((p) => x0 < p.x1 + 4 && x1 > p.x0 - 4 && y0 < p.y1 + 2 && y1 > p.y0 - 2);
    items.forEach((it) => {
      const { m, s } = it;
      const w = m.w * s;
      const h = m.h * s;
      // try in place, then dodge sideways, then lift one row and repeat
      const ox = w / 2 + 10;
      let dy = 0;
      let dx = 0;
      let ok = false;
      for (let guard = 0; guard < 10 && !ok; guard += 1) {
        const y1 = it.sy - dy;
        const y0 = y1 - h;
        let blocker = null;
        for (const cand of [0, ox, -ox]) {
          const x0 = it.sx + cand - w / 2;
          const x1 = it.sx + cand + w / 2;
          const hit = collide(x0, x1, y0, y1);
          if (!hit) {
            dx = cand;
            ok = true;
            break;
          }
          if (cand === 0) blocker = hit;
        }
        if (!ok) dy += y1 - blocker.y0 + 2;
      }
      const hide = !ok || dy > LABEL_MAX_LIFT;
      m.dy = hide ? 0 : dy;
      m.dx = hide ? 0 : dx;
      m.obj.element.classList.toggle("w3-lbl-clash", hide);
      const { inner, stem } = m.obj.userData;
      inner.style.transform = `translate(${m.dx.toFixed(1)}px, ${-m.dy.toFixed(1)}px) scale(${s.toFixed(3)})`;
      // stem runs from the anchor (pillar cap) to the tag's bottom centre
      const len = Math.hypot(m.dx, m.dy) + 12 * s;
      const ang = Math.atan2(m.dx, m.dy + 12 * s);
      stem.style.height = `${len.toFixed(1)}px`;
      stem.style.transform = `rotate(${ang.toFixed(4)}rad)`;
      if (!hide) placed.push({ x0: it.sx + dx - w / 2, x1: it.sx + dx + w / 2, y0: it.sy - dy - h, y1: it.sy - dy });
    });
  }

  /* ---------- bases (organisations) + forward lines ---------- */
  function buildBases(list, xOf, W) {
    clearGroup(basesG);
    const half = W / 2;
    const groups = new Map();
    list.forEach((e) => {
      const key = baseKeyOf(e);
      if (!key) return;
      if (!groups.has(key)) groups.set(key, { key, name: baseNameOf(e), events: [] });
      groups.get(key).events.push(e);
    });
    // Only organisations, or anyone with 2+ dated items, gets a base.
    const bases = [...groups.values()].filter((g) => g.events.some((e) => e.lane === "company" || e.lane === "deploy") || g.events.length >= 2);
    bases.forEach((g) => {
      const xs = g.events.map((e) => nodes.get(e.id)?.x ?? xOf(parseDay(e.day)));
      g.x = xs.reduce((a, b) => a + b, 0) / xs.length;
    });
    bases.sort((a, b) => a.x - b.x || (a.key < b.key ? -1 : 1));
    // deterministic 1-D relax
    const GAP = 7.5;
    for (let i = 1; i < bases.length; i += 1) {
      if (bases[i].x - bases[i - 1].x < GAP) bases[i].x = bases[i - 1].x + GAP;
    }
    const overflow = bases.length ? bases[bases.length - 1].x - (half - 3) : 0;
    if (overflow > 0) bases.forEach((b) => (b.x -= overflow));
    for (let i = bases.length - 2; i >= 0; i -= 1) {
      if (bases[i + 1].x - bases[i].x < GAP) bases[i].x = bases[i + 1].x - GAP;
    }

    const faceMat = track({ material: new THREE.MeshStandardMaterial({ color: BASE_FACE, roughness: 0.6, metalness: 0.2 }) }).material;
    const edgeMat = track({ material: new THREE.LineBasicMaterial({ color: ACCENT, transparent: true, opacity: 0.85 }) }).material;

    bases.forEach((g) => {
      const hb = 2.2 + 1.5 * g.events.length;
      const geo = track({ geometry: new THREE.BoxGeometry(3.4, hb, 3.4) }).geometry;
      const box = new THREE.Mesh(geo, faceMat);
      box.position.set(g.x, hb / 2, BASE_Z);
      basesG.add(box);
      const edges = new THREE.LineSegments(track({ geometry: new THREE.EdgesGeometry(geo) }).geometry, edgeMat);
      edges.position.copy(box.position);
      basesG.add(edges);

      const lbl = label(`<b>${esc(g.name)}</b><small>${g.events.length}</small>`, "w3-lbl-base");
      lbl.element.style.pointerEvents = "none";
      lbl.center.set(0.5, 1);
      lbl.position.set(g.x, hb + 0.6, BASE_Z);
      basesG.add(lbl);
      managed.push({ obj: lbl, id: null, prio: g.events.length >= 2 ? 3 : 0.5, w: 0, h: 0, dy: 0 });

      g.events.forEach((e) => {
        const n = nodes.get(e.id);
        if (!n) return;
        const c = LANE_COLOR[e.lane] || LANE_COLOR.company;
        const from = new THREE.Vector3(g.x, hb, BASE_Z);
        const to = n.lineEnd.clone(); // deploy lines land on the ground ring
        const mid = from.clone().lerp(to, 0.5);
        mid.y = Math.max(from.y, to.y) + 4 + from.distanceTo(to) * 0.08;
        const curve = new THREE.QuadraticBezierCurve3(from, mid, to);
        const lg = track({ geometry: new THREE.BufferGeometry().setFromPoints(curve.getPoints(28)) }).geometry;
        const line = new THREE.Line(lg, track({ material: new THREE.LineBasicMaterial({ color: c.hi, transparent: true, opacity: 0.26 }) }).material);
        line.userData.eventId = e.id;
        basesG.add(line);
        n.baseLine = line;
      });
    });
  }

  /* ---------- links between events ---------- */
  function buildLinks() {
    clearGroup(linksG);
    (DATA.links || []).forEach((lk) => {
      const a = nodes.get(Number(lk.from));
      const b = nodes.get(Number(lk.to));
      if (!a || !b) return;
      const from = new THREE.Vector3(a.x, a.linkY, a.z);
      const to = new THREE.Vector3(b.x, b.linkY, b.z);
      const mid = from.clone().lerp(to, 0.5);
      mid.y = Math.max(from.y, to.y) + 2.5 + from.distanceTo(to) * 0.14;
      const curve = new THREE.QuadraticBezierCurve3(from, mid, to);
      const geo = track({ geometry: new THREE.BufferGeometry().setFromPoints(curve.getPoints(32)) }).geometry;
      const color = (LANE_COLOR[a.e.lane] || LANE_COLOR.company).hi;
      const mat =
        lk.kind === "indirect"
          ? new THREE.LineDashedMaterial({ color, dashSize: 1.1, gapSize: 0.7, transparent: true, opacity: 0.6 })
          : new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.75 });
      track({ material: mat });
      const line = new THREE.Line(geo, mat);
      if (lk.kind === "indirect") line.computeLineDistances();
      line.userData.pair = [a.e.id, b.e.id];
      linksG.add(line);
    });
  }

  /* ---------- rebuild for a range ---------- */
  function rebuild() {
    disposeAll();
    animations.length = 0;
    const axis = axisRange();
    const W = BOARD_W[state.range];
    const list = windowEvents();
    const xOf = buildBoard(axis, W);
    buildEvents(list, xOf);
    buildBases(list, xOf, W);
    buildLinks();
    applySelectionStyles();
    syncCopy(list.length);
  }

  function syncCopy(n) {
    const counts = ((DATA.window_counts || {})[String(state.range)] || {}).by_lane || {};
    const emptyCore = !(counts.company || counts.deploy);
    const canned = (DATA.ledes || {})[String(state.range)] || "";
    if (ledeEl) {
      ledeEl.textContent = emptyCore && canned
        ? canned
        : `点开观察，读事实与影响，再进入落地或方法 · 过去 ${state.range} 天 · ${n} 条`;
    }
    document.querySelectorAll("[data-range]").forEach((b) => {
      const on = Number(b.dataset.range) === state.range;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    document.querySelectorAll("[data-scope]").forEach((b) => {
      const on = b.dataset.scope === state.scope;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    renderOverview();
    syncRooms();
  }

  /* ---------- selection / hover / chain ---------- */
  function applySelectionStyles() {
    const chainSet = state.chain ? new Set(state.chain.map((c) => Number(c.id))) : null;
    const lit = state.chainLit; // chain items light up one after another
    nodes.forEach((n, id) => {
      const sel = id === state.selected;
      const hov = id === state.hovered;
      const inChain = chainSet ? chainSet.has(id) && (!lit || lit.has(id)) : false;
      const dim = chainSet ? !inChain && !sel : false;
      n.mat.emissiveIntensity = sel || inChain ? 1.0 : hov ? 0.9 : dim ? 0.08 : n.glow;
      n.mat.opacity = n.modified ? (dim ? 0.12 : 0.3) : dim ? 0.3 : 1;
      n.mat.transparent = n.modified || dim;
      const k = sel ? n.hotSel : hov ? n.hotHov : 1;
      n.hot.scale.copy(n.hotBase).multiplyScalar(k);
      n.extras.forEach((x) => {
        x.obj.material.opacity = dim ? x.base * 0.2 : sel || inChain ? Math.min(1, x.base * 1.4) : x.base;
      });
      n.lbl.element.classList.toggle("sel", sel);
      n.lbl.element.classList.toggle("hov", hov);
      n.lbl.element.classList.toggle("dim", dim);
      if (n.baseLine) n.baseLine.material.opacity = sel || inChain ? 0.8 : dim ? 0.06 : 0.26;
    });
    managed.forEach((m) => (m.w = 0)); // hover/selection changes tag size
    labelsDirty = true;
    linksG.children.forEach((line) => {
      const [a, b] = line.userData.pair || [];
      const touch = a === state.selected || b === state.selected;
      const dimmed = chainSet ? !(chainSet.has(a) && chainSet.has(b)) : false;
      line.material.opacity = touch ? 1 : dimmed ? 0.1 : line.material.isLineDashedMaterial ? 0.6 : 0.75;
    });
  }

  function select(id, opts = {}) {
    const e = byId[id];
    if (!e) return;
    if (!inWindow(e)) {
      const fit = [7, 30, 90].find((r) => inWindow(e, r)) || 90;
      state.range = fit;
      rebuild();
    }
    if (state.scope === "featured" && !featuredIds(state.range).has(id)) {
      state.scope = "all"; // 面板相关事件/报告跳转指向精选外节点 → 自动切全量
      rebuild();
    }
    state.selected = id;
    if (!opts.keepChain) state.chain = null;
    applySelectionStyles();
    renderPanel();
    const n = nodes.get(id);
    if (n && !opts.noFly) flyTo(new THREE.Vector3(n.x, Math.min(n.top * 0.5, 4), n.z), Math.max(100, fitDistance() * 0.42));
    history.replaceState(null, "", `?窗=${state.range}#e=${id}`);
  }

  function clearSelection() {
    state.selected = null;
    state.chain = null;
    applySelectionStyles();
    renderPanel();
    requestAnimationFrame(() => homeCamera(false));
    history.replaceState(null, "", `?窗=${state.range}`);
  }

  function showChain(index) {
    const ch = currentChanges()[index];
    if (!ch) return;
    const ids = (ch.chain || []).map((c) => Number(c.id)).filter((id) => byId[id]);
    if (!ids.length) return;
    // 升窗按「链节点在该窗可见」判定（窗内无 company/deploy 时 job_posting 不渲染，纯 inWindow 会判定过松）
    const need = Math.max(...ids.map((id) => [7, 30, 90].find((r) => visibleAt(id, r)) || 90));
    let changed = false;
    if (need > state.range) {
      state.range = need;
      changed = true;
      history.replaceState(null, "", `?窗=${state.range}`);
    }
    if (ensureFeatured(state.range, ids)) changed = true;
    if (changed) rebuild();
    state.chain = ch.chain;
    state.selected = null;
    // light the evidence chain up one item at a time, oldest first
    const order = [...ids].sort((a, b) => (byId[a].day < byId[b].day ? -1 : 1));
    state.chainLit = REDUCED ? null : new Set();
    if (!REDUCED) {
      order.forEach((id, i) => {
        animations.push({
          t0: performance.now() + 420 + i * 260,
          dur: 1,
          tick: () => {
            if (state.chainLit && state.chain === ch.chain) {
              state.chainLit.add(id);
              applySelectionStyles();
            }
          },
        });
      });
    }
    applySelectionStyles();
    renderPanel();
    const box = new THREE.Box3();
    ids.forEach((id) => {
      const n = nodes.get(id);
      if (n) box.expandByPoint(new THREE.Vector3(n.x, n.top, n.z));
    });
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    flyTo(center, Math.max(60, Math.max(size.x, size.z) * 1.25));
  }

  /* ---------- camera ---------- */
  let flight = null;
  function flyTo(target, dist) {
    const dir = camera.position.clone().sub(controls.target);
    dir.y = Math.max(dir.y, dir.length() * 0.42);
    dir.setLength(dist);
    const toPos = target.clone().add(dir);
    if (REDUCED) {
      controls.target.copy(target);
      camera.position.copy(toPos);
      return;
    }
    flight = { t0: performance.now(), dur: 780, fromT: controls.target.clone(), toT: target.clone(), fromP: camera.position.clone(), toP: toPos };
  }
  /* Distance that fits the whole board (lane labels on the left, snapshot
     wall on the right, base row at the back) for the current aspect. */
  function fitDistance() {
    const W = BOARD_W[state.range] + LANE_TEXT_W + 8; // lane names + board + wall
    const D = FRONT_Z - (BASE_Z - 8) + 16;
    const vfov = THREE.MathUtils.degToRad(camera.fov);
    const hfov = 2 * Math.atan(Math.tan(vfov / 2) * camera.aspect);
    const PAD_PX = stage.clientWidth < 700 ? 170 : 64; // 手机上实体标签宽，留白加大才不切边
    const sw = Math.max(stage.clientWidth, 400);
    const usable = Math.max(sw - 2 * PAD_PX, sw * 0.5);
    const byWidth = (W / 2 / Math.tan(hfov / 2)) * (sw / usable) * 1.16; // front edge flares out
    const byDepth = (D / 2 / Math.tan(vfov / 2)) * 0.9;
    return Math.max(byWidth, byDepth);
  }
  function homeCamera(instant) {
    const dist = fitDistance();
    /* 窄屏 fit 远大于桌面（320 旧上限会把相机钳回近景），上限随取景抬高一次到位 */
    controls.maxDistance = Math.max(controls.maxDistance, Math.ceil(dist * 1.4));
    // centre on board + lane-name gutter, not on the board alone
    const target = new THREE.Vector3(-LANE_TEXT_W / 2, 0, (FRONT_Z + BASE_Z) / 2 + 3);
    const pos = new THREE.Vector3(0, dist * 0.7, dist * 0.68).add(target);
    if (instant || REDUCED) {
      controls.target.copy(target);
      camera.position.copy(pos);
      return;
    }
    flight = { t0: performance.now(), dur: 900, fromT: controls.target.clone(), toT: target, fromP: camera.position.clone(), toP: pos };
  }

  /* ---------- picking ---------- */
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  let downAt = null;
  let hoverDirty = false;
  function pick(clientX, clientY) {
    const r = canvas.getBoundingClientRect();
    ndc.set(((clientX - r.left) / r.width) * 2 - 1, -(((clientY - r.top) / r.height) * 2 - 1));
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(pickables, false)[0];
    return hit ? hit.object.userData.id : null;
  }
  canvas.addEventListener("pointerdown", (ev) => (downAt = { x: ev.clientX, y: ev.clientY }));
  canvas.addEventListener("pointerup", (ev) => {
    if (!downAt) return;
    const moved = Math.hypot(ev.clientX - downAt.x, ev.clientY - downAt.y);
    downAt = null;
    if (moved > 5) return;
    const id = pick(ev.clientX, ev.clientY);
    if (id != null) select(id);
  });
  canvas.addEventListener("pointermove", (ev) => {
    if (hoverDirty) return;
    hoverDirty = true;
    requestAnimationFrame(() => {
      hoverDirty = false;
      const id = pick(ev.clientX, ev.clientY);
      if (id !== state.hovered) {
        state.hovered = id;
        canvas.style.cursor = id != null ? "pointer" : "";
        applySelectionStyles();
      }
    });
  });
  labelsHost.addEventListener("click", (ev) => {
    const el = ev.target.closest("[data-id]");
    if (el) select(Number(el.dataset.id));
  });
  canvas.addEventListener("keydown", (ev) => {
    const list = windowEvents();
    if (!list.length) return;
    const i = list.findIndex((e) => e.id === state.selected);
    if (ev.key === "ArrowRight") {
      select(list[Math.min(list.length - 1, i + 1)].id);
      ev.preventDefault();
    } else if (ev.key === "ArrowLeft") {
      select(list[Math.max(0, i - 1)].id);
      ev.preventDefault();
    } else if (ev.key === "Escape") {
      clearSelection();
    } else if (ev.key === "Home") {
      homeCamera(false);
    }
  });

  /* ---------- HUD controls ---------- */
  document.querySelectorAll("[data-range]").forEach((b) =>
    b.addEventListener("click", () => {
      const r = Number(b.dataset.range);
      if (r === state.range) return;
      state.range = r;
      const keep =
        state.selected &&
        inWindow(byId[state.selected]) &&
        (state.scope !== "featured" || featuredIds(state.range).has(state.selected))
          ? state.selected
          : null;
      state.selected = keep;
      state.chain = null;
      rebuild();
      renderPanel();
      homeCamera(false);
      history.replaceState(null, "", `?窗=${state.range}${keep ? "#e=" + keep : ""}`);
    })
  );
  document.querySelectorAll("[data-lens]").forEach((b) =>
    b.addEventListener("click", () => {
      state.lens = b.dataset.lens === "field" ? "field" : "boss";
      document.querySelectorAll("[data-lens]").forEach((x) => {
        const on = x.dataset.lens === state.lens;
        x.classList.toggle("on", on);
        x.setAttribute("aria-pressed", on ? "true" : "false");
      });
      renderPanel();
    })
  );
  document.querySelectorAll("[data-lens]").forEach((x) => {
    const on = x.dataset.lens === state.lens;
    x.classList.toggle("on", on);
    x.setAttribute("aria-pressed", on ? "true" : "false");
  });
  panel.addEventListener("click", (ev) => {
    const pickBtn = ev.target.closest("[data-pick]");
    if (pickBtn) {
      select(Number(pickBtn.dataset.pick), { keepChain: true });
      return;
    }
    const chainBtn = ev.target.closest("[data-chain]");
    if (chainBtn) {
      showChain(Number(chainBtn.dataset.chain));
      return;
    }
    if (ev.target.closest("[data-close]")) clearSelection();
    if (ev.target.closest("[data-home]")) homeCamera(false);
  });

  /* ---------- panel ---------- */
  const fieldCopy = (v, fb) => (v ? `<p>${esc(v)}</p>` : `<p class="w3-empty">${esc(fb)}</p>`);
  /* Whole-paragraph why/prac/ent templates. Unique tails after 要解决的是： stay. */
  const FLUFF_EXACT = {};
  [
    "这是公司自己宣布的组织变化，不是某一家客户的故事",
    "这是公司自己宣布的组织变化",
    "公司把「帮客户落地」写成一条产品线了",
    "股东信是公司对外讲经营。点名驻场团队，说明他们开始这么对外讲；数字要打开原文看",
    "股东信是公司对外讲经营。点名驻场团队，说明他们开始这么对外讲；数字以这篇为准",
    "股东信是公司对外讲经营",
    "官方新闻稿，用来对同一天的说法。不要单独当成第二条变化",
    "官方新闻稿，用来对同一天的说法",
    "有名字的人写的评论。先看他主张什么、数字怎么来的、他是谁",
    "有名字的人写的评论",
    "有日期、有名字的访谈。看现场的人怎么理解这份工作",
    "有日期、有名字的访谈",
    "有日期的演讲。台上的数字不是审计结果",
    "有日期的演讲",
    "有日期的一集播客。用来听大家怎么说，不证明某家客户已经照做",
    "有日期的一集播客",
    "公开讨论。一帖一条；没有日期就不上这条时间线",
    "公开讨论。一帖一条",
    "讲怎么干活的材料。不证明某家客户已经照做",
    "讲怎么干活的材料",
    "工程团队写怎么组这支队伍。这是做法，不是客户故事",
    "工程团队写怎么组这支队伍",
    "官方在招人。只能说明有人在建这支队伍，不说明已经做成了",
    "官方在招人。只能说明有人在建这支队伍",
    "别人统计的招聘情况。一篇一篇看，不要把岗位列表铺满屏幕",
    "别人统计的招聘情况。一篇一篇看",
    "原文没有写 Forward Deployed 头衔。可核的是客户侧叙述，不是编制样板",
    "原文没有写 Forward Deployed 头衔。这条不能当现场样本",
    "原文没写驻场工程师这个岗位名。能核对的是客户怎么用、结果怎样，不是怎么组团队",
    "原文没写驻场工程师这个岗位名。这条不能当成现场怎么干活的例子",
    "原文没写驻场工程师这个岗位名",
    "原文未明确 FDE 职衔",
    "无 驻场这个岗位名",
    "无 FDE 头衔",
    "不是编制样板",
    "不是怎么组团队",
    "不能当成怎么组团队",
    "可核的是客户侧叙述，不是编制样板",
    "可核的是客户自己的结果",
    "可核的是客户侧",
    "可核的是客户",
    "还没写出为什么",
    "这是公开材料",
    "这是动态层收录",
    "可作为交付现场样本",
    "有名字、有日期的客户故事",
    "有名字、有日期",
    "有日期、有名字",
    "具名客户且可作为交付现场样本",
    "这是在招人。一个岗位不等于已经做成，也不等于人已经到位",
    "只能读成"
  ].forEach((s) => { FLUFF_EXACT[s] = true; });
  const FLUFF_JOB_ENT = /^只能读成 .+还在招「.+」。一个岗位不等于已经做成，也不等于人已经到位。?$/;
  const fluffNorm = (s) => String(s || "").trim().replace(/[。.\s]+$/g, "");
  const fluffHan = (s) => {
    const m = String(s || "").match(/[\u4e00-\u9fff]/g);
    return m ? m.length : 0;
  };
  const fluffIntro = (s) => {
    const t = String(s || "").trim();
    if (!t) return true;
    if (/^我们[与和]/.test(t) || /交谈，(?:了解|讨论)/.test(t) || t.indexOf("问答 请介绍") >= 0) return true;
    if (t.slice(0, 24).indexOf("客户案例研究") >= 0) return true;
    const first = t.split("。")[0];
    return (
      /由 .{2,40}创立/.test(first) ||
      /^作为.{2,24}(专家|公司|平台)/.test(first) ||
      /是一家.{0,24}(公司|初创|非营利|零售商|平台|组织)/.test(first) ||
      /是(?:一家|一个).{0,20}(零售商|非营利组织|电商平台|金融科技)/.test(first) ||
      (/是面向.{0,24}(平台|公司|组织)/.test(first) && first.indexOf("需要") < 0) ||
      (/是推动.{0,16}发展的/.test(first) && first.indexOf("需要") < 0)
    );
  };
  const fluffCopy = (text) => {
    const t = String(text || "").trim();
    if (!t) return true;
    const n = fluffNorm(t);
    if (FLUFF_EXACT[n]) return true;
    if (FLUFF_JOB_ENT.test(t) || FLUFF_JOB_ENT.test(n + "。")) return true;
    const parts = t.split(/要解决的是[:：]/);
    if (parts.length > 1) {
      const after = parts.slice(1).join("要解决的是：").trim();
      const nHan = fluffHan(after);
      const specific = after && !fluffIntro(after) && (nHan >= 8 || (nHan >= 6 && /[。！？!?]$/.test(after)));
      return !specific;
    }
    return false;
  };
  function panelEvent(e) {
    const primaryField = state.lens === "field";
    const ent = fluffCopy(e.enterprise) ? "" : `<h3>对企业意味着什么</h3>${fieldCopy(e.enterprise)}`;
    const prac = fluffCopy(e.practitioner) ? "" : `<h3>对干活的人意味着什么</h3>${fieldCopy(e.practitioner)}`;
    const why = "";
    const related = [];
    (DATA.links || []).forEach((lk) => {
      if (Number(lk.from) === e.id) related.push(Number(lk.to));
      else if (Number(lk.to) === e.id) related.push(Number(lk.from));
    });
    const rel = related.filter((id, i) => related.indexOf(id) === i && byId[id]);
    const c = (LANE_COLOR[e.lane] || LANE_COLOR.company).hi;
    const kindBits = [laneLabel(e.lane), e.doc_label].filter((x, i, a) => x && a.indexOf(x) === i);
    return `
<div class="w3-p-top">
  <p class="w3-p-k" style="--c:${c}"><i></i>${esc(monthDay(e.day))} · ${esc(kindBits.join(" · "))}</p>
  <button type="button" class="w3-p-x" data-close aria-label="关闭">×</button>
</div>
<h2>${esc(e.title)}</h2>
<dl class="w3-p-facts">
  <div><dt>来源</dt><dd>${esc(e.host || e.kicker)}</dd></div>
  <div><dt>日期</dt><dd>${esc(e.date_kind === "published" ? e.day : ("页面上写的日期 " + e.day))}</dd></div>
</dl>

<h3>发生了什么</h3>${fieldCopy(e.happened, "还没写出摘要。")}
${why}
${primaryField ? prac + ent : ent + prac}
${e.case_href && e.lane === "deploy" ? `<p><a class="w3-p-more" href="${esc(e.case_href)}">看完整案例</a></p>` : ""}
${rel.length ? `<h3>相关事件（${rel.length}）</h3><ul class="w3-p-rel">${rel.map((id) => `<li><button type="button" data-pick="${id}"><span>${esc(monthDay(byId[id].day))}</span>${esc(byId[id].title_short || byId[id].title)}</button></li>`).join("")}</ul>` : ""}`;
  }

  function renderPanel() {
    const e = state.selected ? byId[state.selected] : null;
    panel.innerHTML = e ? panelEvent(e) : "";
    panel.scrollTop = 0;
    root.classList.toggle("w3-has-sel", !!e);
    /* 报告按钮挂在 body 上，选择态收起它得靠 body 级开关（手机抽屉盖字） */
    document.body.classList.toggle("w3-sheet-open", !!e);
  }

  /* ---------- sizing / loop ---------- */
  let lastAspect = camera.aspect;
  let userTouchedControls = false;
  controls.addEventListener("start", () => { userTouchedControls = true; });
  function resize() {
    const w = stage.clientWidth;
    const h = stage.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    labelRenderer.setSize(w, h);
    groundRenderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    /* 手机/旋屏：初始取景按 aspect=1 算过，宽高比一变就要重新拉远取景，
       用户一旦自己转过视角就不再打扰；同时取消进行中的飞行动画（否则逐帧覆盖回旧取景） */
    try {
      if (!userTouchedControls && Math.abs(camera.aspect - lastAspect) > 0.01) {
        flight = null;
        homeCamera(true);
      }
    } catch (_) {}
    lastAspect = camera.aspect;
    managed.forEach((m) => (m.w = 0)); // re-measure labels
    labelsDirty = true;
  }
  new ResizeObserver(resize).observe(stage);
  resize();

  const easeOutCubic = (k) => 1 - Math.pow(1 - k, 3);

  let running = true;
  document.addEventListener("visibilitychange", () => (running = !document.hidden));

  function frame(now) {
    requestAnimationFrame(frame);
    if (!running) return;
    for (let i = animations.length - 1; i >= 0; i -= 1) {
      const a = animations[i];
      if (now < a.t0) continue;
      const k = Math.min(1, (now - a.t0) / a.dur);
      a.tick(k);
      if (k >= 1) animations.splice(i, 1);
    }
    if (flight) {
      const k = Math.min(1, (now - flight.t0) / flight.dur);
      const s = easeOutCubic(k);
      controls.target.lerpVectors(flight.fromT, flight.toT, s);
      camera.position.lerpVectors(flight.fromP, flight.toP, s);
      if (k >= 1) flight = null;
    }
    controls.update();
    renderer.render(scene, camera);
    groundRenderer.render(scene, camera);
    labelRenderer.render(scene, camera);
    const moved = !_prevCam.equals(camera.matrixWorld);
    if (moved || labelsDirty || animations.length) {
      _prevCam.copy(camera.matrixWorld);
      labelsDirty = false;
      deconflictLabels();
    }
  }

  /* ---------- 解读报告（7/30/90 天，服务端预生成+缓存） ---------- */
  const reportCache = new Map(); // range → {text, events, total}
  function ensureFloatBtn() {
    if (document.getElementById("w3-report-fab")) return;
    const fab = document.createElement("button");
    fab.id = "w3-report-fab";
    fab.type = "button";
    fab.setAttribute("aria-label", "解读报告");
    fab.innerHTML = '<span class="w3-fab-ico">✦</span><span class="w3-fab-t">解读报告</span>';
    document.body.appendChild(fab);
    fab.addEventListener("click", () => openReport(state.range));
  }
  function reportLink(t) {
    // 把 markdown 链接 [标题](url) 映射回沙盘事件（按 url 匹配），点击选中对应形体
    const raw = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, label, url) => {
      const ev = (DATA.events || []).find(
        (x) => x.url === url || (x.detail && x.detail["原文链接"] === url)
      );
      return ev
        ? `<a href="javascript:void(0)" data-report-pick="${ev.id}">${esc(label)}</a>`
        : `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`;
    });
    return raw;
  }
  function mdLite(t) {
    let h = esc(t);
    h = reportLink(h);
    h = h.replace(/^### (.+)$/gm, "<h4>$1</h4>");
    h = h.replace(/^## (.+)$/gm, "<h3>$1</h3>");
    h = h.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    h = h.replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>");
    return `<p>${h}</p>`;
  }
  async function openReport(range) {
    let overlay = document.getElementById("w3-report-overlay");
    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "w3-report-overlay";
      overlay.innerHTML = `
<div class="w3-rp" role="dialog" aria-label="解读报告">
  <header class="w3-rp-h">
    <h2>解读报告</h2>
    <div class="w3-range" role="radiogroup" aria-label="报告时间窗">
      <button type="button" data-rp-range="7">7 天</button>
      <button type="button" data-rp-range="30" class="on">30 天</button>
      <button type="button" data-rp-range="90">90 天</button>
    </div>
    <button type="button" class="w3-rp-x" data-rp-close aria-label="关闭">×</button>
  </header>
  <div class="w3-rp-body" id="w3-rp-body"></div>
</div>`;
      document.body.appendChild(overlay);
      overlay.addEventListener("click", (ev) => {
        const pick = ev.target.closest("[data-report-pick]");
        if (pick) {
          closeReport();
          select(Number(pick.dataset.reportPick), { fly: true });
          return;
        }
        const rbtn = ev.target.closest("[data-rp-range]");
        if (rbtn) {
          openReport(Number(rbtn.dataset.rpRange));
          return;
        }
        if (ev.target.closest("[data-rp-close]") || ev.target === overlay) closeReport();
      });
    }
    overlay.hidden = false;
    overlay.querySelectorAll("[data-rp-range]").forEach((b) => {
      const on = Number(b.dataset.rpRange) === Number(range);
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
    const bodyEl = overlay.querySelector("#w3-rp-body");
    if (reportCache.has(range)) {
      const rep = reportCache.get(range);
      bodyEl.innerHTML = `<div class="w3-ai-text">${mdLite(rep.text)}</div>`;
      return;
    }
    bodyEl.innerHTML = '<p class="w3-ai-loading">✦ 生成中…</p>';
    try {
      const res = await fetch(`/api/ai-report?range=${range}`, { method: range ? "GET" : "GET" });
      const rep = await res.json();
      if (!res.ok || !rep.enabled) throw new Error(rep.error || ("HTTP " + res.status));
      reportCache.set(range, rep);
      bodyEl.innerHTML = `<div class="w3-ai-text">${mdLite(rep.text)}</div>`;
    } catch (err) {
      bodyEl.innerHTML = `<p class="w3-ai-err">报告不可用：${esc(String(err.message || err))}</p>`;
    }
  }
  function closeReport() {
    const overlay = document.getElementById("w3-report-overlay");
    if (overlay) overlay.hidden = true;
  }
  ensureFloatBtn();

  /* ---------- 概览层 / 范围 chips：统一委托在 stage 上 ----------
     .w3-scope 是 #w3-overview 的兄弟节点（绑 overviewEl 收不到 chip 点击）；
     也不绑 document——面板 .w3-panel 在 stage 外且自带 [data-chain] 委托，绑宽了会双重触发。 */
  function setScope(scope) {
    const next = scope === "all" ? "all" : "featured";
    if (next === state.scope) return;
    state.scope = next;
    const keep =
      state.selected &&
      inWindow(byId[state.selected]) &&
      (state.scope !== "featured" || featuredIds(state.range).has(state.selected))
        ? state.selected
        : null;
    state.selected = keep;
    state.chain = null;
    rebuild();
    renderPanel();
    homeCamera(false);
    history.replaceState(null, "", `?窗=${state.range}${keep ? "#e=" + keep : ""}`);
  }
  function bindOverview() {
    stage.addEventListener("click", (ev) => {
      const chainBtn = ev.target.closest("[data-chain]");
      if (chainBtn) {
        enterSandbox(); // 先收概览再飞链；链上节点经升窗+ensureFeatured 必然可见
        showChain(Number(chainBtn.dataset.chain));
        return;
      }
      if (ev.target.closest("[data-ov-all]")) {
        enterSandbox();
        setScope("all");
        return;
      }
      if (ev.target.closest("[data-ov-enter]")) {
        enterSandbox();
        return;
      }
      const scopeBtn = ev.target.closest("[data-scope]");
      if (scopeBtn) setScope(scopeBtn.dataset.scope);
    });
  }
  bindOverview();

  /* ---------- go ---------- */
  rebuild();
  homeCamera(true);
  const hash = /#e=(\d+)/.exec(location.hash);
  const initial = hash ? Number(hash[1]) : null;
  if (initial && byId[initial]) {
    state.scope = "all"; // 深链直入全量沙盘并跳过概览，保住 hash 优先级
    enterSandbox();
    select(initial, { noFly: true });
  } else {
    state.selected = null;
    renderPanel();
  }
  requestAnimationFrame(frame);
  /* 手机/旋屏：初始取景可能与最终画幅不一致（首帧 aspect 与布局不同步、
     遗留飞行动画覆盖），按节拍重取景；用户碰过控制器后停手 */
  [120, 450, 1100].forEach((t) =>
    setTimeout(() => { if (!userTouchedControls) homeCamera(true); }, t)
  );
  if (hintEl) setTimeout(() => hintEl.classList.add("w3-hint-fade"), 6000);
  root.dataset.ready = "1";
}
