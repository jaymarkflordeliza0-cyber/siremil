/*
 * SalaryScope front-end.
 *
 * Written in classic JavaScript (ES5) on purpose, so it runs on old and new
 * browsers alike: no arrow functions, no let/const, no template strings,
 * no async/await, no fetch (uses XMLHttpRequest). No external libraries,
 * so it works offline.
 */
(function () {
  "use strict";

  var CFG = window.APP_CONFIG;

  /* ---------------- Small helpers (work in every browser) ---------------- */
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function matches(el, sel) {
    var fn = el.matches || el.msMatchesSelector || el.webkitMatchesSelector || el.mozMatchesSelector;
    return fn ? fn.call(el, sel) : false;
  }
  function closest(el, sel) {
    while (el && el.nodeType === 1) {
      if (matches(el, sel)) return el;
      el = el.parentNode;
    }
    return null;
  }
  function removeNode(el) { if (el && el.parentNode) el.parentNode.removeChild(el); }
  function data(el, name) { return el.getAttribute("data-" + name); }
  function on(el, type, fn) { el.addEventListener(type, fn, false); }
  // classList.toggle(name, true/false) is not supported by older browsers
  function setClass(el, name, isOn) {
    if (isOn) el.classList.add(name); else el.classList.remove(name);
  }

  function fireInput(el) {
    var ev;
    try {
      ev = new Event("input", { bubbles: true });
    } catch (e) { // older browsers
      ev = document.createEvent("Event");
      ev.initEvent("input", true, true);
    }
    el.dispatchEvent(ev);
  }

  var raf = window.requestAnimationFrame || function (fn) { return setTimeout(function () { fn(now()); }, 16); };
  function now() { return window.performance && performance.now ? performance.now() : new Date().getTime(); }

  var reduceMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  // 23818.6 -> "23,818.60" (same on every browser)
  function money(value) {
    var n = Number(value);
    var sign = n < 0 ? "-" : "";
    var parts = Math.abs(n).toFixed(2).split(".");
    var whole = parts[0];
    var out = "";
    while (whole.length > 3) {
      out = "," + whole.slice(-3) + out;
      whole = whole.slice(0, -3);
    }
    return sign + whole + out + "." + parts[1];
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function initials(name) {
    var words = String(name).replace(/^\s+|\s+$/g, "").split(/\s+/).slice(0, 2);
    var out = "";
    for (var i = 0; i < words.length; i++) out += words[i].charAt(0);
    return out.toUpperCase() || "?";
  }
  function plural(n, word) { return n + " " + word + (Number(n) === 1 ? "" : "s"); }

  var PESO = "₱";

  /* ---------------- Theme ---------------- */
  on($("#themeToggle"), "click", function () {
    var root = document.documentElement;
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) { /* storage not available */ }
  });

  /* ---------------- Tabs ---------------- */
  var indicator = $(".tab-indicator");
  function moveIndicator(tab) {
    if (!tab) return;
    indicator.style.width = tab.offsetWidth + "px";
    var move = "translateX(" + tab.offsetLeft + "px)";
    indicator.style.webkitTransform = move;
    indicator.style.transform = move;
  }
  function showTab(name) {
    $$(".tab").forEach(function (t) {
      var active = data(t, "tab") === name;
      setClass(t, "active", active);
      t.setAttribute("aria-selected", active ? "true" : "false");
      if (active) moveIndicator(t);
    });
    $$(".panel").forEach(function (p) {
      var active = p.id === "panel-" + name;
      if (active) p.removeAttribute("hidden"); else p.setAttribute("hidden", "");
      setClass(p, "active", active);
    });
    if (name === "history") loadHistory();
    if (window.history && history.replaceState) history.replaceState(null, "", "#" + name);
  }
  $$(".tab").forEach(function (t) { on(t, "click", function () { showTab(data(t, "tab")); }); });
  on(window, "resize", function () { moveIndicator($(".tab.active")); });

  /* ---------------- Steppers (+ / - buttons) ---------------- */
  $$(".stepper").forEach(function (st) {
    var input = $("input", st);
    $$(".step", st).forEach(function (btn) {
      on(btn, "click", function () {
        var min = input.getAttribute("min") === null ? -Infinity : Number(input.getAttribute("min"));
        var max = input.getAttribute("max") === null ? Infinity : Number(input.getAttribute("max"));
        var cur = input.value === "" ? 0 : Number(input.value);
        input.value = Math.min(max, Math.max(min, cur + Number(data(btn, "step"))));
        fireInput(input);
      });
    });
  });

  /* ---------------- Working hours: keep 1-168 while typing ---------------- */
  //   above 168 -> set back to 168
  //   0 (or below 1) -> set back to 1
  $$('input[name="working_hours"]').forEach(function (input) {
    var min = Number(input.getAttribute("min"));
    var max = Number(input.getAttribute("max"));
    on(input, "input", function () {
      if (input.value === "" || isNaN(input.value)) return; // still typing / empty
      var value = Number(input.value);
      var message;
      if (value > max) {
        input.value = max;
        message = "Maximum is " + max + " hours per week, so it was set to " + max + ".";
      } else if (value < min) {
        input.value = min;
        message = "Minimum is " + min + " hour per week, so it was set to " + min + ".";
      } else {
        return;
      }
      var hint = $(".hint", closest(input, ".field"));
      if (hint) {
        hint.classList.remove("flash");
        void hint.offsetWidth; // restart the highlight animation
        hint.classList.add("flash");
      }
      toast(message, "info");
    });
  });

  /* ---------------- Sliders ---------------- */
  $$(".range[data-sync]").forEach(function (range) {
    var input = document.getElementById(data(range, "sync"));
    function paint() {
      var min = Number(range.min), max = Number(range.max);
      var p = ((Number(range.value) - min) / (max - min)) * 100;
      range.style.setProperty("--p", p + "%");
    }
    function fromSlider() {
      input.value = range.value;
      paint();
      clearError(closest(input, ".field"));
    }
    on(range, "input", fromSlider);
    on(range, "change", fromSlider); // older browsers only fire "change"
    on(input, "input", function () {
      if (input.value !== "") range.value = Math.min(Number(range.max), Number(input.value));
      paint();
    });
    paint();
  });

  /* ---------------- Validation helpers ---------------- */
  function clearError(field) {
    if (!field) return;
    field.classList.remove("invalid");
    var e = $(".error", field);
    if (e) e.textContent = "";
  }
  function showErrors(form, errors) {
    var first = null;
    Object.keys(errors).forEach(function (key) {
      var holder = $('.error[data-for="' + key + '"]', form);
      if (!holder) return;
      var field = closest(holder, ".field");
      holder.textContent = errors[key];
      field.classList.remove("invalid");
      void field.offsetWidth; // restart shake animation
      field.classList.add("invalid");
      first = first || field;
    });
    if (first) {
      var inp = $("input", first);
      if (inp) inp.focus();
      if (first.scrollIntoView) first.scrollIntoView(false);
    }
  }
  $$("form").forEach(function (form) {
    on(form, "input", function (e) { clearError(closest(e.target, ".field")); });
    on(form, "change", function (e) { clearError(closest(e.target, ".field")); });
  });

  function readForm(form) {
    var result = {};
    $$("input[name]", form).forEach(function (el) {
      if ((el.type === "radio" || el.type === "checkbox") && !el.checked) return;
      result[el.name] = String(el.value).replace(/^\s+|\s+$/g, "");
    });
    return result;
  }

  // Client-side checks mirror the server rules (server is still the source of truth).
  function validate(values, expKeys) {
    var errs = {};
    if (!values.employee_name) errs.employee_name = "Employee name must not be empty.";
    if (!values.education) errs.education = "Please choose an education level.";
    var h = values.working_hours;
    if (h === "" || h === undefined || isNaN(h)) errs.working_hours = "Working hours is required.";
    else if (+h < CFG.minHours || +h > CFG.maxHours)
      errs.working_hours = "Working hours must be between " + CFG.minHours + " and " + CFG.maxHours + " per week.";
    expKeys.forEach(function (pair) {
      var k = pair[0], label = pair[1], v = values[k];
      if (v === "" || v === undefined || isNaN(v)) errs[k] = label + " is required.";
      else if (+v < 0) errs[k] = label + " must be 0 or greater.";
    });
    return errs;
  }

  // HTTP request with XMLHttpRequest (supported by every browser).
  // done(error, body) - error is null when the request succeeded.
  function request(method, url, body, done) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    if (body !== null) xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return;
      var parsed = {};
      try { parsed = JSON.parse(xhr.responseText || "{}"); } catch (e) { parsed = {}; }
      if (xhr.status >= 200 && xhr.status < 300) return done(null, parsed);
      var err = new Error(xhr.status === 0 ? "Server is not running" : (parsed.error || "Request failed"));
      err.details = parsed.details || {};
      done(err, parsed);
    };
    xhr.send(body === null ? null : JSON.stringify(body));
  }

  /* ---------------- Toasts (small pop-up messages) ---------------- */
  function toast(msg, type) {
    type = type || "ok";
    // Only one "info" notice at a time, so repeated typing doesn't stack them up
    if (type === "info") $$(".toast.info").forEach(removeNode);
    var t = document.createElement("div");
    t.className = "toast " + type;
    t.innerHTML = '<span class="ico">' + (type === "ok"
      ? '<svg viewBox="0 0 24 24"><path d="M5 12l5 5 9-10"/></svg>'
      : '<svg viewBox="0 0 24 24"><path d="M12 8v5M12 16.5v.5"/><circle cx="12" cy="12" r="9"/></svg>') +
      "</span><span>" + esc(msg) + "</span>";
    $("#toasts").appendChild(t);
    setTimeout(function () {
      t.classList.add("out");
      setTimeout(function () { removeNode(t); }, 350); // also works without CSS animations
    }, 3200);
  }

  /* ---------------- Visual helpers ---------------- */
  function countUp(el, target, duration) {
    duration = duration || 1100;
    if (reduceMotion) { el.textContent = money(target); return; }
    var start = now();
    function step() {
      var t = Math.min(1, (now() - start) / duration);
      var eased = 1 - Math.pow(1 - t, 4);
      el.textContent = money(target * eased);
      if (t < 1) raf(step);
    }
    raf(step);
  }

  // Piece-wise position: each range (LOW / MEDIUM / HIGH) gets one third of the track.
  function meterPos(salary) {
    var lo = CFG.lowLimit, hi = CFG.highLimit, top = hi * 1.6, p;
    if (salary < lo) p = (Math.max(0, salary) / lo) / 3;
    else if (salary < hi) p = 1 / 3 + ((salary - lo) / (hi - lo)) / 3;
    else p = 2 / 3 + (Math.min(salary - hi, top - hi) / (top - hi)) / 3;
    return Math.max(1.5, Math.min(98.5, p * 100));
  }

  function meterHTML(salary, range) {
    function onIf(name) { return range === name ? " on" : ""; }
    return '<div class="meter" aria-label="Salary range meter">' +
      '<div class="meter-track">' +
        '<span class="low' + onIf("LOW") + '"></span>' +
        '<span class="medium' + onIf("MEDIUM") + '"></span>' +
        '<span class="high' + onIf("HIGH") + '"></span>' +
        '<i class="meter-pin" data-left="' + meterPos(salary) + '"></i>' +
      "</div>" +
      '<div class="meter-labels">' +
        "<span>LOW &lt; " + PESO + (CFG.lowLimit / 1000).toFixed(0) + "k</span>" +
        "<span>MEDIUM</span>" +
        "<span>HIGH &ge; " + PESO + (CFG.highLimit / 1000).toFixed(0) + "k</span>" +
      "</div></div>";
  }

  function highlightJSON(obj) {
    return esc(JSON.stringify(obj, null, 2)).replace(
      /(&quot;(?:[^&]|&(?!quot;))*?&quot;)(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g,
      function (m, str, colon, bool) {
        if (str) return colon ? '<span class="j-key">' + str + "</span>" + colon : '<span class="j-str">' + str + "</span>";
        if (bool) return '<span class="j-bool">' + m + "</span>";
        return '<span class="j-num">' + m + "</span>";
      }
    );
  }

  function jsonBlock(obj, open) {
    return '<details class="json-toggle"' + (open ? " open" : "") + ">" +
      '<summary><svg viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg> JSON output</summary>' +
      '<div class="json-box"><div class="json-head">' +
        '<span class="dots"><i></i><i></i><i></i></span>' +
        "<span>RESPONSE &middot; application/json</span>" +
        '<button type="button" class="copy-btn"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2"/>' +
        '<path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>Copy</button>' +
      "</div><pre>" + highlightJSON(obj) + "</pre></div></details>";
  }

  function copyText(text) {
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch (e) { /* ignore */ }
      removeNode(ta);
      toast("JSON copied to clipboard");
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { toast("JSON copied to clipboard"); }, fallback);
    } else {
      fallback();
    }
  }

  function wireResult(container, obj) {
    raf(function () {
      raf(function () {
        $$(".meter-pin", container).forEach(function (pin) { pin.style.left = data(pin, "left") + "%"; });
        $$(".bar i", container).forEach(function (bar) { bar.style.width = data(bar, "w") + "%"; });
      });
    });
    $$("[data-count]", container).forEach(function (el) { countUp(el, Number(data(el, "count"))); });
    var copy = $(".copy-btn", container);
    if (copy) on(copy, "click", function () { copyText(JSON.stringify(obj, null, 2)); });
  }

  function setLoading(form, isLoading) {
    var btn = $("button[type=submit]", form);
    setClass(btn, "loading", isLoading);
    btn.disabled = isLoading;
  }

  function scrollToResult(box) {
    if (window.innerWidth < 960 && box.scrollIntoView) box.scrollIntoView(true);
  }

  /* ---------------- Predict ---------------- */
  var predictForm = $("#predictForm");
  on(predictForm, "submit", function (e) {
    e.preventDefault();
    var values = readForm(predictForm);
    var errs = validate(values, [["years_experience", "Years of experience"]]);
    if (Object.keys(errs).length) return showErrors(predictForm, errs);

    setLoading(predictForm, true);
    request("POST", "/predict", values, function (err, r) {
      setLoading(predictForm, false);
      if (err) {
        showErrors(predictForm, err.details || {});
        return toast(err.message, "err");
      }
      var box = $("#predictResult");
      box.innerHTML =
        '<div class="result">' +
          '<div class="result-top">' +
            '<div class="who"><div class="avatar">' + esc(initials(r.employee_name)) + "</div>" +
              "<div><h3>" + esc(r.employee_name) + "</h3><p>Predicted " + esc(r.timestamp) + "</p></div></div>" +
            '<span class="badge ' + r.salary_range + '">' + r.salary_range + "</span>" +
          "</div>" +
          '<div class="big-salary"><span class="cur">' + PESO + '</span><span data-count="' + r.predicted_salary + '">0.00</span></div>' +
          '<div class="sub">Estimated monthly salary &middot; ' + esc(r.currency) + "</div>" +
          meterHTML(r.predicted_salary, r.salary_range) +
          '<div class="facts">' +
            '<div class="fact"><span>Education</span><b>' + esc(r.education) + "</b></div>" +
            '<div class="fact"><span>Experience</span><b>' + plural(r.experience, "yr") + "</b></div>" +
            '<div class="fact"><span>Hours / week</span><b>' + r.working_hours + "</b></div>" +
          "</div>" +
          jsonBlock(r, false) +
        "</div>";
      wireResult(box, r);
      scrollToResult(box);
      toast("Saved prediction for " + r.employee_name);
      refreshCount();
    });
  });

  /* ---------------- Compare ---------------- */
  var compareForm = $("#compareForm");
  on(compareForm, "submit", function (e) {
    e.preventDefault();
    var values = readForm(compareForm);
    var errs = validate(values, [["experience_1", "Experience 1"], ["experience_2", "Experience 2"]]);
    if (!errs.experience_1 && !errs.experience_2 && +values.experience_1 === +values.experience_2)
      errs.experience_2 = "Use two different years-of-experience values.";
    if (Object.keys(errs).length) return showErrors(compareForm, errs);

    setLoading(compareForm, true);
    request("POST", "/compare", values, function (err, r) {
      setLoading(compareForm, false);
      if (err) {
        showErrors(compareForm, err.details || {});
        return toast(err.message, "err");
      }
      var diff = r.salary_difference;
      var pct = r.predicted_salary_1 !== 0 ? (diff / Math.abs(r.predicted_salary_1)) * 100 : 0;
      var maxSal = Math.max(r.predicted_salary_1, r.predicted_salary_2, 1);
      var sign = diff > 0 ? "+" : diff < 0 ? "−" : "";
      var w1 = (Math.max(0, r.predicted_salary_1) / maxSal) * 100;
      var w2 = (Math.max(0, r.predicted_salary_2) / maxSal) * 100;

      function scenario(cls, tag, exp, range, salary) {
        return '<div class="scen ' + cls + '">' +
          '<div class="scen-head"><span><span class="tag" style="background:var(--' + cls + ')">' + tag + "</span> " +
            plural(exp, "yr") + '</span><span class="badge ' + range + '">' + range + "</span></div>" +
          '<div class="scen-salary">' + PESO + '<span data-count="' + salary + '">0.00</span></div>' +
          '<div class="sub">Predicted monthly</div></div>';
      }
      function bar(cls, tag, exp, width) {
        return '<div class="bar-row ' + cls + '"><span>' + tag + " &middot; " + plural(exp, "yr") + "</span>" +
          '<div class="bar"><i data-w="' + width + '"></i></div></div>';
      }

      var box = $("#compareResult");
      box.innerHTML =
        '<div class="result">' +
          '<div class="result-top"><div class="who"><div class="avatar">' + esc(initials(r.employee_name)) + "</div>" +
            "<div><h3>" + esc(r.employee_name) + "</h3><p>" + esc(r.education) + " &middot; " +
            plural(r.working_hours, "hr") + "/week</p></div></div></div>" +
          '<div class="versus">' +
            scenario("a", "A", r.experience_1, r.salary_range_1, r.predicted_salary_1) +
            scenario("b", "B", r.experience_2, r.salary_range_2, r.predicted_salary_2) +
          "</div>" +
          '<div class="delta' + (diff < 0 ? " neg" : "") + '">' +
            "<div><small>Salary difference (B &minus; A)</small><b>" + sign + PESO + money(Math.abs(diff)) + "</b></div>" +
            '<span class="pct">' + sign + Math.abs(pct).toFixed(1) + "%</span>" +
          "</div>" +
          '<div class="bars">' + bar("a", "A", r.experience_1, w1) + bar("b", "B", r.experience_2, w2) + "</div>" +
          jsonBlock(r, true) +
        "</div>";
      wireResult(box, r);
      scrollToResult(box);
      toast("Both predictions saved to history");
      refreshCount();
    });
  });

  /* ---------------- History ---------------- */
  var records = [];
  var filters = { q: "", range: "ALL", type: "ALL" };

  function fetchHistory(done) {
    request("GET", "/history", null, function (err, body) {
      if (!err) {
        records = body.records || [];
        $("#historyCount").textContent = records.length;
      }
      if (done) done(err);
    });
  }
  function refreshCount() { fetchHistory(); }
  function loadHistory(done) {
    fetchHistory(function (err) {
      if (err) {
        toast("Could not load history", "err");
      } else {
        renderStats();
        renderTable();
      }
      if (done) done(err);
    });
  }

  function renderStats() {
    var sal = records.map(function (r) { return Number(r.predicted_salary); })
      .filter(function (x) { return !isNaN(x); });
    var total = sal.reduce(function (a, b) { return a + b; }, 0);
    $("#s_total").textContent = records.length;
    $("#s_avg").textContent = sal.length ? PESO + money(total / sal.length) : "—";
    $("#s_max").textContent = sal.length ? PESO + money(Math.max.apply(Math, sal)) : "—";

    var counts = { LOW: 0, MEDIUM: 0, HIGH: 0 };
    records.forEach(function (r) { if (counts.hasOwnProperty(r.salary_range)) counts[r.salary_range]++; });
    var mix = $("#s_mix");
    $(".low", mix).style.flexGrow = counts.LOW;
    $(".medium", mix).style.flexGrow = counts.MEDIUM;
    $(".high", mix).style.flexGrow = counts.HIGH;
    $("#s_mix_legend").innerHTML = [["LOW", "--low"], ["MEDIUM", "--medium"], ["HIGH", "--high"]]
      .map(function (p) { return '<span><i style="background:var(' + p[1] + ')"></i>' + p[0] + " " + counts[p[0]] + "</span>"; })
      .join("");
  }

  function renderTable() {
    var q = filters.q.toLowerCase();
    var rows = records.filter(function (r) {
      return (filters.range === "ALL" || r.salary_range === filters.range) &&
        (filters.type === "ALL" || r.request_type === filters.type) &&
        (!q || (r.employee_name + " " + r.education).toLowerCase().indexOf(q) !== -1);
    });
    var empty = $("#historyEmpty");
    if (rows.length) empty.setAttribute("hidden", ""); else empty.removeAttribute("hidden");
    $("h3", empty).textContent = records.length ? "No matching records" : "No records yet";

    $("#historyBody").innerHTML = rows.map(function (r, i) {
      var isCompare = r.request_type === "compare";
      return '<tr class="' + (isCompare ? "grouped" : "") + '" style="animation-delay:' + Math.min(i, 15) * 25 + 'ms">' +
        '<td class="muted">' + esc(r.timestamp) + "</td>" +
        '<td><div class="person"><span class="avatar">' + esc(initials(r.employee_name)) + "</span>" + esc(r.employee_name) + "</div></td>" +
        "<td>" + esc(r.education) + "</td>" +
        '<td class="num">' + esc(r.years_experience) + "</td>" +
        '<td class="num">' + esc(r.working_hours) + "</td>" +
        '<td class="num money">' + PESO + money(r.predicted_salary) + "</td>" +
        '<td><span class="badge ' + esc(r.salary_range) + '">' + esc(r.salary_range) + "</span></td>" +
        '<td><span class="type-pill ' + esc(r.request_type) + '"' +
          (r.comparison_id ? ' title="Comparison #' + esc(r.comparison_id) + '"' : "") + ">" +
          (isCompare ? "Compare #" + esc(r.comparison_id) : "Predict") + "</span></td>" +
        "</tr>";
    }).join("");
  }

  on($("#h_search"), "input", function (e) { filters.q = e.target.value; renderTable(); });
  on($("#h_search"), "keyup", function (e) { filters.q = e.target.value; renderTable(); }); // older browsers
  [["#h_filter", "range"], ["#h_type", "type"]].forEach(function (pair) {
    var sel = pair[0], key = pair[1];
    $$(sel + " button").forEach(function (b) {
      on(b, "click", function () {
        $$(sel + " button").forEach(function (x) { setClass(x, "active", x === b); });
        filters[key] = data(b, "v");
        renderTable();
      });
    });
  });
  on($("#h_refresh"), "click", function () {
    loadHistory(function (err) { if (!err) toast("History refreshed"); });
  });

  /* ---------------- Init ---------------- */
  var start = String(window.location.hash || "").replace("#", "");
  showTab(["predict", "compare", "history"].indexOf(start) !== -1 ? start : "predict");
  refreshCount();
})();
