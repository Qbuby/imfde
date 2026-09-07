/* OpenFDE world dynamics. Local data only; no network requests. */
(function () {
  "use strict";

  var raw = document.getElementById("world-data");
  if (!raw) return;

  var DATA;
  try {
    DATA = JSON.parse(raw.textContent || "{}");
  } catch (_err) {
    return;
  }

  var board = document.getElementById("world-board");
  var lanesEl = document.getElementById("world-lanes");
  var axisEl = document.getElementById("world-axis");
  var panel = document.getElementById("world-panel");
  var ledeEl = document.querySelector("[data-world-lede]");
  var changesEl = document.getElementById("world-changes");
  var entitiesEl = document.getElementById("world-entities");
  var hitEl = document.getElementById("world-hit");
  if (!board || !lanesEl || !panel || !DATA.events) return;

  function dayZh(iso) {
    var m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return iso || "";
    return Number(m[1]) + "年" + Number(m[2]) + "月" + Number(m[3]) + "日";
  }
  function mdZh(iso) {
    var m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return iso || "";
    return Number(m[2]) + "月" + Number(m[3]) + "日";
  }

  var byId = {};
  DATA.events.forEach(function (event) {
    byId[event.id] = event;
  });

  var laneById = {};
  (DATA.lanes || []).forEach(function (lane) {
    laneById[lane.id] = lane;
  });

  var urlRange = Number((window.location.search.match(/[?&]range=(\d+)/) || [])[1]);
  var state = {
    range: [7, 30, 90].indexOf(urlRange) >= 0 ? urlRange : 30,
    lens: "boss",
    selected: (DATA.default_by_range && DATA.default_by_range["30"]) || DATA.default_id || null,
    query: "",
    hits: null,
    entTab: "company",
  };

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function parseDay(day) {
    if (!day) return null;
    var parts = String(day).split("-").map(Number);
    if (parts.length < 3 || parts.some(function (item) { return !Number.isFinite(item); })) return null;
    return Date.UTC(parts[0], parts[1] - 1, parts[2]);
  }

  function monthDay(day) {
    if (!day) return "无日期";
    return String(Number(day.slice(5, 7))) + "-" + day.slice(8, 10);
  }

  function windowBounds() {
    return {
      start: parseDay(DATA.windows[String(state.range)]),
      end: parseDay(DATA.snapshot),
    };
  }

  function tickLabel(t) {
    var d = new Date(t);
    return (d.getUTCMonth() + 1) + "-" + String(d.getUTCDate()).padStart(2, "0");
  }

  function axisRange() {
    // The axis spans exactly the server-side window (snapshot − (range−1) … snapshot),
    // so no in-window event can fall off the left edge.
    var DAY = 86400000;
    var bounds = windowBounds();
    var end = bounds.end;
    var start = bounds.start || end - (state.range - 1) * DAY;
    var ticks = [];
    if (state.range === 7) {
      for (var day = start; day <= end; day += DAY) {
        ticks.push({ t: day, label: tickLabel(day) });
      }
    } else if (state.range === 90) {
      // 1st and 15th of each month inside the window, plus the snapshot day
      var s = new Date(start);
      var sy = s.getUTCFullYear();
      var sm = s.getUTCMonth();
      var sd = s.getUTCDate();
      var cursor = new Date(sd <= 1 ? Date.UTC(sy, sm, 1) : sd <= 15 ? Date.UTC(sy, sm, 15) : Date.UTC(sy, sm + 1, 1));
      while (cursor.getTime() < end - 6 * DAY) {
        ticks.push({ t: cursor.getTime(), label: tickLabel(cursor.getTime()) });
        var year = cursor.getUTCFullYear();
        var month = cursor.getUTCMonth();
        if (cursor.getUTCDate() === 1) cursor = new Date(Date.UTC(year, month, 15));
        else cursor = new Date(Date.UTC(year, month + 1, 1));
      }
      ticks.push({ t: end, label: tickLabel(end) });
    } else {
      // weekly ticks counted back from the snapshot so the last tick is the snapshot
      for (var t = end; t >= start; t -= 7 * DAY) {
        ticks.unshift({ t: t, label: tickLabel(t) });
      }
      if (ticks[0].t - start >= 3 * DAY) ticks.unshift({ t: start, label: tickLabel(start) });
    }
    return { start: start, end: end, ticks: ticks };
  }

  function inWindow(event) {
    var day = parseDay(event.day);
    var bounds = windowBounds();
    return !!day && day >= bounds.start && day <= bounds.end;
  }

  function isMatch(event) {
    if (!state.query) return true;
    var words = state.query.toLowerCase().split(/\s+/).filter(Boolean);
    var haystack = [
      event.title,
      event.kicker,
      event.sub,
      event.host,
      event.customer,
      event.happened,
      event.why,
    ].join(" ").toLowerCase();
    return words.every(function (word) { return haystack.indexOf(word) >= 0; });
  }

  function currentEvents() {
    return DATA.events.filter(inWindow).sort(function (a, b) {
      if (a.day !== b.day) return a.day < b.day ? -1 : 1;
      return a.id - b.id;
    });
  }

  function laneIcon(lane) {
    var icon = {
      company: "landmark",
      deploy: "rocket",
      people: "user-round",
      method: "code-2",
    }[lane] || "";
    return '<span class="lane-glyph" aria-hidden="true"><img src="/static/icons/' + icon + '.svg" alt=""/></span>';
  }

  function laneLabel(lane) {
    var item = laneById[lane];
    return item && item.zh ? item.zh : "来源";
  }

  function axisTitle(event) {
    if (state.range >= 90 && event.title_short) return event.title_short;
    return event.title;
  }

  function signalRank(event) {
    if (event && event.signal === "high") return 0;
    if (event && event.signal === "mid") return 1;
    if (event && event.signal === "low") return 2;
    return 3;
  }

  function eventButton(event) {
    var selected = event.id === state.selected ? " on" : "";
    var dim = isMatch(event) ? "" : " dim";
    return (
      '<button type="button" class="ev sig-' + esc(event.signal || "mid") + selected + dim +
      '" data-id="' + esc(event.id) + '" data-lane="' + esc(event.lane) +
      '" data-kind="' + esc(event.date_kind) + '" title="' + esc(event.title) + '">' +
      '<span class="event-date">' + esc(monthDay(event.day)) + "</span>" +
      '<span class="lbl"><span class="cap">' + esc(axisTitle(event)) + "</span></span>" +
      '<i class="node" aria-hidden="true"></i></button>'
    );
  }

  function renderLanes() {
    var events = currentEvents();
    lanesEl.innerHTML = (DATA.lanes || []).map(function (lane) {
      var laneEvents = events.filter(function (event) { return event.lane === lane.id; });
      var content = laneEvents.length
        ? laneEvents.map(function (event) { return eventButton(event); }).join("")
        : '<p class="lane-empty">这 ' + state.range + " 天没有" + esc(lane.zh) + "信号</p>";
      return (
        '<div class="lane" data-lane="' + esc(lane.id) + '">' +
          '<div class="lane-label">' + laneIcon(lane.id) +
            '<span class="lane-label-copy"><span class="zh">' + esc(lane.zh) +
            '</span><span class="en">' + esc(lane.en) + '</span></span>' +
            '<span class="n">' + laneEvents.length + ' 条</span>' +
          '</div>' +
          '<div class="lane-plot" data-lane="' + esc(lane.id) + '">' + content + '</div>' +
        '</div>'
      );
    }).join("");
  }

  function packRow(items, minGap, minX, maxX) {
    if (!items.length) return;
    items.sort(function (a, b) { return a._x - b._x; });
    function spread() {
      items.forEach(function (el) { el._lx = el._x; });
      var i;
      for (i = 1; i < items.length; i += 1) {
        if (items[i]._lx < items[i - 1]._lx + minGap) items[i]._lx = items[i - 1]._lx + minGap;
      }
      if (items[items.length - 1]._lx > maxX) {
        items[items.length - 1]._lx = maxX;
        for (i = items.length - 2; i >= 0; i -= 1) {
          if (items[i]._lx > items[i + 1]._lx - minGap) items[i]._lx = items[i + 1]._lx - minGap;
        }
      }
      if (items[0]._lx < minX) {
        items[0]._lx = minX;
        for (i = 1; i < items.length; i += 1) {
          if (items[i]._lx < items[i - 1]._lx + minGap) items[i]._lx = items[i - 1]._lx + minGap;
        }
      }
    }
    spread();
    while (
      items.length > 1 &&
      (items[0]._lx < minX - 0.5 || items[items.length - 1]._lx > maxX + 0.5)
    ) {
      var dropAt = -1;
      var worst = -1;
      items.forEach(function (el, index) {
        if (Number(el.getAttribute("data-id")) === state.selected) return;
        var score = Math.abs(el._lx - el._x);
        if (score >= worst) {
          worst = score;
          dropAt = index;
        }
      });
      if (dropAt < 0) break;
      items[dropAt]._labeled = false;
      items.splice(dropAt, 1);
      spread();
    }
    items.forEach(function (el) { el._labeled = true; });
  }

  function positionNodes() {
    var bounds = axisRange();
    var span = Math.max(bounds.end - bounds.start, 86400000);
    document.querySelectorAll(".lane-plot").forEach(function (plot) {
      var plotWidth = plot.clientWidth;
      if (!plotWidth) return;
      var els = Array.prototype.slice.call(plot.querySelectorAll(".ev"));
      if (!els.length) return;
      if (window.getComputedStyle(els[0]).position !== "absolute") {
        els.forEach(function (el) {
          el.classList.remove("cap-hide");
          el.classList.remove("same-day-hide");
          el.style.removeProperty("--lbl-dx");
        });
        return;
      }

      var labelW = state.range === 7 ? 118 : state.range >= 90 ? 108 : 104;
      var minGap = labelW + (state.range >= 90 ? 6 : 8);
      var nodePad = 18;
      var labPad = Math.ceil(labelW / 2) + 8;
      var nodeMin = nodePad;
      var nodeMax = Math.max(nodeMin, plotWidth - nodePad);
      var labMin = labPad;
      var labMax = Math.max(labMin, plotWidth - labPad);

      els.forEach(function (el) {
        var event = byId[Number(el.getAttribute("data-id"))];
        var day = parseDay(event && event.day);
        var ratio = day == null ? 0 : (day - bounds.start) / span;
        el._day = (event && event.day) || "";
        el._ideal = nodeMin + Math.max(0, Math.min(1, ratio)) * (nodeMax - nodeMin);
        el._labeled = true;
        el._sameDayGroup = false;
        el._sameDayKeeper = false;
      });

      var dayGroups = {};
      els.forEach(function (el) {
        if (!dayGroups[el._day]) dayGroups[el._day] = [];
        dayGroups[el._day].push(el);
      });
      Object.keys(dayGroups).forEach(function (day) {
        var group = dayGroups[day];
        if (state.range !== 90 && group.length > 1) {
          var keeper = group.slice().sort(function (a, b) {
            var aId = Number(a.getAttribute("data-id"));
            var bId = Number(b.getAttribute("data-id"));
            if (aId === state.selected || bId === state.selected) {
              return aId === state.selected ? -1 : 1;
            }
            var aRank = signalRank(byId[aId]);
            var bRank = signalRank(byId[bId]);
            return aRank === bRank ? aId - bId : aRank - bRank;
          })[0];
          group.forEach(function (el) {
            el._sameDayGroup = true;
            el._sameDayKeeper = el === keeper;
          });
        }
        var step = group.length > 1 ? 22 : 0;
        group.forEach(function (el, index) {
          el._x = Math.max(nodeMin, Math.min(nodeMax, el._ideal + (index - (group.length - 1) / 2) * step));
          el._nudge = 0;
        });
        if (group.length > 1) {
          group.forEach(function (el, index) {
            el._nudge = index % 2 ? 1 : -1;
          });
        }
      });

      els.sort(function (a, b) {
        if (a._x !== b._x) return a._x - b._x;
        return Number(a.getAttribute("data-id")) - Number(b.getAttribute("data-id"));
      });
      for (var n = 1; n < els.length; n += 1) {
        if (els[n]._x - els[n - 1]._x >= 22) continue;
        if (els[n]._nudge && els[n - 1]._nudge) continue;
        if (!els[n - 1]._nudge) els[n - 1]._nudge = -1;
        if (!els[n]._nudge) els[n]._nudge = els[n - 1]._nudge === -1 ? 1 : -1;
      }

      // 7/30 days: two-line captions only fit in one row above the nodes (as in the design),
      // so every label shares row 0 and is packed left/right or hidden. 90 days uses
      // one-line captions, which leaves room for a second, lower row.
      var useTwoRows = state.range === 90;
      if (!useTwoRows) {
        els.forEach(function (el) { el._row = 0; });
      } else {
        var lastEnd = [-1e9, -1e9];
        els.forEach(function (el) {
          var cost0 = Math.max(0, lastEnd[0] + minGap - el._x);
          var cost1 = Math.max(0, lastEnd[1] + minGap - el._x);
          var row = el._nudge === 1 ? 1 : el._nudge === -1 ? 0 : (cost0 <= cost1 ? 0 : 1);
          el._row = row;
          lastEnd[row] = Math.max(el._x, lastEnd[row] + minGap);
        });
      }

      if (state.range === 90) {
        els.forEach(function (el) { el._lx = el._x; });
      } else {
        packRow(els.filter(function (el) { return el._row === 0; }), minGap, labMin, labMax);
      }

      var maxOff = state.range === 7 ? 48 : state.range === 90 ? 8 : 48;
      els.forEach(function (el) {
        if (el._lx == null) el._lx = el._x;
        if (el._lx > el._x + maxOff) el._lx = el._x + maxOff;
        if (el._lx < el._x - maxOff) el._lx = el._x - maxOff;
        if (el._lx > labMax) el._lx = labMax;
        if (el._lx < labMin) el._lx = labMin;
      });
      // same-day groups (7/30 days): only the keeper may carry a caption / date
      if (state.range !== 90) {
        els.forEach(function (el) {
          if (el._sameDayGroup && !el._sameDayKeeper) el._labeled = false;
        });
      }
      els.sort(function (a, b) { return a._lx - b._lx; });
      var lastTitle = [-1e9, -1e9];
      els.forEach(function (el) {
        var row = el._row || 0;
        if (el._labeled && el._lx - lastTitle[row] < minGap && Number(el.getAttribute("data-id")) !== state.selected) {
          el._labeled = false;
        }
        if (el._labeled) lastTitle[row] = el._lx;
      });
      els.sort(function (a, b) { return a._x - b._x; });
      // dates sit on the same line for both rows, so collision is checked across rows
      var lastDate = -1e9;
      els.forEach(function (el) {
        var hidden = state.range !== 90 && el._sameDayGroup && !el._sameDayKeeper;
        var hideDate = hidden || (el._x - lastDate < 30 && Number(el.getAttribute("data-id")) !== state.selected);
        el._hideDate = hideDate;
        if (!hideDate) lastDate = el._x;
      });
      els.forEach(function (el) {
        var lx = el._labeled ? el._lx : el._x;
        el.style.left = el._x.toFixed(1) + "px";
        el.style.setProperty("--lbl-dx", (lx - el._x).toFixed(1) + "px");
        el.classList.toggle("cap-down", el._row === 1);
        el.classList.toggle("node-up", el._nudge === -1);
        el.classList.toggle("node-down", el._nudge === 1);
        el.classList.toggle("cap-hide", !el._labeled);
        el.classList.toggle("same-day-hide", state.range !== 90 && el._sameDayGroup && !el._sameDayKeeper);
        el.classList.toggle("date-hide", !!el._hideDate);
        el.classList.toggle("lbl-offset", el._labeled && Math.abs(lx - el._x) > 16);
      });
    });
  }

  function renderAxis() {
    var axis = axisRange();
    var span = Math.max(axis.end - axis.start, 86400000);
    var parts = [];
    axis.ticks.forEach(function (tick, index) {
      var ratio = (tick.t - axis.start) / span;
      var last = index === axis.ticks.length - 1;
      var cls = last ? "tick end" : "tick";
      var body = last
        ? '<span class="tick-d">' + tick.label + '<i class="mark"></i></span>'
        : '<i class="mark"></i>' + tick.label;
      parts.push(
        '<span class="' + cls + '" style="left:' + (ratio * 100).toFixed(3) + '%">' + body + "</span>"
      );
    });
    axisEl.innerHTML = parts.join("");
  }

  function sourceName(event) {
    return event.entity_name || event.kicker || event.host || event.url || "";
  }

  function sourceTitle(event) {
    var name = sourceName(event);
    var title = event.title || "";
    if (!name || title.toLowerCase().indexOf(name.toLowerCase()) === 0) return title;
    return name + "：" + title;
  }

  function shortUrl(url) {
    var text = String(url || "").replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/[?#].*$/, "").replace(/\/$/, "");
    return text.length > 64 ? text.slice(0, 61) + "…" : text;
  }

  function dateCopy(event) {
    if (event.date_kind === "modified") return "页上修改日：" + event.day;
    return "原始发布日期：" + event.day;
  }

  function fieldCopy(value, fallback) {
    return value ? "<p>" + esc(value) + "</p>" : '<p class="empty-field">' + esc(fallback) + "</p>";
  }

  function panelHtml(event) {
    if (!event) return '<p class="panel-empty">选择时间轴上的节点，查看来源与影响。</p>';
    var enterprise = event.enterprise || "";
    var practitioner = event.practitioner || "";
    var fluffWhy = !event.why || /有名字、有日期|有日期、有名字|具名客户且|可作为交付现场|这是公开材料|有名字的人写的评论|有日期的演讲|有日期的一集播客|公开讨论。一帖一条|讲怎么干活的材料|这是公司自己宣布的组织变化|工程团队写怎么组这支队伍|官方新闻稿，用来对同一天|公司把「帮客户落地」写成|股东信是公司对外讲经营/.test(String(event.why));
    var fluffPrac = !practitioner || /Forward Deployed 头衔|驻场工程师这个岗位名|不是编制样板|不是怎么组团队|可核的是客户/.test(practitioner);
    var primaryTitle = state.lens === "field" ? "对干活的人意味着什么" : "对企业意味着什么";
    var primaryBody = state.lens === "field"
      ? (fluffPrac ? "" : fieldCopy(practitioner, ""))
      : (enterprise ? fieldCopy(enterprise, "") : "");
    var secondaryTitle = state.lens === "field" ? "对企业意味着什么" : "对干活的人意味着什么";
    var secondaryBody = state.lens === "field"
      ? (enterprise ? fieldCopy(enterprise, "") : "")
      : (fluffPrac ? "" : fieldCopy(practitioner, ""));
    var relatedIds = [];
    (DATA.links || []).forEach(function (link) {
      if (Number(link.from) === event.id) relatedIds.push(Number(link.to));
      else if (Number(link.to) === event.id) relatedIds.push(Number(link.from));
    });
    relatedIds = relatedIds.filter(function (id, index) {
      return relatedIds.indexOf(id) === index && byId[id];
    });
    var relatedInWindow = relatedIds.filter(function (id) { return inWindow(byId[id]); });
    var relatedShow = relatedInWindow.length ? relatedInWindow : relatedIds;
    var relatedPick = relatedShow[0] || 0;
    var caseHref = event.lane === "deploy" && (event.case_href || (event.href && event.href.indexOf("/案例/") === 0 ? event.href : ""));
    function heading(ico, title) {
      return '<h3 data-ico="' + ico + '">' + esc(title) + "</h3>";
    }
    return (
      '<div class="panel-top"><p class="panel-k">' + esc(monthDay(event.day)) + " · " + esc(laneLabel(event.lane)) +
      '</p><button type="button" class="panel-x" data-close aria-label="关闭详情"><img src="/static/icons/x.svg" alt="" aria-hidden="true"/></button></div>' +
      '<h2>' + esc(event.title) + '</h2>' +
      '<dl class="panel-facts">' +
      '<div><dt>来源</dt><dd><span class="src-pill" data-lane="' + esc(event.lane) + '">' +
      '<img class="src-pill-logo" src="' + esc(chainLogo(event)) + '" alt="" aria-hidden="true"/>' + esc(sourceName(event)) +
      '</span>' +
      (sourceName(event) !== event.host && event.host ? '<span class="src-host">' + esc(event.host) + '</span>' : '') + '</dd></div>' +
      '<div><dt>日期</dt><dd>' + esc(event.date_kind === "published" ? event.day : ("页面上写的日期 " + event.day)) + "</dd></div>" +
      "</dl>" +
      heading("talk", "发生了什么") + fieldCopy(event.happened, "还没写出摘要。") +
      (fluffWhy ? "" : heading("why", "为什么要看") + fieldCopy(event.why, "")) +
      (primaryBody ? heading(state.lens === "field" ? "person" : "org", primaryTitle) + primaryBody : "") +
      (secondaryBody ? heading(state.lens === "field" ? "org" : "person", secondaryTitle) + secondaryBody : "") +
      heading("src", "对照原文") +
      (event.orig_href
        ? '<a class="src-line" href="' + esc(event.orig_href) + '">' +
          '<b>对照存下来的原文</b>' +
          '<span class="src-url">' + esc(event.host || "") + '</span></a>'
        : event.url
          ? '<a class="src-line" href="' + esc(event.url) + '" target="_blank" rel="noopener noreferrer">' +
            '<b>打开原文</b>' +
            '<span class="src-url">' + esc(event.host || "") + '</span></a>'
          : '<p class="src-line">没有原文链接</p>') +
      (caseHref
        ? '<a class="panel-bottom-link" href="' + esc(typeof caseHref === "string" ? caseHref : event.href) + '">看完整案例 <img src="/static/icons/arrow-right.svg" alt="" aria-hidden="true"/></a>'
        : "") +
      (relatedPick
        ? '<button type="button" class="panel-related" data-pick="' + esc(relatedPick) + '"><img src="/static/icons/share-2.svg" alt="" aria-hidden="true"/>查看相关事件 (' + relatedShow.length + ")</button>"
        : "")
    );
  }

  function renderPanel() {
    panel.innerHTML = panelHtml(state.selected ? byId[state.selected] : null);
    panel.scrollTop = 0;
  }

  function chainEvents(change) {
    // Evidence chain for the current window: newest events of the change's lanes,
    // one per organisation first, shown oldest → newest. Empty window → empty chain.
    var lanes = change.lanes || [];
    var skipJobs = change.skip_jobs !== false && change.skip_jobs !== 0;
    if (change.skip_jobs === false) skipJobs = false;
    var pool = currentEvents().filter(function (event) {
      if (lanes.indexOf(event.lane) < 0) return false;
      if (skipJobs && event.info_kind === "job_posting") return false;
      return true;
    });
    var picks = [];
    var seenKey = {};
    var i;
    for (i = pool.length - 1; i >= 0 && picks.length < 3; i -= 1) {
      var key = pool[i].entity_key || pool[i].host || pool[i].id;
      if (seenKey[key]) continue;
      seenKey[key] = 1;
      picks.push(pool[i]);
    }
    for (i = pool.length - 1; i >= 0 && picks.length < 3; i -= 1) {
      if (picks.indexOf(pool[i]) < 0) picks.push(pool[i]);
    }
    return picks.sort(function (a, b) {
      if (a.day !== b.day) return a.day < b.day ? -1 : 1;
      return a.id - b.id;
    });
  }

  function chainAction(event) {
    // full title minus the org prefix; CSS ellipsis handles the truncation
    var short = event.title || event.title_short || "";
    var name = event.entity_name || event.kicker || "";
    if (name && short.indexOf(name) === 0) {
      short = short.slice(name.length).replace(/^[\s·:：\-—]+/, "");
    }
    return short || event.title;
  }

  function chainLogo(event) {
    var logo = entityLogo({ key: event.entity_key, name: event.entity_name });
    if (logo.indexOf("/brands/") >= 0) return logo;
    var icon = { company: "landmark", deploy: "rocket", people: "user-round", method: "code-2" }[event.lane] || "building-2";
    return "/static/icons/" + icon + ".svg";
  }

  function currentChanges() {
    var byRange = DATA.changes_by_range || {};
    return byRange[String(state.range)] || DATA.changes || [];
  }

  function renderChanges() {
    if (!changesEl) return;
    changesEl.innerHTML = currentChanges().map(function (change) {
      var picks = chainEvents(change);
      var chain = picks.map(function (event) {
        var on = event.id === state.selected ? " on" : "";
        return (
          '<button type="button" class="chain-card' + on + '" data-pick="' + esc(event.id) + '" data-lane="' + esc(event.lane) +
          '" title="' + esc(event.title) + '">' +
          '<span class="cc-av" aria-hidden="true"><img src="' + esc(chainLogo(event)) + '" alt=""/></span>' +
          '<span class="cc-body"><b>' + esc(event.entity_name || event.kicker || event.host) + '</b>' +
          '<time>' + esc(monthDay(event.day)) + '</time>' +
          '<small>' + esc(chainAction(event)) + '</small></span></button>'
        );
      }).join('<img class="chain-arrow" src="/static/icons/arrow-right.svg" alt="" aria-hidden="true"/>');
      var lanes = change.lanes || [];
      var total = chainEvents(change).length ? currentEvents().filter(function (event) {
        if (lanes.indexOf(event.lane) < 0) return false;
        if (change.skip_jobs !== false && event.info_kind === "job_posting") return false;
        return true;
      }).length : 0;
      return (
        '<li><span class="change-num">' + esc(change.num) + '</span><div><h3>' + esc(change.title) +
        '</h3><p>' + esc(change.body) + '</p><div class="chain">' + (chain || '<span class="chain-empty">这 ' + state.range + ' 天窗口内没有对应信号</span>') +
        '<span class="n">窗口内 ' + esc(total) + ' 条信号</span></div></div></li>'
      );
    }).join("");
  }

  function sparkSvg(values) {
    var list = values.length ? values : [0, 0, 0, 0, 0, 0];
    var max = Math.max.apply(null, list.concat([1]));
    var points = list.map(function (value, index) {
      var x = 1 + index * (56 / Math.max(1, list.length - 1));
      var y = 18 - (value / max) * 13;
      return x.toFixed(1) + "," + y.toFixed(1);
    }).join(" ");
    return '<svg class="spark" viewBox="0 0 58 20" aria-hidden="true"><polyline points="' + points + '" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>';
  }

  function normalizeEntity(value) {
    return String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  function entityLogo(seed) {
    var logos = {
      openai: "openai",
      palantir: "palantir",
      shopify: "shopify",
      netflix: "netflix",
      linear: "linear",
    };
    var values = [normalizeEntity(seed && seed.key), normalizeEntity(seed && seed.name)];
    for (var index = 0; index < values.length; index += 1) {
      if (logos[values[index]]) return "/static/icons/brands/" + logos[values[index]] + ".svg";
    }
    return "/static/icons/building-2.svg";
  }

  function entityItems() {
    var events = currentEvents();
    var seeds = (DATA.entities || []).filter(function (item) { return item.tab === state.entTab; });
    return seeds.map(function (seed) {
      var ids = seed.event_ids || [];
      var hits = events.filter(function (event) { return ids.indexOf(event.id) >= 0; });
      if (!hits.length) return null;
      var byMonth = [0, 0, 0, 0, 0, 0];
      hits.forEach(function (event) {
        var t = parseDay(event.day);
        var start = windowBounds().start;
        var slot = Math.floor(((t - start) / Math.max(86400000, windowBounds().end - start)) * 6);
        byMonth[Math.max(0, Math.min(5, slot))] += 1;
      });
      var last = hits.slice().sort(function (a, b) { return a.day < b.day ? 1 : -1; })[0];
      var age = Math.max(0, Math.round((parseDay(DATA.snapshot) - parseDay(last.day)) / 86400000));
      return { seed: seed, hits: hits, values: byMonth, last: last, age: age };
    }).filter(Boolean).sort(function (a, b) {
      if (a.hits.length !== b.hits.length) return b.hits.length - a.hits.length;
      return a.seed.name.localeCompare(b.seed.name);
    }).slice(0, 6);
  }

  function renderEntities() {
    if (!entitiesEl) return;
    var rows = entityItems();
    if (!rows.length) {
      entitiesEl.innerHTML = '<p class="ent-empty">该窗口没有带明确日期的实体。</p>';
      return;
    }
    entitiesEl.innerHTML = rows.map(function (row) {
      var label = row.age === 0 ? mdZh(DATA.snapshot) : row.age + " 天前";
      var logo = entityLogo(row.seed);
      return '<button type="button" class="ent-row" data-entkey="' + esc(row.seed.key) + '">' +
        '<span class="av" aria-hidden="true"><img src="' + esc(logo) + '" alt=""/></span>' +
        '<span class="nm">' + esc(row.seed.name) + '</span>' + sparkSvg(row.values) +
        '<span class="n">' + esc(row.hits.length) + '↑</span><span class="ago">' + esc(label) + '</span></button>';
    }).join("");
  }

  function updateLede() {
    if (!ledeEl) return;
    var ledes = DATA.ledes || {};
    if (ledes[String(state.range)]) {
      ledeEl.textContent = ledes[String(state.range)];
    }
    var changeNote = document.querySelector(".below-col.changes .below-note");
    if (changeNote) {
      changeNote.textContent = "基于最近 " + state.range + " 天的判断";
    }
    var winEl = document.querySelector("[data-world-window]");
    if (winEl && DATA.windows) {
      var start = DATA.windows[String(state.range)] || "";
      winEl.innerHTML = "最近 " + state.range + " 天（" + esc(dayZh(start)) + " – " + esc(dayZh(DATA.snapshot)) + "）<br/>北京时间<br/><a class=\"foot-link\" href=\"/落地\">负责人</a> · <a class=\"foot-link\" href=\"/现场\">从业者</a> · <a class=\"foot-link\" href=\"/方法\">学习</a>";
    }
  }

  function paint() {
    if (board) {
      board.classList.toggle("range-dense", state.range >= 90);
      board.classList.toggle("range-week", state.range === 7);
    }
    var events = currentEvents();
    var inWindow = state.selected && events.some(function (event) { return event.id === state.selected; });
    if (!inWindow) {
      var fallback = DATA.default_by_range && DATA.default_by_range[String(state.range)];
      if (fallback && events.some(function (event) { return event.id === fallback; })) {
        state.selected = fallback;
      } else {
        state.selected = events.length ? events[events.length - 1].id : null;
      }
    }
    updateLede();
    renderLanes();
    renderAxis();
    renderPanel();
    renderChanges();
    renderEntities();
    requestAnimationFrame(function () {
      positionNodes();
      drawAreas();
      drawLinks();
    });
  }

  function drawAreas() {
    // Density "mountains" behind each lane: a kernel sum over the positioned nodes,
    // weighted by signal strength. Pure visualisation of where signals cluster in time.
    var NS = "http://www.w3.org/2000/svg";
    var weight = { high: 1, mid: 0.7, low: 0.45 };
    document.querySelectorAll(".lane-plot").forEach(function (plot) {
      var svg = plot.querySelector(".lane-area");
      if (!svg) {
        svg = document.createElementNS(NS, "svg");
        svg.setAttribute("class", "lane-area");
        svg.setAttribute("aria-hidden", "true");
        plot.insertBefore(svg, plot.firstChild);
      }
      var w = plot.clientWidth;
      var h = plot.clientHeight;
      var els = Array.prototype.slice.call(plot.querySelectorAll(".ev"));
      if (!w || !h || !els.length || window.getComputedStyle(els[0]).position !== "absolute") {
        svg.innerHTML = "";
        return;
      }
      svg.setAttribute("viewBox", "0 0 " + w + " " + h);
      svg.setAttribute("width", w);
      svg.setAttribute("height", h);
      var lane = plot.getAttribute("data-lane") || "lane";
      var pts = els.map(function (el) {
        var event = byId[Number(el.getAttribute("data-id"))] || {};
        return { x: parseFloat(el.style.left) || 0, w: weight[event.signal] || 0.7 };
      });
      var sigma = Math.max(22, w * (state.range === 7 ? 0.06 : state.range === 90 ? 0.025 : 0.035));
      var step = 4;
      var values = [];
      var peak = 0;
      var x;
      for (x = 0; x <= w; x += step) {
        var v = 0;
        pts.forEach(function (p) {
          var d = (x - p.x) / sigma;
          v += p.w * Math.exp(-0.5 * d * d);
        });
        values.push(v);
        if (v > peak) peak = v;
      }
      var top = h * 0.42;
      var base = h - 1;
      var scale = (base - top) / Math.max(1.6, peak);
      var line = [];
      values.forEach(function (v, index) {
        line.push((index * step).toFixed(1) + " " + (base - v * scale).toFixed(1));
      });
      var ridge = "M" + line.join(" L");
      var area = ridge + " L" + w + " " + base + " L0 " + base + " Z";
      var gid = "la-" + lane;
      svg.innerHTML =
        '<defs><linearGradient id="' + gid + '" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0" stop-color="currentColor" stop-opacity="0.26"/>' +
        '<stop offset="1" stop-color="currentColor" stop-opacity="0.02"/></linearGradient></defs>' +
        '<path class="la-fill" d="' + area + '" fill="url(#' + gid + ')"/>' +
        '<path class="la-ridge" d="' + ridge + '"/>';
    });
  }

  function drawLinks() {
    var svg = document.getElementById("world-links");
    var boardEl = document.getElementById("world-board");
    if (!svg || !boardEl) return;
    var width = boardEl.clientWidth;
    var height = boardEl.clientHeight;
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("width", width);
    svg.setAttribute("height", height);
    var origin = boardEl.getBoundingClientRect();
    var nodes = {};
    boardEl.querySelectorAll(".ev").forEach(function (item) {
      var node = item.querySelector(".node") || item;
      var box = node.getBoundingClientRect();
      nodes[item.getAttribute("data-id")] = {
        x: box.left + box.width / 2 - origin.left,
        y: box.top + box.height / 2 - origin.top,
      };
    });
    var parts = [];
    var seen = {};
    var links = [];
    function addLink(fromId, toId, kind, lane) {
      if (fromId === toId) return;
      if (!nodes[String(fromId)] || !nodes[String(toId)]) return;
      var key = fromId + ">" + toId;
      if (seen[key]) return;
      seen[key] = 1;
      links.push({ from: fromId, to: toId, kind: kind || "indirect", lane: lane || "company" });
    }
    (DATA.links || []).forEach(function (link) {
      var fromEvent = byId[link.from] || {};
      addLink(link.from, link.to, link.kind, fromEvent.lane);
    });
    if (state.range < 90) {
      (DATA.lanes || []).forEach(function (lane) {
        var seq = currentEvents().filter(function (event) { return event.lane === lane.id; });
        for (var i = 1; i < seq.length; i += 1) {
          addLink(seq[i - 1].id, seq[i].id, "indirect", lane.id);
        }
      });
    }
    links.forEach(function (link) {
      var from = nodes[String(link.from)];
      var to = nodes[String(link.to)];
      var dx = to.x - from.x;
      var lift = Math.max(18, Math.min(36, Math.abs(dx) * 0.12 + 14));
      if (Math.abs(to.y - from.y) > 20) lift = Math.min(36, Math.max(lift, Math.abs(to.y - from.y) * 0.28));
      var c1y = Math.max(10, from.y - lift);
      var c2y = Math.max(10, to.y - lift * 0.45);
      var on = state.selected && (Number(link.from) === state.selected || Number(link.to) === state.selected);
      var d = "M" + from.x.toFixed(1) + " " + from.y.toFixed(1) +
        " C " + (from.x + dx * 0.32).toFixed(1) + " " + c1y.toFixed(1) +
        ", " + (to.x - dx * 0.28).toFixed(1) + " " + c2y.toFixed(1) +
        ", " + to.x.toFixed(1) + " " + to.y.toFixed(1);
      parts.push('<path class="lk-' + esc(link.lane) + " lk-" + esc(link.kind) + (on ? " lk-on" : "") + '" d="' + d + '"/>');
    });
    svg.innerHTML = parts.join("");
  }

  document.querySelectorAll(".range button").forEach(function (button) {
    var initial = Number(button.getAttribute("data-range")) === state.range;
    button.classList.toggle("on", initial);
    button.setAttribute("aria-pressed", initial ? "true" : "false");
    button.addEventListener("click", function () {
      state.range = Number(button.getAttribute("data-range"));
      document.querySelectorAll(".range button").forEach(function (other) {
        var active = other === button;
        other.classList.toggle("on", active);
        other.setAttribute("aria-pressed", active ? "true" : "false");
      });
      paint();
    });
  });

  document.querySelectorAll("[data-lens]").forEach(function (button) {
    button.addEventListener("click", function () {
      state.lens = button.getAttribute("data-lens");
      document.querySelectorAll("[data-lens]").forEach(function (other) {
        var active = other === button;
        other.classList.toggle("on", active);
        other.setAttribute("aria-pressed", active ? "true" : "false");
      });
      renderPanel();
    });
  });

  document.querySelectorAll("[data-ent]").forEach(function (button) {
    button.addEventListener("click", function () {
      state.entTab = button.getAttribute("data-ent");
      document.querySelectorAll("[data-ent]").forEach(function (other) {
        var active = other === button;
        other.classList.toggle("on", active);
        other.setAttribute("aria-selected", active ? "true" : "false");
      });
      renderEntities();
    });
  });

  var ask = document.getElementById("world-ask");
  if (ask) {
    ask.addEventListener("submit", function (event) {
      event.preventDefault();
      var input = document.getElementById("world-q");
      state.query = (input ? input.value : "").trim();
      state.hits = currentEvents().filter(isMatch);
      if (state.query && state.hits.length) state.selected = state.hits[0].id;
      if (hitEl) {
        hitEl.hidden = !state.query;
        hitEl.textContent = state.query
          ? "找到 " + state.hits.length + " 条有日期的来源，已打开第一条。"
          : "";
      }
      paint();
    });
  }

  document.addEventListener("click", function (event) {
    var close = event.target.closest("[data-close]");
    if (close) {
      state.selected = null;
      paint();
      return;
    }
    var pick = event.target.closest("[data-pick]");
    if (pick) {
      state.selected = Number(pick.getAttribute("data-pick"));
      paint();
      return;
    }
    var node = event.target.closest(".ev");
    if (node) {
      state.selected = Number(node.getAttribute("data-id"));
      paint();
      return;
    }
    var entity = event.target.closest("[data-entkey]");
    if (entity) {
      var key = entity.getAttribute("data-entkey");
      var seed = (DATA.entities || []).find(function (item) { return item.tab === state.entTab && item.key === key; });
      var ids = seed ? seed.event_ids || [] : [];
      var hit = currentEvents().find(function (item) { return ids.indexOf(item.id) >= 0; });
      if (hit) {
        state.selected = hit.id;
        paint();
      }
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      state.selected = null;
      paint();
    }
  });

  var resizeTimer = 0;
  window.addEventListener("resize", function () {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(function () {
      positionNodes();
      drawAreas();
      drawLinks();
    }, 80);
  });

  paint();
})();
