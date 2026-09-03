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

const params = new URLSearchParams(location.search);
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const NARROW = matchMedia("(max-width: 767px)").matches;
const DAY = 86400000;

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
  range: [7, 30, 90].includes(Number(params.get("range"))) ? Number(params.get("range")) : 30,
  lens: params.get("lens") === "field" ? "field" : "boss",
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
const windowEvents = () =>
  (DATA.events || []).filter((e) => inWindow(e)).sort((a, b) => (a.day !== b.day ? (a.day < b.day ? -1 : 1) : a.id - b.id));

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
  root.classList.add("w3-flat");
  fallback.hidden = false;
  const why = document.getElementById("w3-fallback-why");
  if (why && reason) why.textContent = reason;
  const list = document.getElementById("w3-fallback-list");
  if (list) {
    list.innerHTML = windowEvents()
      .map(
        (e) =>
          `<li><span class="w3-fb-day">${esc(monthDay(e.day))}</span><span class="w3-fb-lane" data-lane="${esc(e.lane)}">${esc(laneLabel(e.lane))}</span><a href="${esc(e.url)}" target="_blank" rel="noopener noreferrer">${esc(e.title)}</a><small>${esc(e.host)}</small></li>`
      )
      .join("");
  }
}

if (!webglOK()) {
  showFallback("此设备不支持 WebGL，已切换到平面列表。数据与 3D 沙盘完全一致。");
} else if (NARROW && params.get("force3d") !== "1") {
  showFallback("屏幕较窄，已切换到平面列表。桌面端可查看 3D 沙盘。");
} else {
  boot();
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
  controls.minDistance = 30;
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
      const lbl = groundText(`<b>${esc(laneLabel(lane))}</b><small>${esc(laneEn(lane))}</small>`, "w3-g-lane", { width: LW });
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
      const tl = groundText(last ? `${esc(tk.label)}<em>快照</em>` : esc(tk.label), last ? "w3-g-tick w3-g-tick-end" : "w3-g-tick");
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
    const bl = groundText(`<b>大本营</b><small>Organisations</small>`, "w3-g-lane", { width: LANE_TEXT_W / GT });
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
    if (ledeEl) ledeEl.textContent = `过去 ${state.range} 天 · ${n} 条有日期的官方原文上轴 · 塔、落点、信号灯、轨道都可点开核对`;
    document.querySelectorAll("[data-range]").forEach((b) => {
      const on = Number(b.dataset.range) === state.range;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
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
    state.selected = id;
    if (!opts.keepChain) state.chain = null;
    applySelectionStyles();
    renderPanel();
    const n = nodes.get(id);
    if (n && !opts.noFly) flyTo(new THREE.Vector3(n.x, n.top * 0.5, n.z), 54);
    history.replaceState(null, "", `?range=${state.range}&lens=${state.lens}#e=${id}`);
  }

  function clearSelection() {
    state.selected = null;
    state.chain = null;
    applySelectionStyles();
    renderPanel();
    history.replaceState(null, "", `?range=${state.range}&lens=${state.lens}`);
  }

  function showChain(index) {
    const ch = (DATA.changes || [])[index];
    if (!ch) return;
    const ids = (ch.chain || []).map((c) => Number(c.id)).filter((id) => byId[id]);
    if (!ids.length) return;
    const need = Math.max(...ids.map((id) => [7, 30, 90].find((r) => inWindow(byId[id], r)) || 90));
    if (need > state.range) {
      state.range = need;
      rebuild();
    }
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
    renderPanel(index);
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
    const PAD_PX = 64; // billboard tags may poke out a little
    const sw = Math.max(stage.clientWidth, 400);
    const usable = Math.max(sw - 2 * PAD_PX, sw * 0.5);
    const byWidth = (W / 2 / Math.tan(hfov / 2)) * (sw / usable) * 1.16; // front edge flares out
    const byDepth = (D / 2 / Math.tan(vfov / 2)) * 0.9;
    return Math.max(byWidth, byDepth);
  }
  function homeCamera(instant) {
    const dist = fitDistance();
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
      const keep = state.selected && inWindow(byId[state.selected]) ? state.selected : null;
      state.selected = keep;
      state.chain = null;
      rebuild();
      renderPanel();
      homeCamera(false);
      history.replaceState(null, "", `?range=${state.range}&lens=${state.lens}${keep ? "#e=" + keep : ""}`);
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
  function panelEvent(e) {
    const primaryField = state.lens === "field";
    const ent = fieldCopy(e.enterprise, "原文未写可核对的企业影响。");
    const prac = fieldCopy(e.practitioner, "原文未写可核对的从业者影响。");
    const related = [];
    (DATA.links || []).forEach((lk) => {
      if (Number(lk.from) === e.id) related.push(Number(lk.to));
      else if (Number(lk.to) === e.id) related.push(Number(lk.from));
    });
    const rel = related.filter((id, i) => related.indexOf(id) === i && byId[id]);
    const c = (LANE_COLOR[e.lane] || LANE_COLOR.company).hi;
    return `
<div class="w3-p-top">
  <p class="w3-p-k" style="--c:${c}"><i></i>${esc(monthDay(e.day))} · ${esc(laneLabel(e.lane))} · ${esc(e.doc_label || e.info_kind)}</p>
  <button type="button" class="w3-p-x" data-close aria-label="关闭详情">×</button>
</div>
<h2>${esc(e.title)}</h2>
<dl class="w3-p-facts">
  <div><dt>来源</dt><dd>${esc(e.host || e.kicker)}</dd></div>
  <div><dt>原始发布日期</dt><dd>${esc(e.date_kind === "published" ? e.day : "待补（页上修改日 " + e.day + "）")}</dd></div>
  <div><dt>收录快照</dt><dd>${esc(DATA.snapshot)}</dd></div>
  <div><dt>信号</dt><dd>${esc({ low: "低", mid: "中", high: "高" }[e.signal] || e.signal)}</dd></div>
</dl>
<h3>发生了什么</h3>${fieldCopy(e.happened, "当前未提取正文摘要。")}
<h3>为什么值得关注</h3>${fieldCopy(e.why, "当前未提取判断依据。")}
<h3>${primaryField ? "对 FDE 从业者的影响" : "对企业落地的影响"}</h3>${primaryField ? prac : ent}
<h3>${primaryField ? "对企业落地的影响" : "对 FDE 从业者的影响"}</h3>${primaryField ? ent : prac}
<h3>原始来源</h3>
<p class="w3-p-url"><a href="${esc(e.url)}" target="_blank" rel="noopener noreferrer">${esc(e.url)}</a></p>
${e.lane === "deploy" && e.href && e.href.indexOf("/案例/") === 0 ? `<p><a class="w3-p-more" href="${esc(e.href)}">在部署证据库中查看这条案例 →</a></p>` : ""}
${rel.length ? `<h3>相关事件（${rel.length}）</h3><ul class="w3-p-rel">${rel.map((id) => `<li><button type="button" data-pick="${id}"><span>${esc(monthDay(byId[id].day))}</span>${esc(byId[id].title_short || byId[id].title)}</button></li>`).join("")}</ul>` : ""}`;
  }

  function panelOverview(activeChain) {
    const list = windowEvents();
    const bases = new Map();
    list.forEach((e) => {
      const k = baseKeyOf(e);
      if (!k) return;
      if (!bases.has(k)) bases.set(k, { name: baseNameOf(e), n: 0, lane: e.lane, ids: [] });
      bases.get(k).n += 1;
      bases.get(k).ids.push(e.id);
    });
    const baseRows = [...bases.values()]
      .sort((a, b) => b.n - a.n || (a.name < b.name ? -1 : 1))
      .slice(0, 8)
      .map((b) => `<li><button type="button" data-pick="${b.ids[b.ids.length - 1]}" style="--c:${(LANE_COLOR[b.lane] || LANE_COLOR.company).hi}"><i></i>${esc(b.name)}<span>${b.n}</span></button></li>`)
      .join("");
    const changes = (DATA.changes || [])
      .map(
        (ch, i) => `<li class="${activeChain === i ? "on" : ""}"><button type="button" data-chain="${i}"><b>${esc(ch.num)}</b><span><strong>${esc(ch.title)}</strong><small>${esc(ch.body)}</small></span></button>${
          activeChain === i
            ? `<ol class="w3-chain">${(ch.chain || []).map((c) => `<li><button type="button" data-pick="${c.id}" style="--c:${(LANE_COLOR[c.lane] || LANE_COLOR.company).hi}"><i></i>${esc(c.title)}</button></li>`).join("")}</ol>`
            : ""
        }</li>`
      )
      .join("");
    return `
<div class="w3-p-top"><p class="w3-p-k"><i style="background:${ACCENT}"></i>过去 ${state.range} 天 · ${list.length} 条上轴</p><button type="button" class="w3-p-x" data-home title="回到全景">⌂</button></div>
<h2 class="w3-p-h">AI 识别的三条变化</h2>
<p class="w3-p-note">点一条，沙盘只留下它的证据链。</p>
<ol class="w3-changes">${changes}</ol>
<h2 class="w3-p-h">窗口内实体</h2>
<ul class="w3-bases">${baseRows || "<li class='w3-empty'>窗口内没有上轴事件。</li>"}</ul>
<p class="w3-p-note">灰色底行是「大本营」，细线指向它在这段时间里推到前线的每一份原文。</p>`;
  }

  function renderPanel(activeChain) {
    const e = state.selected ? byId[state.selected] : null;
    panel.innerHTML = e ? panelEvent(e) : panelOverview(activeChain);
    panel.scrollTop = 0;
    root.classList.toggle("w3-has-sel", !!e);
  }

  /* ---------- sizing / loop ---------- */
  function resize() {
    const w = stage.clientWidth;
    const h = stage.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    labelRenderer.setSize(w, h);
    groundRenderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
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

  /* ---------- go ---------- */
  rebuild();
  homeCamera(true);
  const hash = /#e=(\d+)/.exec(location.hash);
  const initial = hash ? Number(hash[1]) : null;
  if (initial && byId[initial]) select(initial, { noFly: true });
  else {
    state.selected = null;
    renderPanel();
  }
  requestAnimationFrame(frame);
  if (hintEl) setTimeout(() => hintEl.classList.add("w3-hint-fade"), 6000);
  root.dataset.ready = "1";
}
