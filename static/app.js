(function () {
  "use strict";
  var t = function (key, vars) { return window.i18n ? window.i18n.t(key, vars) : ""; };
  var store = {
    get: function (k) { try { return JSON.parse(sessionStorage.getItem(k) || "null"); } catch (e) { return null; } },
    set: function (k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  };
  var fold = function (s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); };

  /* ---------------- Home: tabs, chips, tags, search ---------------- */
  var grid = document.getElementById("grid");
  if (grid) {
    var index = {};
    try {
      JSON.parse(document.getElementById("search-index").textContent).forEach(function (e) { index[e.s] = e.t; });
    } catch (e) {}
    var cards = Array.prototype.slice.call(grid.querySelectorAll(".card"));
    var q = document.getElementById("q");
    var latest = document.querySelector(".latest");
    var empty = document.querySelector(".empty");
    var active = document.querySelector(".active-filter");
    var params = new URLSearchParams(location.search);
    var state = { cat: params.get("cat") || "", sub: params.get("sub") || "", tag: params.get("tag") || "", q: params.get("q") || "" };
    if (q) q.value = state.q;

    var apply = function (push) {
      document.querySelectorAll(".tab").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.cat === state.cat)); });
      document.querySelectorAll(".subs").forEach(function (s) {
        s.hidden = s.dataset.for !== state.cat;
        s.querySelectorAll(".chip").forEach(function (c) { c.setAttribute("aria-pressed", String(c.dataset.sub === state.sub)); });
      });
      var words = fold(state.q.trim()).split(/\s+/).filter(Boolean);
      var shown = 0;
      cards.forEach(function (c) {
        var ok = (!state.cat || c.dataset.cat === state.cat) &&
                 (!state.sub || c.dataset.sub === state.sub) &&
                 (!state.tag || (" " + c.dataset.tags + " ").indexOf(" " + state.tag + " ") > -1) &&
                 words.every(function (w) { return (index[c.dataset.slug] || "").indexOf(w) > -1; });
        c.hidden = !ok;
        if (ok) shown++;
      });
      var filtered = state.cat || state.sub || state.tag || words.length;
      if (latest) latest.hidden = !!filtered;
      empty.hidden = shown > 0;
      empty.textContent = t("empty", { q: state.q });
      active.hidden = !state.tag;
      if (state.tag) active.querySelector("span").textContent = t("tagged", { tag: state.tag, n: shown });
      if (push !== false) {
        var p = new URLSearchParams();
        ["cat", "sub", "tag", "q"].forEach(function (k) { if (state[k]) p.set(k, state[k]); });
        history.replaceState(null, "", p.toString() ? "?" + p : location.pathname);
      }
    };

    document.querySelectorAll(".tab").forEach(function (b) {
      b.addEventListener("click", function () { state.cat = b.dataset.cat; state.sub = ""; state.tag = ""; apply(); });
    });
    document.querySelectorAll(".chip").forEach(function (c) {
      c.addEventListener("click", function () { state.sub = state.sub === c.dataset.sub ? "" : c.dataset.sub; apply(); });
    });
    document.querySelectorAll(".tag-cloud .tag").forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        state = { cat: "", sub: "", tag: new URL(a.href).searchParams.get("tag"), q: "" };
        if (q) q.value = "";
        apply();
        document.querySelector(".tabs").scrollIntoView({ behavior: "smooth" });
      });
    });
    var clear = document.querySelector("[data-clear]");
    if (clear) clear.addEventListener("click", function () { state = { cat: "", sub: "", tag: "", q: "" }; if (q) q.value = ""; apply(); });
    if (q) {
      var timer;
      q.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(function () { state.q = q.value; apply(); }, 80); });
      document.addEventListener("keydown", function (e) {
        if (e.key === "/" && document.activeElement !== q) { e.preventDefault(); q.focus(); }
      });
    }
    apply(false);
    document.addEventListener("langchange", function () { apply(false); });
  }

  /* ---------------- Recipe: ingredient ticks, step progress ---------------- */
  var recipe = document.querySelector(".recipe");
  if (recipe) {
    var key = "r:" + recipe.dataset.slug;
    var saved = store.get(key) || { i: [], s: [] };
    var save = function () {
      saved.i = []; saved.s = [];
      recipe.querySelectorAll(".section-ingredients li").forEach(function (li, n) { if (li.classList.contains("got")) saved.i.push(n); });
      recipe.querySelectorAll(".section-steps ol > li").forEach(function (li, n) { if (li.classList.contains("done")) saved.s.push(n); });
      store.set(key, saved);
    };

    recipe.querySelectorAll(".section-ingredients li").forEach(function (li, n) {
      if (li.querySelector("ul, ol")) return;
      var label = document.createElement("label");
      var box = document.createElement("input");
      box.type = "checkbox";
      var span = document.createElement("span");
      while (li.firstChild) span.appendChild(li.firstChild);
      label.appendChild(box); label.appendChild(span); li.appendChild(label);
      if (saved.i.indexOf(n) > -1) { box.checked = true; li.classList.add("got"); }
      box.addEventListener("change", function () { li.classList.toggle("got", box.checked); save(); });
    });

    recipe.querySelectorAll(".section-steps ol").forEach(function (ol) {
      if (ol.hasAttribute("start")) ol.style.counterReset = "step " + (parseInt(ol.getAttribute("start"), 10) - 1);
    });
    recipe.querySelectorAll(".section-steps ol > li").forEach(function (li, n) {
      li.tabIndex = 0;
      li.setAttribute("role", "button");
      li.setAttribute("aria-pressed", "false");
      if (saved.s.indexOf(n) > -1) { li.classList.add("done"); li.setAttribute("aria-pressed", "true"); }
      var toggle = function (e) {
        if (e.target.closest("a")) return;
        var on = li.classList.toggle("done");
        li.setAttribute("aria-pressed", String(on));
        save();
      };
      li.addEventListener("click", toggle);
      li.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(e); } });
    });

    /* Ingredients follow you down the page when they fit on screen */
    var panel = recipe.querySelector(".two-col > .section-ingredients");
    var fit = function () { if (panel) panel.classList.toggle("is-sticky", panel.offsetHeight < window.innerHeight - 32); };
    fit(); window.addEventListener("resize", fit);

    /* Keep the screen on while cooking */
    var wake = document.querySelector(".wake");
    if (wake && "wakeLock" in navigator) {
      var lock = null;
      wake.hidden = false;
      var setOn = function (on) {
        wake.setAttribute("aria-pressed", String(on));
        wake.dataset.i18n = on ? "wake_on" : "wake_off";
        wake.textContent = t(wake.dataset.i18n);
      };
      wake.addEventListener("click", function () {
        if (lock) { lock.release(); lock = null; setOn(false); return; }
        navigator.wakeLock.request("screen").then(function (l) {
          lock = l; setOn(true);
          l.addEventListener("release", function () { if (lock === l) { lock = null; setOn(false); } });
        }).catch(function () { setOn(false); });
      });
    }
  }
})();
