(function () {
  var root = document.getElementById("room");
  var panel = document.getElementById("room-panel");
  var dataEl = document.getElementById("room-data");
  if (!root || !panel || !dataEl) return;

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

  function panelEvent(e) {
    var field = lens === "field";
    var fluffWhy = !e.why || /有名字、有日期|有日期、有名字|具名客户且|可作为交付现场|这是公开材料|有名字的人写的评论|有日期的演讲|有日期的一集播客|公开讨论。一帖一条|讲怎么干活的材料|这是公司自己宣布的组织变化|工程团队写怎么组这支队伍|官方新闻稿，用来对同一天|公司把「帮客户落地」写成|股东信是公司对外讲经营/.test(String(e.why));
    var fluffPrac = !e.practitioner || /Forward Deployed 头衔|驻场工程师这个岗位名|不是编制样板|不是怎么组团队|可核的是客户/.test(String(e.practitioner));
    var impact = field ? e.practitioner : e.enterprise;
    var skipImpact = field ? fluffPrac : !impact;
    var h = field ? "对你意味着什么" : "对企业意味着什么";
    var orig = e.orig_href
      ? '<a class="room-more ghost" href="' +
        esc(e.orig_href) +
        '">对照存下来的原文' +
        (e.host ? " · " + esc(e.host) : "") +
        "</a>"
      : e.url
        ? '<a class="room-more ghost" href="' +
          esc(e.url) +
          '" target="_blank" rel="noopener noreferrer">打开原文' +
          (e.host ? " · " + esc(e.host) : "") +
          "</a>"
        : '<p class="room-note">没有原文链接</p>';
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
      (fluffWhy ? "" : "<h3>为什么要看</h3><p>" + esc(e.why) + "</p>") +
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
