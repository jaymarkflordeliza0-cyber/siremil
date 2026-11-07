/* SalaryScope front-end — vanilla JS, no external libraries (works offline). */
(function () {
  "use strict";

  const CFG = window.APP_CONFIG;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const money = (n) =>
    Number(n).toLocaleString("en-PH", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const initials = (name) =>
    name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------- Theme ---------------- */
  $("#themeToggle").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("theme", next);
  });

  /* ---------------- Tabs ---------------- */
  const indicator = $(".tab-indicator");
  function moveIndicator(tab) {
    indicator.style.width = tab.offsetWidth + "px";
    indicator.style.transform = `translateX(${tab.offsetLeft}px)`;
  }
  function showTab(name) {
    $$(".tab").forEach((t) => {
      const on = t.dataset.tab === name;
      t.classList.toggle("active", on);
      t.setAttribute("aria-selected", on);
      if (on) moveIndicator(t);
    });
    $$(".panel").forEach((p) => {
      const on = p.id === "panel-" + name;
      p.hidden = !on;
      p.classList.toggle("active", on);
    });
    if (name === "history") loadHistory();
    history.replaceState(null, "", "#" + name);
  }
  $$(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));
  window.addEventListener("resize", () => moveIndicator($(".tab.active")));

  /* ---------------- Steppers & sliders ---------------- */
  $$(".stepper").forEach((st) => {
    const input = $("input", st);
    $$(".step", st).forEach((btn) =>
      btn.addEventListener("click", () => {
        const min = input.min === "" ? -Infinity : Number(input.min);
        const max = input.max === "" ? Infinity : Number(input.max);
        const cur = input.value === "" ? 0 : Number(input.value);
        input.value = Math.min(max, Math.max(min, cur + Number(btn.dataset.step)));
        input.dispatchEvent(new Event("input", { bubbles: true }));
      })
    );
  });
  // Working hours: while typing, keep the value inside 1-168.
  //   above 168 -> set back to 168
  //   0 (or below 1) -> set back to 1
  $$('input[name="working_hours"]').forEach((input) => {
    const min = Number(input.min);
    const max = Number(input.max);
    input.addEventListener("input", () => {
      if (input.value === "" || isNaN(input.value)) return; // still typing / empty
      const value = Number(input.value);
      let message = "";
      if (value > max) {
        input.value = max;
        message = `Maximum is ${max} hours per week, so it was set to ${max}.`;
      } else if (value < min) {
        input.value = min;
        message = `Minimum is ${min} hour per week, so it was set to ${min}.`;
      } else {
        return;
      }
      const hint = $(".hint", input.closest(".field"));
      if (hint) {
        hint.classList.remove("flash");
        void hint.offsetWidth; // restart the highlight animation
        hint.classList.add("flash");
      }
      toast(message, "info");
    });
  });

  $$(".range[data-sync]").forEach((range) => {
    const input = document.getElementById(range.dataset.sync);
    const paint = () => {
      const p = ((range.value - range.min) / (range.max - range.min)) * 100;
      range.style.setProperty("--p", p + "%");
    };
    range.addEventListener("input", () => {
      input.value = range.value;
      paint();
      clearError(input.closest(".field"));
    });
    input.addEventListener("input", () => {
      if (input.value !== "") range.value = Math.min(range.max, input.value);
      paint();
    });
    paint();
  });

  /* ---------------- Validation helpers ---------------- */
  function clearError(field) {
    if (!field) return;
    field.classList.remove("invalid");
    const e = $(".error", field);
    if (e) e.textContent = "";
  }
  function showErrors(form, errors) {
    let first = null;
    Object.entries(errors).forEach(([key, msg]) => {
      const holder = $(`.error[data-for="${key}"]`, form);
      if (!holder) return;
      const field = holder.closest(".field");
      holder.textContent = msg;
      field.classList.remove("invalid");
      void field.offsetWidth; // restart shake animation
      field.classList.add("invalid");
      first = first || field;
    });
    if (first) {
      const inp = $("input", first);
      if (inp) inp.focus({ preventScroll: true });
      first.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
    }
  }
  $$("form").forEach((form) =>
    form.addEventListener("input", (e) => clearError(e.target.closest(".field")))
  );

  function readForm(form) {
    const data = {};
    new FormData(form).forEach((v, k) => (data[k] = typeof v === "string" ? v.trim() : v));
    return data;
  }

  // Client-side checks mirror the server rules (server is still the source of truth).
  function validate(data, expKeys) {
    const errs = {};
    if (!data.employee_name) errs.employee_name = "Employee name must not be empty.";
    if (!data.education) errs.education = "Please choose an education level.";
    const h = data.working_hours;
    if (h === "" || isNaN(h)) errs.working_hours = "Working hours is required.";
    else if (+h < CFG.minHours || +h > CFG.maxHours)
      errs.working_hours = `Working hours must be between ${CFG.minHours} and ${CFG.maxHours} per week.`;
    expKeys.forEach(([k, label]) => {
      const v = data[k];
      if (v === "" || v === undefined || isNaN(v)) errs[k] = `${label} is required.`;
      else if (+v < 0) errs[k] = `${label} must be 0 or greater.`;
    });
    return errs;
  }

  async function post(url, data) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(body.error || "Request failed");
      err.details = body.details || {};
      throw err;
    }
    return body;
  }

  /* ---------------- Toasts ---------------- */
  function toast(msg, type = "ok") {
    // Only one "info" notice at a time, so repeated typing doesn't stack them up
    if (type === "info") $$(".toast.info").forEach((old) => old.remove());
    const t = document.createElement("div");
    t.className = "toast " + type;
    t.innerHTML = `<span class="ico">${
      type === "ok"
        ? '<svg viewBox="0 0 24 24"><path d="M5 12l5 5 9-10"/></svg>'
        : '<svg viewBox="0 0 24 24"><path d="M12 8v5M12 16.5v.5"/><circle cx="12" cy="12" r="9"/></svg>'
    }</span><span>${esc(msg)}</span>`;
    $("#toasts").appendChild(t);
    setTimeout(() => {
      t.classList.add("out");
      t.addEventListener("animationend", () => t.remove());
    }, 3200);
  }

  /* ---------------- Visual helpers ---------------- */
  function countUp(el, target, duration = 1100) {
    if (reduceMotion) { el.textContent = money(target); return; }
    const start = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 4);
      el.textContent = money(target * eased);
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // Piece-wise position: each range (LOW / MEDIUM / HIGH) gets one third of the track.
  function meterPos(salary) {
    const { lowLimit: lo, highLimit: hi } = CFG;
    const top = hi * 1.6;
    let p;
    if (salary < lo) p = (Math.max(0, salary) / lo) / 3;
    else if (salary < hi) p = 1 / 3 + ((salary - lo) / (hi - lo)) / 3;
    else p = 2 / 3 + (Math.min(salary - hi, top - hi) / (top - hi)) / 3;
    return Math.max(1.5, Math.min(98.5, p * 100));
  }

  function meterHTML(salary, range) {
    return `
      <div class="meter" aria-label="Salary range meter">
        <div class="meter-track">
          <span class="low ${range === "LOW" ? "on" : ""}"></span>
          <span class="medium ${range === "MEDIUM" ? "on" : ""}"></span>
          <span class="high ${range === "HIGH" ? "on" : ""}"></span>
          <i class="meter-pin" data-left="${meterPos(salary)}"></i>
        </div>
        <div class="meter-labels">
          <span>LOW &lt; ₱${(CFG.lowLimit / 1000).toFixed(0)}k</span>
          <span>MEDIUM</span>
          <span>HIGH ≥ ₱${(CFG.highLimit / 1000).toFixed(0)}k</span>
        </div>
      </div>`;
  }

  function highlightJSON(obj) {
    return esc(JSON.stringify(obj, null, 2)).replace(
      /(&quot;(?:[^&]|&(?!quot;))*?&quot;)(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g,
      (m, str, colon, bool) => {
        if (str) return colon ? `<span class="j-key">${str}</span>${colon}` : `<span class="j-str">${str}</span>`;
        if (bool) return `<span class="j-bool">${m}</span>`;
        return `<span class="j-num">${m}</span>`;
      }
    );
  }

  function jsonBlock(obj, open) {
    return `
      <details class="json-toggle" ${open ? "open" : ""}>
        <summary><svg viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg> JSON output</summary>
        <div class="json-box">
          <div class="json-head">
            <span class="dots"><i></i><i></i><i></i></span>
            <span>RESPONSE · application/json</span>
            <button type="button" class="copy-btn"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>Copy</button>
          </div>
          <pre>${highlightJSON(obj)}</pre>
        </div>
      </details>`;
  }

  function wireResult(container, obj) {
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        $$(".meter-pin", container).forEach((pin) => (pin.style.left = pin.dataset.left + "%"));
        $$(".bar i", container).forEach((bar) => (bar.style.width = bar.dataset.w + "%"));
      })
    );
    $$("[data-count]", container).forEach((el) => countUp(el, Number(el.dataset.count)));
    const copy = $(".copy-btn", container);
    if (copy)
      copy.addEventListener("click", async () => {
        const text = JSON.stringify(obj, null, 2);
        try {
          await navigator.clipboard.writeText(text);
        } catch (_) {
          const ta = document.createElement("textarea");
          ta.value = text; document.body.appendChild(ta); ta.select();
          document.execCommand("copy"); ta.remove();
        }
        toast("JSON copied to clipboard");
      });
  }

  function setLoading(form, on) {
    const btn = $("button[type=submit]", form);
    btn.classList.toggle("loading", on);
    btn.disabled = on;
  }

  /* ---------------- Predict ---------------- */
  const predictForm = $("#predictForm");
  predictForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = readForm(predictForm);
    const errs = validate(data, [["years_experience", "Years of experience"]]);
    if (Object.keys(errs).length) return showErrors(predictForm, errs);

    setLoading(predictForm, true);
    try {
      const r = await post("/predict", data);
      const box = $("#predictResult");
      box.innerHTML = `
        <div class="result">
          <div class="result-top">
            <div class="who">
              <div class="avatar">${esc(initials(r.employee_name))}</div>
              <div><h3>${esc(r.employee_name)}</h3><p>Predicted ${esc(r.timestamp)}</p></div>
            </div>
            <span class="badge ${r.salary_range}">${r.salary_range}</span>
          </div>
          <div class="big-salary"><span class="cur">₱</span><span data-count="${r.predicted_salary}">0.00</span></div>
          <div class="sub">Estimated monthly salary · ${r.currency}</div>
          ${meterHTML(r.predicted_salary, r.salary_range)}
          <div class="facts">
            <div class="fact"><span>Education</span><b>${esc(r.education)}</b></div>
            <div class="fact"><span>Experience</span><b>${r.experience} yr${r.experience == 1 ? "" : "s"}</b></div>
            <div class="fact"><span>Hours / week</span><b>${r.working_hours}</b></div>
          </div>
          ${jsonBlock(r, false)}
        </div>`;
      wireResult(box, r);
      if (innerWidth < 960) box.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
      toast(`Saved prediction for ${r.employee_name}`);
      refreshCount();
    } catch (err) {
      showErrors(predictForm, err.details || {});
      toast(err.message === "Failed to fetch" ? "Server is not running" : err.message, "err");
    } finally {
      setLoading(predictForm, false);
    }
  });

  /* ---------------- Compare ---------------- */
  const compareForm = $("#compareForm");
  compareForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = readForm(compareForm);
    const errs = validate(data, [["experience_1", "Experience 1"], ["experience_2", "Experience 2"]]);
    if (!errs.experience_1 && !errs.experience_2 && +data.experience_1 === +data.experience_2)
      errs.experience_2 = "Use two different years-of-experience values.";
    if (Object.keys(errs).length) return showErrors(compareForm, errs);

    setLoading(compareForm, true);
    try {
      const r = await post("/compare", data);
      const diff = r.salary_difference;
      const pct = r.predicted_salary_1 !== 0 ? (diff / Math.abs(r.predicted_salary_1)) * 100 : 0;
      const maxSal = Math.max(r.predicted_salary_1, r.predicted_salary_2, 1);
      const sign = diff > 0 ? "+" : diff < 0 ? "−" : "";
      const box = $("#compareResult");
      box.innerHTML = `
        <div class="result">
          <div class="result-top">
            <div class="who">
              <div class="avatar">${esc(initials(r.employee_name))}</div>
              <div><h3>${esc(r.employee_name)}</h3><p>${esc(r.education)} · ${r.working_hours} hr${r.working_hours == 1 ? "" : "s"}/week</p></div>
            </div>
          </div>
          <div class="versus">
            <div class="scen a">
              <div class="scen-head"><span><span class="tag" style="background:var(--a)">A</span> ${r.experience_1} yr${r.experience_1 == 1 ? "" : "s"}</span><span class="badge ${r.salary_range_1}">${r.salary_range_1}</span></div>
              <div class="scen-salary">₱<span data-count="${r.predicted_salary_1}">0.00</span></div>
              <div class="sub">Predicted monthly</div>
            </div>
            <div class="scen b">
              <div class="scen-head"><span><span class="tag" style="background:var(--b)">B</span> ${r.experience_2} yr${r.experience_2 == 1 ? "" : "s"}</span><span class="badge ${r.salary_range_2}">${r.salary_range_2}</span></div>
              <div class="scen-salary">₱<span data-count="${r.predicted_salary_2}">0.00</span></div>
              <div class="sub">Predicted monthly</div>
            </div>
          </div>
          <div class="delta ${diff < 0 ? "neg" : ""}">
            <div><small>Salary difference (B − A)</small><b>${sign}₱${money(Math.abs(diff))}</b></div>
            <span class="pct">${sign}${Math.abs(pct).toFixed(1)}%</span>
          </div>
          <div class="bars">
            <div class="bar-row a"><span>A · ${r.experience_1} yrs</span><div class="bar"><i data-w="${(Math.max(0, r.predicted_salary_1) / maxSal) * 100}"></i></div></div>
            <div class="bar-row b"><span>B · ${r.experience_2} yrs</span><div class="bar"><i data-w="${(Math.max(0, r.predicted_salary_2) / maxSal) * 100}"></i></div></div>
          </div>
          ${jsonBlock(r, true)}
        </div>`;
      wireResult(box, r);
      if (innerWidth < 960) box.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
      toast("Both predictions saved to history");
      refreshCount();
    } catch (err) {
      showErrors(compareForm, err.details || {});
      toast(err.message === "Failed to fetch" ? "Server is not running" : err.message, "err");
    } finally {
      setLoading(compareForm, false);
    }
  });

  /* ---------------- History ---------------- */
  let records = [];
  const filters = { q: "", range: "ALL", type: "ALL" };

  async function fetchHistory() {
    const res = await fetch("/history");
    const body = await res.json();
    records = body.records || [];
    $("#historyCount").textContent = records.length;
    return records;
  }
  async function refreshCount() {
    try { await fetchHistory(); } catch (_) { /* ignore */ }
  }
  async function loadHistory() {
    try {
      await fetchHistory();
      renderStats();
      renderTable();
    } catch (_) {
      toast("Could not load history", "err");
    }
  }

  function renderStats() {
    const n = records.length;
    const sal = records.map((r) => Number(r.predicted_salary)).filter((x) => !isNaN(x));
    $("#s_total").textContent = n;
    $("#s_avg").textContent = sal.length ? "₱" + money(sal.reduce((a, b) => a + b, 0) / sal.length) : "—";
    $("#s_max").textContent = sal.length ? "₱" + money(Math.max(...sal)) : "—";
    const counts = { LOW: 0, MEDIUM: 0, HIGH: 0 };
    records.forEach((r) => counts[r.salary_range] !== undefined && counts[r.salary_range]++);
    const mix = $("#s_mix");
    $(".low", mix).style.flexGrow = counts.LOW;
    $(".medium", mix).style.flexGrow = counts.MEDIUM;
    $(".high", mix).style.flexGrow = counts.HIGH;
    $("#s_mix_legend").innerHTML = [["LOW", "--low"], ["MEDIUM", "--medium"], ["HIGH", "--high"]]
      .map(([k, c]) => `<span><i style="background:var(${c})"></i>${k} ${counts[k]}</span>`)
      .join("");
  }

  function renderTable() {
    const q = filters.q.toLowerCase();
    const rows = records.filter(
      (r) =>
        (filters.range === "ALL" || r.salary_range === filters.range) &&
        (filters.type === "ALL" || r.request_type === filters.type) &&
        (!q || `${r.employee_name} ${r.education}`.toLowerCase().includes(q))
    );
    $("#historyEmpty").hidden = rows.length > 0;
    if (!records.length) {
      $("#historyEmpty h3").textContent = "No records yet";
    } else if (!rows.length) {
      $("#historyEmpty h3").textContent = "No matching records";
    }
    $("#historyBody").innerHTML = rows
      .map(
        (r, i) => `
        <tr class="${r.request_type === "compare" ? "grouped" : ""}" style="animation-delay:${Math.min(i, 15) * 25}ms">
          <td class="muted">${esc(r.timestamp)}</td>
          <td><div class="person"><span class="avatar">${esc(initials(r.employee_name))}</span>${esc(r.employee_name)}</div></td>
          <td>${esc(r.education)}</td>
          <td class="num">${esc(r.years_experience)}</td>
          <td class="num">${esc(r.working_hours)}</td>
          <td class="num money">₱${money(r.predicted_salary)}</td>
          <td><span class="badge ${esc(r.salary_range)}">${esc(r.salary_range)}</span></td>
          <td><span class="type-pill ${esc(r.request_type)}" ${r.comparison_id ? `title="Comparison #${esc(r.comparison_id)}"` : ""}>${
            r.request_type === "compare" ? "Compare #" + esc(r.comparison_id) : "Predict"
          }</span></td>
        </tr>`
      )
      .join("");
  }

  $("#h_search").addEventListener("input", (e) => { filters.q = e.target.value; renderTable(); });
  [["#h_filter", "range"], ["#h_type", "type"]].forEach(([sel, key]) =>
    $$(`${sel} button`).forEach((b) =>
      b.addEventListener("click", () => {
        $$(`${sel} button`).forEach((x) => x.classList.toggle("active", x === b));
        filters[key] = b.dataset.v;
        renderTable();
      })
    )
  );
  $("#h_refresh").addEventListener("click", () => loadHistory().then(() => toast("History refreshed")));

  /* ---------------- Init ---------------- */
  const start = location.hash.replace("#", "");
  showTab(["predict", "compare", "history"].includes(start) ? start : "predict");
  refreshCount();
})();
