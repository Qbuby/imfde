/**
 * imfde.ai Worker：动态端点（静态资产由 [assets] 直接服务，不经本 Worker）。
 *
 * run_worker_first 只把以下路径送到这里（见 wrangler.toml）：
 *   /api/ai-report   解读报告：优先读仓库预生成缓存（/ai-cache/<key>.json 静态资产），未命中返回「生成中」
 *   /api/me          会话 cookie → 用户 JSON（页面端 auth-me.js 用它把「登录」升级成头像）
 *   /login           登录页
 *   /login/<provider> 302 到授权页（state 自包含 HMAC 签名，不依赖数据库）
 *   /oauth/<provider>/callback  换 token → 签会话 cookie → 302 回原页
 *   /logout          清 cookie → 302
 *
 * 会话与 state 的签名格式与 portal/site/auth.py 完全一致
 * （body = base64url(JSON)，mac = HMAC-SHA256(SECRET_KEY, body) 的 hex），
 * 两边发的 cookie 互相可验。
 */

const SESSION_COOKIE = "imfde_session";
const SESSION_TTL = 60 * 60 * 24 * 30;

const SYSTEM_PROMPT = `你是 Forward Deployed Engineering（FDE）领域的资深分析师。
给用户一段「可核对的公开原文材料」（含结构化字段），输出两部分：

1) 结论（3-5 条）：这条材料真正在说什么，对 FDE 从业者/企业决策者分别意味着什么。
   每条一句话，先说事实再说含义，不空谈。
2) 原文内容解读：基于下面的字段，把原文讲清楚——
   业务问题是什么、原来怎么做、卡在哪、AI 怎么接进去、怎么评测的、
   实测结果有哪些数字、失败与迭代是什么、最后有没有沉淀成产品能力。
   只依据给到的字段，不许编造；字段没写的明确说「原文未提」。

要求：简体中文。不吹捧、不写套话。直接给要点，不要复述我的提示词。`;

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };

function jsonResp(obj, status = 200, extra = {}) {
  return new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: { ...JSON_HEADERS, ...extra },
  });
}

function textResp(text, status = 200, extra = {}) {
  return new Response(text, { status, headers: { "content-type": "text/plain; charset=utf-8", ...extra } });
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// ---------- HMAC（与 auth.py 同格式） ----------
const enc = new TextEncoder();

async function hmacKey(secret) {
  return crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
}

async function hmacHex(secret, msg) {
  const k = await hmacKey(secret);
  const sig = await crypto.subtle.sign("HMAC", k, enc.encode(msg));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function sha1hex16(s) {
  const d = await crypto.subtle.digest("SHA-1", enc.encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

function b64urlEncode(bytes) {
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlDecode(text) {
  const pad = "=".repeat((4 - (text.length % 4)) % 4);
  const bin = atob(text.replace(/-/g, "+").replace(/_/g, "/") + pad);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

async function signSession(env, payload) {
  const body = b64urlEncode(enc.encode(JSON.stringify(payload)));
  const mac = await hmacHex(env.SECRET_KEY || "imfde-dev-secret", body);
  return `${body}.${mac}`;
}

async function verifySession(env, token) {
  if (!token || !token.includes(".")) return null;
  const dot = token.lastIndexOf(".");
  const body = token.slice(0, dot);
  const mac = token.slice(dot + 1);
  const expect = await hmacHex(env.SECRET_KEY || "imfde-dev-secret", body);
  if (mac !== expect) return null;
  try {
    const payload = JSON.parse(new TextDecoder().decode(b64urlDecode(body)));
    if ((payload.exp || 0) * 1000 < Date.now()) return null;
    return payload;
  } catch {
    return null;
  }
}

async function makeState(env, next) {
  const body = b64urlEncode(enc.encode(next || "/"));
  const mac = await hmacHex(env.SECRET_KEY || "imfde-dev-secret", body);
  return `${body}.${mac}`;
}

async function verifyState(env, state) {
  if (!state || !state.includes(".")) return null;
  const dot = state.lastIndexOf(".");
  const body = state.slice(0, dot);
  const mac = state.slice(dot + 1);
  const expect = await hmacHex(env.SECRET_KEY || "imfde-dev-secret", body);
  if (mac !== expect) return null;
  try {
    return new TextDecoder().decode(b64urlDecode(body));
  } catch {
    return null;
  }
}

function parseCookies(header) {
  const out = {};
  for (const part of (header || "").split(";")) {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

// ---------- OAuth providers ----------
function providerEnv(env, provider) {
  if (provider === "github") return { id: env.GITHUB_CLIENT_ID, secret: env.GITHUB_CLIENT_SECRET };
  if (provider === "google") return { id: env.GOOGLE_CLIENT_ID, secret: env.GOOGLE_CLIENT_SECRET };
  if (provider === "wechat") return { id: env.WECHAT_APPID, secret: env.WECHAT_SECRET };
  return null;
}

function authorizeUrl(provider, redirectUri, state, env) {
  const q = new URLSearchParams({ state });
  if (provider === "github") {
    q.set("client_id", env.GITHUB_CLIENT_ID || "");
    q.set("redirect_uri", redirectUri);
    q.set("scope", "read:user user:email");
    return `https://github.com/login/oauth/authorize?${q}`;
  }
  if (provider === "google") {
    q.set("client_id", env.GOOGLE_CLIENT_ID || "");
    q.set("redirect_uri", redirectUri);
    q.set("response_type", "code");
    q.set("scope", "openid email profile");
    q.set("access_type", "online");
    q.set("prompt", "select_account");
    return `https://accounts.google.com/o/oauth2/v2/auth?${q}`;
  }
  if (provider === "wechat") {
    q.set("appid", env.WECHAT_APPID || "");
    q.set("redirect_uri", redirectUri);
    q.set("response_type", "code");
    q.set("scope", "snsapi_login");
    return `https://open.weixin.qq.com/connect/qrconnect?${q}`;
  }
  return null;
}

async function fetchUser(env, provider, code, redirectUri) {
  const cred = providerEnv(env, provider);
  let access = "";
  let info = {};
  if (provider === "github") {
    let r = await fetch("https://github.com/login/oauth/access_token", {
      method: "POST",
      headers: { "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ client_id: cred.id, client_secret: cred.secret, code, redirect_uri: redirectUri }),
    });
    const tok = await r.json();
    if (tok.error) throw new Error(`github oauth: ${tok.error}`);
    access = tok.access_token || "";
    r = await fetch("https://api.github.com/user", { headers: { Authorization: `Bearer ${access}`, "User-Agent": "imfde.ai", Accept: "application/vnd.github+json" } });
    info = await r.json();
    let email = info.email || "";
    if (!email) {
      try {
        const emails = await (await fetch("https://api.github.com/user/emails", { headers: { Authorization: `Bearer ${access}`, "User-Agent": "imfde.ai", Accept: "application/vnd.github+json" } })).json();
        email = (emails.find((e) => e.primary) || {}).email || "";
      } catch {}
    }
    return { uid: String(info.id ?? ""), name: info.name || info.login || "", email, avatar: info.avatar_url || "" };
  }
  if (provider === "google") {
    const r = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ code, client_id: cred.id, client_secret: cred.secret, redirect_uri: redirectUri, grant_type: "authorization_code" }),
    });
    const tok = await r.json();
    if (tok.error) throw new Error(`google oauth: ${tok.error}`);
    access = tok.access_token || "";
    info = await (await fetch("https://www.googleapis.com/oauth2/v3/userinfo", { headers: { Authorization: `Bearer ${access}` } })).json();
    return { uid: String(info.sub ?? ""), name: info.name || "", email: info.email || "", avatar: info.picture || "" };
  }
  if (provider === "wechat") {
    const r = await fetch(`https://api.weixin.qq.com/sns/oauth2/access_token?appid=${cred.id}&secret=${cred.secret}&code=${encodeURIComponent(code)}&grant_type=authorization_code`);
    const tok = await r.json();
    if (tok.errcode) throw new Error(`wechat oauth: ${tok.errcode}`);
    access = tok.access_token || "";
    const openid = tok.openid || "";
    info = await (await fetch(`https://api.weixin.qq.com/sns/userinfo?access_token=${access}&openid=${openid}`)).json();
    return { uid: openid, name: info.nickname || "", email: "", avatar: info.headimgurl || "" };
  }
  throw new Error(provider);
}

function loginPageHtml(nextPath, env, base) {
  const nextQ = encodeURIComponent(nextPath || "/");
  const btns = [];
  for (const [key, label, cls] of [["github", "GitHub 登录", "auth-gh"], ["google", "Google 登录", "auth-google"], ["wechat", "微信登录", "auth-wechat"]]) {
    if (providerEnv(env, key).id && providerEnv(env, key).secret) {
      btns.push(`<a class="auth-btn ${cls}" href="${base}/login/${key}?next=${nextQ}">${label}</a>`);
    }
  }
  if (!btns.length) btns.push('<p class="auth-empty">登录渠道未配置（需在部署环境设置 OAuth 凭据环境变量）。</p>');
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>登录 · imfde.ai</title>
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
  background:#020a12;color:#eeebe5;font:16px/1.6 -apple-system,"PingFang SC",sans-serif}
.auth-card{text-align:center;padding:48px 56px;border:1px solid rgba(143,178,196,.2);border-radius:16px;
  background:rgba(7,19,30,.8)}
.auth-card h1{font-size:20px;margin:0 0 8px}
.auth-card p.k{font-size:13px;color:#7f8b93;margin:0 0 28px}
.auth-btn{display:block;width:240px;margin:0 auto 12px;padding:12px 0;border-radius:10px;
  text-decoration:none;font-weight:650;font-size:14px;border:1px solid rgba(143,178,196,.3);color:#eeebe5;
  transition:border-color .15s,background .15s}
.auth-btn:hover{border-color:#3fc0c0;background:rgba(63,192,192,.08)}
.auth-gh{background:#0d1117}
.auth-google{background:#fff;color:#1f2328}
.auth-wechat{background:#07c160;color:#fff;border-color:#07c160}
.auth-empty{color:#7f8b93;font-size:14px}
</style>
</head>
<body>
<div class="auth-card">
  <h1>登录 imfde.ai</h1>
  <p class="k">登录后内容不变 —— 全站依然免费开放，仅用于展示头像与昵称。</p>
  ${btns.join("\n  ")}
</div>
</body>
</html>`;
}

// ---------- 报告生成（缓存未命中时的兜底材料，取自静态 world.json） ----------
function buildUserMaterial(events) {
  const lines = [];
  for (const key of ["title", "kicker", "host", "day", "date_kind", "lane", "doc_label"]) {
    if (events[key]) lines.push(`${key}: ${events[key]}`);
  }
  for (const key of ["happened", "why", "enterprise", "practitioner"]) {
    if (events[key]) lines.push(`${key}: ${events[key]}`);
  }
  const url = events.url || "";
  if (url) {
    lines.push("");
    lines.push(`原文链接: ${url}`);
  }
  return lines.join("\n");
}

async function callAi(env, userContent) {
  if (!env.AI_API_KEY) throw new Error("AI_API_KEY 未配置");
  const payload = {
    model: env.AI_MODEL || "MiniMax-M3.1-Flash",
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "user", content: userContent },
    ],
    temperature: 0.3,
  };
  const r = await fetch(`${(env.AI_BASE_URL || "https://api.minimaxi.com/v1").replace(/\/$/, "")}/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.AI_API_KEY}` },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const detail = (await r.text()).slice(0, 400);
    throw Object.assign(new Error(`上游 AI 返回 ${r.status}`), { status: r.status, detail });
  }
  const d = await r.json();
  return ((d.choices || [{}])[0].message || {}).content || "";
}

// ---------- 路由 ----------
async function handleApiAiReport(request, env) {
  const url = new URL(request.url);
  const range = String(parseInt(url.searchParams.get("range") || "30", 10) || 30);
  const snapshot = (url.searchParams.get("snapshot") || "").trim();
  if (![7, 30, 90].includes(Number(range))) {
    return jsonResp({ enabled: false, error: "range 只支持 7/30/90" }, 400);
  }
  if (snapshot) {
    const key = await sha1hex16(`report:${range}:${snapshot}`);
    try {
      const asset = await env.ASSETS.fetch(new URL(`/ai-cache/${key}.json`, url.origin));
      if (asset.ok) {
        const cache = await asset.json();
        if (cache && cache.text) {
          return jsonResp({
            enabled: true, range: Number(range),
            snapshot: cache.cached_at_snapshot || snapshot,
            total: cache.total ?? 0, text: cache.text, cached: true,
          });
        }
      }
    } catch {}
  }
  if (!env.AI_API_KEY) {
    return jsonResp({ enabled: false, error: "AI 未配置（缺少 AI_API_KEY）" }, 200);
  }
  // 兜底：拿静态 world.json 现场生成（缓存一般由本地预生成，这条路径很少走）
  try {
    const world = await (await env.ASSETS.fetch(new URL("/world.json", url.origin))).json();
    const snap = snapshot || world.snapshot || "";
    const start = new Date(Date.parse(`${snap}T00:00:00Z`) - Number(range) * 86400000).toISOString().slice(0, 10);
    const win = (world.events || []).filter((e) => e.day && e.day >= start && e.day <= snap);
    if (!win.length) return jsonResp({ enabled: true, range: Number(range), snapshot: snap, total: 0, text: "窗口内暂无事件。", cached: false });
    const material = win.map((e, i) => `### 事件 ${i + 1}：${e.title || ""}（${e.kicker || ""} · ${e.day || ""} · ${e.lane || ""}）\n` +
      ["happened", "why", "enterprise", "practitioner"].map((k) => (e[k] ? `- ${k}: ${e[k]}` : "")).filter(Boolean).join("\n") +
      (e.url ? `\n- 原文链接: ${e.url}` : "")).join("\n\n");
    const text = await callAi(env, `时间窗：过去 ${range} 天（共 ${win.length} 条上轴事件，快照 ${snap}）。\n\n${material}`);
    return jsonResp({ enabled: true, range: Number(range), snapshot: snap, total: win.length, text, cached: false });
  } catch (err) {
    return jsonResp({ enabled: true, error: `AI 调用失败：${String(err.message || err).slice(0, 300)}` }, 502);
  }
}

// ---------- 干净 URL → 静态资产映射（中文路径的 _redirects 匹配不可靠，这里用代码映射） ----------
const STATIC_MAP = {
  "/": "/world3d.html",
  "/world3d": "/world3d.html",
  "/世界动态": "/world3d.html",
  "/平面": "/world.html",
  "/落地": "/deploy.html",
  "/现场": "/field.html",
  "/方法": "/methods.html",
  "/案例": "/cases.html",
};

async function serveAsset(env, url, targetPath) {
  const assetUrl = new URL(targetPath + (url.search || ""), url.origin);
  const asset = await env.ASSETS.fetch(assetUrl);
  return new Response(asset.body, {
    status: asset.status,
    headers: asset.headers,
  });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    // 平台可能给解码后的裸 UTF-8 路径，也可能给百分编码——先原样保留，仅在含 % 时解码
    let rawPath = url.pathname.replace(/\/+$/, "") || "/";
    let path = rawPath;
    if (path.includes("%")) {
      try {
        path = decodeURIComponent(path);
      } catch {
        /* 保留原样，交给 404 */
      }
    }
    const method = (request.method || "GET").toUpperCase();

    try {
      if (path === "/api/ai-report") return await handleApiAiReport(request, env);

      if (path === "/api/me") {
        const cookies = parseCookies(request.headers.get("Cookie"));
        const user = await verifySession(env, cookies[SESSION_COOKIE]);
        return jsonResp({ user: user ? { name: user.name, avatar: user.avatar, provider: user.provider } : null });
      }

      if (path === "/logout") {
        const next = url.searchParams.get("next") || "/";
        return new Response(null, {
          status: 302,
          headers: {
            Location: next.startsWith("/") ? next : "/",
            "Set-Cookie": `${SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax`,
          },
        });
      }

      const mLogin = path.match(/^\/login\/([A-Za-z0-9]+)$/);
      const mCallback = path.match(/^\/oauth\/([A-Za-z0-9]+)\/callback$/);

      if (path === "/login") {
        const next = url.searchParams.get("next") || "/";
        return new Response(loginPageHtml(next, env, url.origin), {
          status: 200,
          headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
        });
      }

      if (mLogin) {
        const provider = mLogin[1].toLowerCase();
        const cred = providerEnv(env, provider);
        let next = url.searchParams.get("next") || "/";
        if (!next.startsWith("/")) next = "/";
        if (!cred || !cred.id || !cred.secret) {
          return new Response(loginPageHtml(next, env, url.origin), {
            status: 200, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
          });
        }
        const base = (env.IMFOAUTHBASE || url.origin).replace(/\/$/, "");
        const state = await makeState(env, next);
        const redirectUri = `${base}/oauth/${provider}/callback`;
        return new Response(null, { status: 302, headers: { Location: authorizeUrl(provider, redirectUri, state, env) } });
      }

      if (mCallback) {
        const provider = mCallback[1].toLowerCase();
        const code = url.searchParams.get("code") || "";
        const next = await verifyState(env, url.searchParams.get("state") || "");
        if (!code || !next) return textResp("登录状态失效，请重试", 400);
        const base = (env.IMFOAUTHBASE || url.origin).replace(/\/$/, "");
        const info = await fetchUser(env, provider, code, `${base}/oauth/${provider}/callback`);
        const token = await signSession(env, {
          uid: info.uid, provider, name: info.name || "", avatar: info.avatar || "",
          exp: Math.floor(Date.now() / 1000) + SESSION_TTL,
        });
        return new Response(null, {
          status: 302,
          headers: {
            Location: next || "/",
            "Set-Cookie": `${SESSION_COOKIE}=${encodeURIComponent(token)}; Path=/; Max-Age=${SESSION_TTL}; HttpOnly; SameSite=Lax`,
          },
        });
      }

      // ---- 干净 URL → 预渲染资产 ----
      if (STATIC_MAP[path] && method === "GET") {
        return await serveAsset(env, url, STATIC_MAP[path]);
      }
      let m = path.match(/^\/案例\/(\d+)$/);
      if (m && method === "GET") return await serveAsset(env, url, `/cases/${m[1]}.html`);
      m = rawPath.match(/^\/%E6%A1%88%E4%BE%8B\/(\d+)$/);
      if (m && method === "GET") return await serveAsset(env, url, `/cases/${m[1]}.html`);
      m = path.match(/^\/动态\/(\d+)$/);
      if (m && method === "GET") return await serveAsset(env, url, `/events/${m[1]}.html`);
      m = rawPath.match(/^\/%E5%8A%A8%E6%80%81\/(\d+)$/);
      if (m && method === "GET") return await serveAsset(env, url, `/events/${m[1]}.html`);
      m = path.match(/^\/方法\/([a-z0-9-]+)$/);
      if (m && method === "GET") return await serveAsset(env, url, `/methods/${m[1]}.html`);
      m = rawPath.match(/^\/%E6%96%B9%E6%B3%95\/([a-z0-9-]+)$/);
      if (m && method === "GET") return await serveAsset(env, url, `/methods/${m[1]}.html`);

      // 其余交给静态资产（world3d.html、events/、site/static/、_redirects 等）
      return await env.ASSETS.fetch(request);
    } catch (err) {
      return jsonResp({ error: String((err && err.message) || err).slice(0, 400) }, 500);
    }
  },
};
