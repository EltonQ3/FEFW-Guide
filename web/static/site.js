/* 萬縷千絲 · 資料織錦 — 互動腳本（無外部依賴） */
(function () {
  "use strict";
  var doc = document, root = doc.documentElement, body = doc.body;
  var ROOT = body.getAttribute("data-root") || "";
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  var reduceMotion = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  function $(s, el) { return (el || doc).querySelector(s); }
  function $$(s, el) { return Array.prototype.slice.call((el || doc).querySelectorAll(s)); }

  /* ---------- 明暗 ---------- */
  $$("[data-theme-toggle]").forEach(function (b) {
    b.addEventListener("click", function () {
      var next = root.dataset.theme === "light" ? "dark" : "light";
      root.dataset.theme = next;
      store.set("fw.theme", next);
    });
  });

  /* ---------- 手機選單 ---------- */
  var menuBtn = $("[data-menu]"), nav = $("#site-nav");
  if (menuBtn && nav) {
    menuBtn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    doc.addEventListener("click", function (e) {
      if (nav.classList.contains("open") && !nav.contains(e.target) && !menuBtn.contains(e.target)) {
        nav.classList.remove("open"); menuBtn.setAttribute("aria-expanded", "false");
      }
    });
  }

  /* ---------- 簡繁切換時保留錨點與篩選 ---------- */
  $$("[data-lang-link]").forEach(function (a) {
    a.addEventListener("click", function () {
      a.href = a.href.split("#")[0].split("?")[0] + location.search + location.hash;
    });
  });

  /* ---------- 回到頂部 ---------- */
  var toTop = $("[data-to-top]");
  if (toTop) {
    var onScroll = function () { toTop.classList.toggle("show", window.scrollY > 900); };
    window.addEventListener("scroll", onScroll, { passive: true }); onScroll();
    toTop.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" }); });
  }

  /* ---------- 進場動畫 ---------- */
  var reveals = $$(".reveal");
  if (reveals.length && "IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } });
    }, { rootMargin: "0px 0px -8% 0px" });
    reveals.forEach(function (el) { io.observe(el); });
  } else { reveals.forEach(function (el) { el.classList.add("in"); }); }

  /* ---------- 篩選 ---------- */
  function norm(s) { return (s || "").toLowerCase().replace(/\s+/g, ""); }
  $$("[data-filter-scope]").forEach(function (scope) {
    var input = $("[data-filter-text]", scope);
    var countEl = $("[data-filter-count]", scope);
    var empty = $("[data-filter-empty]", scope);
    var groups = $$("[data-filter-group]", scope);
    var items = $$("[data-item]", scope);
    var state = {};
    var hay = items.map(function (el) { return norm((el.getAttribute("data-text") || "") + " " + (el.getAttribute("data-alt") || "")); });

    function apply(push) {
      var q = norm(input ? input.value : "");
      var terms = q ? q.split(/[,，、]/).filter(Boolean) : [];
      var shown = 0, seenCards = 0;
      items.forEach(function (el, i) {
        var ok = terms.every(function (t) { return hay[i].indexOf(t) !== -1; });
        if (ok) {
          for (var k in state) {
            if (!state[k]) continue;
            var v = (el.getAttribute("data-" + k) || "").split(" ");
            if (v.indexOf(state[k]) === -1) { ok = false; break; }
          }
        }
        el.hidden = !ok;
        if (ok && el.tagName !== "TR") shown++;
        if (el.tagName !== "TR") seenCards++;
      });
      if (!seenCards) shown = items.filter(function (el) { return !el.hidden; }).length;
      $$("[data-filter-section]", scope).forEach(function (sec) {
        sec.hidden = !$$("[data-item]", sec).some(function (el) { return !el.hidden; });
      });
      $$("[data-filter-section-row]", scope).forEach(function (row) {
        var n = row.nextElementSibling, any = false;
        while (n && !n.hasAttribute("data-filter-section-row")) { if (!n.hidden) any = true; n = n.nextElementSibling; }
        row.hidden = !any;
      });
      if (countEl) countEl.textContent = shown;
      if (empty) empty.classList.toggle("show", shown === 0);
      if (push) syncUrl();
    }
    function syncUrl() {
      var params = (scope.getAttribute("data-url-params") || "").split(" ").filter(Boolean);
      if (!params.length || !history.replaceState) return;
      var sp = new URLSearchParams(location.search);
      params.forEach(function (p) { if (state[p]) sp.set(p, state[p]); else sp.delete(p); });
      var qs = sp.toString();
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
    }
    function setGroup(g, value) {
      var key = g.getAttribute("data-filter-group");
      state[key] = value;
      $$("button[data-value]", g).forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-value") === value ? "true" : "false"); });
    }
    groups.forEach(function (g) {
      g.addEventListener("click", function (e) {
        var b = e.target.closest("button[data-value]");
        if (!b) return;
        var v = b.getAttribute("data-value");
        var key = g.getAttribute("data-filter-group");
        if (v && state[key] === v) v = "";
        setGroup(g, v); apply(true);
      });
    });
    if (input) {
      var t;
      input.addEventListener("input", function () { clearTimeout(t); t = setTimeout(function () { apply(false); }, 60); });
    }
    // 由網址帶入初始篩選（例如 ?route=kai）
    var sp = new URLSearchParams(location.search);
    groups.forEach(function (g) {
      var key = g.getAttribute("data-filter-group"), v = sp.get(key);
      if (v && $('button[data-value="' + v + '"]', g)) setGroup(g, v);
    });
    if (sp.get("q") && input) input.value = sp.get("q");
    apply(false);

    // 卡片／表格
    var viewBtns = $$(".view-toggle button", scope);
    if (viewBtns.length) {
      var vkey = "fw.view." + (scope.getAttribute("data-view-scope") || "x");
      var setView = function (v) {
        scope.classList.toggle("view-table", v === "table");
        scope.classList.toggle("view-cards", v !== "table");
        viewBtns.forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-view") === v ? "true" : "false"); });
      };
      viewBtns.forEach(function (b) { b.addEventListener("click", function () { var v = b.getAttribute("data-view"); setView(v); store.set(vkey, v); }); });
      setView(store.get(vkey) || "cards");
    }
  });

  /* ---------- 詳細資料（dialog） ---------- */
  var dlg = $("#detail"), dlgBody = $("[data-detail-body]");
  var lastTrigger = null;
  function openDetail(tplId, trigger, hash) {
    var tpl = doc.getElementById(tplId);
    if (!tpl || !dlg) return;
    dlgBody.innerHTML = "";
    dlgBody.appendChild(tpl.content.cloneNode(true));
    dlgBody.scrollTop = 0;
    lastTrigger = trigger || null;
    if (typeof dlg.showModal === "function") { if (!dlg.open) dlg.showModal(); } else { dlg.setAttribute("open", ""); }
    if (hash && history.replaceState) history.replaceState(null, "", location.pathname + location.search + "#" + hash);
  }
  function closeDetail() {
    if (!dlg) return;
    if (dlg.open) { if (typeof dlg.close === "function") dlg.close(); else dlg.removeAttribute("open"); }
  }
  if (dlg) {
    dlg.addEventListener("close", function () {
      if (history.replaceState && location.hash) history.replaceState(null, "", location.pathname + location.search);
      if (lastTrigger) lastTrigger.focus({ preventScroll: true });
    });
    dlg.addEventListener("click", function (e) { if (e.target === dlg || e.target.closest("[data-close]")) closeDetail(); });
    $$("[data-detail]").forEach(function (el) {
      el.addEventListener("click", function () { openDetail(el.getAttribute("data-detail"), el, el.getAttribute("data-hash")); });
    });
  }
  function openFromHash() {
    var h = decodeURIComponent(location.hash.slice(1));
    if (!h) return;
    var el = doc.getElementById(h);
    if (el && el.hasAttribute("data-detail")) {
      el.scrollIntoView({ block: "center" });
      openDetail(el.getAttribute("data-detail"), el, h);
    } else if (el) {
      el.classList.add("flash");
      setTimeout(function () { el.classList.remove("flash"); }, 1600);
    }
  }
  window.addEventListener("hashchange", openFromHash);
  openFromHash();

  /* ---------- 全站搜尋 ---------- */
  var finder = $("#finder"), fInput = $("[data-finder-input]"), fList = $("[data-finder-list]");
  var index = null, results = [], sel = 0;
  function loadIndex() {
    if (index) return Promise.resolve(index);
    return fetch("search.json").then(function (r) { return r.json(); }).then(function (d) { index = d; return d; }).catch(function () { index = []; return index; });
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function render() {
    var q = norm(fInput.value);
    if (!index) return;
    if (!q) { results = index.filter(function (x) { return x.f; }).slice(0, 8); }
    else {
      results = index.map(function (x) {
        var t = norm(x.t), k = norm(x.k);
        var score = t === q ? 0 : t.indexOf(q) === 0 ? 1 : t.indexOf(q) !== -1 ? 2 : k.indexOf(q) !== -1 ? 3 : 9;
        return [score, x];
      }).filter(function (p) { return p[0] < 9; }).sort(function (a, b) { return a[0] - b[0]; }).slice(0, 40).map(function (p) { return p[1]; });
    }
    sel = 0;
    if (!results.length) { fList.innerHTML = '<li class="none">' + esc(fList.getAttribute("data-none") || "沒有結果") + "</li>"; return; }
    fList.innerHTML = results.map(function (x, i) {
      var pic = x.i ? '<img src="' + ROOT + esc(x.i) + '" alt="" loading="lazy">' : '<span class="ph">' + esc(x.t.charAt(0)) + "</span>";
      return '<li><a href="' + esc(x.u) + '" role="option" aria-selected="' + (i === 0) + '">' + pic + '<span><b>' + esc(x.t) + "</b><small>" + esc(x.s || "") + '</small></span><span class="kind">' + esc(x.c) + "</span></a></li>";
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
      var tag = (e.target.tagName || "").toLowerCase();
      var typing = tag === "input" || tag === "textarea" || e.target.isContentEditable;
      if ((e.key === "/" && !typing) || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k")) {
        e.preventDefault(); if (!finder.open) openFinder();
      }
    });
  }

  /* ---------- 首頁：命運絲線 ---------- */
  var canvas = $("canvas[data-weave]");
  if (canvas && canvas.getContext) {
    var ctx = canvas.getContext("2d"), w = 0, h = 0, dpr = Math.min(window.devicePixelRatio || 1, 2), raf = 0, visible = true;
    var colors = ["#5b86de", "#9277d6", "#d9ad3c", "#d4507a"];
    var threads = [];
    for (var i = 0; i < 20; i++) {
      threads.push({
        c: colors[i % 4], y: Math.random(), a: 0.03 + Math.random() * 0.07, f: 0.6 + Math.random() * 1.6,
        p: Math.random() * Math.PI * 2, s: 0.00008 + Math.random() * 0.00018, wdt: i % 4 === 0 ? 1.6 : 0.8 + Math.random() * 0.6,
        o: i < 4 ? 0.5 : 0.12 + Math.random() * 0.2
      });
    }
    var resize = function () {
      var r = canvas.getBoundingClientRect(); w = r.width; h = r.height;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    var draw = function (t) {
      ctx.clearRect(0, 0, w, h);
      var light = root.dataset.theme === "light";
      ctx.globalCompositeOperation = light ? "source-over" : "lighter";
      threads.forEach(function (th) {
        ctx.beginPath();
        var steps = 48;
        for (var k = 0; k <= steps; k++) {
          var x = (k / steps) * w;
          var y = (th.y * 0.8 + 0.1) * h + Math.sin(k / steps * Math.PI * 2 * th.f + th.p + t * th.s * 6) * th.a * h
            + Math.sin(k / steps * Math.PI * 5 + t * th.s * 3) * 6;
          if (k === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = th.c; ctx.globalAlpha = th.o * (light ? 0.55 : 1); ctx.lineWidth = th.wdt;
        ctx.shadowColor = th.c; ctx.shadowBlur = light ? 0 : 8;
        ctx.stroke();
      });
      ctx.globalAlpha = 1; ctx.shadowBlur = 0;
    };
    var loop = function (t) { if (!visible) { raf = 0; return; } draw(t); raf = requestAnimationFrame(loop); };
    resize(); draw(0);
    window.addEventListener("resize", function () { resize(); draw(performance.now()); });
    if (!reduceMotion) {
      if ("IntersectionObserver" in window) {
        new IntersectionObserver(function (en) { visible = en[0].isIntersecting && !doc.hidden; if (visible && !raf) raf = requestAnimationFrame(loop); }).observe(canvas);
      } else { raf = requestAnimationFrame(loop); }
      doc.addEventListener("visibilitychange", function () { visible = !doc.hidden; if (visible && !raf) raf = requestAnimationFrame(loop); });
    }
  }
})();
