// Mission Control — filing form + Flight Director console.
// All user and model text is rendered with textContent. No cost math here:
// costs come from the API (computed in Python) and are only formatted.
"use strict";

const FIELDS = ["name", "station", "wind_knots", "temp_c", "fuel_pct", "note"];
const NUMERIC = new Set(["wind_knots", "temp_c", "fuel_pct"]);
const CODE_STEPS = new Set(["limits", "brief_by"]);

const form = document.getElementById("report-form");
const submitBtn = document.getElementById("submit");
const statusEl = document.getElementById("status");
const listEl = document.getElementById("reports");
const emptyEl = document.getElementById("empty");
const countEl = document.getElementById("report-count");
const detailEl = document.getElementById("detail");

let selectedId = null;
let openSeq = 0; // ignore stale detail responses when clicking quickly

// ---------- small DOM helpers ----------

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function badge(text, kind, title) {
  const b = el("span", `badge badge-${kind}`, text);
  if (title) b.title = title;
  return b;
}

function verdictBadge(verdict, big = false) {
  const size = big ? " badge-lg" : "";
  if (verdict === "go") return badge("GO", "go" + size);
  if (verdict === "no_go") return badge("NO-GO", "nogo" + size);
  return badge("NO RESULT", "muted" + size);
}

function severityChip(severity) {
  return severity ? badge(severity, `sev-${severity}`) : null;
}

function statusChip(status) {
  if (status === "approved") return badge("approved", "approved");
  if (status === "pending") return badge("pending", "pending");
  return null;
}

// Display only: costs are calculated in app/cost.py. Report totals use 6
// decimals; trace cards pass 4 to stay compact.
function formatCost(usd, decimals = 6) {
  return `$${Number(usd || 0).toFixed(decimals)}`;
}

function formatMs(ms) {
  return `${Math.round(Number(ms || 0))} ms`;
}

function formatTime(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleString();
}

function formatInt(n) {
  return Number(n || 0).toLocaleString();
}

function append(parent, ...children) {
  for (const c of children) if (c) parent.append(c);
  return parent;
}

async function readErrors(res) {
  try {
    const body = await res.json();
    return Array.isArray(body.errors) ? body.errors : [];
  } catch {
    return [];
  }
}

// ---------- filing form ----------

function errorEl(field) {
  return form.querySelector(`[data-error-for="${field}"]`);
}

function clearErrors() {
  form.querySelectorAll(".error").forEach((n) => { n.textContent = ""; });
  form.querySelectorAll("[aria-invalid]").forEach((n) => n.removeAttribute("aria-invalid"));
}

function showErrors(errors) {
  for (const { field, message } of errors) {
    const target = errorEl(field) || errorEl("body");
    target.textContent = message;
    const input = form.elements.namedItem(field);
    if (input) input.setAttribute("aria-invalid", "true");
  }
}

function readForm() {
  const data = {};
  for (const field of FIELDS) {
    const raw = form.elements.namedItem(field).value;
    if (NUMERIC.has(field)) {
      const trimmed = raw.trim();
      if (trimmed === "") continue; // omitted -> server says "required"
      const num = Number(trimmed);
      data[field] = Number.isNaN(num) ? trimmed : num; // server decides validity
    } else {
      data[field] = raw;
    }
  }
  return data;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors();
  statusEl.textContent = "Sending… running checks and drafting the briefing";
  submitBtn.disabled = true;

  try {
    const res = await fetch("/api/reports", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(readForm()),
    });
    if (res.status === 422) {
      showErrors(await readErrors(res));
      statusEl.textContent = "Please fix the highlighted fields.";
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const report = await res.json();
    form.reset();
    statusEl.textContent = `Report #${report.id} filed.`;
    selectedId = report.id;
    renderDetail(report);
    setHash(report.id);
    await loadList();
  } catch (err) {
    errorEl("body").textContent = "Could not reach the server. Try again.";
    statusEl.textContent = "";
  } finally {
    submitBtn.disabled = false;
  }
});

// ---------- report list ----------

function renderListItem(r) {
  const li = el("li");
  const btn = el("button", "report-item");
  btn.type = "button";
  btn.dataset.id = String(r.id);
  if (r.id === selectedId) btn.classList.add("selected");
  btn.setAttribute("aria-pressed", r.id === selectedId ? "true" : "false");

  const top = el("div", "item-top");
  append(top,
    verdictBadge(r.verdict),
    el("span", "item-title", `#${r.id} ${r.name}`),
    el("span", "item-cost", formatCost(r.total_cost)),
  );

  const meta = el("div", "item-meta");
  append(meta,
    el("span", "muted", r.station),
    r.subsystem ? el("span", "chip", r.subsystem) : null,
    severityChip(r.severity),
    r.brief_by != null ? el("span", "chip", `brief by ${r.brief_by} min`) : null,
    statusChip(r.briefing_status),
    r.needs_review ? badge("⚠ needs review", "warn") : null,
  );

  btn.append(top, meta);
  btn.addEventListener("click", () => openReport(r.id));
  li.append(btn);
  return li;
}

async function loadList() {
  try {
    const res = await fetch("/api/reports");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const reports = await res.json();
    listEl.replaceChildren(...reports.map(renderListItem));
    emptyEl.hidden = reports.length > 0;
    emptyEl.textContent = "No reports yet.";
    countEl.textContent = reports.length ? `${reports.length}` : "";
  } catch {
    emptyEl.hidden = false;
    emptyEl.textContent = "Could not load reports.";
  }
}

function markSelected() {
  listEl.querySelectorAll(".report-item").forEach((b) => {
    const on = Number(b.dataset.id) === selectedId;
    b.classList.toggle("selected", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
  });
}

// ---------- detail panel ----------

function setHash(id) {
  try { history.replaceState(null, "", `#report-${id}`); } catch { /* ignore */ }
}

async function openReport(id) {
  selectedId = id;
  markSelected();
  setHash(id);
  const seq = ++openSeq;
  detailEl.replaceChildren(el("p", "muted placeholder", "Loading…"));
  try {
    const res = await fetch(`/api/reports/${id}`);
    if (seq !== openSeq) return;
    if (res.status === 404) {
      detailEl.replaceChildren(el("p", "error", `Report #${id} was not found.`));
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const report = await res.json();
    if (seq !== openSeq) return;
    renderDetail(report);
  } catch {
    if (seq === openSeq) {
      detailEl.replaceChildren(el("p", "error", "Could not load this report."));
    }
  }
}

function section(title, ...children) {
  const s = el("section", "detail-section");
  s.append(el("h3", null, title));
  append(s, ...children);
  return s;
}

function stat(label, value, extraClass) {
  const d = el("div", "stat" + (extraClass ? ` ${extraClass}` : ""));
  d.append(el("span", "stat-label", label), el("span", "stat-value", value));
  return d;
}

function warningItems(r) {
  const items = [];
  const checks = r.checks || {};
  const b = r.briefing || {};
  if (r.needs_review || (checks.injection && checks.injection.flag)) {
    items.push(["⚠ Hidden instructions · needs review", "danger",
      checks.injection ? checks.injection.reason : ""]);
  }
  if (checks.missing && checks.missing.flag) {
    items.push(["Missing details", "warn", checks.missing.reason]);
  }
  if (checks.panic && checks.panic.flag) {
    items.push(["Panic tone", "warn", checks.panic.reason]);
  }
  if (b.review_exhausted) {
    items.push(["Review exhausted", "warn",
      `The reviewer did not pass the draft in ${b.rounds} rounds; read it carefully.`]);
  }
  if (r.classification && r.classification.fallback) {
    items.push(["Classification fallback", "warn",
      "The model reply was invalid; defaulted to other / high."]);
  }
  return items;
}

function renderWarnings(r) {
  const items = warningItems(r);
  if (!items.length) return el("p", "muted", "No warnings.");
  const ul = el("ul", "warnings");
  for (const [label, kind, reason] of items) {
    const li = el("li");
    li.append(badge(label, kind));
    if (reason) li.append(el("span", "warning-reason", reason));
    ul.append(li);
  }
  return ul;
}

function renderApproval(r) {
  const b = r.briefing;
  const box = el("div", "approval");

  if (b.status === "approved" && b.approval) {
    box.append(el("p", "approved-line",
      `Approved by ${b.approval.approver_name} at ${formatTime(b.approval.approved_at)}`));
    return box;
  }
  if (b.status !== "pending") return box;

  const f = el("form", "approve-form");
  f.noValidate = true;
  const label = el("label", null, "Flight Director name");
  const input = el("input");
  input.type = "text";
  input.name = "approver_name";
  input.id = `approver-${b.id}`;
  input.autocomplete = "name";
  label.htmlFor = input.id;
  const btn = el("button", "approve-btn", "Approve briefing");
  btn.type = "submit";
  const err = el("p", "error");

  const row = el("div", "approve-row");
  row.append(input, btn);
  f.append(label, row, err);

  f.addEventListener("submit", async (event) => {
    event.preventDefault();
    err.textContent = "";
    input.removeAttribute("aria-invalid");
    btn.disabled = true;
    try {
      const res = await fetch(`/api/briefings/${b.id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approver_name: input.value }),
      });
      if (!res.ok) {
        const errors = await readErrors(res);
        err.textContent = errors.length
          ? errors.map((e) => e.message).join(" ")
          : `Approval failed (HTTP ${res.status}).`;
        if (res.status === 422) input.setAttribute("aria-invalid", "true");
        if (res.status === 409) { await openReport(r.id); await loadList(); }
        return;
      }
      await openReport(r.id);
      await loadList();
    } catch {
      err.textContent = "Could not reach the server. Try again.";
    } finally {
      btn.disabled = false;
    }
  });

  box.append(f);
  return box;
}

function renderBriefing(r) {
  const b = r.briefing;
  if (!b) return section("Briefing", el("p", "muted", "No briefing for this report."));

  const head = el("div", "briefing-head");
  const rounds = b.review_passed
    ? `passed review in ${b.rounds} round${b.rounds === 1 ? "" : "s"}`
    : `not passed after ${b.rounds} rounds`;
  append(head, statusChip(b.status), el("span", "muted", rounds));

  return section("Briefing", head, el("pre", "briefing-text", b.text), renderApproval(r));
}

function renderTraceCard(step, index) {
  const card = el("li", "trace-card");
  const head = el("div", "trace-head");
  append(head,
    el("span", "trace-index", String(index + 1)),
    el("span", "trace-name", step.name),
    badge(CODE_STEPS.has(step.name) ? "code" : "model",
      CODE_STEPS.has(step.name) ? "code" : "model"),
  );

  const stats = el("dl", "trace-stats");
  for (const [k, v] of [
    ["In", formatInt(step.input_tokens)],
    ["Out", formatInt(step.output_tokens)],
    ["Cost", formatCost(step.cost_usd, 4)],
    ["Time", formatMs(step.duration_ms)],
  ]) {
    const d = el("div");
    d.append(el("dt", null, k), el("dd", null, v));
    stats.append(d);
  }

  card.append(head, stats, el("p", "trace-summary", step.summary));
  return card;
}

function renderTrace(r) {
  if (!r.steps || !r.steps.length) return section("Trace", el("p", "muted", "No steps recorded."));
  const ol = el("ol", "trace");
  r.steps.forEach((s, i) => ol.append(renderTraceCard(s, i)));
  return section(`Trace · ${r.steps.length} steps`, ol);
}

function renderDetail(r) {
  const head = el("div", "detail-head");
  const titles = el("div");
  titles.append(
    el("h2", null, `Report #${r.id}`),
    el("p", "muted", `${r.name} · ${r.station} · ${formatTime(r.created_at)}`),
  );
  head.append(verdictBadge(r.verdict, true), titles);

  const stats = el("div", "stats");
  const c = r.classification;
  append(stats,
    stat("Verdict", r.verdict === "go" ? "GO" : r.verdict === "no_go" ? "NO-GO" : "—",
      r.verdict === "go" ? "is-go" : r.verdict === "no_go" ? "is-nogo" : ""),
    stat("Brief by", r.brief_by != null ? `${r.brief_by} min` : "—"),
    stat("Subsystem", c ? c.subsystem : "—"),
    stat("Severity", c ? c.severity : "—"),
    stat("Total cost", formatCost(r.total_cost)),
  );

  const violations = r.violations && r.violations.length
    ? append(el("ul", "violations"), ...r.violations.map((v) => el("li", null, v)))
    : el("p", "muted", r.verdict ? "None — all readings within limits." : "No result.");

  const readings = el("p", "readings",
    `Wind ${r.wind_knots} kn · Temp ${r.temp_c} °C · Fuel ${r.fuel_pct}%`);

  detailEl.replaceChildren(
    head,
    stats,
    section("Verdict & violations (computed in code)", readings, violations),
    section("Warnings", renderWarnings(r)),
    renderBriefing(r),
    section("Engineer note (untrusted)", el("p", "note", r.note)),
    renderTrace(r),
  );
}

// ---------- start ----------

(async function start() {
  await loadList();
  const m = /^#report-(\d+)$/.exec(location.hash);
  if (m) openReport(Number(m[1]));
})();
