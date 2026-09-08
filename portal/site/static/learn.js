(function () {
  if (document.body.classList.contains("learn-list")) return;
  var dataEl = document.getElementById("learn-data");
  var panel = document.getElementById("learn-panel");
  if (!dataEl || !panel) return;

  var nodes;
  try {
    nodes = JSON.parse(dataEl.textContent || "[]");
  } catch (err) {
    return;
  }
  var bySlug = {};
  nodes.forEach(function (n) {
    if (n && n.slug) bySlug[n.slug] = n;
  });

  var root = document.getElementById("learn") || document.body;

  function esc(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function close() {
    root.classList.remove("learn-has-sel");
    document.body.classList.remove("learn-has-sel");
    panel.hidden = true;
    panel.innerHTML = "";
    document.querySelectorAll("[data-group].on").forEach(function (el) {
      el.classList.remove("on");
    });
    document.querySelectorAll("[data-node].on").forEach(function (el) {
      var keep = el.closest(".learn-strip") && el.getAttribute("aria-current") === "page";
      if (keep) return;
      el.classList.remove("on");
      el.setAttribute("aria-pressed", "false");
    });
    if (location.hash) {
      history.replaceState(null, "", location.pathname + location.search);
    }
  }

  var GROUPS = {
    eng: { name: "现场会碰到的工程题", brief: "驻场时反复出现的工程题。点开看这一课。" },
    l2: { name: "组织和生意", brief: "人放哪、怎么治理、钱怎么算。点开看这一课。" }
  };

  function openGroup(group) {
    var meta = GROUPS[group];
    if (!meta) return;
    var members = nodes.filter(function (n) { return n.group === group; });
    document.querySelectorAll("[data-group]").forEach(function (el) {
      var on = el.getAttribute("data-group") === group;
      el.classList.toggle("on", on);
    });
    document.querySelectorAll("[data-node]").forEach(function (el) {
      var stripCurrent =
        el.closest(".learn-strip") && el.getAttribute("aria-current") === "page";
      el.classList.toggle("on", !!stripCurrent);
      el.setAttribute("aria-pressed", "false");
    });
    var items = members.map(function (n) {
      var tag = n.ready ? "教程" : "还没写成课";
      return (
        '<button type="button" class="learn-p-member" data-node="' +
        esc(n.slug) +
        '"><b>' +
        esc(n.name) +
        "</b><span>" +
        tag +
        "</span></button>"
      );
    }).join("");
    panel.hidden = false;
    var allReady = members.every(function (n) { return n.ready; });
    panel.innerHTML =
      '<div class="learn-p-top"><p class="learn-p-k">' +
      (allReady ? "学习 · 教程" : "学习 · 还没写成课") +
      "</p>" +
      '<button type="button" class="learn-p-x" data-learn-close aria-label="关闭">×</button></div>' +
      "<h2>" + esc(meta.name) + "</h2>" +
      '<p class="learn-p-brief">' + esc(meta.brief) + "</p>" +
      '<div class="learn-p-members">' + items + "</div>";
    root.classList.add("learn-has-sel");
    document.body.classList.add("learn-has-sel");
    if (location.hash !== "#" + group) {
      history.replaceState(null, "", "#" + group);
    }
  }

  function open(slug) {
    var n = bySlug[slug];
    if (!n) return;
    document.querySelectorAll("[data-node]").forEach(function (el) {
      var on = el.getAttribute("data-node") === slug;
      var stripCurrent =
        el.closest(".learn-strip") && el.getAttribute("aria-current") === "page";
      el.classList.toggle("on", on || !!stripCurrent);
      el.setAttribute("aria-pressed", on ? "true" : "false");
    });
    var ready = !!n.ready;
    var kicker = ready ? "学习 · 教程" : "学习 · 还没写成课";
    var steps = (n.steps || [])
      .map(function (s) {
        return "<li>" + esc(s) + "</li>";
      })
      .join("");
    var goLabel = ready ? "开始这一课" : "先看看目录";
    var goal = n.goal
      ? "<p class=\"learn-p-goal\">" + esc(n.goal) + "</p>"
      : n.brief
        ? '<p class="learn-p-brief">' + esc(n.brief) + "</p>"
        : "";
    var brief = "";
    var stepBlock = steps
      ? '<h2 class="learn-p-h">这一步</h2><ol class="learn-p-steps">' + steps + "</ol>"
      : '<p class="learn-p-empty">这一步还没写成课。下面有练习情景和阅读材料。</p>';
    panel.hidden = false;
    panel.innerHTML =
      '<div class="learn-p-top"><p class="learn-p-k">' +
      esc(kicker) +
      '</p><button type="button" class="learn-p-x" data-learn-close aria-label="关闭">×</button></div>' +
      "<h2>" +
      esc(n.name) +
      "</h2>" +
      brief +
      goal +
      stepBlock +
      '<p class="learn-p-go"><a href="' +
      esc(n.href) +
      '">' +
      esc(goLabel) +
      "</a></p>";
    root.classList.add("learn-has-sel");
    document.body.classList.add("learn-has-sel");
    if (location.hash !== "#" + slug) {
      history.replaceState(null, "", "#" + slug);
    }
  }

  document.addEventListener("click", function (e) {
    var closer = e.target.closest("[data-learn-close]");
    if (closer) {
      e.preventDefault();
      close();
      return;
    }
    var groupBtn = e.target.closest("[data-group]");
    if (groupBtn) {
      e.preventDefault();
      openGroup(groupBtn.getAttribute("data-group"));
      return;
    }
    var btn = e.target.closest("[data-node]");
    if (!btn) return;
    var slug = btn.getAttribute("data-node");
    if (!slug || !bySlug[slug]) return;
    e.preventDefault();
    if (root.classList.contains("learn-has-sel") && btn.classList.contains("on") && location.hash === "#" + slug) {
      close();
      return;
    }
    open(slug);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") close();
  });

  var hash = (location.hash || "").replace("#", "");
  if (hash && GROUPS[hash]) openGroup(hash);
  else if (hash && bySlug[hash]) open(hash);
})();
