(function () {
  var root = document.getElementById("room");
  var panel = document.getElementById("room-panel");
  var dataEl = document.getElementById("room-data");
  if (!root || !panel || !dataEl) return;
  if (root.classList.contains("room-feed") || root.classList.contains("room-doc")) return;

  var data;
  try {
    data = JSON.parse(dataEl.textContent || "{}");
  } catch (err) {
    return;
  }
  var items = data.items || [];
  var byId = {};
  items.forEach(function (it) {
    if (it && it.id != null) byId[String(it.id)] = it;
  });
  var kind = data.kind || "event";
  var lens = data.lens || root.getAttribute("data-lens") || "boss";

  function esc(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function md(day) {
    var t = String(day || "");
    if (t.length >= 10) return Number(t.slice(5, 7)) + "-" + t.slice(8, 10);
    return t;
  }

  function close() {
    root.classList.add("room-no-panel");
    document.querySelectorAll("[data-pick].on").forEach(function (el) {
      el.classList.remove("on");
      if (el.hasAttribute("aria-pressed")) el.setAttribute("aria-pressed", "false");
    });
  }

  function facts(rows) {
    if (!rows || !rows.length) return "";
    return (
      '<dl class="room-facts">' +
      rows
        .map(function (r) {
          return "<div><dt>" + esc(r[0]) + "</dt><dd>" + esc(r[1]) + "</dd></div>";
        })
        .join("") +
      "</dl>"
    );
  }

  /* Whole-paragraph why/prac/ent templates. Unique tails after 要解决的是： stay. */
  var FLUFF_EXACT = {};
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
  ].forEach(function (s) { FLUFF_EXACT[s] = true; });
  var FLUFF_JOB_ENT = /^只能读成 .+还在招「.+」。一个岗位不等于已经做成，也不等于人已经到位。?$/;

  function fluffNorm(s) {
    return String(s || "").trim().replace(/[。.\s]+$/g, "");
  }
  function fluffHan(s) {
    var m = String(s || "").match(/[\u4e00-\u9fff]/g);
    return m ? m.length : 0;
  }
  function fluffIntro(s) {
    var t = String(s || "").trim();
    if (!t) return true;
    if (/^我们[与和]/.test(t) || /交谈，(?:了解|讨论)/.test(t) || t.indexOf("问答 请介绍") >= 0) return true;
    if (t.slice(0, 24).indexOf("客户案例研究") >= 0) return true;
    var first = t.split("。")[0];
    return (
      /由 .{2,40}创立/.test(first) ||
      /^作为.{2,24}(专家|公司|平台)/.test(first) ||
      /是一家.{0,24}(公司|初创|非营利|零售商|平台|组织)/.test(first) ||
      /是(?:一家|一个).{0,20}(零售商|非营利组织|电商平台|金融科技)/.test(first) ||
      (/是面向.{0,24}(平台|公司|组织)/.test(first) && first.indexOf("需要") < 0) ||
      (/是推动.{0,16}发展的/.test(first) && first.indexOf("需要") < 0)
    );
  }
  function fluffCopy(text) {
    var t = String(text || "").trim();
    if (!t) return true;
    var n = fluffNorm(t);
    if (FLUFF_EXACT[n]) return true;
    if (FLUFF_JOB_ENT.test(t) || FLUFF_JOB_ENT.test(n + "。")) return true;
    var parts = t.split(/要解决的是[:：]/);
    if (parts.length > 1) {
      var after = parts.slice(1).join("要解决的是：").trim();
      var nHan = fluffHan(after);
      var specific = after && !fluffIntro(after) && (nHan >= 8 || (nHan >= 6 && /[。！？!?]$/.test(after)));
      return !specific;
    }
    return false;
  }

  function panelEvent(e) {
    var field = lens === "field";
    var fluffWhy = fluffCopy(e.why);
    var fluffPrac = fluffCopy(e.practitioner);
    var fluffEnt = fluffCopy(e.enterprise);
    var impact = field ? e.practitioner : e.enterprise;
    var skipImpact = field ? fluffPrac : fluffEnt;
    var h = field ? "对你意味着什么" : "对企业意味着什么";
    var orig = "";
    var go = e.case_href && e.lane === "deploy"
      ? '<a class="room-more" href="' + esc(e.case_href) + '">看完整案例</a>'
      : "";
    var rows = [];
    if (e.host) rows.push(["来源", e.host]);
    if (e.day) rows.push(["日期", e.day]);
    if (e.doc_label) rows.push(["类型", e.doc_label]);
    return (
      '<p class="room-pk" data-lane="' +
      esc(e.lane || "") +
      '"><i></i>' +
      esc(md(e.day)) +
      (e.doc_label ? " · " + esc(e.doc_label) : "") +
      ' <button type="button" class="room-x" data-room-close aria-label="关闭">×</button></p>' +
      "<h2>" +
      esc(e.title) +
      "</h2>" +
      facts(rows) +
      orig +
      "<h3>发生了什么</h3><p>" +
      esc(e.happened || "还没写出摘要。") +
      "</p>" +
      "" +
      (skipImpact ? "" : "<h3>" + h + "</h3><p>" + esc(impact) + "</p>") +
      (!field && !fluffPrac && e.practitioner
        ? "<h3>对你意味着什么</h3><p>" + esc(e.practitioner) + "</p>"
        : "") +
      go
    );
  }

  function panelCase(c) {
    var rows = [];
    if (c.vendor) rows.push(["厂商", c.vendor]);
    if (c.evidence) rows.push(["靠不靠谱", c.evidence]);
    if (c.kpi) rows.push(["数字怎么来的", c.kpi]);
    if (c.fde === true) rows.push(["驻场团队", "原文写了"]);
    var go = c.href
      ? '<a class="room-more" href="' + esc(c.href) + '">看完整案例</a>'
      : "";
    return (
      '<p class="room-pk"><i></i>摘要' +
      ' <button type="button" class="room-x" data-room-close aria-label="关闭">×</button></p>' +
      "<h2>" +
      esc(c.title) +
      "</h2>" +
      facts(rows) +
      "<h3>这条说了什么</h3><p>" +
      esc(c.blurb || "打开全文看完整内容。") +
      "</p>" +
      go
    );
  }

  function open(id) {
    var item = byId[String(id)];
    if (!item) return;
    document.querySelectorAll("[data-pick]").forEach(function (el) {
      var on = el.getAttribute("data-pick") === String(id);
      el.classList.toggle("on", on);
      if (el.hasAttribute("aria-pressed")) el.setAttribute("aria-pressed", on ? "true" : "false");
    });
    panel.innerHTML = kind === "case" ? panelCase(item) : panelEvent(item);
    panel.scrollTop = 0;
    root.classList.remove("room-no-panel");
  }

  var initial = document.querySelector("[data-pick].on");
  if (initial) open(initial.getAttribute("data-pick"));
  else root.classList.add("room-no-panel");

  document.addEventListener("click", function (e) {
    if (e.target.closest("[data-room-close]")) {
      e.preventDefault();
      close();
      return;
    }
    var pick = e.target.closest("[data-pick]");
    if (pick && root.contains(pick)) {
      e.preventDefault();
      open(pick.getAttribute("data-pick"));
    }
  });
})();
