/* 萬縷千絲 · 資料織錦 — 互動腳本（無外部依賴） */
(function () {
  "use strict";
  var doc = document, root = doc.documentElement, body = doc.body;
  var ROOT = body.getAttribute("data-root") || "";
  var UP = body.getAttribute("data-up") || "";
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  var reduceMotion = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  function $(s, el) { return (el || doc).querySelector(s); }
  function $$(s, el) { return Array.prototype.slice.call((el || doc).querySelectorAll(s)); }
  function norm(s) { return (s || "").toLowerCase().replace(/\s+/g, ""); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function params() { return new URLSearchParams(location.search); }
  function setParam(k, v) {
    if (!history.replaceState) return;
    var sp = params();
    if (v) sp.set(k, v); else sp.delete(k);
    var qs = sp.toString();
    history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
  }
  function readJSON(id) { var el = doc.getElementById(id); if (!el) return null; try { return JSON.parse(el.textContent); } catch (e) { return null; } }

  /* ---------- 明暗、選單、語言、回到頂部 ---------- */
  $$("[data-theme-toggle]").forEach(function (b) {
    b.addEventListener("click", function () {
      var next = root.dataset.theme === "light" ? "dark" : "light";
      root.dataset.theme = next; store.set("fw.theme", next);
    });
  });
  var menuBtn = $("[data-menu]"), nav = $("#site-nav");
  if (menuBtn && nav) {
    menuBtn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    doc.addEventListener("click", function (e) {
      if (nav.classList.contains("open") && !nav.contains(e.target) && !menuBtn.contains(e.target)) { nav.classList.remove("open"); menuBtn.setAttribute("aria-expanded", "false"); }
    });
  }
  $$("[data-lang-link]").forEach(function (a) {
    a.addEventListener("click", function () { a.href = a.href.split("#")[0].split("?")[0] + location.search + location.hash; });
  });
  var toTop = $("[data-to-top]");
  if (toTop) {
    var onScroll = function () { toTop.classList.toggle("show", window.scrollY > 900); };
    window.addEventListener("scroll", onScroll, { passive: true }); onScroll();
    toTop.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" }); });
  }
  var reveals = $$(".reveal");
  if (reveals.length && "IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
    }, { rootMargin: "0px 0px -8% 0px" });
    reveals.forEach(function (el) { io.observe(el); });
  } else { reveals.forEach(function (el) { el.classList.add("in"); }); }

  /* ---------- 篩選（搜尋＋按鈕群組＋卡片／表格） ---------- */
  $$("[data-filter-scope]").forEach(function (scope) {
    var input = $("[data-filter-text]", scope), countEl = $("[data-filter-count]", scope), empty = $("[data-filter-empty]", scope);
    var groups = $$("[data-filter-group]", scope), items = $$("[data-item]", scope), state = {};
    var hay = items.map(function (el) { return norm((el.getAttribute("data-text") || "") + " " + (el.getAttribute("data-alt") || "")); });
    var urlKeys = (scope.getAttribute("data-url-params") || "").split(" ").filter(Boolean);
    function visibleSet() { return scope.classList.contains("view-table") ? "table" : "cards"; }
    function apply() {
      var q = norm(input ? input.value : ""), terms = q ? q.split(/[,，、]/).filter(Boolean) : [];
      items.forEach(function (el, i) {
        var ok = terms.every(function (t) { return hay[i].indexOf(t) !== -1; });
        if (ok) for (var k in state) {
          if (!state[k]) continue;
          if ((el.getAttribute("data-" + k) || "").split(" ").indexOf(state[k]) === -1) { ok = false; break; }
        }
        el.hidden = !ok;
      });
      var mode = visibleSet(), shown = 0;
      items.forEach(function (el) {
        var inTable = !!el.closest(".only-table"), inCards = !!el.closest(".only-cards");
        if (el.hidden) return;
        if ((mode === "table" && inCards) || (mode === "cards" && inTable)) return;
        shown++;
      });
      $$("[data-filter-section]", scope).forEach(function (sec) { sec.hidden = !$$("[data-item]", sec).some(function (el) { return !el.hidden; }); });
      $$("[data-filter-section-row]", scope).forEach(function (row) {
        var n = row.nextElementSibling, any = false;
        while (n && !n.hasAttribute("data-filter-section-row")) { if (!n.hidden) any = true; n = n.nextElementSibling; }
        row.hidden = !any;
      });
      if (countEl) countEl.textContent = shown;
      if (empty) empty.classList.toggle("show", shown === 0);
    }
    function setGroup(g, value) {
      state[g.getAttribute("data-filter-group")] = value;
      $$("button[data-value]", g).forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-value") === value ? "true" : "false"); });
    }
    groups.forEach(function (g) {
      g.addEventListener("click", function (e) {
        var b = e.target.closest("button[data-value]"); if (!b) return;
        var key = g.getAttribute("data-filter-group"), v = b.getAttribute("data-value");
        if (v && state[key] === v) v = "";
        setGroup(g, v); apply();
        if (urlKeys.indexOf(key) !== -1) setParam(key, v);
      });
    });
    if (input) { var t; input.addEventListener("input", function () { clearTimeout(t); t = setTimeout(apply, 60); }); }
    var sp = params();
    groups.forEach(function (g) {
      var key = g.getAttribute("data-filter-group"), v = sp.get(key);
      if (v && $('button[data-value="' + v + '"]', g)) setGroup(g, v);
    });
    if (sp.get("q") && input) input.value = sp.get("q");
    var viewBtns = $$(".view-toggle button", scope);
    if (viewBtns.length) {
      var vkey = "fw.view." + (scope.getAttribute("data-view-scope") || "x");
      var setView = function (v) {
        scope.classList.toggle("view-table", v === "table"); scope.classList.toggle("view-cards", v !== "table");
        viewBtns.forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-view") === v ? "true" : "false"); });
        apply();
      };
      viewBtns.forEach(function (b) { b.addEventListener("click", function () { var v = b.getAttribute("data-view"); setView(v); store.set(vkey, v); }); });
      setView(store.get(vkey) || (scope.classList.contains("view-table") ? "table" : "cards"));
    } else apply();
  });

  /* ---------- 可排序表格 ---------- */
  $$("table[data-sortable]").forEach(function (table) {
    var tbody = table.tBodies[0];
    $$("th[data-sort-key]", table).forEach(function (th) {
      th.tabIndex = 0;
      var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
      var sort = function () {
        var curSort = th.getAttribute("aria-sort");
        var asc = curSort ? curSort !== "ascending" : !th.hasAttribute("data-num");
        $$("th", table).forEach(function (o) { o.removeAttribute("aria-sort"); });
        th.setAttribute("aria-sort", asc ? "ascending" : "descending");
        var rows = $$("tr", tbody), num = th.hasAttribute("data-num");
        rows.sort(function (a, b) {
          var ca = a.children[idx], cb = b.children[idx];
          var va = ca.hasAttribute("data-v") ? ca.getAttribute("data-v") : ca.textContent.trim();
          var vb = cb.hasAttribute("data-v") ? cb.getAttribute("data-v") : cb.textContent.trim();
          var r = num || (ca.hasAttribute("data-v") && !isNaN(+va)) ? (+va) - (+vb) : va.localeCompare(vb, "zh");
          return asc ? r : -r;
        });
        rows.forEach(function (r) { tbody.appendChild(r); });
      };
      th.addEventListener("click", sort);
      th.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sort(); } });
    });
  });

  /* ---------- 錨點高亮 ---------- */
  function flashHash() {
    var h = decodeURIComponent(location.hash.slice(1)); if (!h) return;
    var el = doc.getElementById(h); if (!el) return;
    el.classList.add("flash"); setTimeout(function () { el.classList.remove("flash"); }, 1600);
  }
  window.addEventListener("hashchange", flashHash); setTimeout(flashHash, 300);

  /* ---------- 全站搜尋 ---------- */
  var finder = $("#finder"), fInput = $("[data-finder-input]"), fList = $("[data-finder-list]"), index = null, results = [], sel = 0;
  function loadIndex() {
    if (index) return Promise.resolve(index);
    return fetch(UP + "search.json").then(function (r) { return r.json(); }).then(function (d) { index = d; return d; }).catch(function () { index = []; return index; });
  }
  function render() {
    if (!index) return;
    var q = norm(fInput.value);
    if (!q) results = index.filter(function (x) { return x.f; }).slice(0, 8);
    else results = index.map(function (x) {
      var t = norm(x.t), k = norm(x.k);
      return [t === q ? 0 : t.indexOf(q) === 0 ? 1 : t.indexOf(q) !== -1 ? 2 : k.indexOf(q) !== -1 ? 3 : 9, x];
    }).filter(function (p) { return p[0] < 9; }).sort(function (a, b) { return a[0] - b[0]; }).slice(0, 40).map(function (p) { return p[1]; });
    sel = 0;
    if (!results.length) { fList.innerHTML = '<li class="none">' + esc(fList.getAttribute("data-none")) + "</li>"; return; }
    fList.innerHTML = results.map(function (x, i) {
      var pic = x.i ? '<img src="' + ROOT + esc(x.i) + '" alt="" loading="lazy">' : '<span class="ph">' + esc(x.t.charAt(0)) + "</span>";
      return '<li><a href="' + UP + esc(x.u) + '" role="option" aria-selected="' + (i === 0) + '">' + pic + "<span><b>" + esc(x.t) + "</b><small>" + esc(x.s || "") + '</small></span><span class="kind">' + esc(x.c) + "</span></a></li>";
    }).join("");
  }
  function move(d) {
    var links = $$("a", fList); if (!links.length) return;
    sel = (sel + d + links.length) % links.length;
    links.forEach(function (a, i) { a.setAttribute("aria-selected", i === sel ? "true" : "false"); });
    links[sel].scrollIntoView({ block: "nearest" });
  }
  function openFinder() {
    if (!finder) return;
    if (typeof finder.showModal === "function") finder.showModal(); else finder.setAttribute("open", "");
    fInput.value = ""; loadIndex().then(render);
    setTimeout(function () { fInput.focus(); }, 30);
  }
  if (finder) {
    $$("[data-open-finder]").forEach(function (b) { b.addEventListener("click", openFinder); });
    fInput.addEventListener("input", render);
    fInput.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      else if (e.key === "Enter") { var a = $$("a", fList)[sel]; if (a) { e.preventDefault(); finder.close(); location.href = a.href; } }
    });
    fList.addEventListener("click", function (e) { if (e.target.closest("a")) finder.close(); });
    finder.addEventListener("click", function (e) { if (e.target === finder) finder.close(); });
    doc.addEventListener("keydown", function (e) {
      var tag = (e.target.tagName || "").toLowerCase(), typing = tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable;
      if ((e.key === "/" && !typing) || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k")) { e.preventDefault(); if (!finder.open) openFinder(); }
    });
  }

  /* ---------- 招募規劃 ---------- */
  var planner = $("[data-planner]");
  if (planner) {
    var KEY = "fw.recruit.v1", done = {};
    try { done = JSON.parse(store.get(KEY) || "{}") || {}; } catch (e) { done = {}; }
    var tabs = $$(".rp", planner), panels = $$("[data-route-panel]", planner);
    var pText = $("[data-planner-text]", planner), pRenown = $("[data-renown]", planner), pHide = $("[data-hide-done]", planner);
    var cur = tabs[0].getAttribute("data-route");
    var save = function () { store.set(KEY, JSON.stringify(done)); };
    $$("input[data-done]", planner).forEach(function (cb) {
      var k = cb.getAttribute("data-done").split(":");
      cb.checked = !!(done[k[0]] && done[k[0]].indexOf(k[1]) !== -1);
      cb.addEventListener("change", function () {
        var list = done[k[0]] = done[k[0]] || [];
        var i = list.indexOf(k[1]);
        if (cb.checked && i === -1) list.push(k[1]); if (!cb.checked && i !== -1) list.splice(i, 1);
        save(); refresh();
      });
    });
    var refresh = function () {
      var q = norm(pText.value), lim = +pRenown.value, hide = pHide.checked;
      panels.forEach(function (p) {
        var active = p.getAttribute("data-route-panel") === cur;
        p.hidden = !active;
        if (!active) return;
        var rows = $$("[data-row]", p), shown = 0, nDone = 0;
        rows.forEach(function (r) {
          var cb = $("input[data-done]", r), isDone = cb && cb.checked;
          r.classList.toggle("is-done", !!isDone); if (isDone) nDone++;
          var ok = (+r.getAttribute("data-renown") <= lim) && (!q || norm(r.getAttribute("data-text")).indexOf(q) !== -1) && !(hide && isDone);
          r.hidden = !ok; if (ok) shown++;
        });
        $("[data-planner-empty]", p).classList.toggle("show", shown === 0);
        $("[data-done-count]", planner).textContent = nDone;
        $("[data-total-count]", planner).textContent = rows.length;
      });
      tabs.forEach(function (t) { t.setAttribute("aria-selected", t.getAttribute("data-route") === cur ? "true" : "false"); });
    };
    tabs.forEach(function (t) { t.addEventListener("click", function () { cur = t.getAttribute("data-route"); setParam("route", cur); store.set("fw.recruit.route", cur); refresh(); }); });
    [pText, pRenown, pHide].forEach(function (el) { el.addEventListener(el === pText ? "input" : "change", refresh); });
    var want = params().get("route") || store.get("fw.recruit.route");
    if (want && tabs.some(function (t) { return t.getAttribute("data-route") === want; })) cur = want;
    var r0 = store.get("fw.recruit.renown"); if (r0) pRenown.value = r0;
    pRenown.addEventListener("change", function () { store.set("fw.recruit.renown", pRenown.value); });
    refresh();
  }

  /* ---------- 成長模擬 ---------- */
  var calc = $("[data-calc]"), cdata = readJSON("calc-data");
  if (calc && cdata) {
    var su = $("[data-calc-unit]", calc), sc = $("[data-calc-class]", calc), out = $("[data-calc-out]", calc);
    var U = {}, C = {}; cdata.units.forEach(function (u) { U[u.id] = u; }); cdata.classes.forEach(function (c) { C[c.id] = c; });
    var draw = function () {
      var u = U[su.value], c = C[sc.value]; if (!u || !c) return;
      var total = 0, rows = cdata.stats.map(function (label, i) {
        var b = u.g[i], k = c.g[i], t = Math.max(0, b + k); total += t;
        var bw = Math.min(b, 100), kw = Math.max(0, Math.min(k, 100 - bw));
        return '<div class="calc-row" style="--c:' + u.c + '"><span class="l">' + esc(label) + '</span><span class="track"><i class="base" style="width:' + bw + '%"></i>' + (k > 0 ? '<i class="cls" style="width:' + kw + '%"></i>' : "") + "</span><b>" + t + "%" + (k ? '<small class="' + (k < 0 ? "neg" : "") + '">' + b + (k > 0 ? " + " + k : " − " + (-k)) + "</small>" : "<small>" + b + "</small>") + "</b></div>";
      }).join("");
      out.innerHTML = '<div class="calc-legend"><span><i style="background:' + u.c + '"></i>' + esc(u.n) + '</span><span><i style="background:var(--jade)"></i>' + esc(c.n) + "加成</span></div>" + rows + '<div class="calc-sum"><span class="hint">合计</span><b>' + total + "</b></div>";
      setParam("unit", su.value); setParam("class", sc.value);
    };
    var p = params();
    if (p.get("unit") && U[p.get("unit")]) su.value = p.get("unit");
    if (p.get("class") && C[p.get("class")]) sc.value = p.get("class");
    else { var def = cdata.classes.filter(function (c) { return c.t === "最上级"; })[0]; if (def) sc.value = def.id; }
    su.addEventListener("change", draw); sc.addEventListener("change", draw); draw();
  }

  /* ---------- 羈絆輪盤 ---------- */
  var bonds = $("[data-bonds]"), bdata = readJSON("bond-data");
  if (bonds && bdata) {
    var B = {}; bdata.units.forEach(function (u) { B[u.id] = u; });
    var nodes = $("[data-wheel-nodes]", bonds), lines = $("[data-wheel-lines]", bonds), side = $("[data-bond-side]", bonds);
    var picks = $$("[data-pick]", bonds), filter = $("[data-bond-filter]", bonds);
    var ava = function (u, cls, x, y, title) {
      var inner = u.a ? '<img src="' + ROOT + "assets/" + esc(u.a) + '" alt="">' : "<i>" + esc(u.n.charAt(0)) + "</i>";
      return '<a class="wnode ' + cls + '" href="' + UP + "unit/" + esc(u.id) + '.html" data-wpick="' + esc(u.id) + '" title="' + esc(title || u.n) + '" style="--c:' + u.c + ";left:" + x + "%;top:" + y + '%">' + inner + "</a>";
    };
    var show = function (id) {
      var u = B[id]; if (!u) return;
      var rings = { A: 22, B: 34, C: 46 }, html = ava(u, "center", 50, 50), svg = "";
      ["A", "B", "C"].forEach(function (rk) {
        var group = u.s.filter(function (s) { return s[1] === rk; });
        group.forEach(function (s, i) {
          var p2 = B[s[0]]; if (!p2) return;
          var ang = (i / group.length) * Math.PI * 2 - Math.PI / 2 + (rk === "B" ? .25 : rk === "C" ? .5 : 0);
          var x = 50 + rings[rk] * Math.cos(ang), y = 50 + rings[rk] * Math.sin(ang);
          html += ava(p2, rk, x.toFixed(2), y.toFixed(2), p2.n + " · " + rk);
          svg += '<line class="' + rk + '" x1="50" y1="50" x2="' + x.toFixed(2) + '" y2="' + y.toFixed(2) + '"/>';
        });
      });
      nodes.innerHTML = html;
      lines.innerHTML = '<svg viewBox="0 0 100 100" preserveAspectRatio="none">' + svg + "</svg>";
      var count = function (rk) { return u.s.filter(function (s) { return s[1] === rk; }).length; };
      var groupHtml = ["A", "B", "C"].map(function (rk) {
        var ms = u.s.filter(function (s) { return s[1] === rk; }).map(function (s) { return B[s[0]]; }).filter(Boolean);
        if (!ms.length) return "";
        return '<div class="sup-row"><span class="rank r' + rk + '">' + rk + '</span><div class="avas">' + ms.map(function (m) {
          return '<a class="ava" href="' + UP + "unit/" + esc(m.id) + '.html" style="--c:' + m.c + '">' + (m.a ? '<img src="' + ROOT + "assets/" + esc(m.a) + '" alt="">' : "<i>" + esc(m.n.charAt(0)) + "</i>") + "<span>" + esc(m.n) + "</span></a>";
        }).join("") + "</div></div>";
      }).join("");
      side.innerHTML = '<span class="facn">' + esc(u.f) + '</span><h3 class="gold-text">' + esc(u.n) + '</h3><div class="counts"><span><span class="rank rA">A</span><b>' + count("A") + '</b></span><span><span class="rank rB">B</span><b>' + count("B") + '</b></span><span><span class="rank rC">C</span><b>' + count("C") + "</b></span></div>" + groupHtml + '<a class="btn small" href="' + UP + "unit/" + esc(u.id) + '.html">角色资料 →</a>';
      picks.forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-pick") === id ? "true" : "false"); });
      setParam("unit", id);
    };
    picks.forEach(function (b) { b.addEventListener("click", function () { show(b.getAttribute("data-pick")); if (window.innerWidth < 900) bonds.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" }); }); });
    nodes.addEventListener("click", function (e) {
      var a = e.target.closest("[data-wpick]"); if (!a || a.classList.contains("center")) return;
      e.preventDefault(); show(a.getAttribute("data-wpick"));
    });
    $$("[data-pick-link]").forEach(function (a) { a.addEventListener("click", function (e) { e.preventDefault(); show(a.getAttribute("data-pick-link")); bonds.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" }); }); });
    if (filter) filter.addEventListener("input", function () {
      var q = norm(filter.value);
      picks.forEach(function (b) { b.hidden = q && norm(b.getAttribute("data-name")).indexOf(q) === -1; });
    });
    var start = params().get("unit");
    show(B[start] ? start : (B.cai ? "cai" : bdata.units[0].id));
  }
})();
